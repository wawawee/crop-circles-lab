"""test_tess_ellipsoid_probe.py — >=12 tests for G17 TESS SETI Ellipsoid.

Run:
    python tools/astro/tests/test_tess_ellipsoid_probe.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from tools.astro.tess_ellipsoid_probe import (
    CATALOG_PATH, COHORT_THRESHOLD_FLOOR_Z2, FORBIDDEN_PHRASES, N_TARGETS,
    OUT_DIR, SEED, STANCE, VERDICT_VOCAB,
    _generate_epoch_grid, _inject_synthetic_dips, _uniform_random_times, _z_score,
    analyze_ellipsoid, build_interpretation, calibrate_cohort_threshold_z2,
    classify_verdict, load_catalog, run_cohort_analysis, run_known_answer,
    run_quiet_star_null, run_time_shuffle_null,
    write_notes,
)

# =========================================================================
# 1. Stance / vocabulary
# =========================================================================


def test_stance_present() -> None:
    assert len(STANCE) > 30
    assert "structure != message" in STANCE.lower()


def test_verdict_vocab() -> None:
    for v in ("PIPELINE_VALIDATED", "UNDERDETERMINED", "NO_SIGNAL", "FPR_CALIBRATED"):
        assert v in VERDICT_VOCAB


def test_forbidden_phrases_defined() -> None:
    expected = ["Dyson", "alien", "megastructure"]
    for needle in expected:
        assert any(needle.lower() in fp.lower() for fp in FORBIDDEN_PHRASES)


def test_forbidden_not_in_run_json_data() -> None:
    path = OUT_DIR / "run.json"
    if not path.exists():
        return
    report = json.loads(path.read_text())
    exclude_keys = {"stance", "interpretation", "forbidden_words_check"}
    text = json.dumps(
        {k: v for k, v in report.items() if k not in exclude_keys}
    ).lower()
    for fp in FORBIDDEN_PHRASES:
        assert fp.lower() not in text


def test_forbidden_not_in_notes_body() -> None:
    path = OUT_DIR / "NOTES.md"
    if not path.exists():
        return
    text = path.read_text()
    sections = text.split("## ")
    relevant = [s for s in sections
                if not s.startswith("Stance") and not s.startswith("Verdict")]
    combined = " ".join(relevant).lower()
    for fp in FORBIDDEN_PHRASES:
        assert fp.lower() not in combined


# =========================================================================
# 2. Catalog / constants
# =========================================================================


def test_catalog_has_32_targets() -> None:
    catalog = load_catalog()
    assert "error" not in catalog
    assert len(catalog["targets"]) == N_TARGETS


def test_catalog_first_target_is_279055252() -> None:
    catalog = load_catalog()
    first = catalog["targets"][0]
    assert first["tic_id"] == 279055252
    assert "ra_deg" in first
    assert "dec_deg" in first
    assert "d_pc" in first
    assert "tcross_year" in first
    assert "tcross_bjd" in first
    assert "cycle" in first


def test_catalog_targets_have_unique_tic_ids() -> None:
    catalog = load_catalog()
    tic_ids = [t["tic_id"] for t in catalog["targets"]]
    assert len(set(tic_ids)) == len(tic_ids)


def test_catalog_has_off_ellipsoid_controls() -> None:
    catalog = load_catalog()
    assert "controls" in catalog
    assert "tic_ids" in catalog["controls"]


def test_catalog_targets_have_varied_tcross() -> None:
    catalog = load_catalog()
    tcross_values = [t["tcross_bjd"] for t in catalog["targets"]]
    assert min(tcross_values) < max(tcross_values)
    assert max(tcross_values) - min(tcross_values) > 500.0


def test_catalog_tcross_not_shared() -> None:
    catalog = load_catalog()
    tcross_values = [t["tcross_bjd"] for t in catalog["targets"]]
    first = tcross_values[0]
    assert not all(abs(v - first) < 1.0 for v in tcross_values), \
        "All targets share the same tcross — must be per-star from paper"


# =========================================================================
# 3. Helper functions
# =========================================================================


def test_generate_epoch_grid() -> None:
    grid = _generate_epoch_grid(2.5, margin_d=1.0, steps=101)
    assert len(grid) == 101
    assert abs(grid[0] - 1.5) < 1e-6
    assert abs(grid[-1] - 3.5) < 1e-6
    assert abs(grid[50] - 2.5) < 1e-6


def test_uniform_random_times_range() -> None:
    times = _uniform_random_times(50, (1000.0, 1100.0), seed=42)
    assert len(times) == 50
    assert times[0] >= 1000.0
    assert times[-1] <= 1100.0
    assert all(times[i] <= times[i + 1] for i in range(len(times) - 1))


def test_inject_synthetic_dips_near_tcross() -> None:
    catalog = load_catalog()
    target = catalog["targets"][0]
    dips = _inject_synthetic_dips(target, period_d=2.5, n_dips=30, seed=42)
    assert len(dips) == 30
    tcross = target["tcross_bjd"]
    assert dips[0] >= tcross - 1.0
    assert dips[-1] <= tcross + 30 * 2.5 + 2.0


def test_z_score_outlier() -> None:
    result = _z_score(10.0, [1.0, 2.0, 1.5, 2.5])
    assert result["z"] > 5.0
    assert result["percentile"] == 0.0


def test_z_score_single_null() -> None:
    result = _z_score(0.0, [0.0])
    assert result["z"] == 0.0


# =========================================================================
# 4. Known-answer path
# =========================================================================


def test_known_answer_recovery_pass() -> None:
    catalog = load_catalog()
    target = catalog["targets"][0]
    ka = run_known_answer(target, seed=42)
    assert ka["recovery_pass"] is True


def test_known_answer_z2_high() -> None:
    catalog = load_catalog()
    target = catalog["targets"][0]
    ka = run_known_answer(target, seed=42)
    assert ka["recovered_z2"] > 30.0, \
        f"Z2={ka['recovered_z2']} too low for injected signal"


def test_known_answer_recovery_error_small() -> None:
    catalog = load_catalog()
    target = catalog["targets"][0]
    ka = run_known_answer(target, seed=42)
    assert ka["recovery_error_days"] < 0.5


# =========================================================================
# 5. Negative controls
# =========================================================================


def test_quiet_star_null_z2_low() -> None:
    null = run_quiet_star_null(30, (1300.0, 1500.0), n_trials=50, seed=42)
    assert null["null_best_z2_mean"] < 15.0


def test_quiet_star_null_max_separated() -> None:
    catalog = load_catalog()
    target = catalog["targets"][0]
    ka = run_known_answer(target, seed=42)
    null = run_quiet_star_null(30, (1300.0, 1500.0), n_trials=50, seed=42)
    assert ka["recovered_z2"] > null["null_best_z2_95pct"] * 2, \
        "KA Z2 should dominate null 95th percentile"


def test_time_shuffle_null_z2_low() -> None:
    catalog = load_catalog()
    targets = catalog["targets"][:10]
    null = run_time_shuffle_null(targets, n_trials=50, seed=42)
    assert null["null_best_z2_mean"] < 15.0


# =========================================================================
# 6. Cohort analysis — no over-claiming
# =========================================================================


def test_cohort_not_overclaiming() -> None:
    catalog = load_catalog()
    targets = catalog["targets"]
    quiet = run_quiet_star_null(
        n_dips=30,
        range_bjd=(1330.75 - 27.0, 1330.75 + 27.0),
        seed=42,
    )
    shuffle = run_time_shuffle_null(targets, seed=42)
    thr = calibrate_cohort_threshold_z2(quiet, shuffle)
    cohort = run_cohort_analysis(targets, seed=42, threshold_z2=thr)
    assert cohort["anomalous_count"] <= 5, \
        f"Cohort reports {cohort['anomalous_count']}/32 anomalous — fixture-only should be quiet"
    assert cohort["anomalous_count"] < len(targets), \
        "Cohort must not report all targets as anomalous"


def test_cohort_threshold_above_null_95() -> None:
    """Regression: cohort cut must not sit under the null 95th percentiles."""
    quiet = {"null_best_z2_95pct": 15.68, "null_best_z2_max": 20.92}
    shuffle = {"null_best_z2_95pct": 16.43, "null_best_z2_max": 21.70}
    thr = calibrate_cohort_threshold_z2(quiet, shuffle)
    assert thr >= quiet["null_best_z2_95pct"]
    assert thr >= shuffle["null_best_z2_95pct"]
    assert thr >= COHORT_THRESHOLD_FLOOR_Z2
    assert thr == 21.0


def test_cohort_threshold_tracks_higher_null() -> None:
    quiet = {"null_best_z2_95pct": 22.5}
    shuffle = {"null_best_z2_95pct": 18.0}
    thr = calibrate_cohort_threshold_z2(quiet, shuffle)
    assert thr == 22.5


def test_cohort_all_targets_tested() -> None:
    catalog = load_catalog()
    cohort = run_cohort_analysis(catalog["targets"], seed=42)
    assert cohort["n_targets"] == N_TARGETS
    assert len(cohort["per_target"]) == N_TARGETS


# =========================================================================
# 7. Verdict classification
# =========================================================================


def test_classify_pipeline_validated() -> None:
    ka = {"recovery_pass": True, "recovered_z2": 60.0}
    qn = {"null_best_z2_95pct": 13.0}
    ts = {"null_best_z2_95pct": 12.0}
    co = {"anomalous_count": 1, "threshold_z2": 20.0, "n_targets": 32}
    v = classify_verdict(ka, qn, ts, co)
    assert "PIPELINE_VALIDATED" in v


def test_classify_underdetermined_ka_fail() -> None:
    ka = {"recovery_pass": False, "recovered_z2": 0.0}
    qn = {"null_best_z2_95pct": 13.0}
    ts = {"null_best_z2_95pct": 12.0}
    co = {"anomalous_count": 0, "threshold_z2": 20.0, "n_targets": 32}
    v = classify_verdict(ka, qn, ts, co)
    assert "UNDERDETERMINED" in v


def test_classify_no_overclaiming_with_anomalous() -> None:
    ka = {"recovery_pass": True, "recovered_z2": 60.0}
    qn = {"null_best_z2_95pct": 13.0}
    ts = {"null_best_z2_95pct": 12.0}
    co = {"anomalous_count": 5, "threshold_z2": 20.0, "n_targets": 32}
    v = classify_verdict(ka, qn, ts, co)
    assert "FPR_CALIBRATED" in v or "PIPELINE_VALIDATED" in v


# =========================================================================
# 8. Full analysis
# =========================================================================


def test_analyze_ellipsoid_structure() -> None:
    report = analyze_ellipsoid(seed=42)
    assert "error" not in report
    assert report["mission"] == "G17"
    assert report["forbidden_words_check"]["all_absent"] is True
    assert report["known_answer"]["recovery_pass"] is True
    assert "negative_controls" in report
    assert "quiet_star_null" in report["negative_controls"]
    assert "time_shuffle_null" in report["negative_controls"]
    assert "cohort_analysis" in report
    assert "PIPELINE_VALIDATED" in report["verdict"]


def test_analyze_ellipsoid_targets_correct() -> None:
    report = analyze_ellipsoid(seed=42)
    assert report["targets"]["n_total"] == N_TARGETS
    assert report["targets"]["first_target_tic"] == 279055252


def test_analyze_ellipsoid_ka_details() -> None:
    report = analyze_ellipsoid(seed=42)
    ka = report["known_answer"]
    assert ka["n_injected_dips"] == 30
    assert ka["recovery_pass"] is True
    assert ka["recovered_z2"] > 30.0


def test_analyze_ellipsoid_null_values_sane() -> None:
    report = analyze_ellipsoid(seed=42)
    qn = report["negative_controls"]["quiet_star_null"]
    ts = report["negative_controls"]["time_shuffle_null"]
    assert qn["null_best_z2_mean"] < 15.0
    assert ts["null_best_z2_mean"] < 15.0


def test_analyze_ellipsoid_cohort_not_overclaiming() -> None:
    report = analyze_ellipsoid(seed=42)
    co = report["cohort_analysis"]
    anom = co["anomalous_count"]
    thr = co["threshold_z2"]
    q95 = report["negative_controls"]["quiet_star_null"]["null_best_z2_95pct"]
    s95 = report["negative_controls"]["time_shuffle_null"]["null_best_z2_95pct"]
    assert thr >= q95
    assert thr >= s95
    assert thr >= COHORT_THRESHOLD_FLOOR_Z2
    assert anom <= 5, f"Cohort over-claims: {anom}/32 anomalous in fixture-only path"
    assert anom < 32, "Cohort must not report all targets as anomalous"


# =========================================================================
# 9. NOTES.md generation
# =========================================================================


def test_notes_contains_verdict() -> None:
    report = analyze_ellipsoid(seed=42)
    notes = write_notes(report)
    assert "G17" in notes
    assert "PIPELINE_VALIDATED" in notes or "UNDERDETERMINED" in notes


def test_notes_contains_all_sections() -> None:
    report = analyze_ellipsoid(seed=42)
    notes = write_notes(report)
    for section in ["Stance", "Catalog", "Known-Answer Path",
                     "Negative Controls", "Cohort Analysis", "Verdict"]:
        assert section in notes


def test_notes_no_forbidden_phrases_in_body() -> None:
    report = analyze_ellipsoid(seed=42)
    notes = write_notes(report)
    sections = notes.split("## ")
    relevant = [s for s in sections
                if not s.startswith("Stance") and not s.startswith("Verdict")]
    combined = " ".join(relevant).lower()
    for fp in FORBIDDEN_PHRASES:
        assert fp.lower() not in combined


# =========================================================================
# 10. Robustness
# =========================================================================


def test_empty_catalog_path() -> None:
    result = load_catalog(Path("/nonexistent/path.json"))
    assert "error" in result


def test_missing_entry_graceful() -> None:
    result = analyze_ellipsoid(
        catalog_path=Path("/nonexistent/catalog.json"),
    )
    assert "error" in result


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
