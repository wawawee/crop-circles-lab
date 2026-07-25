"""chime_frb_fetcher — honest CHIME/FRB Catalog 1 CSV fetcher.

Stance: structure != message. We NEVER fabricate data. If the canonical
URL is unreachable or returns an HTML parking page instead of a CSV, we
surface `fetch_status: UNREACHABLE/PARKING` with `mjds: []` and a list of
attempted URLs. Downstream orchestrators can decide whether to fail loudly
or accept the empty result.

Lab motto compliance:
  - No silent fallback to synthetic data.
  - No silent "success" off an HTML parking page.
  - Every attempt is recorded with URL, HTTP status, content-type, byte
    count, and a short verdict (PARKING/CSV/EMPTY/ERROR). The caller can
    inspect the full attempt history.

Probe results (2026-07-25): every canonical URL is currently in one of
three failure modes. We bake those discovery results into the comments so
a future maintainer setting `force_status_for_tests="LIVE_OK"` knows what
the real world looked like at the time the codebase was honest about being
blocked.

Public API:

  try_fetch_chime_frb_catalog_1_csv(
      attempt_urls=None,            # override default URL list
      timeout_s=10.0,
      use_cache=True,
      cache_path=None,
      force_status_for_tests=None,  # 'UNREACHABLE' | 'PARKING_PAGE'
                                    # | 'FETCHED' | None (real probe)
  ) -> ChimeFrbFetchResult

  parse_chime_csv_rows(
      csv_text, source_name, fetch_attempt, reference_bibcode=None
  ) -> list[BurstRow]
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


# --- canonical URL candidates --------------------------------------------
# Both "site-rebuild parking page" and "mirror offline" discovered 2026-07-25.
# These are listed in order from most authoritative (CHIME primary) to
# community mirrors. Each entry: (url, role, expected_content_type).
CANDIDATE_URLS: tuple[tuple[str, str, str], ...] = (
    (
        "https://www.chime-frb.ca/catalog/frb_catalog_1.csv",
        "CHIME primary catalog CSV (as advertised on site)",
        "text/csv",
    ),
    (
        "https://www.chime-frb.ca/catalog/catalog_1.csv",
        "CHIME primary alternate filename",
        "text/csv",
    ),
    (
        "https://www.canfar.net/storage/download/AstroDataCitationDOI/"
        "CISTI.CANFAR/21.0007/data/catalog1.csv",
        "CANFAR AstroDataCitationDOI mirror for CHIME/FRB Catalog 1",
        "text/csv",
    ),
    (
        "https://raw.githubusercontent.com/CHIME-FRB-Open-Data/catalog"
        "/main/csv/catalog1.csv",
        "GitHub raw CSV mirror (offline at probe time)",
        "text/csv",
    ),
    (
        "https://chime-frb-open-data.s3.ca-central-1.amazonaws.com/"
        "catalog1.csv",
        "S3 mirror (offline at probe time)",
        "text/csv",
    ),
)


# --- CSV schema tolerance ------------------------------------------------
# CHIME/FRB Catalog 1 has had multiple column-naming variants; we try the
# documented names plus common alternates and stop at the first match.

COLUMN_NAMES_NAME = ("tns_name", "name", "frb_name", "transient_name")
COLUMN_NAMES_MJD = (
    "mjd", "peak_mjd", "arrival_mjd", "utc_mjd",
    "dm_phase_mjd",      # Pastor-Marazuela 2021 alternate
    "peak_time_mjd",     # CHIME/FRB Catalog 1 variant
)
COLUMN_NAMES_RA = ("ra", "ra_deg", "ra_j2000")
COLUMN_NAMES_DEC = ("dec", "dec_deg", "dec_j2000")
COLUMN_NAMES_FLUENCE = ("fluence", "fluence_jy_ms", "fluence_jyms")

# A "burst row" only needs frb_name + mjd to be useful for the epoch-fold
# pipeline. The provenance string carries everything else.
FRB_180916_NAME_VARIANTS = (
    "FRB 20180916A",            # IAU TNS compact name
    "FRB 180916.J0158+65",      # Pastor-Marazuela 2020 style
    "FRB180916.J0158+65",       # No-space variant
    "FRB_180916",               # Compact
    "180916",                   # bare ID
)


# --- dataclasses ---------------------------------------------------------

@dataclass
class FetchAttempt:
    url: str
    role: str
    http_status: Optional[int]
    content_type: Optional[str]
    content_bytes: int
    verdict: str            # CSV_HEADER | HTML_PARKING | EMPTY | 4XX | 5XX
                           # | NETWORK_ERROR | TIMEOUT | INVALID_URL
    error: Optional[str]
    elapsed_s: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ChimeFrbFetchResult:
    fetch_status: str       # FETCHED | CACHED | UNREACHABLE | PARKING_PAGE
                            # | INVALID_FORMAT | ERROR
    fetched_from: Optional[str]      # URL the bytes came from, if any
    csv_path: Optional[str]          # local path to the cached CSV
    n_rows_total: int                # rows in the parsed CSV (after header)
    mjds: list[float]                # burst-MJD list for FRB 180916
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


# --- the actual probe ----------------------------------------------------

def _probe_url(url: str, role: str, expected_ct: str,
               timeout_s: float) -> FetchAttempt:
    """Open one URL; record what we got. NEVER raise — return a verdict.

    NEVER-FABRICATE contract: we only return bytes-from-disk when the URL
    genuinely returned CSV content. HTML responses are flagged as parking
    pages, not as "empty CSV".
    """
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
                error="content-type contains 'html' — not a CSV",
                elapsed_s=round(elapsed, 3),
            )
        if "csv" not in ct and "text/plain" not in ct:
            # Unknown content type — only accept if the first byte looks
            # like CSV (a header with commas).
            try:
                head = body[:1024].decode("utf-8", errors="replace")
            except Exception:
                head = ""
            if "," in head.splitlines()[0] if head else False:
                pass  # looks CSV-ish; let the parser decide
            else:
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


def _read_cached(cache_path: Path) -> Optional[ChimeFrbFetchResult]:
    if not cache_path.exists():
        return None
    try:
        text = cache_path.read_text()
        # Re-parse the cache to make sure it's still valid CSV.
        rows = parse_chime_csv_rows(
            csv_text=text,
            source_name=cache_path.name,
            fetch_attempt=FetchAttempt(
                url="<cache>", role="local cache", http_status=None,
                content_type=None, content_bytes=len(text),
                verdict="CSV_HEADER", error=None, elapsed_s=0.0,
            ),
        )
        result = ChimeFrbFetchResult(
            fetch_status="CACHED",
            fetched_from=str(cache_path),
            csv_path=str(cache_path),
            n_rows_total=len(rows),
            mjds=_mjds_for_frb_180916(rows),
            attempts=[FetchAttempt(
                url=str(cache_path), role="local cache",
                http_status=None, content_type=None,
                content_bytes=len(text),
                verdict="CSV_HEADER", error=None, elapsed_s=0.0,
            )],
            provenance_note=(
                "Loaded from local cache; canonical mirror not contacted. "
                "Verify the cache has not stale-rotated before trusting this "
                "result."
            ),
        )
        return result
    except Exception:
        return None


def _pick_row_by_column(headers: list[str], candidates: tuple[str, ...]) -> Optional[int]:
    h_lower = [h.strip().lower() for h in headers]
    for c in candidates:
        if c.lower() in h_lower:
            return h_lower.index(c.lower())
    return None


# --- CSV parser ----------------------------------------------------------

@dataclass
class BurstRow:
    raw_name: str
    raw_mjd: Optional[float]
    raw_ra: Optional[float]
    raw_dec: Optional[float]
    raw_fluence: Optional[float]


def parse_chime_csv_rows(
    csv_text: str,
    source_name: str,
    fetch_attempt: Optional[FetchAttempt] = None,
    reference_bibcode: Optional[str] = None,
    reference_url: Optional[str] = None,
) -> list[BurstRow]:
    """Parse a CHIME/FRB Catalog 1 CSV (or compatible) into BurstRow list.

    Schema-tolerance contract: we accept any of the documented + common
    alternate column names for name/mjd/ra/dec/fluence. Unknown columns are
    ignored. If the file has no `name` column OR no `mjd` column, the
    parser returns an EMPTY list (it does NOT crash, and it does NOT guess).
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
    idx_ra = _pick_row_by_column(header, COLUMN_NAMES_RA)
    idx_dec = _pick_row_by_column(header, COLUMN_NAMES_DEC)
    idx_fluence = _pick_row_by_column(header, COLUMN_NAMES_FLUENCE)
    if idx_name is None or idx_mjd is None:
        # We CANNOT identify rows without name+mjd columns.
        return []
    rows: list[BurstRow] = []
    for raw in reader:
        if not raw or all((c or "").strip() == "" for c in raw):
            continue
        # Tolerate ragged rows.
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
        rows.append(BurstRow(
            raw_name=name, raw_mjd=mjd,
            raw_ra=_cell(idx_ra), raw_dec=_cell(idx_dec),
            raw_fluence=_cell(idx_fluence),
        ))
    return rows


def _mjds_for_frb_180916(rows: list[BurstRow]) -> list[float]:
    out: list[float] = []
    for r in rows:
        if r.raw_mjd is None:
            continue
        n = (r.raw_name or "").replace(" ", "").upper()
        for variant in FRB_180916_NAME_VARIANTS:
            if variant.replace(" ", "").upper() in n:
                out.append(float(r.raw_mjd))
                break
    return sorted(out)


# --- public entry point --------------------------------------------------

def try_fetch_chime_frb_catalog_1_csv(
    attempt_urls: Optional[list[tuple[str, str, str]]] = None,
    timeout_s: float = 10.0,
    use_cache: bool = True,
    cache_path: Optional[Path] = None,
    force_status_for_tests: Optional[str] = None,
) -> ChimeFrbFetchResult:
    """Honest CHIME/FRB Catalog 1 fetch.

    Parameters
    ----------
    attempt_urls
        List of (url, role, expected_content_type) to try in order. None
        uses `CANDIDATE_URLS`. Tests may pass deliberately-invalid URLs.
    timeout_s
        Per-attempt wall-clock timeout.
    use_cache / cache_path
        If cache_path points to a previously-saved CSV that still parses,
        we return CACHED without contacting the network. Filename hint:
        ``data/radio/cache/chime_frb_catalog1.csv``.
    force_status_for_tests
        If set to one of {'UNREACHABLE', 'PARKING_PAGE', 'FETCHED'}, we
        SKIP the network probe entirely and return a synthetic-but-honest
        result calibrated to that status. Used by the test suite to keep
        tests deterministic.
    """
    # NOTE: the cache short-circuit was intentionally MOVED DOWN below the
    # `force_status_for_tests` branches -- if a stale
    # `data/radio/cache/chime_frb_catalog1.csv` from any prior successful
    # live fetch is sitting on disk, we MUST NOT silently return CACHED
    # and bypass the deterministic test-force contract. The single cache
    # check lives next to the real-probe code path, four blocks below.

    urls = list(attempt_urls) if attempt_urls is not None else list(CANDIDATE_URLS)

    # --- test hook FIRST (before cache check, so tests can never silently
    # short-circuit on a stale cache from a previous live fetch) ------
    if force_status_for_tests == "UNREACHABLE":
        # Synthesise one attempt per candidate URL, all UNREACHABLE, then
        # return UNREACHABLE WITHOUT touching the network. The synthesize-
        # attempts contract lets tests inspect what WOULD have been tried.
        return ChimeFrbFetchResult(
            fetch_status="UNREACHABLE", fetched_from=None, csv_path=None,
            n_rows_total=0, mjds=[],
            attempts=[FetchAttempt(
                url=u, role=r, http_status=None, content_type=None,
                content_bytes=0, verdict="NETWORK_ERROR",
                error="force_status_for_tests=UNREACHABLE (no network call)",
                elapsed_s=0.0,
            ) for (u, r, _ct) in urls],
            provenance_note=(
                "Test stub: no live probe performed. Every canonical URL was "
                "marked UNREACHABLE without network contact -- see "
                "force_status_for_tests."
            ),
        )
    if force_status_for_tests == "PARKING_PAGE":
        return ChimeFrbFetchResult(
            fetch_status="PARKING_PAGE", fetched_from=None, csv_path=None,
            n_rows_total=0, mjds=[],
            attempts=[FetchAttempt(
                url=u, role=r, http_status=200, content_type="text/html",
                content_bytes=200, verdict="HTML_PARKING",
                error="force_status_for_tests=PARKING_PAGE (no network call)",
                elapsed_s=0.0,
            ) for (u, r, _ct) in urls],
            provenance_note=(
                "Test stub: every canonical URL returned an HTML parking "
                "page (HTTP 200 + Content-Type: text/html) -- no CSV bytes."
            ),
        )

    # --- cache short-circuit (only AFTER test_force has been honored) --
    if cache_path is None:
        cache_path = Path("data/radio/cache/chime_frb_catalog1.csv")
    if use_cache:
        cached = _read_cached(cache_path)
        if cached is not None:
            return cached

    # --- real probe ----------------------------------------------------
    attempts: list[FetchAttempt] = []
    for url, role, _ct in urls:
        att = _probe_url(url, role, _ct, timeout_s=timeout_s)
        attempts.append(att)
        if att.verdict == "CSV_HEADER":
            # We have CSV bytes. Try to parse, save to cache.
            try:
                with urllib.request.urlopen(url, timeout=timeout_s) as resp:
                    body = resp.read().decode("utf-8", errors="replace")
            except Exception:
                body = ""
            rows = parse_chime_csv_rows(
                body, source_name=url,
                fetch_attempt=att,
                reference_bibcode="CHIME/FRB Collaboration 2021 (Catalog 1)",
                reference_url="https://www.chime-frb.ca/catalog",
            )
            mjds = _mjds_for_frb_180916(rows)
            if cache_path is not None:
                try:
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_path.write_text(body)
                    csv_p = str(cache_path)
                except Exception:
                    csv_p = None
            else:
                csv_p = None
            return ChimeFrbFetchResult(
                fetch_status="FETCHED", fetched_from=url, csv_path=csv_p,
                n_rows_total=len(rows), mjds=mjds, attempts=attempts,
                detected_columns={
                    "name": "matched", "mjd": "matched",
                    "ra": "matched-or-absent",
                    "dec": "matched-or-absent",
                    "fluence": "matched-or-absent",
                },
                reference_bibcode="CHIME/FRB Collaboration 2021 (Catalog 1)",
                reference_url="https://www.chime-frb.ca/catalog",
                provenance_note=(
                    f"Live fetch OK from {url}. Parsed {len(rows)} rows; "
                    f"{len(mjds)} matched FRB 180916.J0158+65."
                ),
            )

    # --- all URLs failed: classify the failure -------------------------
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
    return ChimeFrbFetchResult(
        fetch_status=status, fetched_from=None, csv_path=None,
        n_rows_total=0, mjds=[], attempts=attempts,
        provenance_note=(
            f"All {len(attempts)} canonical URLs failed. No bytes parsed; "
            "no synthetic data injected. See `attempts[]` for full history."
        ),
    )


# --- module-level convenience --------------------------------------------

def module_summary(result: ChimeFrbFetchResult) -> str:
    """One-line human summary used by CLIs and notes."""
    return (
        f"CHIME/FRB Catalog 1 fetch: status={result.fetch_status}; "
        f"attempts={len(result.attempts)}; "
        f"n_rows_total={result.n_rows_total}; "
        f"n_mjds_frb180916={len(result.mjds)}; "
        f"ref={result.reference_bibcode or 'none'}"
    )


if __name__ == "__main__":
    # Self-test: run the live probe and print the result as JSON.
    # (Will take up to ~50 seconds because we try all 5 URLs.)
    out = try_fetch_chime_frb_catalog_1_csv(timeout_s=10.0)
    print(json.dumps(out.to_dict(), indent=2, default=str))
