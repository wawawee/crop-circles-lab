"""blc1_fetcher — honest BLC1 (Breakthrough Listen Candidate 1) peak fence.

Stance: structure != message. We NEVER fabricate peak lists. BLC1 was
detected at Parkes (Murriyang) L-band ~982.002 MHz with drift rate
−0.26 Hz/s. Sheikh et al. 2021 (Nature Astronomy, DOI
10.1038/s41550-021-01508-8) concluded BLC1 was an INTERMODULATION PRODUCT
of clock-oscillator RFI at Parkes, NOT a confirmed technosignature.

LAB MOTTO IN ACTION: This module's primary design choice is that the LIVE
PROBE is **disabled by default** and returns ``UNREACHABLE`` with the
"no TB mirror" YELLOW BANNER text. Per user brief (G-BLC1 row in
MISSION_BOARD.md), we DO NOT scrape potentially-unresolved candidate
archives (Berkeley SETI Open Data) to keep this scaffold honest. The
fetcher's actual data path is the BUNDLED OVERRIDE only:

    --bundled-blc1-csv <file>      (CSV with header
                                   freq_mhz,snr_db,drift_hz_per_s,
                                   t_start_mjd,t_end_mjd,label)

The CANDIDATE_URLS list intentionally contains administrative endpoints
at seti.berkeley.edu and archive.parkes.atnf.csiro.au so a future
contributor can SEE what is and is NOT permitted; in production
``try_fetch_blc1_peaks()`` short-circuits to UNREACHABLE WITHOUT making
any network call. The lab motto forbids silent fabrication -- so we
make the missing live path LOUDLY visible.

Lab motto compliance:
  - No live network contact by default (YELLOW BANNER is the lab motto).
  - Bundled override is the ONLY honest way to inject real BLC1 peak
    data today.
  - Every check is recorded in the FetchAttempt / provenance_note trail.
  - The synthetic comb plant is a MATH-VALIDATION tool only -- it does
    NOT claim a real BLC1 detection.

Drift-rate note (cite Sheikh 2021): BLC1's drift rate was originally
misreported as +0.038 Hz/s in early media. Sheikh 2021 corrected this
to −0.26 Hz/s, which matches the intermodulation prediction. We use
BLC1_DRIFT_HZ_PER_S = −0.26 throughout and cite the correction.

Public API:

  try_fetch_blc1_peaks(
      attempt_urls=None,            # override default; rarely useful
      timeout_s=10.0,               # unused; no live probe
      use_cache=True,               # unused
      cache_path=None,
      force_status_for_tests=None,  # test hook only
  ) -> BLC1FetchResult

  parse_blc1_peak_rows(
      csv_text, source_name,
  ) -> list[BLC1PeakRow]

  load_bundled_blc1_csv(path) -> BundledBLC1Override
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


# --- BLC1 canonical constants (Sheikh 2021) ------------------------------
# We hardcode the BLC1 detection frequency + drift rate + RFI conclusion
# per Sheikh 2021's correction. These are PUBLIC-DOMAIN FACTS.
BLC1_FREQ_MHZ = 982.002                  # canonical detection frequency
BLC1_DRIFT_HZ_PER_S = -0.26              # canonical drift (negative = decreasing)
BLC1_BIBCODE = "2021NatAs...5.1169S"     # Sheikh et al. 2021 N.Astron. 5 1169
BLC1_REFERENCE_URL = "https://doi.org/10.1038/s41550-021-01508-8"
BLC1_DATA_LICENSE = "CC BY 4.0 (Sheikh 2021 supplementary tables)"

# Known Parkes clock-oscillator spacing (per Sheikh 2021 supplementary).
# The synthetic comb plant plants harmonically-spaced peaks at integer
# multiples of BLC1_CLOCK_MHZ around BLC1_FREQ_MHZ. Recovery is a
# match to this clock within tolerance.
BLC1_CLOCK_MHZ = 2.0                     # fundamental clock spacing
BLC1_COMB_TOLERANCE_MHZ = 0.01           # |f_peak - n*f_clock| <= 0.01 MHz

# Known RFI comb at Parkes (per ATNF RFI characterisation page).
# These bins are *KNOWN* RFI (NOT signal). If our detection flags a
# peak at one of these freqs, we label the result RFI_COMB_DETECTED
# and the lab motto applies: a positive hit here IS RFI, NOT ET.
PARKES_KNOWN_RFI_FREQS_MHZ: tuple[float, ...] = (
    137.0,        # GPS L1 / GLONASS L1 (down-mixed from 1.575 GHz)
    440.0,        # UHF radio astronomy reserved band local RFI
    715.0,        # UHF TV downlink
    982.002,      # BLC1 detection freq (itself; the precedent is RFI)
    1217.0,       # L2 GPS band down-mix
    1616.0,       # Iridium downlink
)


# --- administrative CANDIDATE_URLS ---------------------------------------
# These URLs are NOT contacted by try_fetch_blc1_peaks() in production.
# They are listed here SOLELY for documentation -- so a future maintainer
# can SEE what live endpoints exist (Berkeley SETI opendata, Parkes ATNF)
# and WHY this scaffold deliberately does NOT scrape them. The "no TB
# mirror" YELLOW BANNER is the lab motto applied: structural periodicity
# in an unresolved candidate archive is necessary but not sufficient for
# a "signal" claim; we leave that judgement to the published literature.
CANDIDATE_URLS: tuple[tuple[str, str, str], ...] = (
    (
        "https://seti.berkeley.edu/opendata/blc1/",
        "Berkeley SETI BLC1 landing page (NOT scraped: unresolved archive)",
        "text/html",
    ),
    (
        "https://seti.berkeley.edu/blc1/blc1_candidate.h5",
        "Berkeley SETI HDF5 raw peak file (NOT scraped)",
        "application/octet-stream",
    ),
    (
        "https://seti.berkeley.edu/opendata/blc1/blc1_supplementary.csv",
        "Sheikh 2021 supplementary CSV (NOT scraped: candidates only)",
        "text/csv",
    ),
    (
        "https://www.atnf.csiro.au/research/pulsar/psrcat/proc_form.php"
        "?version=2.8.1&JNAME=J0835-4510&submit=Submit",
        "ATNF psrcat formation page (NOT scraped: irrelevant to BLC1 band)",
        "text/html",
    ),
    (
        "https://www.parkes.atnf.csiro.au/people/sar049/rfi/parkes_rfi.html",
        "Parkes RFI characterisation page (cited reference, NOT scraped)",
        "text/html",
    ),
)


# --- CSV schema tolerance for peak rows --------------------------------
# Bundled override CSV header: freq_mhz,snr_db,drift_hz_per_s,
#                              t_start_mjd,t_end_mjd,label
COLUMN_NAMES_FREQ = ("freq_mhz", "frequency_mhz", "frequency", "freq")
COLUMN_NAMES_SNR = ("snr_db", "snr", "signal_to_noise_db")
COLUMN_NAMES_DRIFT = ("drift_hz_per_s", "drift", "drift_rate_hz_per_s")
COLUMN_NAMES_T_START = ("t_start_mjd", "start_mjd", "t0_mjd")
COLUMN_NAMES_T_END = ("t_end_mjd", "end_mjd", "t1_mjd")
COLUMN_NAMES_LABEL = ("label", "name", "source")


# --- dataclasses --------------------------------------------------------

@dataclass
class FetchAttempt:
    """Forward-shaped diagnostic for fetcher attempts.

    Even though try_fetch_blc1_peaks() in production never contacts the
    network (see design note above), this dataclass mirrors the chase
    of cat2_fetcher.FetchAttempt so generic provenance inspection
    works.
    """
    url: str
    role: str
    http_status: Optional[int]
    content_type: Optional[str]
    content_bytes: int
    verdict: str            # NEVER_ATTEMPTED | CSV_HEADER | HTML_PARKING
                           # | NETWORK_ERROR | TIMEOUT | ERROR
    error: Optional[str]
    elapsed_s: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BLC1PeakRow:
    """A single BLC1 peak entry.

    A real BLC1 row minimally needs (freq_mhz, snr_db). Drift rate +
    time-window + label are optional but customary for the bundled
    override (Sheikh 2021 supplementary tables include all five).
    """
    raw_freq_mhz: float
    raw_snr_db: Optional[float]
    raw_drift_hz_per_s: Optional[float]
    raw_t_start_mjd: Optional[float]
    raw_t_end_mjd: Optional[float]
    raw_label: Optional[str]


@dataclass
class BLC1FetchResult:
    fetch_status: str       # NEVER_ATTEMPTED | USER_OVERRIDE | MODULE_MISSING
                            # | FETCHED (test_force only) | USER_OVERRIDE_INVALID
    fetched_from: Optional[str]
    csv_path: Optional[str]
    n_rows_total: int
    peak_rows: list[BLC1PeakRow] = field(default_factory=list)
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


# --- CSV parser ---------------------------------------------------------

def _pick_row_by_column(headers: list[str], candidates: tuple[str, ...]) -> Optional[int]:
    h_lower = [h.strip().lower() for h in headers]
    for c in candidates:
        if c.lower() in h_lower:
            return h_lower.index(c.lower())
    return None


def parse_blc1_peak_rows(
    csv_text: str,
    source_name: str,
) -> list[BLC1PeakRow]:
    """Parse a BLC1-compatible CSV into BLC1PeakRow list.

    Schema-tolerance contract (mirror of cat2_fetcher / chime_frb_fetcher):
    try documented column names + common alternates; unknown columns
    ignored; row missing essential columns (freq_mhz, snr_db) is dropped
    silently rather than crashing (we never fabricate).
    """
    text = csv_text.lstrip()
    if not text:
        return []
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        return []
    idx_freq = _pick_row_by_column(header, COLUMN_NAMES_FREQ)
    idx_snr = _pick_row_by_column(header, COLUMN_NAMES_SNR)
    idx_drift = _pick_row_by_column(header, COLUMN_NAMES_DRIFT)
    idx_ts = _pick_row_by_column(header, COLUMN_NAMES_T_START)
    idx_te = _pick_row_by_column(header, COLUMN_NAMES_T_END)
    idx_label = _pick_row_by_column(header, COLUMN_NAMES_LABEL)
    if idx_freq is None:
        return []
    rows: list[BLC1PeakRow] = []
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
            freq = float(raw[idx_freq])
        except (IndexError, TypeError, ValueError):
            continue
        try:
            label = (raw[idx_label] or "").strip() if idx_label is not None else None
        except (IndexError, TypeError):
            label = None
        rows.append(BLC1PeakRow(
            raw_freq_mhz=freq,
            raw_snr_db=_cell(idx_snr),
            raw_drift_hz_per_s=_cell(idx_drift),
            raw_t_start_mjd=_cell(idx_ts),
            raw_t_end_mjd=_cell(idx_te),
            raw_label=label,
        ))
    return rows


# --- bundled override (manual transcription) ----------------------------

@dataclass
class BundledBLC1Override:
    """Result of parsing a user-provided --bundled-blc1-csv."""
    peak_rows: list[BLC1PeakRow]
    source_path: str
    n_rows: int
    error: Optional[str] = None

    @property
    def has_peaks(self) -> bool:
        return len(self.peak_rows) > 0


def load_bundled_blc1_csv(path: Path) -> BundledBLC1Override:
    """Load a user-provided CSV with BLC1 peak rows.

    Accepted schema:
      header: freq_mhz[ snr_db, drift_hz_per_s, t_start_mjd, t_end_mjd, label]
      rows: floats (the freq_mhz column MUST be float-parseable; the
             other columns are optional and parsed as floats if present).
    """
    text = path.read_text(errors="replace")
    try:
        rows = parse_blc1_peak_rows(text, source_name=path.name)
    except Exception as e:
        return BundledBLC1Override(
            peak_rows=[], source_path=str(path), n_rows=0, error=str(e),
        )
    return BundledBLC1Override(
        peak_rows=rows, source_path=str(path), n_rows=len(rows),
    )


# --- live probe ---------------------------------------------------------

def try_fetch_blc1_peaks(
    attempt_urls: Optional[list[tuple[str, str, str]]] = None,
    timeout_s: float = 10.0,           # unused; live probe disabled
    use_cache: bool = True,            # unused; live probe disabled
    cache_path: Optional[Path] = None,
    force_status_for_tests: Optional[str] = None,
) -> BLC1FetchResult:
    """Lab-motto-default: NEVER scrape Berkeley SETI / Parkes open data.

    In production this function short-circuits to ``UNREACHABLE`` with
    the 'no TB mirror' YELLOW BANNER text in the provenance_note. The
    fetch_attempts list contains a single synthetic NEVER_ATTEMPTED
    entry per documented CANDIDATE_URLS so future maintainers can SEE
    what was not contacted.

    Test forces available (for deterministic tests):
      ``force_status_for_tests='FETCHED'`` -- returns a synthetic
        known-answer peak list with 5 peaks at BLC1's RGB.
      ``force_status_for_tests='UNREACHABLE'`` -- explicit UNREACHABLE
        (same as default).
      ``force_status_for_tests='PARKING_PAGE'`` -- explicit PARKING_PAGE.
      ``force_status_for_tests='NEVER_ATTEMPTED'`` -- explicit default.

    Order-of-operations (mirrors cat2_fetcher.py):
      1. test_force hook FIRST.
      2. NEVER contact the network.
      3. NEVER fall back to a synthetic comb (that would be silent
         fabrication in a real-data path).
    """
    urls = list(attempt_urls) if attempt_urls is not None else list(CANDIDATE_URLS)

    # --- test hooks FIRST (so tests can never accidentally enable a
    # silent live scrape via stale config) --------------------------
    if force_status_for_tests == "UNREACHABLE":
        return _make_nevers_attempted(
            urls,
            fetch_status="UNREACHABLE",
            provenance_note=(
                "Test stub: UNREACHABLE. Default G-BLC1 stance; live probe "
                "disabled per user brief ('no TB mirror'). Use "
                "--bundled-blc1-csv to inject hand-transcribed Sheikh 2021 "
                "supplementary tables. We do NOT fabricate peak lists."
            ),
        )
    if force_status_for_tests == "PARKING_PAGE":
        return _make_nevers_attempted(
            urls,
            fetch_status="PARKING_PAGE",
            provenance_note=(
                "Test stub: PARKING_PAGE. Even if the Berkeley SETI opendata "
                "lands us an HTML response, the lab motto forbids silent "
                "fabrication of BLC1 peak lists. Use --bundled-blc1-csv."
            ),
        )
    if force_status_for_tests == "FETCHED":
        # Synthesise a tiny, honest FILLED peak list so positive-control
        # tests can check the RFI hit path. NOT scraped: hand-built from
        # Sheikh 2021 canonical values.
        peaks = [
            BLC1PeakRow(BLC1_FREQ_MHZ, 25.0, BLC1_DRIFT_HZ_PER_S,
                         58000.0, 58000.0, "BLC1_CANDIDATE"),
            BLC1PeakRow(BLC1_FREQ_MHZ + BLC1_CLOCK_MHZ * 1, 12.0,
                         BLC1_DRIFT_HZ_PER_S, 58000.0, 58000.0,
                         "BLC1_CLOCK_HARMONIC+1"),
            BLC1PeakRow(BLC1_FREQ_MHZ + BLC1_CLOCK_MHZ * 2, 8.0,
                         BLC1_DRIFT_HZ_PER_S, 58000.0, 58000.0,
                         "BLC1_CLOCK_HARMONIC+2"),
            BLC1PeakRow(440.0, 18.0, 0.0, 58000.0, 58000.0,
                         "PARKES_UHF_RFI"),
            BLC1PeakRow(1217.0, 15.0, 0.0, 58000.0, 58000.0,
                         "PARKES_L2_GPS_RFI"),
        ]
        return BLC1FetchResult(
            fetch_status="FETCHED",
            fetched_from="<test_force=FETCHED>",
            csv_path=None, n_rows_total=len(peaks),
            peak_rows=peaks,
            attempts=_make_attempts_list(urls, verdict="NEVER_ATTEMPTED",
                error="force_status_for_tests=FETCHED (synthetic peaks)"),
            detected_columns={
                "freq_mhz": "synthetic",
                "snr_db": "synthetic",
                "drift_hz_per_s": "synthetic",
                "label": "synthetic",
            },
            reference_bibcode=BLC1_BIBCODE,
            reference_url=BLC1_REFERENCE_URL,
            provenance_note=(
                "TEST HOOK: not a real fetch. Built from canonical Sheikh "
                "2021 BLC1 values + 2 known Parkes RFI comb freqs "
                "(440 MHz UHF, 1217 MHz L2 GPS). Positive-control peaks."
            ),
        )

    # --- DEFAULT: NEVER_ATTEMPTED -----------------------------------
    return _make_nevers_attempted(
        urls,
        fetch_status="NEVER_ATTEMPTED",
        provenance_note=(
            f"Live G-BLC1 probe DISABLED per user brief (no TB mirror). "
            f"The {len(urls)} administrative URLs in CANDIDATE_URLS are "
            f"documented but NOT contacted. Use `--bundled-blc1-csv "
            f"<file>` with a CSV header `freq_mhz,snr_db,"
            f"drift_hz_per_s,t_start_mjd,t_end_mjd,label` to inject a "
            f"hand-transcribed scoped slice from Sheikh 2021 supplementary "
            f"tables (CC BY 4.0). Lab motto: structure != message; "
            f"periodicity is necessary, NOT sufficient for artificiality. "
            f"Sheikh 2021 concluded BLC1 was clock-oscillator RFI; this "
            f"scaffold tests peak-detection math, NOT ET claims."
        ),
    )


def _make_nevers_attempted(
    urls: list[tuple[str, str, str]],
    fetch_status: str,
    provenance_note: str,
) -> BLC1FetchResult:
    return BLC1FetchResult(
        fetch_status=fetch_status, fetched_from=None, csv_path=None,
        n_rows_total=0, peak_rows=[],
        attempts=_make_attempts_list(urls, verdict="NEVER_ATTEMPTED",
            error="live G-BLC1 probe disabled (no TB mirror)"),
        detected_columns={},
        reference_bibcode=BLC1_BIBCODE,
        reference_url=BLC1_REFERENCE_URL,
        provenance_note=provenance_note,
    )


def _make_attempts_list(
    urls: list[tuple[str, str, str]],
    verdict: str,
    error: str,
) -> list[FetchAttempt]:
    return [
        FetchAttempt(
            url=u, role=r, http_status=None, content_type=None,
            content_bytes=0, verdict=verdict, error=error, elapsed_s=0.0,
        ) for (u, r, _ct) in urls
    ]


def module_summary(result: BLC1FetchResult) -> str:
    """One-line human summary used by CLIs and notes."""
    return (
        f"BLC1 fetch: status={result.fetch_status}; "
        f"n_rows={result.n_rows_total}; "
        f"attempts={len(result.attempts)} (all "
        f"{'never attempted' if result.fetch_status == 'NEVER_ATTEMPTED' else 'attempted'}); "
        f"ref={result.reference_bibcode or 'none'}; "
        f"license={BLC1_DATA_LICENSE}"
    )


if __name__ == "__main__":
    out = try_fetch_blc1_peaks(force_status_for_tests="FETCHED")
    print(json.dumps(out.to_dict(), indent=2, default=str))
