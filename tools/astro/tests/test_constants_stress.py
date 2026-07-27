"""Tests for tools/astro/constants_stress.py.

These pin the sweep shape: SWEEP_TOLS includes 10c, the 10c row is computed,
and the headline md renders without errors. We deliberately do not pin
specific hit counts -- those depend on the canonical constants table, which
PDG will update over time, and the test should outlive refactors to the table.

Standalone runnable: `python3 tools/astro/tests/test_constants_stress.py`.
End-to-end subprocess tests use tempfile.mkdtemp directly so they work both
under pytest AND in plain-script mode (no pytest-fixture dependency).
"""
from __future__ import annotations

import csv
import inspect
import json
import math
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ASTRO = HERE.parent

from tools.astro import constants_probe as CP
from tools.astro import constants_stress as CS


def test_sweep_tols_includes_10c_reference():
    """The 10-cent bar is the explicit ASSIGNMENT deliverable. It MUST appear
    in SWEEP_TOLS or the 'harmonic bar' question is unanswerable."""
    assert 10.0 in CS.SWEEP_TOLS


def test_sweep_row_returns_expected_schema():
    """Each row must expose the headline numbers used downstream."""
    const = CP.get_table("core")
    row = CS._sweep_row(const, tol=20.0, n_trials=50, seed=42)
    expected = {"tol_cents", "n_pairs_all", "n_pairs_for_hits",
                "hits_real_all", "hits_real_filt",
                "decade_mean", "decade_p95", "decade_p99", "decade_max",
                "perm_mean", "perm_p95", "perm_p99", "perm_max",
                "perm_gap_z",   # added in round 6 (scale-invariant)
                "p_decade_gte_real_filt", "p_perm_gte_real_filt"}
    assert expected <= set(row.keys()), f"missing keys: {expected - set(row.keys())}"
    assert row["tol_cents"] == 20.0
    assert isinstance(row["hits_real_filt"], int)
    assert isinstance(row["p_decade_gte_real_filt"], float)
    assert isinstance(row["perm_gap_z"], float)


def test_run_sweep_small_control_finishes_in_budget():
    """Smallest reasonable sweep -- 50 trials, core, full tols -- should run
    in well under a second. Pin a guardrail against an accidental N² blow-up."""
    import time
    const = CP.get_table("core")
    t0 = time.time()
    rows = CS.run_sweep(const, n_trials=50, seed=42)
    dt = time.time() - t0
    assert len(rows) == len(CS.SWEEP_TOLS)
    assert dt < 10.0, f"sweep took {dt:.2f}s -- well above guardrail"


def test_sweep_outputs_consistent():
    """End-to-end smoke: CS.main writes all three artefacts and the JSON
    contains every sweep row. Uses tempfile.mkdtemp for runnability in both
    pytest and plain-script modes."""
    import subprocess
    td = Path(tempfile.mkdtemp(prefix="cs_stress_"))
    out = td / "stress"
    res = subprocess.run([
        sys.executable,
        str(ASTRO / "constants_stress.py"),
        "--set", "core", "--small-control", "--out", str(out),
    ], capture_output=True, text=True, timeout=120)
    assert res.returncode == 0, (
        f"constants_stress.py failed:\nSTDOUT:\n{res.stdout[:600]}\n"
        f"STDERR:\n{res.stderr[:600]}"
    )
    assert (out / "stress_sweep.csv").exists()
    assert (out / "stress_sweep.json").exists()
    assert (out / "stress_sweep_notes.md").exists()
    with open(out / "stress_sweep.json") as f:
        d = json.load(f)
    assert len(d["rows"]) == len(CS.SWEEP_TOLS)
    by_tol = {r["tol_cents"] for r in d["rows"]}
    assert 10.0 in by_tol, "10-cent row missing from JSON output"
    with open(out / "stress_sweep.csv") as f:
        rdr = list(csv.DictReader(f))
    assert len(rdr) == len(d["rows"])
    rl_20 = next(r for r in d["rows"] if r["tol_cents"] == 20.0)
    assert rl_20["hits_real_filt"] >= 0


def test_render_markdown_does_not_crash_and_lists_strict_verdict():
    """Even with minimal data we should render cleanly AND expose the
    new STRICT-VERDICT survival features (beats_a_strict, low_p_b)."""
    md = CS._render_markdown(
        rows=[{
            "tol_cents": 20.0, "n_pairs_all": 100, "n_pairs_for_hits": 90,
            "hits_real_all": 5, "hits_real_filt": 3,
            "decade_mean": 4.0, "decade_p50": 4.0, "decade_p95": 8.0,
            "decade_p99": 10.0, "decade_max": 12,
            "perm_mean": 3.5, "perm_p50": 3.0, "perm_p95": 7.0,
            "perm_p99": 9.0, "perm_max": 11,
            "perm_gap_z": 4.250,  # round-6 scale-invariant score
            "p_decade_gte_real_filt": 0.85, "p_perm_gte_real_filt": 0.82,
        }],
        constant_set="core", n_constants_total=15, n_constants_for_hits=15,
        tol_cents=20.0, n_trials=200, seed=42, used_small=False,
    )
    assert "## Headline" in md
    assert "20c" in md
    assert "STRICT >" in md, "rendered MD should advertise the strict-vertict bar"
    assert "degenerat" in md.lower(), (
        "rendered MD should mention null-degeneracy detection"
    )
    # Round-6: the calibration requirement that perm_gap_z appear in the
    # hit-rate table column.
    assert "perm_gap_z" in md


# --- gap_z + bootstrap calibration (round 6) ------------------------------

def test_gap_z_pins_known_distributions():
    """gap_z = (max - mean) / sqrt(max(mean, 1)). Pin three points:
    perfectly degenerate (all same value) -> 0;
    modest spread -> exact 0.5;
    wider spread with closed-form gap -> exact closed-form.

    NOTE: 'modest' and 'wide' refer to spread of the hit distribution, NOT
    the magnitude of the hits. gap_z is scale-invariant in mean.
    """
    # Pertectly degenerate: all hits identical
    arr_const = np.array([5, 5, 5, 5, 5])
    assert CS.gap_z(arr_const) == 0.0
    # Modest spread: arr [3,4,4,4,5] -> mean=4.0, max=5 -> gap_z = 1.0/sqrt(4.0) = 0.5
    arr_modest = np.array([3, 4, 4, 4, 5])
    assert abs(CS.gap_z(arr_modest) - 0.5) < 1e-9
    # Wider spread: arr [18,20,21,21] -> mean=20.0, max=21 -> gap_z = 1.0/sqrt(20.0)
    arr_wide = np.array([18, 20, 21, 21])
    assert abs(CS.gap_z(arr_wide) - (1.0 / math.sqrt(20.0))) < 1e-9, (
        f"expected 1.0/sqrt(20.0) but got {CS.gap_z(arr_wide):.6f}"
    )


def test_gap_z_scales_invariantly_across_magnitudes():
    """Same absolute gap (1.0) at higher mean produces substantially SMALLER
    gap_z -- this is the property that lets DEGENERACY_Z_DEFAULT = 2.0 apply
    at tight tolerance (~3 hits) AND loose tolerance (~134 hits) without
    manual per-tol tuning.
    """
    arr_low_mean = [2, 2, 3]       # mean ~2.33, max=3
    arr_high_mean = [130, 131, 132]  # mean 131, max=132
    gz_low = CS.gap_z(arr_low_mean)
    gz_high = CS.gap_z(arr_high_mean)
    assert gz_low > gz_high * 3, (
        f"gap_z should shrink with higher mean (same absolute gap); "
        f"got gz_low={gz_low:.3f}, gz_high={gz_high:.3f}"
    )


def test_calibrate_degeneracy_threshold_is_deterministic():
    """Same (constants, tol, n_trials, seed, n_bootstrap) => same return dict."""
    const = CP.get_table("core")
    a = CS.calibrate_degeneracy_threshold(
        const, tol=20.0, n_trials=100, seed=42, n_bootstrap=20, multiplier=4
    )
    b = CS.calibrate_degeneracy_threshold(
        const, tol=20.0, n_trials=100, seed=42, n_bootstrap=20, multiplier=4
    )
    assert a == b, f"calibration is non-deterministic: {a} vs {b}"
    expected = {"tol_cents", "n_bootstrap", "multiplier", "pool_size",
                "p05_gap_z", "p25_gap_z", "p50_gap_z",
                "mean_gap_z", "max_gap_z", "seed"}
    assert expected <= set(a.keys()), f"missing keys: {expected - set(a.keys())}"
    assert a["tol_cents"] == 20.0
    assert a["pool_size"] >= 100 + 10
    assert 0 <= a["p05_gap_z"] <= a["max_gap_z"]


def test_calibrate_degeneracy_threshold_propagates_seed():
    """calibrate_degeneracy_threshold correctly records input seed and runs
    the same procedure for any seed input. Lock for reproducibility.

    IMPORTANT LAB FINDING (round 6): the underlying `pair_permutation_control`
    on the canonical core set is MATHEMATICALLY INVARIANT under permutation
    of name->value mapping -- the multiset of pairwise ratios is preserved
    regardless of which name carries which value, so every trial produces
    the EXACT same hit count, hence gap_z is identically 0. This means Null B
    (the permutation null) does NOT add information beyond Null A (the magnitude
    null) on this constant set -- a real design flaw worth flagging.
    See MISSION_BOARD N3 'What remains for N3+'.
    """
    const = CP.get_table("core")
    a = CS.calibrate_degeneracy_threshold(
        const, tol=20.0, n_trials=100, seed=42, n_bootstrap=20, multiplier=4
    )
    b = CS.calibrate_degeneracy_threshold(
        const, tol=20.0, n_trials=100, seed=9999, n_bootstrap=20, multiplier=4
    )
    # Seed propagation ALWAYS works regardless of pool degeneracy
    assert a["seed"] == 42, "seed not propagated to result"
    assert b["seed"] == 9999, "seed not propagated to result"
    # Pool size = max(n_bootstrap*multiplier, n_trials+10)
    assert a["pool_size"] == 100 + 10
    # The pool is constant across seeds (degenerate by construction on this
    # constant set), so stats match. This is what we WANT to detect.
    assert a["mean_gap_z"] == b["mean_gap_z"] == 0.0, (
        f"expected degenerate stats (mean_gap_z=0) on core pair-permutation "
        f"null; got a={a['mean_gap_z']}, b={b['mean_gap_z']}"
    )
    # Subsample indices are seed-derived but pool is constant; p05_gap_z too
    assert a["p05_gap_z"] == b["p05_gap_z"] == 0.0
    assert a["max_gap_z"] == b["max_gap_z"] == 0.0


def test_main_with_calibrate_runs_calibration_step():
    """End-to-end: --calibrate flag invokes bootstrap and emits results in
    the markdown + JSON without raising. Uses tempfile.mkdtemp instead of
    pytest's tmp_path fixture so this is standalone-runnable."""
    import subprocess
    td = Path(tempfile.mkdtemp(prefix="cs_cal_"))
    out = td / "cal_out"
    res = subprocess.run([
        sys.executable,
        str(ASTRO / "constants_stress.py"),
        "--set", "core", "--small-control", "--calibrate",
        "--out", str(out),
    ], capture_output=True, text=True, timeout=180)
    assert res.returncode == 0, (
        f"--calibrate run failed:\nSTDOUT:\n{res.stdout[:600]}\n"
        f"STDERR:\n{res.stderr[:600]}"
    )
    assert (out / "stress_sweep.json").exists()
    with open(out / "stress_sweep.json") as f:
        d = json.load(f)
    cal = d.get("degeneracy_floor_used", {}).get("calibrated", [])
    assert cal, f"calibrated list empty; got {list(d.keys())}"
    assert len(cal) == len(CS.SWEEP_TOLS)
    for c in cal:
        assert isinstance(c["p05_gap_z"], float)
        assert 0 <= c["p05_gap_z"] <= c["max_gap_z"] + 1e-9
    md = (out / "stress_sweep_notes.md").read_text()
    assert "## Calibration (--calibrate" in md, (
        "calibrate mode should produce a '## Calibration' section in markdown"
    )


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    def _needs_fixture(f):
        params = list(inspect.signature(f).parameters)
        return bool(params)
    runnable = [f for f in fns if not _needs_fixture(f)]
    skipped = [f for f in fns if _needs_fixture(f)]
    for fn in skipped:
        print(f"SKIP {fn.__name__}  (private pytest-fixture)")
    ok = 0; bad = 0
    for fn in runnable:
        try:
            fn()
            print(f"PASS {fn.__name__}")
            ok += 1
        except Exception as e:
            print(f"FAIL {fn.__name__}: {type(e).__name__}: {e}")
            bad += 1
    print(f"\n{ok}/{len(runnable)} passed, {bad} failed, {len(skipped)} skipped")
    sys.exit(0 if bad == 0 else 1)
