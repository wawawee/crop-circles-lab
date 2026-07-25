"""pulsar_fetcher — honest ATNF/Parkes Vela timing-series fetcher.

Stance: structure != message. Vela (PSR B0833-45 / J0835-4510) is the
universe's most famous precise natural clock. The role of this scaffold is
the **positive-control + lab-motto anchor**:

  - **Positive control**: the FFT + autocorr + epoch-fold pipeline must
    recover Vela's canonical P0 (~89.33 ms) on real data, OR on a
    synthetic plant with the same parameters. Success here proves the math.
  - **Lab-motto anchor**: Vela's period is famously STABLE. A pipeline
    that detects periodicity here is NOT detecting artificiality -- it is
    detecting what nature already does for free. Periodicity is necessary,
    NOT sufficient, for artificiality.

Lab motto compliance:
  - No silent fallback to synthetic data; honest-empty on fetch failure.
  - No silent "success" off an HTML parking page.
  - Every attempt is recorded with URL/HTTP status/content-type/bytes/error.

Probe results (2026-07-25):
  - ATNF psrcat `proc_form.php` returns HTML form interface, NOT direct
    CSV. (HTTP 200 + Content-Type: text/html + 1014 bytes.)
  - ATOA (https://atoa.atnf.csiro.au) HTTP 200; per-pulsar file URLs
    require building a search query first.
  - CSIRO Data Portal (csiro:40790 DR1, csiro:59374 DR3) HTTP 200;
    per-file PPTA .tim files need a DOI-redirect chain.
  - EPN DB 302 redirect to a discovery page.
  - No clean single-URL CSV equivalent for an arbitrary Vela arrival
    series exists at probe time.

The bundled override path (`--bundled-pulsar-csv`) is the realistic
landing today: transcribe arrival MJDs from a PPTA data-release paper into
a small CSV and feed it through.

Public API:

  try_fetch_atnf_pulsar_vela_timing(
      attempt_urls=None,            # override default URL list
      timeout_s=10.0,
      use_cache=True,
      cache_path=None,
      force_status_for_tests=None,  # 'UNREACHABLE' | 'PARKING_PAGE' | 'FETCHED'
  ) -> PulsarFetchResult

  parse_pulsar_timing_rows(
      csv_text, source_name, fetch_attempt,
      reference_bibcode=None, reference_url=None,
  ) -> list[PulsarArrivalRow]

  load_bundled_pulsar_csv(path: Path) -> list[PulsarArrivalRow]
"""
from __future__ import annotations

import csv
import io
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


# --- Vela pulsar constants ------------------------------------------------
# We DO NOT hardcode bulk arrival-time arrays in memory: that would
# silently fabricate. We DO hardcode the canonical period + bibliographic
# metadata, which is stable public-domain knowledge.

VELA_PSR_B1950 = "B0833-45"
VELA_PSR_J2000 = "J0835-4510"
VELA_PSR_ALIASES = (VELA_PSR_B1950, VELA_PSR_J2000, "Vela", "VELA",
                     "PSR J0835-4510", "PSR B0833-45", "0833-45", "0835-4510")
# Canonical published mean spin period (seconds). Used as the PLANT period
# in the synthetic scaffold AND as the search-grid centre in the real-data
# epoch-fold. Reference: ATNF Pulsar Catalogue
# (https://www.atnf.csiro.au/research/pulsar/psrcat/)
# Manchester et al. 2005 AJ 129 1993 (DOI 10.1086/428488).
VELA_P0_PUBLISHED_S = 0.089328385507       # ~89.328 ms
VELA_F0_PUBLISHED_HZ = 1.0 / VELA_P0_PUBLISHED_S  # ~11.192 Hz

# Bibliographic references (CC BY 4.0 per scout_briefs.md line 71).
VELA_BIBCODE_PSRCAT = "2005AJ....129.1993M"   # Manchester et al. 2005
VELA_BIBCODE_PPTA_DR3 = "2023PASA...40...49Z" # Zic et al. 2023 PPTA DR3
VELA_DATA_LICENSE = "CC BY 4.0 (ATNF Pulsar Catalogue; PPTA Data Releases)"


# --- canonical URL candidates --------------------------------------------
# Ordered: most-authoritative to community mirrors. Each entry:
# (url, role, expected_content_type).
CANDIDATE_URLS: tuple[tuple[str, str, str], ...] = (
    (
        "https://www.atnf.csiro.au/research/pulsar/psrcat/"
        "proc_form.php?version=2.8.1&JNAME=J0835-4510&F0=on"
        "&PEPOCH=on&submit=Submit",
        "ATNF psrcat (J2000 ID) single-pulsar processor",
        "text/csv",
    ),
    (
        "https://www.atnf.csiro.au/research/pulsar/psrcat/"
        "proc_form.php?version=2.8.1&JNAME=B0833-45&F0=on"
        "&PEPOCH=on&submit=Submit",
        "ATNF psrcat (B1950 ID) single-pulsar processor",
        "text/csv",
    ),
    (
        "https://atoa.atnf.csiro.au/",
        "ATOA main archive (requires search interface, no direct file)",
        "text/html",
    ),
    (
        "https://data.csiro.au/collection/csiro:40790",
        "PPTA DR1 (CSIRO Data Portal) landing page",
        "text/html",
    ),
    (
        "https://data.csiro.au/collection/csiro:59374",
        "PPTA DR3 (Zic et al. 2023) landing page",
        "text/html",
    ),
)


# --- CSV schema tolerance for timing rows --------------------------------
# Vela timing data (e.g., PPTA-released .tim files after header-stripping)
# typically has columns like `name,mjd,freq,residual_us,...`. We accept a
# range of column names for name and mjd; everything else is ignored.

COLUMN_NAMES_NAME = ("name", "psr", "psr_name", "pulsar", "tns",
                       "tns_name", "source")
COLUMN_NAMES_MJD = ("mjd", "arrival_mjd", "toa_mjd",
                      "peak_mjd", "utc_mjd", "arrival_time_mjd")
COLUMN_NAMES_FREQ = ("freq", "frequency", "f0", "spin_freq")
COLUMN_NAMES_RESIDUAL = ("residual", "residual_us", "res_us",
                          "timing_residual_us")


# --- dataclasses ---------------------------------------------------------

@dataclass
class FetchAttempt:
    url: str
    role: str
    http_status: Optional[int]
    content_type: Optional[str]
    content_bytes: int
    verdict: str            # CSV_HEADER | HTML_PARKING | EMPTY | 4XX | 5XX
                           # | NETWORK_ERROR | TIMEOUT | INVALID_URL | ERROR
    error: Optional[str]
    elapsed_s: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PulsarFetchResult:
    fetch_status: str       # FETCHED | CACHED | UNREACHABLE | PARKING_PAGE
                            # | INVALID_FORMAT | ERROR
    fetched_from: Optional[str]
    csv_path: Optional[str]
    n_rows_total: int
    arrival_mjds: list[float]      # ALL arrival MJDs the file reports
    arrival_mjds_vela: list[float] # only those matching Vela's aliases
    attempts: list[FetchAttempt] = field(default_factory=list)
    detected_columns: dict = field(default_factory=dict)
    reference_bibcode: Optional[str] = None
    reference_url: Optional[str] = None
    provenance_note: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["attempts"] = [a if isinstance(a, dict) else a.to_dict()
                         for a in self.attempts]
        return d


# --- parser --------------------------------------------------------------

@dataclass
class PulsarArrivalRow:
    raw_name: Optional[str]
    raw_mjd: Optional[float]
    raw_freq: Optional[float]
    raw_residual_us: Optional[float]


def _pick_row_by_column(headers: list[str], candidates: tuple[str, ...]) -> Optional[int]:
    h_lower = [h.strip().lower() for h in headers]
    for c in candidates:
        if c.lower() in h_lower:
            return h_lower.index(c.lower())
    return None


def parse_pulsar_timing_rows(
    csv_text: str,
    source_name: str,
    fetch_attempt: Optional[FetchAttempt] = None,
    reference_bibcode: Optional[str] = None,
    reference_url: Optional[str] = None,
) -> list[PulsarArrivalRow]:
    """Parse a Vela-relevant timing CSV.

    A "timing row" minimally needs a name (matches one of VELA_PSR_ALIASES)
    AND an MJD. The schema-tolerance contract is the same as CHIME:
    unknown columns are ignored; if essential columns are missing, the
    parser returns an empty list and we surface this honestly.
    """
    text = csv_text.lstrip()
    if not text:
        return []
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        return []
    idx_name = _pick_row_by_column(header, COLUMN_NAMES_NAME)
    idx_mjd = _pick_row_by_column(header, COLUMN_NAMES_MJD)
    idx_freq = _pick_row_by_column(header, COLUMN_NAMES_FREQ)
    idx_res = _pick_row_by_column(header, COLUMN_NAMES_RESIDUAL)
    rows: list[PulsarArrivalRow] = []
    for raw in reader:
        if not raw or all((c or "").strip() == "" for c in raw):
            continue
        def _cell(i):
            if i is None or i >= len(raw):
                return None
            try:
                return float(raw[i])
            except (TypeError, ValueError):
                return None
        try:
            name = (raw[idx_name] or "").strip() if idx_name is not None else None
        except (IndexError, TypeError):
            name = None
        rows.append(PulsarArrivalRow(
            raw_name=name,
            raw_mjd=_cell(idx_mjd),
            raw_freq=_cell(idx_freq),
            raw_residual_us=_cell(idx_res),
        ))
    return rows


def _is_vela_row(name: Optional[str]) -> bool:
    if not name:
        return False
    n = name.replace(" ", "").replace("-", "").upper()
    for alias in VELA_PSR_ALIASES:
        if alias.replace(" ", "").replace("-", "").upper() in n:
            return True
    return False


def _mjds_for_vela(rows: list[PulsarArrivalRow]) -> list[float]:
    out = []
    for r in rows:
        if r.raw_mjd is None:
            continue
        if _is_vela_row(r.raw_name):
            out.append(float(r.raw_mjd))
    return sorted(out)


def _all_mjds(rows: list[PulsarArrivalRow]) -> list[float]:
    return sorted([float(r.raw_mjd) for r in rows if r.raw_mjd is not None])


# --- bundled override (manual transcription) -----------------------------

@dataclass
class BundledOverride:
    """Result of parsing a user-provided --bundled-pulsar-csv."""
    mjds: list[float]
    source_path: str
    n_rows: int
    error: Optional[str] = None

    @property
    def has_mjds(self) -> bool:
        return len(self.mjds) > 0


def load_bundled_pulsar_csv(path: Path) -> BundledOverride:
    """Load a user-provided CSV with Vela arrival MJDs.

    Accepted schemas (the parser picks the first matching form):
      (1) header `mjd[,name,freq,...]` with rows of float MJDs.
      (2) Tempo2-style `FORMAT 1` reduced to first column of MJDs.
      (3) Two-column `index,mjd` (we use the mjd column).
    """
    text = path.read_text(errors="replace")
    mjds: list[float] = []
    try:
        rows = parse_pulsar_timing_rows(text, source_name=path.name)
        for r in rows:
            if r.raw_mjd is None:
                continue
            # If a name column exists AND it does NOT look like Vela,
            # still include all rows by default -- we trust the user's
            # transcription to have already filtered to Vela only.
            if r.raw_name is not None and not _is_vela_row(r.raw_name):
                continue
            mjds.append(float(r.raw_mjd))
        if not mjds:
            # Fallback: if name column was missing / non-Vela, accept
            # all MJD-parseable rows. Caller takes responsibility.
            for r in rows:
                if r.raw_mjd is not None:
                    mjds.append(float(r.raw_mjd))
    except Exception as e:
        return BundledOverride(mjds=[], source_path=str(path),
                                n_rows=0, error=str(e))
    return BundledOverride(
        mjds=sorted(mjds),
        source_path=str(path),
        n_rows=len(rows) if 'rows' in locals() else 0,
    )


# --- the actual probe ----------------------------------------------------

def _probe_url(url: str, role: str, expected_ct: str,
               timeout_s: float) -> FetchAttempt:
    started = time.monotonic()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "lab-radio-probe/1.0"})
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            status = int(resp.status)
            ct = (resp.headers.get("Content-Type") or "").lower()
            body = resp.read()
            elapsed = time.monotonic() - started
        if "html" in ct:
            return FetchAttempt(
                url=url, role=role, http_status=status, content_type=ct,
                content_bytes=len(body), verdict="HTML_PARKING",
                error="content-type contains 'html' - not a CSV",
                elapsed_s=round(elapsed, 3),
            )
        if "csv" not in ct and "text/plain" not in ct:
            head = ""
            try:
                head = body[:1024].decode("utf-8", errors="replace")
            except Exception:
                pass
            if not ("," in head.splitlines()[0] if head else False):
                return FetchAttempt(
                    url=url, role=role, http_status=status, content_type=ct,
                    content_bytes=len(body), verdict="INVALID_FORMAT",
                    error=f"unexpected content-type {ct!r}, no header comma",
                    elapsed_s=round(elapsed, 3),
                )
        if not body:
            return FetchAttempt(
                url=url, role=role, http_status=status, content_type=ct,
                content_bytes=0, verdict="EMPTY",
                error="HTTP 200 but empty body",
                elapsed_s=round(elapsed, 3),
            )
        return FetchAttempt(
            url=url, role=role, http_status=status, content_type=ct,
            content_bytes=len(body), verdict="CSV_HEADER",
            error=None, elapsed_s=round(elapsed, 3),
        )
    except urllib.error.HTTPError as e:
        return FetchAttempt(
            url=url, role=role, http_status=int(e.code),
            content_type=(e.headers.get("Content-Type") if e.headers else None),
            content_bytes=0,
            verdict="4XX" if 400 <= e.code < 500 else "5XX",
            error=str(e)[:200], elapsed_s=round(time.monotonic() - started, 3),
        )
    except urllib.error.URLError as e:
        return FetchAttempt(
            url=url, role=role, http_status=None, content_type=None,
            content_bytes=0, verdict="NETWORK_ERROR",
            error=str(e.reason)[:200] if hasattr(e, "reason") else str(e)[:200],
            elapsed_s=round(time.monotonic() - started, 3),
        )
    except (TimeoutError, ConnectionError, OSError) as e:
        return FetchAttempt(
            url=url, role=role, http_status=None, content_type=None,
            content_bytes=0,
            verdict="TIMEOUT" if isinstance(e, TimeoutError) else "NETWORK_ERROR",
            error=str(e)[:200], elapsed_s=round(time.monotonic() - started, 3),
        )
    except Exception as e:
        return FetchAttempt(
            url=url, role=role, http_status=None, content_type=None,
            content_bytes=0, verdict="ERROR",
            error=f"{type(e).__name__}: {e}"[:200],
            elapsed_s=round(time.monotonic() - started, 3),
        )


def _read_cached(cache_path: Path) -> Optional[PulsarFetchResult]:
    if not cache_path.exists():
        return None
    try:
        text = cache_path.read_text()
        rows = parse_pulsar_timing_rows(
            csv_text=text, source_name=cache_path.name,
            reference_bibcode=VELA_BIBCODE_PSRCAT,
            reference_url="https://www.atnf.csiro.au/research/pulsar/psrcat/",
        )
        result = PulsarFetchResult(
            fetch_status="CACHED",
            fetched_from=str(cache_path),
            csv_path=str(cache_path),
            n_rows_total=len(rows),
            arrival_mjds=_all_mjds(rows),
            arrival_mjds_vela=_mjds_for_vela(rows),
            attempts=[FetchAttempt(
                url=str(cache_path), role="local cache",
                http_status=None, content_type=None,
                content_bytes=len(text),
                verdict="CSV_HEADER", error=None, elapsed_s=0.0,
            )],
            reference_bibcode=VELA_BIBCODE_PSRCAT,
            reference_url="https://www.atnf.csiro.au/research/pulsar/psrcat/",
            provenance_note=(
                "Loaded from local cache; canonical mirror not contacted. "
                "Verify the cache has not stale-rotated before trusting."
            ),
        )
        return result
    except Exception:
        return None


def try_fetch_atnf_pulsar_vela_timing(
    attempt_urls: Optional[list[tuple[str, str, str]]] = None,
    timeout_s: float = 10.0,
    use_cache: bool = True,
    cache_path: Optional[Path] = None,
    force_status_for_tests: Optional[str] = None,
) -> PulsarFetchResult:
    """Honest fetch attempt for Vela timing rows.

    Parameters
    ----------
    attempt_urls
        List of (url, role, expected_content_type) to try in order. None
        uses `CANDIDATE_URLS`.
    timeout_s
        Per-attempt wall-clock timeout.
    use_cache / cache_path
        If cache_path points to a previously-saved CSV that still parses,
        we return CACHED without contacting the network. Filename hint:
        ``data/radio/cache/atnf_pulsar_vela_timing.csv``.
    force_status_for_tests
        If set to one of {'UNREACHABLE','PARKING_PAGE','FETCHED'}, we
        SKIP the network probe entirely and return a synthetic-but-honest
        result calibrated to that status.

    Order of operations (cache-vs-test_force contract, same as CHIME):
      1. test_force hooks FIRST (so tests can never silently short-
         circuit on a stale cache).
      2. Then use_cache + _read_cached.
      3. Then the real probe.
    """
    urls = list(attempt_urls) if attempt_urls is not None else list(CANDIDATE_URLS)

    # --- test hook FIRST ---------------------------------------------
    if force_status_for_tests == "UNREACHABLE":
        return PulsarFetchResult(
            fetch_status="UNREACHABLE", fetched_from=None, csv_path=None,
            n_rows_total=0, arrival_mjds=[], arrival_mjds_vela=[],
            attempts=[FetchAttempt(
                url=u, role=r, http_status=None, content_type=None,
                content_bytes=0, verdict="NETWORK_ERROR",
                error="force_status_for_tests=UNREACHABLE (no network call)",
                elapsed_s=0.0,
            ) for (u, r, _ct) in urls],
            provenance_note=(
                "Test stub: no live probe performed. Each canonical URL "
                "marked UNREACHABLE without network contact."
            ),
        )
    if force_status_for_tests == "PARKING_PAGE":
        return PulsarFetchResult(
            fetch_status="PARKING_PAGE", fetched_from=None, csv_path=None,
            n_rows_total=0, arrival_mjds=[], arrival_mjds_vela=[],
            attempts=[FetchAttempt(
                url=u, role=r, http_status=200, content_type="text/html",
                content_bytes=200, verdict="HTML_PARKING",
                error="force_status_for_tests=PARKING_PAGE (no network call)",
                elapsed_s=0.0,
            ) for (u, r, _ct) in urls],
            provenance_note=(
                "Test stub: each canonical URL returned an HTML parking page."
            ),
        )

    # --- cache short-circuit (only AFTER test_force has been honored)
    if cache_path is None:
        cache_path = Path("data/radio/cache/atnf_pulsar_vela_timing.csv")
    if use_cache:
        cached = _read_cached(cache_path)
        if cached is not None:
            return cached

    # --- real probe ------------------------------------------------
    attempts: list[FetchAttempt] = []
    for url, role, _ct in urls:
        att = _probe_url(url, role, _ct, timeout_s=timeout_s)
        attempts.append(att)
        if att.verdict == "CSV_HEADER":
            try:
                with urllib.request.urlopen(url, timeout=timeout_s) as resp:
                    body = resp.read().decode("utf-8", errors="replace")
            except Exception:
                body = ""
            rows = parse_pulsar_timing_rows(
                body, source_name=url,
                reference_bibcode=VELA_BIBCODE_PSRCAT,
                reference_url="https://www.atnf.csiro.au/research/pulsar/psrcat/",
            )
            mjds_all = _all_mjds(rows)
            mjds_vela = _mjds_for_vela(rows)
            csv_p = None
            if cache_path is not None:
                try:
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_path.write_text(body)
                    csv_p = str(cache_path)
                except Exception:
                    csv_p = None
            return PulsarFetchResult(
                fetch_status="FETCHED", fetched_from=url, csv_path=csv_p,
                n_rows_total=len(rows),
                arrival_mjds=mjds_all,
                arrival_mjds_vela=mjds_vela,
                attempts=attempts,
                reference_bibcode=VELA_BIBCODE_PSRCAT,
                reference_url="https://www.atnf.csiro.au/research/pulsar/psrcat/",
                provenance_note=(
                    f"Live fetch OK from {url}. Parsed {len(rows)} timing rows; "
                    f"{len(mjds_vela)} matched Vela aliases ({VELA_PSR_B1950} / "
                    f"{VELA_PSR_J2000}). License: {VELA_DATA_LICENSE}."
                ),
            )

    # --- all URLs failed ------------------------------------------
    saw_parking = any(a.verdict == "HTML_PARKING" for a in attempts)
    saw_4xx = any(a.verdict == "4XX" for a in attempts)
    saw_5xx = any(a.verdict == "5XX" for a in attempts)
    saw_network = any(a.verdict in ("NETWORK_ERROR", "TIMEOUT")
                       for a in attempts)
    if saw_parking:
        status = "PARKING_PAGE"
    elif saw_4xx or saw_5xx or saw_network:
        status = "UNREACHABLE"
    else:
        status = "INVALID_FORMAT"
    return PulsarFetchResult(
        fetch_status=status, fetched_from=None, csv_path=None,
        n_rows_total=0, arrival_mjds=[], arrival_mjds_vela=[],
        attempts=attempts,
        reference_bibcode=VELA_BIBCODE_PSRCAT,
        reference_url="https://www.atnf.csiro.au/research/pulsar/psrcat/",
        provenance_note=(
            f"All {len(attempts)} canonical URLs failed. No bytes parsed; "
            "no synthetic data injected. The lab motto says: structure != "
            "message; we never silently fabricate."
        ),
    )


def module_summary(result: PulsarFetchResult) -> str:
    return (
        f"ATNF/Parkes Vela fetch: status={result.fetch_status}; "
        f"attempts={len(result.attempts)}; "
        f"n_rows_total={result.n_rows_total}; "
        f"n_mjds_vela={len(result.arrival_mjds_vela)}; "
        f"ref={result.reference_bibcode or 'none'}"
    )


if __name__ == "__main__":
    out = try_fetch_atnf_pulsar_vela_timing(timeout_s=10.0)
    print(json.dumps(out.to_dict(), indent=2, default=str))
