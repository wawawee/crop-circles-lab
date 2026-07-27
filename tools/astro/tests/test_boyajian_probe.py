"""test_boyajian_probe.py — >=12 tests for G20 Boyajian's Star.

Run:
    python tools/astro/tests/test_boyajian_probe.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

from tools.astro.boyajian_probe import (
    FIXTURE, FORBIDDEN_PHRASES, OUT_DIR, PLANTED_PERIOD_DAYS, SEED, STANCE,
    TARGET, VERDICT_VOCAB,
    _generate_period_grid, _random_phase_offset, _uniform_random_times, _z_score,
    analyze_boyajian, build_interpretation, classify_verdict,
    load_fixture, run_known_answer, run_quiet_star_null,
    run_random_phase_null, write_notes,
)

# =========================================================================
# 1. Stance / vocabulary
# =========================================================================


def test_stance_present() -> None:
    assert len(STANCE) > 30
    assert "structure != message" in STANCE.lower()


def test_verdict_vocab() -> None:
    for v in ("DIP_STRUCTURE", "NO_SIGNAL", "UNDERDETERMINED"):
        assert v in VERDICT_VOCAB


def test_forbidden_phrases_defined() -> None:
    expected = ["Dyson", "alien", "megastructure", "confirms ET"]
    for needle in expected:
        assert any(needle.lower() in fp.lower() for fp in FORBIDDEN_PHRASES), \
            f"missing forbidden: {needle}"


def test_forbidden_not_in_run_json_data() -> None:
    """Check that non-stance fields do not contain forbidden phrases.

    The stance field explicitly denounces forbidden claims; exclude it
    and the interpretation (which embeds stance) from the scan.
    """
    path = OUT_DIR / "run.json"
    if not path.exists():
        return
    report = json.loads(path.read_text())
    exclude_keys = {"stance", "interpretation", "forbidden_words_check"}
    text = json.dumps(
        {k: v for k, v in report.items() if k not in exclude_keys}
    ).lower()
    for fp in FORBIDDEN_PHRASES:
        assert fp.lower() not in text, f"run.json data contains forbidden: {fp}"


def test_forbidden_not_in_notes_body() -> None:
    """Check NOTES.md body (excluding Stance section) for forbidden phrases."""
    path = OUT_DIR / "NOTES.md"
    if not path.exists():
        return
    text = path.read_text()
    sections = text.split("## ")
    relevant = [s for s in sections
                if not s.startswith("Stance") and not s.startswith("Verdict")]
    combined = " ".join(relevant).lower()
    for fp in FORBIDDEN_PHRASES:
        assert fp.lower() not in combined, f"NOTES.md body contains forbidden: {fp}"


# =========================================================================
# 2. Target / constants
# =========================================================================


def test_target_correct() -> None:
    assert "TIC 272172248" in TARGET
    assert "KIC 8462852" in TARGET
    assert "Boyajian" in TARGET


def test_planted_period() -> None:
    assert PLANTED_PERIOD_DAYS == 24.5


# =========================================================================
# 3. Helper functions
# =========================================================================


def test_generate_period_grid() -> None:
    grid = _generate_period_grid(24.5, margin_d=5.0, steps=101)
    assert len(grid) == 101
    assert abs(grid[0] - 19.5) < 1e-6
    assert abs(grid[-1] - 29.5) < 1e-6


def test_generate_period_grid_symmetric() -> None:
    grid = _generate_period_grid(10.0, margin_d=2.0, steps=5)
    assert grid[0] == 8.0
    assert grid[2] == 10.0
    assert grid[4] == 12.0


def test_uniform_random_times_range() -> None:
    times = _uniform_random_times(100, (0.0, 100.0), seed=42)
    assert len(times) == 100
    assert times[0] >= 0.0
    assert times[-1] <= 100.0
    assert all(times[i] <= times[i + 1] for i in range(len(times) - 1))


def test_random_phase_offset_preserves_count() -> None:
    times = _uniform_random_times(30, (800.0, 1600.0), seed=42)
    shifted = _random_phase_offset(times, 24.5, seed=99)
    assert len(shifted) == len(times)


def test_random_phase_offset_destroys_periodicity() -> None:
    times = _uniform_random_times(30, (800.0, 1600.0), seed=42)
    shifted = _random_phase_offset(times, 24.5, seed=99)
    assert not np.array_equal(times, shifted)


def test_random_phase_offset_sorted() -> None:
    times = _uniform_random_times(30, (800.0, 1600.0), seed=42)
    shifted = _random_phase_offset(times, 24.5, seed=99)
    assert all(shifted[i] <= shifted[i + 1] for i in range(len(shifted) - 1))


# =========================================================================
# 4. Z-score helper
# =========================================================================


def test_z_score_perfect_match_std_zero() -> None:
    """When all null values are identical, std=0 and we get z=0, pct=50."""
    result = _z_score(5.0, [5.0, 5.0, 5.0])
    assert result["z"] == 0.0
    assert result["percentile"] == 50.0


def test_z_score_outlier() -> None:
    """Value far above null -> large positive z, 0th percentile."""
    result = _z_score(10.0, [1.0, 2.0, 1.5, 2.5])
    assert result["z"] > 5.0
    assert result["percentile"] == 0.0


def test_z_score_single_null() -> None:
    result = _z_score(0.0, [0.0])
    assert result["z"] == 0.0


# =========================================================================
# 5. Fixture loading
# =========================================================================


def test_fixture_loads() -> None:
    fixture = load_fixture()
    assert "error" not in fixture, f"Fixture load failed: {fixture.get('error')}"
    assert "metadata" in fixture
    assert "dip_times_bjd" in fixture
    assert len(fixture["dip_times_bjd"]) == 30


def test_fixture_planted_period() -> None:
    fixture = load_fixture()
    assert fixture["metadata"]["planted_period_days"] == 24.5


def test_fixture_has_quiet_star_control() -> None:
    fixture = load_fixture()
    assert "controls" in fixture
    assert "quiet_star" in fixture["controls"]


# =========================================================================
# 6. Known-answer path
# =========================================================================


def test_known_answer_recovery_pass() -> None:
    fixture = load_fixture()
    dip_times = fixture["dip_times_bjd"]
    ka = run_known_answer(dip_times)
    assert ka["recovery_pass"] is True, \
        f"Known-answer recovery failed: error={ka['recovery_error_days']} d"


def test_known_answer_z2_high() -> None:
    fixture = load_fixture()
    dip_times = fixture["dip_times_bjd"]
    ka = run_known_answer(dip_times)
    n = len(dip_times)
    expected_max = 2.0 * n
    assert ka["recovered_z2"] > expected_max * 0.8, \
        f"Z2={ka['recovered_z2']} too low, expected ~{expected_max}"


def test_known_answer_recovered_period_close() -> None:
    fixture = load_fixture()
    dip_times = fixture["dip_times_bjd"]
    ka = run_known_answer(dip_times)
    err = ka["recovery_error_days"]
    assert err < 0.5, f"Recovery error {err} d exceeds tolerance"


# =========================================================================
# 7. Negative controls
# =========================================================================


def test_quiet_star_null_z2_low() -> None:
    null = run_quiet_star_null(30, (750.0, 1600.0), n_trials=50, seed=42)
    assert null["null_best_z2_mean"] < 15.0, \
        f"Quiet-star null Z2 mean {null['null_best_z2_mean']} too high"


def test_quiet_star_null_max_below_planted() -> None:
    null = run_quiet_star_null(30, (750.0, 1600.0), n_trials=50, seed=42)
    assert null["null_best_z2_max"] < 59.0, \
        f"Quiet-star null max Z2 {null['null_best_z2_max']} at or above planted Z2"


def test_random_phase_null_z2_low() -> None:
    fixture = load_fixture()
    dip_times = fixture["dip_times_bjd"]
    null = run_random_phase_null(dip_times, n_trials=50, seed=42)
    assert null["null_best_z2_mean"] < 20.0, \
        f"Random-phase null Z2 mean {null['null_best_z2_mean']} too high"


def test_random_phase_null_max_below_planted() -> None:
    fixture = load_fixture()
    dip_times = fixture["dip_times_bjd"]
    null = run_random_phase_null(dip_times, n_trials=50, seed=42)
    assert null["null_best_z2_max"] < 59.0, \
        f"Random-phase null max Z2 {null['null_best_z2_max']} at or above planted Z2"


# =========================================================================
# 8. Verdict classification
# =========================================================================


def test_classify_dip_structure() -> None:
    ka = {"recovery_pass": True, "recovered_z2": 60.0}
    qn = {"null_best_z2_95pct": 13.0}
    rp = {"null_best_z2_95pct": 12.0}
    v = classify_verdict(ka, qn, rp)
    assert "DIP_STRUCTURE" in v, f"Expected DIP_STRUCTURE, got: {v}"


def test_classify_no_signal_low_z2() -> None:
    ka = {"recovery_pass": True, "recovered_z2": 5.0}
    qn = {"null_best_z2_95pct": 13.0}
    rp = {"null_best_z2_95pct": 12.0}
    v = classify_verdict(ka, qn, rp)
    assert "NO_SIGNAL" in v, f"Expected NO_SIGNAL, got: {v}"


def test_classify_underdetermined_ka_fail() -> None:
    ka = {"recovery_pass": False, "recovered_z2": 0.0}
    qn = {"null_best_z2_95pct": 13.0}
    rp = {"null_best_z2_95pct": 12.0}
    v = classify_verdict(ka, qn, rp)
    assert "UNDERDETERMINED" in v, f"Expected UNDERDETERMINED, got: {v}"


# =========================================================================
# 9. Full analysis
# =========================================================================


def test_analyze_boyajian_structure() -> None:
    report = analyze_boyajian(seed=42)
    assert "error" not in report, f"Analysis error: {report.get('error')}"
    assert report["mission"] == "G20"
    assert report["forbidden_words_check"]["all_absent"] is True
    assert report["known_answer"]["recovery_pass"] is True
    assert "fixture" in report
    assert "negative_controls" in report
    assert "quiet_star_null" in report["negative_controls"]
    assert "random_phase_null" in report["negative_controls"]
    assert "DIP_STRUCTURE" in report["verdict"]


def test_analyze_boyajian_known_answer_details() -> None:
    report = analyze_boyajian(seed=42)
    ka = report["known_answer"]
    assert ka["n_dips"] == 30
    assert ka["planted_period_days"] == 24.5
    assert ka["recovery_error_days"] < 0.5
    assert ka["recovered_z2"] > 50.0


def test_analyze_boyajian_null_values_sane() -> None:
    report = analyze_boyajian(seed=42)
    qn = report["negative_controls"]["quiet_star_null"]
    rp = report["negative_controls"]["random_phase_null"]
    assert qn["null_best_z2_mean"] < 15.0
    assert rp["null_best_z2_mean"] < 20.0


# =========================================================================
# 10. NOTES.md generation
# =========================================================================


def test_notes_contains_verdict() -> None:
    report = analyze_boyajian(seed=42)
    notes = write_notes(report)
    assert "DIP_STRUCTURE" in notes
    assert "G20" in notes
    assert "Boyajian" in notes


def test_notes_contains_all_sections() -> None:
    report = analyze_boyajian(seed=42)
    notes = write_notes(report)
    for section in ["Stance", "Target", "Fixture", "Known-Answer Path",
                     "Negative Controls", "Verdict"]:
        assert section in notes, f"NOTES.md missing section: {section}"


def test_notes_no_forbidden_phrases_in_body() -> None:
    """Forbidden phrases must not appear outside the Stance section."""
    report = analyze_boyajian(seed=42)
    notes = write_notes(report)
    sections = notes.split("## ")
    relevant = [s for s in sections
                if not s.startswith("Stance") and not s.startswith("Verdict")]
    combined = " ".join(relevant).lower()
    for fp in FORBIDDEN_PHRASES:
        assert fp.lower() not in combined, f"NOTES.md body contains forbidden: {fp}"


# =========================================================================
# 11. Output files
# =========================================================================


def test_outputs_run_json_exists() -> None:
    path = OUT_DIR / "run.json"
    assert path.exists(), "outputs/boyajian/run.json missing -- run probe first"


def test_outputs_run_json_verdict_valid() -> None:
    path = OUT_DIR / "run.json"
    assert path.exists()
    report = json.loads(path.read_text())
    assert "DIP_STRUCTURE" in report["verdict"]
    assert report["forbidden_words_check"]["all_absent"] is True
    assert report["mission"] == "G20"


def test_outputs_notes_md_contains_verdict() -> None:
    path = OUT_DIR / "NOTES.md"
    assert path.exists()
    text = path.read_text()
    assert "DIP_STRUCTURE" in text
    assert "G20" in text
    assert "Boyajian" in text


# =========================================================================
# 12. Robustness
# =========================================================================


def test_empty_fixture_path() -> None:
    result = load_fixture(Path("/nonexistent/path.json"))
    assert "error" in result


def test_low_n_quiet_star() -> None:
    null = run_quiet_star_null(5, (0.0, 100.0), n_trials=10, seed=42)
    assert null["n_dips"] == 5
    assert null["null_best_z2_mean"] >= 0


def test_interpretation_contains_key_elements() -> None:
    ka = {"recovered_z2": 59.96, "recovered_period_days": 24.5,
          "recovery_pass": True}
    qn = {"null_best_z2_95pct": 13.28}
    rp = {"null_best_z2_95pct": 11.49}
    interp = build_interpretation(ka, qn, rp, None, "DIP_STRUCTURE")
    assert "Boyajian" in interp
    assert "DIP_STRUCTURE" in interp
    assert "structure" in interp.lower()


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
