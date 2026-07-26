"""test_chankillo_probe.py — ≥12 tests for G14 Chankillo.

Run:
    python tools/astro/tests/test_chankillo_probe.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from tools.astro.chankillo_probe import (
    FORBIDDEN_PHRASES, N_TOWERS, OUT_DIR, SEED, STANCE, VERDICT_VOCAB,
    _angular_delta, _haversine_bearing, _rising_az_for_dec, _span_deg,
    _sunrise_azimuth, classify_verdict,
    compute_lunar_ranges, compute_solar_extremes,
    compute_tower_horizon_azimuths, run_scrambled_azimuth_null,
    run_synthetic_ridge_null,
)
# rename to avoid clash with test function names
from tools.astro.chankillo_probe import test_solar_coverage as solar_coverage_func

# =========================================================================
# 1. Stance / vocabulary
# =========================================================================


def test_stance_present() -> None:
    assert len(STANCE) > 30
    assert "structure != message" in STANCE.lower()
    assert "underdetermined" in STANCE.lower()


def test_verdict_vocab() -> None:
    for v in ("ORIENTATION_STRUCTURE", "NO_SIGNAL", "LUNAR_UNDERDETERMINED"):
        assert v in VERDICT_VOCAB


def test_forbidden_phrases_guard() -> None:
    expected = [
        "alien observatory",
        "extraterrestrial calendar",
        "ancient astronaut",
    ]
    for needle in expected:
        assert needle in FORBIDDEN_PHRASES, f"missing forbidden: {needle}"


def test_forbidden_not_in_output() -> None:
    path = OUT_DIR / "run.json"
    if not path.exists():
        return
    report = json.loads(path.read_text())
    text = json.dumps({k: v for k, v in report.items()
                       if k not in ("stance", "forbidden_words_check")}).lower()
    for fp in FORBIDDEN_PHRASES:
        assert fp.lower() not in text, f"output contains forbidden: {fp}"


def test_forbidden_not_in_notes() -> None:
    path = OUT_DIR / "NOTES.md"
    if not path.exists():
        return
    text = path.read_text()
    sections = text.split("## ")
    relevant = [s for s in sections if not s.startswith("Stance")]
    combined = " ".join(relevant).lower()
    for fp in FORBIDDEN_PHRASES:
        assert fp.lower() not in combined, f"NOTES.md contains forbidden: {fp}"


# =========================================================================
# 2. Angular helpers
# =========================================================================


def test_haversine_bearing_north() -> None:
    b = _haversine_bearing(0, 0, 10, 0)
    assert abs(b - 0) < 1 or abs(b - 360) < 1


def test_haversine_bearing_east() -> None:
    b = _haversine_bearing(0, 0, 0, 10)
    assert abs(b - 90) < 1


def test_haversine_bearing_south() -> None:
    b = _haversine_bearing(0, 0, -10, 0)
    assert abs(b - 180) < 1


def test_angular_delta_identical() -> None:
    assert _angular_delta(121.17, 121.17) == 0.0


def test_angular_delta_opposite() -> None:
    assert _angular_delta(0.0, 180.0) == 180.0


def test_angular_delta_wrap() -> None:
    assert _angular_delta(355.0, 5.0) == 10.0


def test_span_deg_simple() -> None:
    assert _span_deg([10, 20, 30]) == 20.0


def test_span_deg_single() -> None:
    assert _span_deg([42]) == 0.0


# =========================================================================
# 3. Tower azimuth computation
# =========================================================================


def test_tower_count() -> None:
    assert N_TOWERS == 13


def test_tower_azimuths_ordered() -> None:
    taz = compute_tower_horizon_azimuths()
    azs = taz["azimuths_deg"]
    assert len(azs) == 13
    for i in range(len(azs) - 1):
        assert azs[i] <= azs[i + 1], "azimuths must be sorted ascending"


def test_tower_azimuths_span() -> None:
    taz = compute_tower_horizon_azimuths()
    span = taz["span_deg"]
    assert 80 <= span <= 100, f"expected ~90° span, got {span}°"


def test_tower_azimuths_observation_point() -> None:
    taz = compute_tower_horizon_azimuths()
    assert taz["observation_point"]["lat"] == -9.559


# =========================================================================
# 4. Solar extremes
# =========================================================================


def test_solar_extremes_structure() -> None:
    solar = compute_solar_extremes()
    assert "epoch_year" in solar
    assert "jun_solstice_sunrise" in solar
    assert "dec_solstice_sunrise" in solar


def test_solar_extremes_values() -> None:
    solar = compute_solar_extremes()
    jun = solar["jun_solstice_sunrise"]
    dec = solar["dec_solstice_sunrise"]

    if jun.get("az_deg") is not None:
        assert 40 <= jun["az_deg"] <= 80, f"Jun az {jun['az_deg']}° outside expected range"

    if dec.get("az_deg") is not None:
        assert 100 <= dec["az_deg"] <= 140, f"Dec az {dec['az_deg']}° outside expected range"


def test_solar_span_reasonable() -> None:
    solar = compute_solar_extremes()
    span = solar.get("solar_span_deg")
    if span is not None:
        assert 40 <= span <= 60, f"solar span {span}° outside 40-60° range"


# =========================================================================
# 5. Solar coverage (known answer)
# =========================================================================


def test_solar_bracketed() -> None:
    taz = compute_tower_horizon_azimuths()
    solar = compute_solar_extremes()
    cov = solar_coverage_func(taz, solar)

    if cov.get("june_az_deg") is not None and cov.get("dec_az_deg") is not None:
        assert cov["both_bracketed"] is True, (
            "Both solstices should be within tower azimuth range"
        )


def test_solar_margin_nonnegative() -> None:
    taz = compute_tower_horizon_azimuths()
    solar = compute_solar_extremes()
    cov = solar_coverage_func(taz, solar)

    if cov.get("margin_north_deg") is not None:
        assert cov["margin_north_deg"] >= 0
    if cov.get("margin_south_deg") is not None:
        assert cov["margin_south_deg"] >= 0


# =========================================================================
# 6. Lunar ranges
# =========================================================================


def test_lunar_ranges_structure() -> None:
    lunar = compute_lunar_ranges()
    assert "major_standstill" in lunar
    assert "minor_standstill" in lunar
    assert lunar["verdict"] == "LUNAR_UNDERDETERMINED"
    assert len(lunar["caveat"]) > 20


def test_lunar_major_standstill_dec() -> None:
    lunar = compute_lunar_ranges()
    ms = lunar["major_standstill"]
    assert 28 <= ms["dec_deg"] <= 30, f"major standstill dec {ms['dec_deg']}°"


def test_lunar_minor_standstill_dec() -> None:
    lunar = compute_lunar_ranges()
    ms = lunar["minor_standstill"]
    assert 17 <= ms["dec_deg"] <= 20, f"minor standstill dec {ms['dec_deg']}°"


def test_lunar_range_inside_tower_span() -> None:
    taz = compute_tower_horizon_azimuths()
    lunar = compute_lunar_ranges()
    ms = lunar["major_standstill"]
    mr = ms.get("range_deg")
    if mr is not None:
        assert mr <= taz["span_deg"], (
            f"Lunar range {mr}° > tower span {taz['span_deg']}°"
        )


# =========================================================================
# 7. Rising azimuth helper
# =========================================================================


def test_rising_az_eq_at_equator() -> None:
    az = _rising_az_for_dec(0, 0)
    assert az is not None
    assert abs(az - 90) < 1


def test_rising_az_south_of_east() -> None:
    az = _rising_az_for_dec(-10, -23)
    assert az is not None
    assert az > 90


def test_rising_az_north_of_east() -> None:
    az = _rising_az_for_dec(-10, 23)
    assert az is not None
    assert az < 90


def test_rising_az_circumpolar() -> None:
    az = _rising_az_for_dec(-10, 85)
    assert az is None


# =========================================================================
# 8. Negative controls
# =========================================================================


def test_synthetic_ridge_null_structure() -> None:
    taz = compute_tower_horizon_azimuths()
    solar = compute_solar_extremes()
    cov = solar_coverage_func(taz, solar)

    null = run_synthetic_ridge_null(cov, n_trials=100, seed=SEED)
    assert null["n_trials"] == 100
    assert 0 <= null["bracketed_fraction"] <= 1
    assert null["mean_trial_span_deg"] > 0


def test_scrambled_azimuth_null_structure() -> None:
    taz = compute_tower_horizon_azimuths()
    solar = compute_solar_extremes()
    cov = solar_coverage_func(taz, solar)

    null = run_scrambled_azimuth_null(taz, cov, n_trials=100, seed=SEED)
    assert null["n_trials"] == 100
    assert null["null_mean_hits"] >= 0


# =========================================================================
# 9. Verdict classification
# =========================================================================


def test_classify_orientation_structure() -> None:
    cov = {"both_bracketed": True, "june_az_deg": 66, "dec_az_deg": 114}
    lunar = {"verdict": "LUNAR_UNDERDETERMINED"}
    ridge_null = {"bracketed_fraction": 0.5}
    parts = classify_verdict(cov, lunar, ridge_null)
    assert "ORIENTATION_STRUCTURE" in parts
    assert "LUNAR_UNDERDETERMINED" in parts


def test_classify_no_signal() -> None:
    cov = {"both_bracketed": False, "june_az_deg": 0, "dec_az_deg": 0}
    lunar = {"verdict": "LUNAR_UNDERDETERMINED"}
    ridge_null = {"bracketed_fraction": 0.5}
    parts = classify_verdict(cov, lunar, ridge_null)
    assert "NO_SIGNAL" in parts


def test_classify_control_separated() -> None:
    cov = {"both_bracketed": True, "june_az_deg": 66, "dec_az_deg": 114}
    lunar = {"verdict": "LUNAR_UNDERDETERMINED"}
    ridge_null = {"bracketed_fraction": 0.01}
    parts = classify_verdict(cov, lunar, ridge_null)
    assert "CONTROL_SEPARATED" in parts


# =========================================================================
# 10. Integration
# =========================================================================


def test_analyze_chankillo_structure() -> None:
    from tools.astro.chankillo_probe import analyze_chankillo
    report = analyze_chankillo()
    assert report["mission"] == "G14"
    assert report["site"]["n_towers"] == 13
    assert "ORIENTATION_STRUCTURE" in report["verdict"]
    assert report["forbidden_words_check"]["all_absent"] is True
    assert "tower_horizon_azimuths" in report
    assert "solar_extremes" in report
    assert "lunar_standstills" in report
    assert "negative_controls" in report
    assert "synthetic_ridge_null" in report["negative_controls"]
    assert "scrambled_azimuth_null" in report["negative_controls"]


# =========================================================================
# 11. Output files
# =========================================================================


def test_outputs_run_json_exists() -> None:
    path = OUT_DIR / "run.json"
    assert path.exists(), "outputs/chankillo/run.json missing — run probe first"


def test_outputs_run_json_verdict_valid() -> None:
    path = OUT_DIR / "run.json"
    assert path.exists()
    report = json.loads(path.read_text())
    assert "ORIENTATION_STRUCTURE" in report["verdict"]
    assert report["forbidden_words_check"]["all_absent"] is True


def test_outputs_notes_md_contains_verdict() -> None:
    path = OUT_DIR / "NOTES.md"
    assert path.exists()
    text = path.read_text()
    assert "ORIENTATION_STRUCTURE" in text
    assert "LUNAR_UNDERDETERMINED" in text
    assert "Chankillo" in text


# =========================================================================
# 12. Known-answer test: injected alignment
# =========================================================================


def test_known_answer_alignment() -> None:
    """If towers are placed to exactly bracket the solar range, coverage exists."""
    tower_az = {
        "min_az_deg": 60,
        "max_az_deg": 120,
        "span_deg": 60,
        "azimuths_deg": list(range(60, 121, 5)),
    }
    solar = {"jun_solstice_sunrise": {"az_deg": 65},
             "dec_solstice_sunrise": {"az_deg": 115},
             "solar_span_deg": 50}
    cov = solar_coverage_func(tower_az, solar)
    assert cov["both_bracketed"] is True


# =========================================================================
# runner
# =========================================================================

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
