"""frb_real_sources — published FRB burst sources data layer.

Stance: structure != message. We NEVER fabricate burst arrival MJDs. If a
caller wants real data, they must EITHER:
  (a) let `chime_frb_fetcher` contact the canonical CHIME/FRB Catalog 1
      mirror (which is currently offline — see chime_frb_fetcher for the
      probe history), OR
  (b) pass a user-provided JSON file with a flat `[mjd, mjd, ...]` list
      via `--bundled-mjd-json path/to/file.json`. This is the ONLY honest
      way to inject real data until the canonical mirror comes back.

This module exposes a single function `load_published_frb_180916_bursts`
which (a) returns the live fetcher data if available, (b) returns user-
provided data if --bundled-mjd-json was supplied, and (c) returns an
honest-empty `PublishedBurstSource` with `burst_mjds == []` and a clear
provenance string otherwise.

The companion `PASTOR_MARAZUELA_2021_FRB_180916_MJDS` constant is
**intentionally empty** at this revision because the underlying paper's
MJD table cannot be programmatically extracted (PDF tables are image-only).
A future maintainer with the published table should populate it from a
manual transcription under `data/radio/published_tables/` -- but the lab's
"never fabricate" rule means we deliberately leave it empty rather than
papering over the gap with hand-copied values from memory.

Public API:

  load_published_frb_180916_bursts(
      bundled_json_path: Path | None = None,
      fetch_timeout_s: float = 10.0,
      attempt_urls=None,
      use_chime_fetcher: bool = True,
      force_status_for_tests: str | None = None,
  ) -> PublishedBurstSource

  PublishedBurstSource  -- dataclass
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

# IMPORTANT: do NOT use relative imports here. The test runner loads
# `chime_frb_fetcher` and `frb_real_sources` as flat modules via
# `sys.path.insert(0, str(TOOLS_RADIO))`. A relative import
# (`from .chime_frb_fetcher import ...`) would raise:
#   `ImportError: attempted relative import with no known parent package`.
# We import via top-level name; the package boundary is enforced by
# `tools/radio/__init__.py` separately.
try:
    from chime_frb_fetcher import (  # type: ignore
        try_fetch_chime_frb_catalog_1_csv,
        ChimeFrbFetchResult,
    )
except ImportError:  # pragma: no cover
    try_fetch_chime_frb_catalog_1_csv = None
    ChimeFrbFetchResult = None


# Intentional-empty. To populate:
#   1. Extract the MJD burst table from Pastor-Marazuela 2021
#      (ApJ 923 L6 / arXiv:2001.08645) by manual transcription
#      (PDF tables are image-only -- pdftotext cannot extract them).
#   2. Save as JSON: data/radio/published_tables/pastor_marazuela_2021_frb_180916_mjds.json,
#      either as a flat list of floats (preferred) or as a list of
#      {"name", "mjd"} objects.
#   3. Refactor this module to load it via load_published_table() helper.
PASTOR_MARAZUELA_2021_FRB_180916_MJDS: tuple[float, ...] = ()
PASTOR_MARAZUELA_2021_BIBCODE: str = "2021ApJ...923L...6P"
PASTOR_MARAZUELA_2021_REFERENCE_URL: str = "https://arxiv.org/abs/2001.08645"


@dataclass
class PublishedBurstSource:
    """A single source of truth for FRB 180916 burst MJDs.

    Burst MJDs are sorted ascending and finite. Provenance is ALWAYS set
    to a non-empty string so downstream consumers can NEVER mistake
    "no data yet" for "data exists".
    """
    burst_mjds: list[float] = field(default_factory=list)
    source_name: str = "unknown"
    source_type: str = "empty"          # chime_csv_fetch | user_provided
                                       # | bundled_attempt | empty
    reference_bibcode: Optional[str] = None
    reference_url: Optional[str] = None
    fetched_from: Optional[str] = None
    provenance_note: str = ""
    fetch_attempts: list[dict] = field(default_factory=list)
    fetch_status: str = "empty"

    @property
    def has_mjds(self) -> bool:
        return len(self.burst_mjds) > 0

    def to_dict(self) -> dict:
        return asdict(self)


def _load_user_json(path: Path) -> list[float]:
    """Load MJDs from a user-provided JSON file.

    Accepted shapes (schemas are documented here; raise on mismatch so we
    never silently drop or coerce data):
      (1) flat list of floats: [58700.1, 58716.5, ...]
      (2) list of {"name", "mjd"} dicts: [{"name":"FRB 180916","mjd":...}]
    """
    text = path.read_text()
    data = json.loads(text)
    if isinstance(data, list):
        # All-float OR all-dict.
        if all(isinstance(x, (int, float)) for x in data):
            return [float(x) for x in data]
        if all(isinstance(x, dict) and "mjd" in x for x in data):
            return [float(x["mjd"]) for x in data]
        raise ValueError(
            f"{path}: list must be all-float OR all-dict-with-mjd-key; "
            f"got mixed types"
        )
    raise ValueError(
        f"{path}: top-level JSON must be a list, got {type(data).__name__}"
    )


def load_published_frb_180916_bursts(
    bundled_json_path: Optional[Path] = None,
    fetch_timeout_s: float = 10.0,
    attempt_urls=None,
    use_chime_fetcher: bool = True,
    force_status_for_tests: Optional[str] = None,
) -> PublishedBurstSource:
    """Resolve FRB 180916 burst MJDs from the most-authoritative source available.

    Resolution order:
      1. `bundled_json_path` exists and parses -> user_provided source
      2. `use_chime_fetcher=True` and (live net) -> chime_csv_fetch source
      3. otherwise -> empty source with honest "no data yet" provenance
    """
    # --- 1. user-provided override path --------------------------------
    if bundled_json_path is not None and Path(bundled_json_path).exists():
        try:
            mjds = sorted(_load_user_json(Path(bundled_json_path)))
            return PublishedBurstSource(
                burst_mjds=mjds,
                source_name=str(Path(bundled_json_path).name),
                source_type="user_provided",
                reference_bibcode="USER_PROVIDED",
                reference_url=f"file://{Path(bundled_json_path).resolve()}",
                fetched_from=str(Path(bundled_json_path)),
                provenance_note=(
                    f"Burst MJDs supplied via --bundled-mjd-json "
                    f"{bundled_json_path}. The caller is responsible for "
                    f"verifying the source paper / table provenance. We do "
                    f"NOT validate the values independently."
                ),
                fetch_attempts=[],
                fetch_status="USER_OVERRIDE",
            )
        except Exception as e:
            # Surface the override-load failure as an empty source so the
            # caller knows we couldn't honor it -- NEVER silently ignore.
            return PublishedBurstSource(
                burst_mjds=[],
                source_name=str(Path(bundled_json_path).name),
                source_type="empty",
                reference_bibcode=None,
                reference_url=None,
                fetched_from=None,
                provenance_note=(
                    f"User-provided --bundled-mjd-json {bundled_json_path} "
                    f"failed to parse: {e}. Falling back to empty source."
                ),
                fetch_attempts=[],
                fetch_status="USER_OVERRIDE_INVALID",
            )

    # --- 2. chime_frb_fetcher live probe -------------------------------
    if use_chime_fetcher:
        result: ChimeFrbFetchResult = try_fetch_chime_frb_catalog_1_csv(
            attempt_urls=attempt_urls,
            timeout_s=fetch_timeout_s,
            use_cache=True,
            force_status_for_tests=force_status_for_tests,
        )
        if result.fetch_status == "FETCHED" or result.fetch_status == "CACHED":
            return PublishedBurstSource(
                burst_mjds=result.mjds,
                source_name="CHIME/FRB Catalog 1",
                source_type="chime_csv_fetch",
                reference_bibcode=result.reference_bibcode,
                reference_url=result.reference_url,
                fetched_from=result.fetched_from,
                provenance_note=result.provenance_note,
                fetch_attempts=[a.to_dict() for a in result.attempts],
                fetch_status=result.fetch_status,
            )
        # Live fetch failed -- return empty with EXACTLY the failure history.
        return PublishedBurstSource(
            burst_mjds=[],
            source_name="CHIME/FRB Catalog 1",
            source_type="empty",
            reference_bibcode=result.reference_bibcode,
            reference_url=result.reference_url,
            fetched_from=None,
            provenance_note=(
                f"Live CHIME/FRB Catalog 1 fetch returned "
                f"{result.fetch_status}. No MJDs obtained from the network. "
                f"The bundled Pastor-Marazuela 2021 table is intentionally "
                f"empty (extraction pending). To populate today, pass "
                f"--bundled-mjd-json <file> with a flat JSON list of MJDs. "
                f"See `data/radio/README.md` for the honest-empty rationale."
            ),
            fetch_attempts=[a.to_dict() for a in result.attempts],
            fetch_status=result.fetch_status,
        )

    # --- 3. honest-empty default ---------------------------------------
    return PublishedBurstSource(
        burst_mjds=[],
        source_name="(none)",
        source_type="empty",
        reference_bibcode=None,
        reference_url=None,
        fetched_from=None,
        provenance_note=(
            "Real-data path disabled. Use a live CHIME fetch or pass a "
            "--bundled-mjd-json override. Bundled Pastor-Marazuela 2021 "
            "table deliberately empty (no programmatic extraction path)."
        ),
        fetch_attempts=[],
        fetch_status="DISABLED",
    )


if __name__ == "__main__":
    src = load_published_frb_180916_bursts()
    print(json.dumps(src.to_dict(), indent=2))
