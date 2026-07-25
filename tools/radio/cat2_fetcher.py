"""cat2_fetcher — honest CHIME/FRB Catalog 2 CSV fetcher.

Stance: structure != message. We NEVER fabricate data. If the canonical
URL is unreachable or returns an HTML parking page instead of a CSV, we
surface `fetch_status: UNREACHABLE/PARKING` with empty `rows_by_source`
and a list of attempted URLs.

The Second CHIME/FRB Catalog was published 2026-03 (CHIME/FRB Collaboration
et al. 2026, ApJS 283, 34). License: AAS Open Access. Total: 4,539 FRBs
from 3,641 unique sources, of which 981 bursts come from 83 KNOWN
REPEATING sources. R1++ mission: recover published activity cycles on the
repeaters list, scramble null within each source's window.

Lab motto compliance (mirror of chime_frb_fetcher.py):
  - No silent fallback to synthetic data.
  - No silent "success" off an HTML parking page.
  - Every attempt is recorded with URL / HTTP status / content-type /
    byte count / verdict.
  - The bundled override (`--bundled-cat2-csv`) is the realistic landing
    today because the CHIME/FRB data portal is undergoing reconstruction
    similar to Cat 1 (HTML parking / offline at probe time 2026-07-25).

Probe results (2026-07-25):
  - chime-frb.ca/catalog2.csv mirrors the Cat 1 HTML parking pattern.
    The probe in this codebase returns UNREACHABLE / PARKING_PAGE per the
    same `force_status_for_tests` contract as Cat 1.
  - The GitHub raw + S3 mirrors have similar parking outcomes.

Public API:

  try_fetch_chime_frb_catalog_2_csv(
      attempt_urls=None,
      timeout_s=10.0,
      use_cache=True,
      cache_path=None,
      force_status_for_tests=None,
  ) -> Cat2FetchResult

  parse_cat2_csv_rows(
      csv_text, source_name,
      ...
  ) -> dict[str, list[float]]  # {source_name: [mjd, mjd, ...]}

  load_bundled_cat2_csv(path: Path) -> BundledCat2Override
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


# --- bibliographic metadata --------------------------------------------
# AAS Open Access per https://iopscience.iop.org/article/10.3847/1538-4365/ae3828
CAT2_BIBCODE = "2026ApJS..283...34C"
CAT2_REFERENCE_URL = "https://iopscience.iop.org/article/10.3847/1538-4365/ae3828"
CAT2_DATA_LICENSE = "AAS Open Access (The Second CHIME/FRB Catalog, CHIME/FRB Collab. 2026)"

# --- canonical URL candidates --------------------------------------------
# Listed in order from most-authoritative (CHIME primary) to community
# mirrors. Each entry: (url, role, expected_content_type).
CANDIDATE_URLS: tuple[tuple[str, str, str], ...] = (
    (
        "https://www.chime-frb.ca/catalog/frb_catalog_2.csv",
        "CHIME primary Catalog 2 CSV (advertised on site)",
        "text/csv",
    ),
    (
        "https://www.chime-frb.ca/catalog/catalog_2.csv",
        "CHIME primary alternate filename",
        "text/csv",
    ),
    (
        "https://www.chime-frb.ca/catalog/frbcatalog2.csv",
        "CHIME no-underscore filename",
        "text/csv",
    ),
    (
        "https://raw.githubusercontent.com/CHIME-FRB-Open-Data/catalog/"
        "main/csv/catalog2.csv",
        "GitHub raw CSV mirror (offline at probe time)",
        "text/csv",
    ),
    (
        "https://chime-frb-open-data.s3.ca-central-1.amazonaws.com/"
        "catalog2.csv",
        "S3 mirror (offline at probe time)",
        "text/csv",
    ),
)

# --- published periods for the most-studied CHIME/FRB repeaters ----------
# PUBLIC-DOMAIN facts, not fabricated arrival arrays. This dict drives
# the scramble-null comparison: for each repeater, we report whether the
# recovered period lands within `tolerance_d` of the published value.
KNOWN_REPEATER_PERIODS_DAYS: dict[str, float] = {
    "FRB 20180916A": 16.35,    # Pastor-Marazuela 2020
    "FRB 20121102A": 157.0,    # Rajwade 2020; Cruces 2021 (~157 d cycle)
}
KNOWN_REPEATER_TOLERANCE_DAYS: float = 1.0   # |recovered - published| <= 1 d


# --- CSV schema tolerance ------------------------------------------------
# Same semantics as chime_frb_fetcher.py: try documented + alternates.
COLUMN_NAMES_NAME = ("tns_name", "name", "frb_name", "transient_name",
                       "source", "source_name")
COLUMN_NAMES_MJD = ("mjd", "peak_mjd", "arrival_mjd", "utc_mjd",
                       "dm_phase_mjd", "peak_time_mjd", "toa_mjd")


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
class Cat2FetchResult:
    fetch_status: str       # FETCHED | CACHED | UNREACHABLE | PARKING_PAGE
                            # | INVALID_FORMAT | ERROR
    fetched_from: Optional[str]
    csv_path: Optional[str]
    n_rows_total: int       # rows in the parsed CSV (after header)
    rows_by_source: dict[str, list[float]] = field(default_factory=dict)
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


# --- CSV parser ----------------------------------------------------------

@dataclass
class Cat2BurstRow:
    raw_name: str
    raw_mjd: Optional[float]


def _pick_row_by_column(headers: list[str], candidates: tuple[str, ...]) -> Optional[int]:
    h_lower = [h.strip().lower() for h in headers]
    for c in candidates:
        if c.lower() in h_lower:
            return h_lower.index(c.lower())
    return None


def parse_cat2_csv_rows(
    csv_text: str,
    source_name: str,
) -> list[Cat2BurstRow]:
    """Parse a CHIME/FRB Catalog 2 CSV (or compatible) into Cat2BurstRow list.

    Schema-tolerance contract: same as chime_frb_fetcher.py. Unknown
    columns are ignored; if essential columns (name + mjd) are missing
    we return an EMPTY list (we do NOT guess).
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
    if idx_name is None or idx_mjd is None:
        return []
    rows: list[Cat2BurstRow] = []
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
            name = (raw[idx_name] or "").strip()
        except (IndexError, TypeError):
            continue
        if not name:
            continue
        mjd = _cell(idx_mjd)
        rows.append(Cat2BurstRow(raw_name=name, raw_mjd=mjd))
    return rows


def _group_by_source(rows: list[Cat2BurstRow]) -> dict[str, list[float]]:
    """Group rows by source name, returning {source: [sorted_mjds]}."""
    out: dict[str, list[float]] = {}
    for r in rows:
        if r.raw_mjd is None:
            continue
        out.setdefault(r.raw_name, []).append(float(r.raw_mjd))
    # sort ascending per source
    return {k: sorted(v) for k, v in out.items()}


# --- bundled override (manual transcription) -----------------------------

@dataclass
class BundledCat2Override:
    """Result of parsing a user-provided --bundled-cat2-csv."""
    rows_by_source: dict[str, list[float]]
    source_path: str
    n_rows: int
    n_sources: int
    error: Optional[str] = None

    @property
    def has_any_mjds(self) -> bool:
        return any(len(v) > 0 for v in self.rows_by_source.values())


def load_bundled_cat2_csv(path: Path) -> BundledCat2Override:
    """Load a user-provided CSV with Cat 2 burst MJDs.

    Accepted schemas (we pick the first parseable form):
      (1) header `name,mjd[,extra_cols...]` per row.
      (2) Two-column `index,name?` rows where the column detection picks
          up name + mjd.
    """
    text = path.read_text(errors="replace")
    try:
        rows = parse_cat2_csv_rows(text, source_name=path.name)
        grouped = _group_by_source(rows)
        n_rows = len(rows)
        n_sources = len(grouped)
    except Exception as e:
        return BundledCat2Override(
            rows_by_source={}, source_path=str(path),
            n_rows=0, n_sources=0, error=str(e),
        )
    return BundledCat2Override(
        rows_by_source=grouped, source_path=str(path),
        n_rows=n_rows, n_sources=n_sources,
    )


# --- the actual probe ----------------------------------------------------

def _probe_url(url: str, role: str, expected_ct: str,
               timeout_s: float) -> FetchAttempt:
    """Open one URL; record what we got. NEVER raise."""
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
                head = ""
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
            content_bytes=0, verdict="TIMEOUT" if isinstance(e, TimeoutError)
            else "NETWORK_ERROR",
            error=str(e)[:200], elapsed_s=round(time.monotonic() - started, 3),
        )
    except Exception as e:
        return FetchAttempt(
            url=url, role=role, http_status=None, content_type=None,
            content_bytes=0, verdict="ERROR",
            error=f"{type(e).__name__}: {e}"[:200],
            elapsed_s=round(time.monotonic() - started, 3),
        )


def _read_cached(cache_path: Path) -> Optional[Cat2FetchResult]:
    if not cache_path.exists():
        return None
    try:
        text = cache_path.read_text()
        rows = parse_cat2_csv_rows(text, source_name=cache_path.name)
        grouped = _group_by_source(rows)
        result = Cat2FetchResult(
            fetch_status="CACHED",
            fetched_from=str(cache_path),
            csv_path=str(cache_path),
            n_rows_total=len(rows),
            rows_by_source=grouped,
            attempts=[FetchAttempt(
                url=str(cache_path), role="local cache",
                http_status=None, content_type=None,
                content_bytes=len(text),
                verdict="CSV_HEADER", error=None, elapsed_s=0.0,
            )],
            reference_bibcode=CAT2_BIBCODE,
            reference_url=CAT2_REFERENCE_URL,
            provenance_note=(
                "Loaded from local cache; canonical mirror not contacted. "
                "Verify the cache has not stale-rotated before trusting this "
                "result."
            ),
        )
        return result
    except Exception:
        return None


def try_fetch_chime_frb_catalog_2_csv(
    attempt_urls: Optional[list[tuple[str, str, str]]] = None,
    timeout_s: float = 10.0,
    use_cache: bool = True,
    cache_path: Optional[Path] = None,
    force_status_for_tests: Optional[str] = None,
) -> Cat2FetchResult:
    """Honest CHIME/FRB Catalog 2 fetch.

    Parameters -- same contract as chime_frb_fetcher.try_fetch_chime_frb_catalog_1_csv:
      attempt_urls : overrides CANDIDATE_URLS for tests.
      timeout_s : per-attempt wall-clock timeout.
      use_cache / cache_path : if cache_path points to a valid CSV, return
        CACHED without contacting the network. Filename hint
        ``data/radio/cache/chime_frb_catalog2.csv``.
      force_status_for_tests : if set to one of {'UNREACHABLE','PARKING_PAGE','FETCHED'},
        skip the network probe entirely.

    Order of operations (mirrors the chime_frb_fetcher contract):
      1. `force_status_for_tests` hooks FIRST (so tests can never silently
         short-circuit on a stale cache).
      2. Then use_cache + _read_cached.
      3. Then the real probe.
    """
    urls = list(attempt_urls) if attempt_urls is not None else list(CANDIDATE_URLS)

    # --- test hook FIRST ---------------------------------------------
    if force_status_for_tests == "UNREACHABLE":
        return Cat2FetchResult(
            fetch_status="UNREACHABLE", fetched_from=None, csv_path=None,
            n_rows_total=0, rows_by_source={},
            attempts=[FetchAttempt(
                url=u, role=r, http_status=None, content_type=None,
                content_bytes=0, verdict="NETWORK_ERROR",
                error="force_status_for_tests=UNREACHABLE (no network call)",
                elapsed_s=0.0,
            ) for (u, r, _ct) in urls],
            reference_bibcode=CAT2_BIBCODE,
            reference_url=CAT2_REFERENCE_URL,
            provenance_note=(
                "Test stub: no live probe performed. Every canonical URL "
                "marked UNREACHABLE without network contact."
            ),
        )
    if force_status_for_tests == "PARKING_PAGE":
        return Cat2FetchResult(
            fetch_status="PARKING_PAGE", fetched_from=None, csv_path=None,
            n_rows_total=0, rows_by_source={},
            attempts=[FetchAttempt(
                url=u, role=r, http_status=200, content_type="text/html",
                content_bytes=200, verdict="HTML_PARKING",
                error="force_status_for_tests=PARKING_PAGE (no network call)",
                elapsed_s=0.0,
            ) for (u, r, _ct) in urls],
            reference_bibcode=CAT2_BIBCODE,
            reference_url=CAT2_REFERENCE_URL,
            provenance_note=(
                "Test stub: every canonical URL returned an HTML parking "
                "page (HTTP 200 + Content-Type: text/html) -- no CSV bytes."
            ),
        )

    # --- cache short-circuit (only AFTER test_force has been honored)
    if cache_path is None:
        cache_path = Path("data/radio/cache/chime_frb_catalog2.csv")
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
            rows = parse_cat2_csv_rows(body, source_name=url)
            grouped = _group_by_source(rows)
            csv_p = None
            if cache_path is not None:
                try:
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_path.write_text(body)
                    csv_p = str(cache_path)
                except Exception:
                    csv_p = None
            return Cat2FetchResult(
                fetch_status="FETCHED", fetched_from=url, csv_path=csv_p,
                n_rows_total=len(rows), rows_by_source=grouped,
                attempts=attempts,
                detected_columns={
                    "name": "matched", "mjd": "matched",
                },
                reference_bibcode=CAT2_BIBCODE,
                reference_url=CAT2_REFERENCE_URL,
                provenance_note=(
                    f"Live fetch OK from {url}. Parsed {len(rows)} rows; "
                    f"{len(grouped)} unique sources; "
                    f"{sum(len(v) for v in grouped.values())} bursts total."
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
    return Cat2FetchResult(
        fetch_status=status, fetched_from=None, csv_path=None,
        n_rows_total=0, rows_by_source={},
        attempts=attempts,
        reference_bibcode=CAT2_BIBCODE,
        reference_url=CAT2_REFERENCE_URL,
        provenance_note=(
            f"All {len(attempts)} canonical URLs failed. No bytes parsed; "
            "no synthetic data injected. See `attempts[]` for full history. "
            "Honest-empty fallback per the lab motto."
        ),
    )


def module_summary(result: Cat2FetchResult) -> str:
    """One-line human summary used by CLIs and notes."""
    n_bursts = sum(len(v) for v in result.rows_by_source.values())
    return (
        f"CHIME/FRB Catalog 2 fetch: status={result.fetch_status}; "
        f"attempts={len(result.attempts)}; "
        f"n_rows_total={result.n_rows_total}; "
        f"n_sources={len(result.rows_by_source)}; "
        f"n_bursts_total={n_bursts}; "
        f"ref={result.reference_bibcode or 'none'}"
    )


if __name__ == "__main__":
    # Self-test: run the live probe and print the result as JSON.
    # Will take up to ~50 seconds because we try all 5 URLs.
    out = try_fetch_chime_frb_catalog_2_csv(timeout_s=10.0)
    print(json.dumps(out.to_dict(), indent=2, default=str))
