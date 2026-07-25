"""cat2_real_sources — CHIME/FRB Catalog 2 multi-source data layer.

Stance: structure != message. We NEVER fabricate burst arrival MJDs. The
Second CHIME/FRB Catalog was published 2026-03 (CHIME/FRB Collaboration
et al. 2026, ApJS 283, 34; AAS Open Access). 4,539 FRBs across 3,641
unique sources; 981 bursts from 83 known REPEATING sources.

R1++ wiring (Ozma, 2026-07-25): `load_published_cat2_bursts` now mirrors
`frb_real_sources.load_published_frb_180916_bursts` exactly, but keyed by
source (Cat 2 has 83 known repeaters, not a single FRB):

  - dataclass PublishedCat2BurstSource  (multi-source row group + provenance)
  - load_published_cat2_bursts() resolving, in order:
      1. `--bundled-cat2-csv` override via cat2_fetcher.load_bundled_cat2_csv
      2. live/cached probe via cat2_fetcher.try_fetch_chime_frb_catalog_2_csv
      3. honest-empty (DISABLED / MODULE_MISSING) fallback
    It NEVER fabricates arrival MJDs; on fetch failure it returns
    rows_by_source={} plus the full attempt history and fetch_status.

The synthetic periodicity known-answer (recover 16.35 d + scramble null)
lives in `radio_probe.run_cat2_synthetic`; this module is the honest
real-data layer only.

Lab motto compliance (preserve across the R1++ completion pass):
  - NO silent fallback to synthetic data when the canonical mirror is
    offline; honest-empty on fetch failure.
  - Scramble null per-source: shuffle MJDs within each source's window.
  - Per-source period recovery compares to KNOWN_REPEATER_PERIODS_DAYS
    (FRB 180916 = 16.35 d; FRB 121102 = ~157 d) with
    KNOWN_REPEATER_TOLERANCE_DAYS = 1.0 d.
  - Cat 1 (536 FRBs) is NOT conflated with Cat 2 (4,539 FRBs).
  - Lab motto: periodicity is necessary, NOT sufficient for artificiality.

Public API (full wiring deferred):

  load_published_cat2_bursts(
      bundled_csv_path: Path | None = None,
      fetch_timeout_s: float = 10.0,
      attempt_urls=None,
      use_cat2_fetcher: bool = True,
      force_status_for_tests: str | None = None,
  ) -> PublishedCat2BurstSource

  PublishedCat2BurstSource  -- dataclass
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

# Best-effort import so this module loads in environments where the JSON
# LDD-style imports would otherwise fail.
try:
    from cat2_fetcher import (  # type: ignore
        try_fetch_chime_frb_catalog_2_csv,
        Cat2FetchResult,
        load_bundled_cat2_csv,
        BundledCat2Override,
        CAT2_BIBCODE,
        CAT2_REFERENCE_URL,
    )
except ImportError:  # pragma: no cover
    try_fetch_chime_frb_catalog_2_csv = None
    Cat2FetchResult = None
    load_bundled_cat2_csv = None
    BundledCat2Override = None
    CAT2_BIBCODE = "2026ApJS..283...34C"
    CAT2_REFERENCE_URL = "https://iopscience.iop.org/article/10.3847/1538-4365/ae3828"


@dataclass
class PublishedCat2BurstSource:
    """Row-group source for CHIME/FRB Catalog 2 burst MJDs.

    rows_by_source: dict[source_name -> sorted_list_of_MJDs]
    """
    rows_by_source: dict[str, list[float]] = field(default_factory=dict)
    source_name: str = "unknown"
    source_type: str = "empty"     # chime_csv_fetch_cat2 | user_provided_cat2
                                   # | bundled_attempt_cat2 | empty |
                                   # module_missing | deferred
    reference_bibcode: Optional[str] = None
    reference_url: Optional[str] = None
    fetched_from: Optional[str] = None
    provenance_note: str = ""
    fetch_attempts: list[dict] = field(default_factory=list)
    fetch_status: str = "empty"

    @property
    def has_any_mjds(self) -> bool:
        return any(len(v) > 0 for v in self.rows_by_source.values())

    @property
    def n_sources(self) -> int:
        return len(self.rows_by_source)

    @property
    def n_bursts_total(self) -> int:
        return sum(len(v) for v in self.rows_by_source.values())

    def to_dict(self) -> dict:
        return asdict(self)


def load_published_cat2_bursts(
    bundled_csv_path: Optional[Path] = None,
    fetch_timeout_s: float = 10.0,
    attempt_urls=None,
    use_cat2_fetcher: bool = True,
    force_status_for_tests: Optional[str] = None,
) -> PublishedCat2BurstSource:
    """Resolve CHIME/FRB Catalog 2 burst MJDs (multi-source) from the most
    authoritative source available. Mirrors
    `frb_real_sources.load_published_frb_180916_bursts` but keyed by source.

    Resolution order:
      1. `bundled_csv_path` exists and parses -> ``user_provided_cat2``
      2. `use_cat2_fetcher=True` and (live/cached) -> ``chime_csv_fetch_cat2``
      3. otherwise -> honest-empty (``DISABLED`` / ``MODULE_MISSING``)

    We NEVER fabricate arrival MJDs. On any fetch failure the returned
    source has ``rows_by_source == {}`` plus the full ``fetch_attempts``
    history and the underlying ``fetch_status`` so callers can never
    mistake "no data yet" for "data exists".
    """
    # --- 1. bundled override path --------------------------------------
    if bundled_csv_path is not None and Path(bundled_csv_path).exists():
        if load_bundled_cat2_csv is None:  # pragma: no cover
            return PublishedCat2BurstSource(
                rows_by_source={},
                source_name=str(Path(bundled_csv_path).name),
                source_type="module_missing",
                reference_bibcode=CAT2_BIBCODE,
                reference_url=CAT2_REFERENCE_URL,
                fetched_from=None,
                provenance_note=(
                    "cat2_fetcher module not importable; cannot parse the "
                    f"--bundled-cat2-csv {bundled_csv_path}. No data loaded."
                ),
                fetch_attempts=[],
                fetch_status="MODULE_MISSING",
            )
        bundle = load_bundled_cat2_csv(Path(bundled_csv_path))
        if bundle.error is not None:
            return PublishedCat2BurstSource(
                rows_by_source={},
                source_name=str(Path(bundled_csv_path).name),
                source_type="empty",
                reference_bibcode=CAT2_BIBCODE,
                reference_url=CAT2_REFERENCE_URL,
                fetched_from=None,
                provenance_note=(
                    f"User-provided --bundled-cat2-csv {bundled_csv_path} "
                    f"failed to parse: {bundle.error}. Falling back to empty "
                    f"source. No synthetic data injected."
                ),
                fetch_attempts=[],
                fetch_status="USER_OVERRIDE_INVALID",
            )
        return PublishedCat2BurstSource(
            rows_by_source=bundle.rows_by_source,
            source_name=str(Path(bundled_csv_path).name),
            source_type="user_provided_cat2",
            reference_bibcode="USER_PROVIDED",
            reference_url=f"file://{Path(bundled_csv_path).resolve()}",
            fetched_from=str(bundled_csv_path),
            provenance_note=(
                f"Cat 2 burst MJDs supplied via --bundled-cat2-csv "
                f"{bundled_csv_path} ({bundle.n_sources} sources, "
                f"{bundle.n_rows} rows). The caller is responsible for "
                f"verifying the source paper / table provenance. We do NOT "
                f"validate the values independently."
            ),
            fetch_attempts=[],
            fetch_status="USER_OVERRIDE",
        )

    # --- 2. live/cached cat2_fetcher probe -----------------------------
    if use_cat2_fetcher:
        if try_fetch_chime_frb_catalog_2_csv is None:  # pragma: no cover
            return PublishedCat2BurstSource(
                rows_by_source={},
                source_name="CHIME/FRB Catalog 2",
                source_type="module_missing",
                reference_bibcode=CAT2_BIBCODE,
                reference_url=CAT2_REFERENCE_URL,
                fetched_from=None,
                provenance_note=(
                    "cat2_fetcher module not importable; live Cat 2 probe "
                    "disabled. Pass --bundled-cat2-csv to inject data. No "
                    "synthetic data injected."
                ),
                fetch_attempts=[],
                fetch_status="MODULE_MISSING",
            )
        result = try_fetch_chime_frb_catalog_2_csv(
            attempt_urls=attempt_urls,
            timeout_s=fetch_timeout_s,
            use_cache=True,
            force_status_for_tests=force_status_for_tests,
        )
        attempts = [a if isinstance(a, dict) else a.to_dict()
                    for a in result.attempts]
        if result.fetch_status in ("FETCHED", "CACHED") and result.rows_by_source:
            return PublishedCat2BurstSource(
                rows_by_source=result.rows_by_source,
                source_name="CHIME/FRB Catalog 2",
                source_type="chime_csv_fetch_cat2",
                reference_bibcode=result.reference_bibcode,
                reference_url=result.reference_url,
                fetched_from=result.fetched_from,
                provenance_note=result.provenance_note,
                fetch_attempts=attempts,
                fetch_status=result.fetch_status,
            )
        # Live fetch failed OR returned zero rows -> honest-empty with the
        # EXACT failure history. NEVER synthesize.
        return PublishedCat2BurstSource(
            rows_by_source={},
            source_name="CHIME/FRB Catalog 2",
            source_type="empty",
            reference_bibcode=result.reference_bibcode,
            reference_url=result.reference_url,
            fetched_from=None,
            provenance_note=(
                f"Live CHIME/FRB Catalog 2 fetch returned "
                f"{result.fetch_status}. No MJDs obtained from the network. "
                f"The Cat 2 data portal mirrors the Cat 1 offline/parking "
                f"state at probe time (2026-07-25). To populate today, pass "
                f"--bundled-cat2-csv with a CSV of `name,mjd` rows "
                f"transcribed from the published catalog. No synthetic data "
                f"injected."
            ),
            fetch_attempts=attempts,
            fetch_status=result.fetch_status,
        )

    # --- 3. honest-empty default ---------------------------------------
    return PublishedCat2BurstSource(
        rows_by_source={},
        source_name="(none)",
        source_type="empty",
        reference_bibcode=CAT2_BIBCODE,
        reference_url=CAT2_REFERENCE_URL,
        fetched_from=None,
        provenance_note=(
            "Real-data path disabled (use_cat2_fetcher=False). Use a live/"
            "cached Cat 2 fetch or pass --bundled-cat2-csv. No synthetic "
            "data injected."
        ),
        fetch_attempts=[],
        fetch_status="DISABLED",
    )


if __name__ == "__main__":
    src = load_published_cat2_bursts()
    print(json.dumps(src.to_dict(), indent=2))
