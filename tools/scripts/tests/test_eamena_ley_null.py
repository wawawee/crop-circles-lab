"""
test_eamena_ley_null.py — G18 tests for EAMENA ley-line null hypothesis probe.

Geometry/analysis functions now live in tools/ccat/spatial_pattern.py (reusable
module); probe-specific tests (stance, forbidden phrases, verdict, loaders, I/O)
stay here.

Run:
  python tools/scripts/tests/test_eamena_ley_null.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

import tools.scripts.eamena_ley_null as EL  # noqa: E402
from tools.scripts.eamena_ley_null import (  # noqa: E402
    DATA_DIR, FORBIDDEN_PHRASES, OUT_DIR, STANCE,
    load_data, load_geojson, build_verdict, write_notes_md,
)
from tools.ccat import spatial_pattern as SP  # noqa: E402


# ---------------------------------------------------------------------------
# Stance / forbidden phrases
# ---------------------------------------------------------------------------

def test_stance_present() -> None:
    assert len(STANCE) > 50
    assert "structure" in STANCE.lower()


def test_forbidden_phrases_listed() -> None:
    expected = (
        "ancient highways",
        "ET corridors",
        "proves ley network",
        "sacred geometry network",
        "ancient aliens",
    )
    for needle in expected:
        assert needle in FORBIDDEN_PHRASES


def test_assert_no_forbidden_phrases_clean_text_passes() -> None:
    EL.assert_no_forbidden_phrases(
        "EAMENA ley-line null FPR calibration: no structure detected. "
        "This is a spatial statistics exercise, not a fringe claim.",
        where="clean text",
    )


def test_assert_no_forbidden_phrases_raises_on_banned() -> None:
    for phrase in FORBIDDEN_PHRASES:
        bad = f"the output text mentions {phrase} and must be caught."
        try:
            EL.assert_no_forbidden_phrases(bad, where="bad text")
        except ValueError:
            pass
        else:
            raise AssertionError(
                f"forbidden phrase {phrase!r} did NOT trigger ValueError"
            )


# ---------------------------------------------------------------------------
# Data loading (mission-specific)
# ---------------------------------------------------------------------------

def test_load_synthetic_csr_produces_correct_n() -> None:
    coords, meta = load_data(geojson_path=None, n_synthetic=500, seed_csr=0)
    assert len(coords) == 500
    assert meta["distribution"] == "csr"
    assert meta["n_sites"] == 500


def test_generate_synthetic_csr_in_bounds() -> None:
    coords, meta = SP.generate_synthetic_csr(n=100, seed=42)
    assert len(coords) == 100
    bbox = meta["bbox"]
    for lat, lon in coords:
        assert bbox[1] <= lat <= bbox[3], f"lat {lat} out of bounds"
        assert bbox[0] <= lon <= bbox[2], f"lon {lon} out of bounds"


def test_load_geojson_synthetic_file() -> None:
    path = ROOT / "data" / "geo" / "eamena" / "synthetic_csr_sites.json"
    coords, meta = load_geojson(str(path))
    assert len(coords) == 500
    assert meta["n_sites"] == 500
    assert meta["distribution"] == "csr"


def test_load_geojson_raises_on_bad_format() -> None:
    path = ROOT / "data" / "geo" / "eamena" / "README.md"
    try:
        load_geojson(str(path))
    except (ValueError, json.JSONDecodeError, FileNotFoundError):
        pass
    else:
        raise AssertionError("Should have raised on non-GeoJSON file")


# ---------------------------------------------------------------------------
# Geometry helpers (delegated to spatial_pattern — smoke tests)
# ---------------------------------------------------------------------------

def test_haversine_known_distance() -> None:
    d = SP.haversine_km(0.0, 0.0, 1.0, 0.0)
    assert 110.0 < d < 112.0


def test_haversine_zero_distance() -> None:
    d = SP.haversine_km(30.0, 35.0, 30.0, 35.0)
    assert d < 0.001


def test_perpendicular_distance_collinear() -> None:
    d = SP.perpendicular_distance_km(0.0, 0.0, 1.0, 0.0, -1.0, 0.0)
    assert d < 0.1


def test_perpendicular_distance_non_collinear() -> None:
    d = SP.perpendicular_distance_km(0.0, 1.0, 0.0, 0.0, 0.0, 0.0)
    assert d > 100.0


# ---------------------------------------------------------------------------
# Spatial analysis (delegated — smoke via spatial_pattern)
# ---------------------------------------------------------------------------

def test_mean_nn_synthetic_csr_reasonable() -> None:
    coords, _ = SP.generate_synthetic_csr(n=100, seed=0)
    m = SP.mean_nn_km(coords)
    assert 1 < m < 100


def test_clark_evans_csr_z_near_zero() -> None:
    coords, _ = SP.generate_synthetic_csr(n=100, seed=1)
    ce = SP.clark_evans_analysis(coords, n_sims=49, seed=0)
    assert abs(ce["z_vs_csr"]) < 3.0


def test_count_collinear_triples_handles_n_lt_3() -> None:
    coords = [(30.0, 35.0), (31.0, 36.0)]
    result = SP.count_collinear_triples(coords, n_triple_samples=5, seed=0)
    assert result["pairs_evaluated"] == 0


def test_ley_fpr_analysis_underdetermined_n_lt_3() -> None:
    coords = [(30.0, 35.0), (31.0, 36.0)]
    fpr = SP.ley_line_fpr_analysis(coords, n_sims=10, n_triple_samples=10, seed=0)
    assert fpr["verdict"] == "UNDERDETERMINED"


# ---------------------------------------------------------------------------
# Verdict assembly
# ---------------------------------------------------------------------------

def test_verdict_no_signal_on_csr_data() -> None:
    import random as rnd
    coords, _ = SP.generate_synthetic_csr(n=100, seed=0)
    ce = SP.clark_evans_analysis(coords, n_sims=29, seed=0)
    fpr = SP.ley_line_fpr_analysis(coords, n_sims=29, n_triple_samples=200, seed=0)
    v = build_verdict(ce, fpr, len(coords))
    assert "NO_LEY_SIGNAL" in v


def test_verdict_underdetermined_on_small_n() -> None:
    ce = {}
    fpr = {}
    v = build_verdict(ce, fpr, n=10)
    assert "UNDERDETERMINED" in v


# ---------------------------------------------------------------------------
# End-to-end main / outputs
# ---------------------------------------------------------------------------

def test_run_main_writes_outputs() -> None:
    saved_out = EL.OUT_DIR
    EL.OUT_DIR = OUT_DIR
    sys_argv_backup = sys.argv
    try:
        sys.argv = [
            "eamena_ley_null",
            "--n-synthetic", "100",
            "--n-sims", "29",
            "--n-triples", "200",
            "--seed", "0",
        ]
        EL.main()
    finally:
        sys.argv = sys_argv_backup
        EL.OUT_DIR = saved_out
    assert (OUT_DIR / "run.json").exists()
    assert (OUT_DIR / "NOTES.md").exists()


def test_run_json_has_expected_keys() -> None:
    path = OUT_DIR / "run.json"
    assert path.exists(), "run.json missing — main() not run yet?"
    rep = json.loads(path.read_text())
    for k in ("mission", "generated_at", "verdict", "metadata",
              "clark_evans", "ley_fpr", "caveats", "data_source",
              "stance", "forbidden_phrases", "pipeline"):
        assert k in rep, f"missing key: {k}"
    assert rep["mission"] == "G18"
    assert "NO_LEY_SIGNAL" in rep["verdict"]


def test_notes_md_has_stance_and_caveats() -> None:
    path = OUT_DIR / "NOTES.md"
    assert path.exists()
    text = path.read_text()
    assert "structure != meaning" in text.lower()
    assert "## Stance" in text
    assert "## Caveats" in text
    assert "## Verdict" in text
    assert "NO_LEY_SIGNAL" in text or "UNDERDETERMINED" in text


# ---------------------------------------------------------------------------
# spatial_pattern dependency check
# ---------------------------------------------------------------------------

def test_probe_uses_spatial_pattern() -> None:
    """Verify the probe delegates to the reusable module."""
    assert hasattr(EL, "SP"), "EL.SP not found — probe may not import spatial_pattern"
    assert hasattr(SP, "clark_evans_analysis")
    assert hasattr(SP, "ley_line_fpr_analysis")
    assert hasattr(SP, "generate_synthetic_csr")


if __name__ == "__main__":
    fns = [(k, v) for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    ok = bad = 0
    for name, fn in fns:
        try:
            fn()
            print(f"PASS {name}")
            ok += 1
        except AssertionError as e:
            print(f"FAIL {name}: {e}")
            bad += 1
        except Exception as e:
            print(f"ERROR {name}: {type(e).__name__}: {e}")
            bad += 1
    print(f"\n{ok}/{len(fns)} passed, {bad} failed")
    sys.exit(0 if bad == 0 else 1)
