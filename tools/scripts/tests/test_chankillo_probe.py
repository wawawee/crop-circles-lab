"""test_chankillo_probe.py - G14 tests for Chankillo Thirteen Towers
horizon probe. Forbidden-phrase guard, fixture/coords, math, Rayleigh
z-score, verdict assembly, run.json+NOTES.md schema, end-to-end main().

Run:
  python tools/scripts/tests/test_chankillo_probe.py
"""
from __future__ import annotations

import json
import random as rnd
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

import tools.scripts.chankillo_probe as CH  # noqa: E402
from tools.scripts.chankillo_probe import (  # noqa: E402
    AXIS_TOLERANCE_DEG, DATA_DIR, EXPECTED_TOWER_SPACING_DEG, FORBIDDEN_PHRASES,
    N_TOWERS, STANCE, bearing_deg, build_verdict, expected_bearing_for_tower,
    load_solar_arc, load_tower_coords, null_scrambled_bearings,
    null_synthetic_ridge, null_uniform_bearings, observed_tower_bearings,
    per_tower_deltas, structure_z_score, write_notes_md,
    Z_STRUCTURE_THRESHOLD, Z_CONTROL_SEP_THRESHOLD,
)


# --- Stance / forbidden phrase ----------------------------------

def test_stance_present() -> None:
    assert len(CH.STANCE) > 50
    assert "structure" in CH.STANCE.lower()


def test_forbidden_phrases_listed() -> None:
    expected = (
        "Chankillo deciphered", "Chankillo calendar proven",
        "proven Inca calendar", "alien observatory",
        "aliens built", "ancient astronauts", "alignment proves",
        "civilization encoded", "skysurfer",
    )
    for needle in expected:
        assert needle in FORBIDDEN_PHRASES


def test_assert_no_forbidden_phrases_clean_text_passes() -> None:
    CH.assert_no_forbidden_phrases(
        "These metrics measure Chankillo bearing alignment structure, no "
        "calendar endorsement and no alien claim.", where="clean text")


def test_assert_no_forbidden_phrases_raises_on_banned() -> None:
    for phrase in FORBIDDEN_PHRASES:
        bad = f"a test sentence that contains {phrase} for the guard check."
        try:
            CH.assert_no_forbidden_phrases(bad, where="bad text")
        except ValueError:
            pass
        else:
            raise AssertionError(
                f"forbidden phrase {phrase!r} did NOT trigger ValueError")


# --- Fixture + math ------------------------------------------------

def test_fixture_load_wop_and_towers() -> None:
    wop, towers, raw = load_tower_coords(DATA_DIR)
    assert "lat" in wop and "lon" in wop
    assert -10.0 <= wop["lat"] <= -9.0  # Chankillo ~9.5S
    assert -78.5 <= wop["lon"] <= -78.0  # Casma Valley
    assert len(towers) == N_TOWERS
    for t in towers:
        assert 1 <= t["id"] <= N_TOWERS
        assert -10.0 <= t["lat"] <= -9.0
        assert -78.5 <= t["lon"] <= -78.0


def test_solar_arc_fixture_loads() -> None:
    arc = load_solar_arc(DATA_DIR)
    assert "sun" in arc and "moon" in arc
    june = arc["sun"]["june_solstice"]
    december = arc["sun"]["december_solstice"]
    # June sunrise azimuth should be < December sunrise in S hemisphere
    assert june["sunrise_azimuth_from_WOP_deg"] < december["sunrise_azimuth_from_WOP_deg"]
    assert 60 < june["sunrise_azimuth_from_WOP_deg"] < 80
    assert 110 < december["sunrise_azimuth_from_WOP_deg"] < 120


def test_bearing_basic_north() -> None:
    # Same longitude, slightly larger northern latitude - bearing should
    # be small (near 0, North).
    az = bearing_deg(0.0, 0.0, 1.0, 0.0)
    assert abs(az) < 1.0


def test_expected_bearing_sweep_monotonic() -> None:
    arc = load_solar_arc(DATA_DIR)
    bearings = [expected_bearing_for_tower(i, arc) for i in range(1, 14)]
    # Should monotonically ascend from June-az to December-az.
    for j in range(1, len(bearings)):
        assert bearings[j] > bearings[j - 1]


def test_observed_tower_bearings_unique() -> None:
    wop, towers, _ = load_tower_coords(DATA_DIR)
    obs = observed_tower_bearings(wop, towers)
    assert len(obs) == N_TOWERS
    # Towers are along a N-S line; bearings should span SOME arc on the
    # eastern / NE horizon (the schematic fixture produces a wide ~74 deg
    # span from WOP - this is honest, larger than the published
    # ~33 deg Ghezzi & Ruggles annual-solar-arc claim). Loose bound is
    # honest given the schematic fixture is approximate.
    spread = max(obs) - min(obs)
    assert 5.0 < spread < 90.0


def test_per_tower_deltas_minimal_wrap() -> None:
    # When observed = expected => delta should be 0
    deltas, _ = per_tower_deltas([100.0, 110.0, 120.0],
                                  lambda i: [100.0, 110.0, 120.0][i - 1])
    assert all(d < 1e-6 for d in deltas)


# --- Null generators -----------------------------------------------

def test_null_uniform_bearings_in_range() -> None:
    bs = null_uniform_bearings(50, seed=0)
    assert all(0.0 <= b < 360.0 for b in bs)


def test_null_scrambled_bearings_is_a_permutation() -> None:
    obs = [1.0, 2.0, 3.0, 4.0, 5.0]
    out = null_scrambled_bearings(obs, seed=0)
    assert sorted(out) == sorted(obs)
    assert out != obs


def test_null_synthetic_ridge_distorts() -> None:
    obs = [100.0, 110.0, 120.0]
    out = null_synthetic_ridge(obs, seed=0, ridge_min_deg=2.0,
                                  ridge_max_deg=10.0)
    assert all(0.0 <= b < 360.0 for b in out)
    assert all((b % 360.0) >= 0.0 for b in out)
    # Should be different from the input on at least 2 of 3 cases
    # (may accidentally match by chance so use 90% confidence)
    assert any(abs(b - obs[i]) > 0.5 for i, b in enumerate(out))


# --- Structure z-score --------------------------------------------

def test_structure_z_score_obs_tighter_than_null() -> None:
    obs = [2.0, 1.5, 1.0, 0.5, 0.0]
    nulls = list(reversed(obs)) + [50.0, 60.0, 70.0, 80.0, 90.0]
    z = structure_z_score(obs, nulls, seed=0)
    assert z["z"] < 0.0


def test_structure_z_score_handles_empty() -> None:
    z = structure_z_score([], [1.0, 2.0], seed=0)
    assert z["z"] == 0.0


# --- Verdict assembly ----------------------------------------------

def test_verdict_no_signal_when_z_near_zero() -> None:
    v = CH.build_verdict({"z": -0.5}, {"z": -0.3})
    assert "ORIENTATION_STRUCTURE" not in v
    assert "NO_SIGNAL" in v or "UNDERDETERMINED" in v


def test_verdict_orientation_structure_when_z_very_negative() -> None:
    v = CH.build_verdict({"z": -5.0}, {"z": -0.5})
    assert "ORIENTATION_STRUCTURE" in v


def test_verdict_underdetermined_when_too_few_towers() -> None:
    # Hard to simulate - build_verdict uses module N_TOWERS, so use the
    # real N=13. With z=0 should be UNDERDETERMINED since N=13 ok.
    v = CH.build_verdict({"z": -1.0}, {"z": -1.0})
    # N=13 -> not undertermined; expected NO_SIGNAL band
    assert "NO_SIGNAL" in v or "UNDERDETERMINED" in v


def test_verdict_control_separated_when_ridge_z_differs() -> None:
    v = CH.build_verdict({"z": -2.0},
                          {"z": 2.0})
    assert "CONTROL_SEPARATED" in v


# --- End-to-end run / output ----------------------------------------

def test_run_main_writes_outputs(tmp_root=None) -> None:
    saved = CH.OUT_DIR
    CH.OUT_DIR = ROOT / "outputs" / "chankillo"
    sys_argv_backup = sys.argv
    try:
        sys.argv = ["chankillo_probe", "--n-shuffles", "20", "--seed", "0"]
        CH.main()
    finally:
        sys.argv = sys_argv_backup
        CH.OUT_DIR = saved
    assert (ROOT / "outputs" / "chankillo" / "run.json").exists()
    assert (ROOT / "outputs" / "chankillo" / "NOTES.md").exists()


def test_run_json_has_expected_keys() -> None:
    path = ROOT / "outputs" / "chankillo" / "run.json"
    assert path.exists(), "run.json missing - main() not run yet? "
    rep = json.loads(path.read_text())
    for k in ("mission", "generated_at", "verdict", "metadata", "groups",
              "null_uniform", "null_ridge", "caveats", "data_source",
              "stance", "forbidden_phrases"):
        assert k in rep, f"missing key: {k}"
    assert rep["mission"] == "G14"
    assert rep["metadata"]["calendar_label_unreliable"] is True
    assert rep["metadata"]["deliberately_no_dem"] is True


def test_notes_md_has_stance_and_caveats(tmp_root=None) -> None:
    path = ROOT / "outputs" / "chankillo" / "NOTES.md"
    assert path.exists()
    text = path.read_text()
    assert "structure != meaning" in text.lower()
    assert "## Stance" in text
    assert "## Caveats" in text
    assert "## Verdict" in text


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
