"""cat2_real_sources — CHIME/FRB Catalog 2 multi-source data layer.

Stance: structure != message. We NEVER fabricate burst arrival MJDs. The
Second CHIME/FRB Catalog was published 2026-03 (CHIME/FRB Collaboration
et al. 2026, ApJS 283, 34; AAS Open Access). 4,539 FRBs across 3,641
unique sources; 981 bursts from 83 known REPEATING sources.

NOTE: this module is currently a STUB. The full R1++ wiring (live fetch
integration, multi-source scramble-null, write_notes_markdown BLC1 block,
test suite) was deferred to a future turn when the user pivoted to G-BLC1.
What remains here is:

  - dataclass PublishedCat2BurstSource  (multi-source row group + provenance)
  - stub load_published_cat2_bursts() returning an honest-empty source

This is sufficient for `import cat2_real_sources` to succeed; downstream
orchestration that wants live Cat 2 data should use `--bundled-cat2-csv`
with `cat2_fetcher.load_bundled_cat2_csv()` directly (which is fully
implemented in `cat2_fetcher.py`).

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
    """STUB: honest-empty until the full R1++ wiring lands.

    For now this returns an honest-empty source with a clear "deferred"
    provenance_note. When the user pivots back to R1++, this function
    will be expanded to mirror `frb_real_sources.load_published_frb_180916_bursts`
    exactly: (1) bundled override, (2) live cat2_fetcher probe, (3) honest-empty.

    Until then, callers wanting live Cat 2 data should use the bundled
    override via `cat2_fetcher.load_bundled_cat2_csv(path)` directly.
    """
    return PublishedCat2BurstSource(
        rows_by_source={},
        source_name=str(Path(bundled_csv_path).name) if bundled_csv_path
        else "(deferred)",
        source_type="deferred",
        reference_bibcode=None if CAT2_BIBCODE is None else CAT2_BIBCODE,
        reference_url=None if CAT2_REFERENCE_URL is None else CAT2_REFERENCE_URL,
        fetched_from=None,
        provenance_note=(
            "cat2_real_sources.load_published_cat2_bursts is a STUB "
            "until the full R1++ wiring lands. The CHIME/FRB Cat 2 "
            "fetch module (`cat2_fetcher.py`) IS fully implemented "
            "and can be used via `cat2_fetcher.load_bundled_cat2_csv(path)` "
            "with `--bundled-cat2-csv`. No synthetic data injected."
        ),
        fetch_attempts=[],
        fetch_status="DEFERRED",
    )


if __name__ == "__main__":
    src = load_published_cat2_bursts()
    print(json.dumps(src.to_dict(), indent=2))
