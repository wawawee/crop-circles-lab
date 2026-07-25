"""Tests for tools/radio/radio_probe.py.

Stance: structure != message. Every quantitative test pins an invariant of
the scaffold math, NOT a claim about real Wow! / real FRBs.

Standalone-runnable: `python3 tools/radio/tests/test_radio_probe.py`.
"""
from __future__ import annotations

import inspect
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS_RADIO = HERE.parent
ROOT = TOOLS_RADIO.parent.parent
sys.path.insert(0, str(TOOLS_RADIO))

import numpy as np  # noqa: E402

import radio_probe as RP  # noqa: E402


# --- FFT known-answer -----------------------------------------------------

def test_synth_periodic_train_fft_peaks_at_known_freq():
    """Plant a sin at period 1.0 s. FFT peak must be within 1.5 bins of 1.0 Hz
    when Hann-windowed."""
    x, _dt = RP.synth_periodic_train(
        period_s=1.0, dt_s=0.01, n=1000, noise_frac=0.0, seed=42
    )
    fs = 1.0 / 0.01
    expected_freq = 1.0 / 1.0
    freqs, power = RP.fft_power_spectrum(x, sample_dt=0.01, window="hann")
    summary = RP.fft_summary(freqs, power, n_top=3)
    res = fs / len(x)  # freq resolution
    assert summary["peak_freq_hz"] is not None
    err = abs(summary["peak_freq_hz"] - expected_freq)
    assert err <= res * 1.5, (
        f"FFT peak at {summary['peak_freq_hz']} Hz, expected ~1.0 Hz, "
        f"res={res}, err={err}"
    )


def test_fft_summary_excludes_dc_from_top_bins():
    """The DC bin should never appear in the top-N list even when the
    signal has a strong mean (it's an after-detrend leak, not a signal)."""
    x = np.zeros(64)
    rng = np.random.default_rng(0)
    x[1:] = rng.standard_normal(63) * 0.01  # tiny signal, big DC
    x[0] = 1000.0  # spurious DC spike
    freqs, power = RP.fft_power_spectrum(x, sample_dt=1.0, window="none")
    summary = RP.fft_summary(freqs, power, n_top=3)
    # No top_bin should have bin_index == 0 (DC).
    for tb in summary["top_bins"]:
        assert tb["bin_index"] != 0, (
            f"DC leaked into top_bins: {summary['top_bins']}"
        )


# --- autocorrelation known-answer -----------------------------------------

def test_autocorr_value_at_plant_period_is_high():
    """For a sin at period 1.0 s, dt=0.01 s -> period_in_samples = 100.
    At that lag the autocorrelation MUST be > 0.5 (clear positive
    correlation at the FFT-detected period). We do NOT assert lag 100
    via argmax: for dense periodic sin waves (period << N), raw argmax
    lands at lag 1 (r=0.996) not lag P (r=0.9) because adjacent-sample
    correlation stays near 1.0. The CONFIRMATORY contract is therefore
    `r[period_in_samples] > threshold` against the FFT-detected
    period -- the FFT peak is the proper period detector.
    """
    x, _dt = RP.synth_periodic_train(
        period_s=1.0, dt_s=0.01, n=1000, noise_frac=0.0, seed=7
    )
    r = RP.autocorrelation(x, max_lag=200)
    plant_in_samples = int(round(1.0 / 0.01))  # 100
    ac = RP.autocorr_summary(r, plant_period_in_samples=plant_in_samples)
    # Confirmatory mode keys:
    assert ac["plant_period_in_samples"] == plant_in_samples, (
        f"summary plant_period_in_samples got {ac.get('plant_period_in_samples')}, "
        f"expected {plant_in_samples}"
    )
    assert ac["r_at_plant_period"] > 0.5, (
        f"r at plant period = {ac.get('r_at_plant_period')}, expected > 0.5 "
        f"(a clean sin at lag=P should give ~0.9 since r ≈ (N-P)/N × cos(2π) ≈ "
        f"(N-P)/N)"
    )
    assert ac["r_at_plant_period_is_high"] is True, (
        "r_at_plant_period_is_high must be True when r > 0.5"
    )


# --- epoch-fold / Rayleigh Z² ---------------------------------------------

def test_epoch_fold_recovers_plant_period_16p35d():
    """30 synthetic arrivals around multiples of 16.35 d -> epoch-fold
    should recover 16.35 d ± 1 d with Z² >> 1."""
    times = RP.synth_frb_arrivals(
        period_d=RP.FRB_180916_PERIOD_DAYS,
        n_arrivals=30,
        obs_window_d=500.0,
        jitter_d=0.1,  # very tight clustering
        seed=0,
    )
    grid = np.arange(10.0, 30.0 + 1e-9, 0.05)
    fold = RP.epoch_fold(times, grid)
    assert fold["best_period"] is not None
    err = abs(fold["best_period"] - 16.35)
    assert err <= 1.0, f"epoch_fold missed plant: {fold['best_period']}"
    assert fold["best_z2"] > 30.0, (
        f"Z² = {fold['best_z2']} below expected ~60 for N=30 tight "
        f"arrivals -- formula or normalization is wrong"
    )
    assert fold["best_p_value"] < 0.01, (
        f"p = {fold['best_p_value']} not below 0.01 for tight clustering"
    )


def test_epoch_fold_uniform_null_stays_low():
    """A uniform random schedule should NOT produce a Z² so large that
    it looks like a real signal. Fisher-Ballager max-of-grid distribution
    sets the upper bound: E[max Z²] ≈ log(n_grid) + γ(2). For n_grid=401
    that's ≈ 6.6, but variance is high and a specific seed can sneak
    higher. We test "stays in the noise regime" with the liberal bound
    Z² < 18 -- strict enough to catch a true plant (Z² ≈ 60) and loose
    enough to never flake under grid-search noise."""
    rng = np.random.default_rng(20260725)
    times = rng.uniform(0.0, 500.0, size=30)
    grid = np.arange(10.0, 30.0 + 1e-9, 0.05)
    fold = RP.epoch_fold(times, grid)
    assert fold["best_z2"] < 18.0, (
        f"shuffled null produced Z² = {fold['best_z2']} > 18 -- looks "
        f"like a real signal where there should be only uniform noise"
    )


# --- Wow! honesty audit ----------------------------------------------------

def test_wow_six_samples_has_only_three_freq_bins():
    """With 6 samples, the rfft produces 4 bins total (DC + 3 unique freq).
    NOT 6 -- the negative half of the DFT is mirrored.
    """
    wow = RP.wow_honest_check()
    assert wow["n_samples"] == 6
    assert wow["n_bins"] == 4, (
        f"Wow! DFT has 6 samples -> 4 bins (DC + 3 freq). "
        f"Got n_bins = {wow['n_bins']}"
    )
    assert wow["freq_resolution_hz"] is not None
    # resolution = 1 / (6 * 12) = 1/72 ≈ 0.01389
    expected = 1.0 / (6 * 12.0)
    assert abs(wow["freq_resolution_hz"] - expected) < 1e-6


def test_fft_rejects_nonfinite_samples():
    """A NaN or inf in the input must raise, NOT silently propagate a
    NaN spectrum downstream."""
    import math
    try:
        RP.fft_power_spectrum([1.0, float("nan"), 0.5, -0.3], sample_dt=1.0)
        raised = False
    except ValueError:
        raised = True
    assert raised, "fft_power_spectrum must raise on NaN input"
    try:
        RP.fft_power_spectrum([1.0, float("inf"), 0.5, -0.3], sample_dt=1.0)
        raised2 = False
    except ValueError:
        raised2 = True
    assert raised2, "fft_power_spectrum must raise on inf input"


def test_autocorr_rejects_nonfinite_samples():
    """Same nan/inf guard contract as the FFT."""
    try:
        RP.autocorrelation([1.0, float("nan"), 0.5, -0.3, 0.1, 0.2], max_lag=3)
        raised = False
    except ValueError:
        raised = True
    assert raised, "autocorrelation must raise on NaN input"


def test_rayleigh_z2_uses_standard_2N_over_N_formula():
    """Standard Rayleigh Z² = 2/N * R². For N tight arrivals at multiples
    of a candidate period, Z² should approach 2*N (≈60 for N=30)."""
    times = RP.synth_frb_arrivals(
        period_d=RP.FRB_180916_PERIOD_DAYS,
        n_arrivals=30,
        jitter_d=0.001,  # very tight
        seed=0,
    )
    z2, phase = RP.rayleigh_z2(times, RP.FRB_180916_PERIOD_DAYS)
    # Tight clustering: Z² ≈ 2*N = 60.
    assert z2 > 50.0, (
        f"Tight-cluster Z² = {z2}, expected ~60 for N=30; the 2*R²/N "
        f"formulation must yield this magnitude, NOT the (R/N)² formula "
        f"which would give ~1."
    )
    assert phase >= 0.0 and phase < 2 * math.pi


def test_wow_six_samples_claim_blocked_is_True():
    """claim_blocked must be True -- the scaffold is audit-only."""
    wow = RP.wow_honest_check()
    assert wow["claim_blocked"] is True, (
        "Wow! claim_blocked must be True -- 6 samples can NEVER support "
        "a periodicity claim"
    )


def test_wow_uses_published_six_intensities():
    """The 6EQUJ5 sigma values must surface in our report, not be re-imagined."""
    assert RP.WOW_SAMPLES_SIGMA == (6.5, 14.5, 26.5, 30.5, 19.5, 5.5)
    wow = RP.wow_honest_check()
    assert wow["freq_mhz"] == 1420.0
    assert wow["sample_dt_s"] == 12.0


# --- run-level integration -------------------------------------------------

def test_run_known_train_overall_pass():
    """Top-level orchestrator: FFT + autocorr known-answer should both pass."""
    out = RP.run_known_train(seed=11)
    ka = out["known_answer"]
    assert ka["fft_pass"], f"FFT known-answer failed: {ka}"
    assert ka["autocorr_pass"], f"autocorr known-answer failed: {ka}"
    assert ka["overall_pass"], "overall known-answer should pass"


def test_run_wow_blocked_by_design():
    """run_wow_honest surfaces claim_blocked = True so the orchestrator
    level is also honest."""
    out = RP.run_wow_honest()
    assert out["wow_honest"]["claim_blocked"] is True


def test_run_frb_180916_recovery_pass():
    """FRB 180916 scaffold recovers the 16.35-d plant within 1 d."""
    out = RP.run_frb_180916(seed=0)
    ka = out["known_answer"]
    assert ka["recovery_pass"], f"FRB recovery failed: {ka}"
    # Shuffled null must stay well below.
    nc = out["negative_controls"]
    assert nc["shuffled_uniform_z2_max"] < out["epochfold"]["best_z2"], (
        "Shuffled control should NOT outperform the plant"
    )


def test_frb_180916_scaffold_does_not_use_frb_121102_period():
    """Belt-and-suspenders: the scaffold MUST use 16.35 d, not the FRB 121102
    cycle of ~157 d."""
    out = RP.run_frb_180916(seed=0)
    plant = out["plant"]
    assert plant["true_period_d"] == 16.35
    assert plant["decoy_period_d_for_frb_121102"] == 157.0
    # And the recovered period must come down near 16.35 d, NOT 157 d.
    rec = out["epochfold"]["best_period"]
    assert 10.0 <= rec <= 30.0, (
        f"recovered period {rec} d outside the 10..30 d search grid -- "
        f"the epoch-fold is searching the WRONG range"
    )


# --- markdown notes & CLI --------------------------------------------------

def test_write_notes_markdown_runs_without_error_and_advertises_honesty():
    """Notes-renderer must surface the honesty framing."""
    report = RP.analyze(mode="all", seed=0)
    md = RP.write_notes_markdown(report)
    assert isinstance(md, str)
    # Honesty hits:
    assert "Structure ≠ message" in md or "Structure != message" in md, (
        "Markdown must surface the lab motto"
    )
    # Wow! honest block must be present
    assert "claim_blocked" in md
    # FRB 180916 must be present
    assert "FRB 180916" in md
    # Synthesized FRB 121102's 157 d must NOT be the active plant period
    assert "16.35" in md


def test_cli_all_of_above_writes_both_files():
    """End-to-end CLI: --all-of-the-above produces run.json and notes.md
    in a temp dir; both files are non-empty and parseable.
    """
    td = Path(tempfile.mkdtemp(prefix="radio_all_"))
    out_json = td / "run.json"
    out_md = td / "notes.md"
    res = subprocess.run([
        sys.executable, str(TOOLS_RADIO / "radio_probe.py"),
        "--all-of-the-above", "--seed", "0",
        "--out-json", str(out_json), "--out-md", str(out_md),
    ], capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, (
        f"CLI failed:\nSTDOUT:\n{res.stdout[:600]}\n"
        f"STDERR:\n{res.stderr[:600]}"
    )
    assert out_json.exists() and out_md.exists()
    d = json.load(open(out_json))
    assert "known_train" in d and "wow_honest" in d and "frb_180916" in d
    # Wow! honest audit must show claim_blocked = True
    assert d["wow_honest"]["wow_honest"]["claim_blocked"] is True
    # FRB 180916 known-answer should pass
    assert d["frb_180916"]["known_answer"]["recovery_pass"] is True
    # notes.md should have an FFT peak line for the train
    md_text = out_md.read_text()
    assert "known-answer" in md_text.lower()


# --- Standalone runner ----------------------------------------------------

if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    def _needs_fixture(f):
        return bool(list(inspect.signature(f).parameters))
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
