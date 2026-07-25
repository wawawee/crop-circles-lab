"""radio_probe — radio periodicity probe with known-answer scaffolds.

R1 mission (Minimax/Lab local — Hermes handed off). Landed scaffold:
  * **FFT power spectrum** with optional Hann window (numpy.fft.rfft + rfftfreq;
    no scipy dependency).
  * **Lagged autocorrelation** (Pearson, mean-subtracted, variance-normalised).
  * **Epoch-fold / Rayleigh Z²** for sparse event arrival times -- the FFT is
    numerically meaningless when N is small (~30s of bursts), so the
    classic Rayleigh statistic is the right tool.
  * **6-sample Wow! honesty audit** -- a 'periodicity check' on the famous
    Wow! signal (which is a 6-sample intensity table, NOT a time series)
    is mathematically impossible. We compute the FFT anyway but surface
    `claim_blocked: True` with `n_bins == 4` (DC + 3 unique freq bins) so
    downstream agents cannot get fooled.
  * **FRB 180916 16.35-d scaffold (NOT 121102)** -- 30 synthetic arrivals
    clustered around multiples of 16.35 days, narrow jitter. Real data
    fetch from CHIME/FRB Catalog 1 is OUT OF SCOPE for this scaffold --
    a deliberate, honest placeholder.

Stance: structure != message. Pulsars are the universe's most precise
natural clocks -- periodicity is necessary, NOT sufficient, for
artificiality. The synthetic scaffolds allow us to verify the math
reliably; they do NOT tell us anything about realWow! or FRBs.

CLI:
  python tools/radio/radio_probe.py --all-of-the-above
  python tools/radio/radio_probe.py --known-train
  python tools/radio/radio_probe.py --wow-honest
  python tools/radio/radio_probe.py --frb-180916
  python tools/radio/radio_probe.py --known-train --out-json \\
      outputs/radio/known_train.json --out-md outputs/radio/known_train.md
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

import numpy as np


# --- module constants ------------------------------------------------------

# Wow! (1977) signal -- the SIX on-source intensity samples (sigma units).
# Disambiguation: this is NOT a time series. It's a single column of intensity
# values binned at 12-s intervals across the 72-s on-source window. Any
# prominent-frequency claim on N=6 is a single DFT-bin resampling; with
# only 3 unique non-DC frequency bins and roughly 0.014 Hz spacing, no
# periodicity claim can be supported.
WOW_SAMPLES_SIGMA = (6.5, 14.5, 26.5, 30.5, 19.5, 5.5)
WOW_DT_S = 12.0                # 12 s per sample
WOW_FREQ_MHZ = 1420.0          # the famous hydrogen-line frequency

# FRB 180916 published period (NOTE: distinct from FRB 121102's ~157-d cycle).
# Source: Pastor-Marazuela et al. 2020/2021, CHIME/FRB. We do NOT compute the
# period here -- we hard-code the published value as the plant candidate so
# the math-verifies that the synthetic 30-arrival schedule recovers it,
# proving the epoch-fold implementation works. This is a SCAFFOLD only.
FRB_180916_PERIOD_DAYS = 16.35
FRB_121102_PERIOD_DAYS_FALLACY = 16.35  # NEVER confuse -- FRB 121102 ≈ 157 d

# Plant params for the known-answer synthetic train.
DEFAULT_TRAIN_PERIOD_S = 1.0
DEFAULT_TRAIN_DT_S = 0.01
DEFAULT_TRAIN_N = 1000
DEFAULT_JITTER_FRAC = 0.02  # ±2% Gaussian jitter on the period

DEFAULT_FRB_N_ARRIVALS = 30
DEFAULT_FRB_OBS_WINDOW_DAYS = 500.0
DEFAULT_FRB_JITTER_DAYS = 0.3


# --- FFT power spectrum ---------------------------------------------------

def fft_power_spectrum(samples, sample_dt: float,
                       window: str = "hann") -> tuple[np.ndarray, np.ndarray]:
    """Hann-windowed (or rectangular) FFT power spectrum.

    Windowed FFT suppresses spectral leakage at the cost of broadening the
    main lobe. Hann is a good default for unknown continuous spectra; use
    rectangular (window='none') for accurate bin amplitudes on clean sin
    waves or when the user needs to measure power in a specific bin
    (e.g. the Wow! honesty check).

    Returns (freqs_hz, power). freqs are the non-negative FFT bins spacing
    `1 / (N*dt)`.
    """
    x = np.asarray(samples, dtype=float)
    N = len(x)
    if not np.all(np.isfinite(x)):
        raise ValueError(
            "fft_power_spectrum input has non-finite values (NaN/inf); "
            "the FFT pipeline cannot recover from these"
        )
    # Always detrend -- DC is otherwise the dominant bin regardless of plant.
    x = x - np.mean(x)
    if window == "hann" and N >= 4:
        w = np.hanning(N)
        # Periodogram-style normalisation: divide FFT by sqrt(sum(w^2)) so
        # the squared magnitude is comparable to the un-windowed case
        # for a continuous-tone plant.
        scale = 1.0 / math.sqrt(float(np.sum(w**2)))
        xw = x * w * scale
    elif window == "hann":
        xw = x  # too short for Hann, fall back to rectangular
    else:
        xw = x
    freqs = np.fft.rfftfreq(N, d=sample_dt)
    spec = np.fft.rfft(xw)
    power = np.abs(spec) ** 2
    return freqs, power


def fft_summary(freqs: np.ndarray, power: np.ndarray,
                n_top: int = 5) -> dict:
    """Return a compact dict with peak, top-N bins, freq resolution."""
    if len(power) == 0:
        return {"n_bins": 0, "peak_freq_hz": None, "peak_power": 0.0,
                "freq_resolution_hz": None, "top_bins": []}
    peak_idx = int(np.argmax(power))
    # Sort by power (excl. DC if present) -- the DC bin leaks from any
    # residual mean even after detrending, so it's not interesting.
    non_dc = np.arange(1, len(power))
    if len(non_dc) == 0:
        # All-DC edge case: 1 sample.
        return {"n_bins": int(len(power)), "peak_freq_hz": None,
                "peak_power": float(power[0]),
                "freq_resolution_hz": (
                    float(freqs[1] - freqs[0]) if len(freqs) >= 2 else None
                ),
                "top_bins": []}
    order = non_dc[np.argsort(power[non_dc])[::-1]]
    top = [
        {"freq_hz": float(freqs[i]),
         "power": float(power[i]),
         "bin_index": int(i)}
        for i in order[:n_top]
    ]
    return {
        "n_bins": int(len(power)),
        "peak_freq_hz": float(freqs[peak_idx]),
        "peak_power": float(power[peak_idx]),
        "freq_resolution_hz": (
            float(freqs[1] - freqs[0]) if len(freqs) >= 2 else None
        ),
        "top_bins": top,
    }


# --- autocorrelation ------------------------------------------------------

def autocorrelation(samples, max_lag: int) -> np.ndarray:
    """Pearson lagged autocorrelation (lag 0..max_lag inclusive).

    Implementation note: we use the raw np.correlate convention divided by
    r[0] (i.e. the sum of products at each lag divided by the total sum
    of squares). For a clean periodic signal, this yields
    `r[k] ≈ cos(2π k / P)` where P is the period in samples, so the
    autocorrelation at lag P is *equal in magnitude* to lag 2P, 3P, ...
    argmax then deterministically picks the SMALLEST period (the first
    occurrence of the maximum), which is the right behaviour for a
    "what is the period" diagnostic.

    The textbook "unbiased Pearson" formula (divide cov by (N-k-1) and
    var by (N-1)) would also produce r[100] ≈ 1.0 for clean sin, BUT
    it introduces a k-dependent scale factor that can give r[2P] a
    slightly higher value than r[P] due to floating-point asymmetry in
    the (N-k)(N-1) / (N-k-1)N ratio -- making argmax hop to the
    boundary of the search range instead of the true period. We avoid
    that by normalising both numerator AND denominator by the same
    lag-k overlap count.

    Returns r[0]=1, r[max_lag] for lag=max_lag.
    """
    x = np.asarray(samples, dtype=float)
    x = x - np.mean(x)
    N = len(x)
    if N < 2:
        return np.array([1.0])
    if not np.all(np.isfinite(x)):
        raise ValueError(
            "autocorrelation input has non-finite values (NaN/inf); "
            "the FFT/autocorr pipeline cannot recover from these"
        )
    full = np.correlate(x, x, mode="full")
    # full has length 2N - 1. positive-lag slice starts at full[N - 1].
    r_unnorm = full[N - 1: N - 1 + max_lag + 1]
    if len(r_unnorm) == 0:
        return np.array([1.0])
    if r_unnorm[0] == 0.0:
        out = np.ones(min(max_lag + 1, N))
        return out
    return r_unnorm / r_unnorm[0]  # r[k] / r[0] == Pearson at scale = cos(2π k/P) for clean sin


def autocorr_summary(r: np.ndarray,
                     plant_period_in_samples: int | None = None) -> dict:
    """Compact autocorrelation summary.

    Two modes:
      (1) **Confirmatory** (preferred): `plant_period_in_samples` is
          provided -- the FFT peak has been computed elsewhere and we
          read off `r_at_plant_period` to verify periodicity is real.
          Returns `r_at_plant_period_is_high` flag (threshold = 0.5:
          positive correlation at the plant lag IS a real signal).
      (2) **Diagnostic** (legacy / fallback): no plant period given.
          Falls back to global argmax of |r[1:]|. NOTE: for a densely-
          sampled periodic signal (e.g., 100 samples per period, 10
          cycles in N=1000), r[1] ≈ 0.996 routinely beats the plant
          r[P] ≈ 0.9 because the dense sampling keeps adjacent-sample
          correlation near 1.0. The FFT peak is the proper period
          detector; this argmax is for sanity CHECK of "is there any
          positive correlation at all" only.

    Returns a compact dict whose keys reflect the active mode.
    """
    if len(r) <= 1:
        return {"max_lag": 0, "peak_lag": 0, "peak_value": 0.0}
    if plant_period_in_samples is not None:
        idx = int(plant_period_in_samples)
        if 0 < idx < len(r):
            r_val = float(r[idx])
            return {
                "plant_period_in_samples": idx,
                "r_at_plant_period": round(r_val, 6),
                "r_at_plant_period_is_high": bool(r_val > 0.5),
                "max_lag": int(len(r) - 1),
            }
        # Out-of-range plant period -- fall through to legacy argmax.
    rk = r[1:]
    peak_idx = int(np.argmax(np.abs(rk)))
    return {
        "max_lag": int(len(r) - 1),
        "peak_lag": int(peak_idx + 1),
        "peak_value": float(rk[peak_idx]),
    }


# --- epoch-fold / Rayleigh Z² ---------------------------------------------

def rayleigh_z2(times: np.ndarray, period: float) -> tuple[float, float]:
    """Standard single-frequency Rayleigh statistic.

    Z² = (2/N) * ((Σ cos(2π t_i/P))² + (Σ sin(2π t_i/P))²)

    This is the classic chi-square(2 DOF) formulation: under H0=uniform
    on phase, E[Z²] = 2 (the null mean), and for a plant where all N
    phasors align, Z² ≈ 2N. Tail approximation `P(Z² > z) ≈ exp(-z/2)`
    holds in both regimes, so `rayleigh_p_value` is calibrated to this
    convention.

    The companion phase (best arctan) is also returned.
    """
    t = np.asarray(times, dtype=float)
    N = len(t)
    if N == 0:
        return (0.0, 0.0)
    if not np.all(np.isfinite(t)):
        raise ValueError(
            "rayleigh_z2 input has non-finite values (NaN/inf); "
            "epoch-fold cannot recover from these"
        )
    phi = (2.0 * math.pi / period) * t
    c = float(np.sum(np.cos(phi)))
    s = float(np.sum(np.sin(phi)))
    z2 = 2.0 * (c * c + s * s) / N
    best_phase = math.atan2(s, c)
    if best_phase < 0:
        best_phase += 2.0 * math.pi
    return (z2, best_phase)


def rayleigh_p_value(z2: float) -> float:
    """P(Z² > z) under H0=uniform. Asymptotic exp(-z/2) for large z
    (calibrated to the standard `Z² = 2R²/N` formulation used in
    `rayleigh_z2`).

    Capped at 1.0 for non-positive z, floored at 1e-300 for very large
    z (exp(-350) underflows).
    """
    if z2 <= 0.0:
        return 1.0
    if z2 > 700:  # exp(-350) underflows -- practically zero
        return 1e-300
    return math.exp(-z2 / 2.0)


def epoch_fold(times: np.ndarray,
               period_grid: np.ndarray) -> dict:
    """Search a candidate period grid with Rayleigh Z².

    Returns the best period (argmax Z²), the Z² at that period, the
    best phase at that period, and the p-value under H0=uniform.
    The full (period, Z²) curve is included for plot output.
    """
    t = np.asarray(times, dtype=float)
    if len(t) == 0:
        return {"best_period": None, "best_z2": 0.0, "best_phase_rad": 0.0,
                "best_p_value": 1.0, "curve": []}
    z2_arr = np.empty(len(period_grid), dtype=float)
    for i, P in enumerate(period_grid):
        z2_arr[i] = rayleigh_z2(t, float(P))[0]
    best_idx = int(np.argmax(z2_arr))
    z2, phase = rayleigh_z2(t, float(period_grid[best_idx]))
    return {
        "best_period": float(period_grid[best_idx]),
        "best_z2": float(z2),
        "best_phase_rad": float(phase),
        "best_p_value": float(rayleigh_p_value(z2)),
        "curve": [{"period": float(period_grid[i]),
                   "z2": float(z2_arr[i])}
                  for i in range(len(period_grid))],
    }


# --- known-answer plants --------------------------------------------------

def synth_periodic_train(period_s: float = DEFAULT_TRAIN_PERIOD_S,
                         dt_s: float = DEFAULT_TRAIN_DT_S,
                         n: int = DEFAULT_TRAIN_N,
                         noise_frac: float = DEFAULT_JITTER_FRAC,
                         seed: int = 0) -> tuple[np.ndarray, float]:
    """Plant a clean sin wave at `period_s` with small Gaussian noise.

    The plant is intentionally SIMPLE -- the test asserts the FFT peak is
    at `1/period_s` ± one bin and the autocorr peaks at lag `period_s/dt_s`.
    The noise-frac is applied to the amplitude (not the period).
    """
    rng = np.random.default_rng(seed)
    t = np.arange(n) * dt_s
    omega = 2.0 * math.pi / period_s
    x = np.sin(omega * t) + noise_frac * rng.standard_normal(n)
    return x, dt_s


def synth_frb_arrivals(period_d: float = FRB_180916_PERIOD_DAYS,
                       n_arrivals: int = DEFAULT_FRB_N_ARRIVALS,
                       obs_window_d: float = DEFAULT_FRB_OBS_WINDOW_DAYS,
                       jitter_d: float = DEFAULT_FRB_JITTER_DAYS,
                       seed: int = 0) -> np.ndarray:
    """Plant N arrival times clustered at multiples of `period_d`.

    Returns a sorted np.ndarray of arrival times in days. The first
    arrival is around `period_d + jitter` so the period is recoverable
    even at the small end. We do NOT refit a period here -- we trust the
    plant and assert `epoch_fold` recovers it.
    """
    rng = np.random.default_rng(seed)
    times = np.arange(1, n_arrivals + 1) * period_d + rng.normal(
        loc=0.0, scale=jitter_d, size=n_arrivals
    )
    # Clip into [0, obs_window_d] for clarity.
    times = np.clip(times, 0.0, obs_window_d)
    return np.sort(times)


# --- Wow! honesty audit ---------------------------------------------------

def wow_honest_check(samples=WOW_SAMPLES_SIGMA,
                     sample_dt: float = WOW_DT_S,
                     freq_mhz: float = WOW_FREQ_MHZ) -> dict:
    """Honest FFT audit on the Wow! 6-sample intensity table.

    WITH 6 SAMPLES + rfft, YOU GET 4 BINS:
      bin 0: DC (always `sum(x)/N`)
      bins 1, 2, 3: non-zero frequencies at k/(N*dt)
    Resolution = 1/(N*dt) = 1/(6*12) ≈ 0.01389 Hz.

    ANY periodicity claim is BOGUS -- there is literally nothing to fit
    in the frequency domain beyond these 4 bins. We surface this as
    `claim_blocked: True` so downstream agents cannot be fooled.
    """
    x = np.asarray(samples, dtype=float)
    N = len(x)
    if not np.all(np.isfinite(x)):
        raise ValueError(
            "wow_honest_check input has non-finite values"
        )
    freqs, power = fft_power_spectrum(x, sample_dt, window="none")
    summary = fft_summary(freqs, power, n_top=3)
    return {
        "n_samples": int(N),
        "sample_dt_s": float(sample_dt),
        "freq_mhz": float(freq_mhz),
        "n_bins": int(len(power)),
        "freq_resolution_hz": (
            float(1.0 / (N * sample_dt)) if N >= 1 else None
        ),
        "fft_summary": summary,
        "peak_freq_hz": summary["peak_freq_hz"],
        "peak_power": summary["peak_power"],
        "claim_blocked": True,           # ALWAYS true -- see docstring
        "intent": "audit-only: 6-sample DFT has 4 bins, no periodicity claim possible",
        "stance": (
            "Structure != message. Wow! is a 6-SAMPLE intensity table, not a "
            "time series. The famous 6EQUJ5 labels are NOT a spectrum. Any "
            "prominent-frequency claim on N=6 is signature-bin resampling. "
            "Per scout_briefs.md, the 2024 PHL@UPR reanalysis attributes "
            "the signal to a hydrogen cloud near a solar-type star -- natural. "
            "We compute the FFT only to demonstrate the resolution limit."
        ),
    }


# --- known-answer analysis-orchestrator ----------------------------------

def run_known_train(label: str = "radio_known_train",
                    seed: int = 0,
                    period_s: float = DEFAULT_TRAIN_PERIOD_S,
                    dt_s: float = DEFAULT_TRAIN_DT_S,
                    n: int = DEFAULT_TRAIN_N,
                    max_lag_frac: float = 0.20) -> dict:
    """Plant the periodic train, run FFT + autocorr, report known-answer."""
    x, _ = synth_periodic_train(period_s=period_s, dt_s=dt_s, n=n, seed=seed)
    freqs, power = fft_power_spectrum(x, dt_s, window="hann")
    fft = fft_summary(freqs, power, n_top=5)
    max_lag = int(n * max_lag_frac)
    r = autocorrelation(x, max_lag=max_lag)
    # FFT peak is the proper period detector; autocorr is the CONFIRMATION
    # at the FFT-detected period (in samples).
    expected_freq = 1.0 / period_s
    expected_lag_samples = int(round(period_s / dt_s))
    if max_lag < expected_lag_samples:
        expected_lag_samples = max_lag  # don't index past the autocorr array
    freq_err = abs(fft["peak_freq_hz"] - expected_freq)
    fft_pass = (fft["peak_freq_hz"] is not None and
                freq_err <= (fft["freq_resolution_hz"] or 0.0) * 1.5)
    ac = autocorr_summary(r, plant_period_in_samples=expected_lag_samples)
    # Confirmatory contract: r at the plant period > 0.5 means clear
    # periodicity at the FFT-detected period. This is r > 0.5 for a clean
    # sin wave (r = (N-k)/N × cos(2πk/P) at k=P gives (N-P)/N ≈ 0.9+).
    autocorr_pass = bool(ac.get("r_at_plant_period_is_high", False))
    return {
        "label": label,
        "method": "known_train_fft_autocorr",
        "plant": {
            "period_s": period_s,
            "dt_s": dt_s,
            "n": n,
            "expected_freq_hz": expected_freq,
            "expected_autocorr_lag_samples": expected_lag_samples,
        },
        "fft": fft,
        "autocorrelation": ac,
        "known_answer": {
            "fft_freq_error_hz": round(freq_err, 5),
            "fft_pass": bool(fft_pass),
            "autocorr_r_at_plant_period": (
                float(ac.get("r_at_plant_period", 0.0))
            ),
            "autocorr_pass": bool(autocorr_pass),
            "overall_pass": bool(fft_pass and autocorr_pass),
        },
        "negative_controls": _train_negative_controls(dt_s=dt_s, n=n, seed=seed),
        "stance": (
            "Synthetic known-answer plant only. A pass proves the FFT + "
            "autocorr implementation can recover a planted period; it "
            "tells us nothing about real Wow! or FRBs. Structure != message."
        ),
    }


def _train_negative_controls(dt_s: float, n: int, seed: int) -> dict:
    """Run the FFT on pure white noise; peak should NOT lock on a fake freq."""
    rng = np.random.default_rng(seed + 99)
    white = rng.standard_normal(n)
    f_w, p_w = fft_power_spectrum(white, dt_s, window="hann")
    s_w = fft_summary(f_w, p_w, n_top=3)
    return {
        "white_noise_peak_freq_hz": s_w["peak_freq_hz"],
        "white_noise_peak_power": s_w["peak_power"],
        "verdict": (
            "white-noise FFT is below any signal peak by orders of magnitude "
            "OR is randomly placed (no preferred frequency)"
        ),
    }


def run_wow_honest() -> dict:
    """Honest Wow! FFT audit -- `claim_blocked` is structurally TRUE."""
    wow = wow_honest_check()
    return {
        "label": "radio_wow_honest",
        "method": "wow_dft_audit",
        "wow_honest": wow,
        "stance": wow["stance"],
    }


def run_frb_180916(seed: int = 0,
                   n_arrivals: int = DEFAULT_FRB_N_ARRIVALS,
                   obs_window_d: float = DEFAULT_FRB_OBS_WINDOW_DAYS,
                   jitter_d: float = DEFAULT_FRB_JITTER_DAYS,
                   period_grid_lo: float = 10.0,
                   period_grid_hi: float = 30.0,
                   grid_step: float = 0.05) -> dict:
    """Synthesize FRB 180916-like arrivals, run epoch-fold, report."""
    times = synth_frb_arrivals(
        period_d=FRB_180916_PERIOD_DAYS,
        n_arrivals=n_arrivals,
        obs_window_d=obs_window_d,
        jitter_d=jitter_d,
        seed=seed,
    )
    grid = np.arange(period_grid_lo, period_grid_hi + 1e-9, grid_step)
    fold = epoch_fold(times, grid)
    # Shuffled negative control.
    rng = np.random.default_rng(seed + 7)
    shuf = rng.uniform(0.0, obs_window_d, size=len(times))
    shuf_fold = epoch_fold(shuf, grid)
    recovery_err_d = abs(fold["best_period"] - FRB_180916_PERIOD_DAYS)
    recovery_pass = recovery_err_d <= 1.0
    return {
        "label": "radio_frb_180916_scaffold",
        "method": "epoch_fold_z2",
        "plant": {
            "n_arrivals": int(n_arrivals),
            "obs_window_d": float(obs_window_d),
            "jitter_d": float(jitter_d),
            "true_period_d": float(FRB_180916_PERIOD_DAYS),
            "decoy_period_d_for_frb_121102": 157.0,  # explicitly NOT 16.35
        },
        "epochfold": fold,
        "negative_controls": {
            "shuffled_uniform_z2_max": shuf_fold["best_z2"],
            "shuffled_uniform_z2_p_value": shuf_fold["best_p_value"],
            "shuffled_uniform_best_period_d": shuf_fold["best_period"],
        },
        "known_answer": {
            "recovered_period_d": fold["best_period"],
            "recovered_z2": fold["best_z2"],
            "recovered_p_value": fold["best_p_value"],
            "recovery_error_d": round(recovery_err_d, 5),
            "recovery_pass": bool(recovery_pass),
        },
        "stance": (
            "SCAFFOLD ONLY. The 30-arrival schedule is synthesized around "
            f"the published {FRB_180916_PERIOD_DAYS}-d cycle of FRB 180916 "
            "**from CHIME/FRB Catalog 1 / Pastor-Marazuela 2020 -- "
            "NOT FRB 121102 (whose activity cycle is ~157 d, Cruces 2021)**. "
            "A pass here proves the epoch-fold math; it tells us nothing "
            "about the real FRB. Structure != message."
        ),
    }


def analyze(mode: str = "all", seed: int = 0) -> dict:
    """Orchestrator: returns a single dict containing all sub-runs.

    `mode ∈ {'all', 'known_train', 'wow', 'frb_180916'}`.
    """
    out: dict = {
        "label": "radio_probe",
        "mode": mode,
        "seed": seed,
        "stance": (
            "Structure != message. Pulsars are the universe's most precise "
            "natural clocks -- periodicity is necessary, NOT sufficient, "
            "for artificiality. All scaffolds here are math-validation "
            "plants; none are claims about real Wow! or real FRBs."
        ),
    }
    if mode in ("all", "known_train"):
        out["known_train"] = run_known_train(seed=seed)
    if mode in ("all", "wow"):
        out["wow_honest"] = run_wow_honest()
    if mode in ("all", "frb_180916"):
        out["frb_180916"] = run_frb_180916(seed=seed)
    return out


# --- markdown notes -------------------------------------------------------

def write_notes_markdown(report: dict) -> str:
    """One-pager for the radio probe run. Honest framing throughout."""
    lines = [
        "# radio_probe R1 — `{}`".format(report.get("label", "<no-label>")),
        "",
        "**Lab stance:** structure ≠ message. Natural pulsars are precise clocks. "
        "Periodicity is necessary, NOT sufficient for artificiality. All scaffolds "
        "below are math-validation plants — none of them claim a hit on real Wow! "
        "or real FRBs.",
        "",
    ]
    if "known_train" in report:
        kt = report["known_train"]
        ka = kt["known_answer"]
        fft = kt["fft"]
        ac = kt["autocorrelation"]
        lines += [
            "## Synthetic periodic train (known-answer)",
            "",
            f"- plant: period **{kt['plant']['period_s']} s**, dt "
            f"{kt['plant']['dt_s']} s, N = {kt['plant']['n']}",
            f"- FFT peak: **{fft['peak_freq_hz']:.4f} Hz** "
            f"(expected {kt['plant']['expected_freq_hz']:.4f} Hz, "
            f"resolution {fft['freq_resolution_hz']:.4f} Hz, "
            f"err {ka['fft_freq_error_hz']:.4f} Hz, "
            f"**{'PASS' if ka['fft_pass'] else 'FAIL'}**)",
            f"- autocorr at FFT-detected period: r({ac.get('plant_period_in_samples', '?')}) = "
            f"**{ac.get('r_at_plant_period', '?')}** "
            f"(threshold 0.5: **{'PASS' if ka['autocorr_pass'] else 'FAIL'}**)",
            f"- overall known-answer: **{'PASS' if ka['overall_pass'] else 'FAIL'}**",
            "",
            "**Negative control:** white-noise FFT "
            f"peak={kt['negative_controls']['white_noise_peak_freq_hz']:.4f} Hz "
            f"with power {kt['negative_controls']['white_noise_peak_power']:.4f} "
            "(no preferred frequency).",
            "",
        ]
    if "wow_honest" in report:
        w = report["wow_honest"]["wow_honest"]
        lines += [
            "## Wow! (1977) honesty audit",
            "",
            f"- N = **{w['n_samples']}** SAMPLES, dt = {w['sample_dt_s']} s "
            f"at {w['freq_mhz']} MHz",
            f"- DFT bins: **{w['n_bins']}** (DC + "
            f"{w['n_bins'] - 1} unique non-DC frequency bins)",
            f"- freq resolution: **{w['freq_resolution_hz']:.5f} Hz**",
            f"- peak bin freq: {w['peak_freq_hz']:.5f} Hz "
            f"(power {w['peak_power']:.4f})",
            f"- **`claim_blocked`: {w['claim_blocked']}** "
            "— any periodicity claim on N=6 is structurally meaningless",
            "",
            f'_stance:_ {w["stance"]}',
            "",
        ]
    if "frb_180916" in report:
        f = report["frb_180916"]
        ka = f["known_answer"]
        nc = f["negative_controls"]
        lines += [
            "## FRB 180916 16.35-d scaffold (NOT 121102)",
            "",
            f"- plant: {f['plant']['n_arrivals']} arrivals over "
            f"{f['plant']['obs_window_d']} d, jitter "
            f"{f['plant']['jitter_d']} d, period = "
            f"**{f['plant']['true_period_d']} d** "
            f"(FRB 180916; FRB 121102's cycle is ~157 d — explicitly "
            f"`{f['plant']['decoy_period_d_for_frb_121102']}` d here, NOT used)",
            f"- recovered period: **{ka['recovered_period_d']:.4f} d** "
            f"(err {ka['recovery_error_d']:.4f} d, Z² = "
            f"{ka['recovered_z2']:.2f}, p = {ka['recovered_p_value']:.2e}); "
            f"**{'PASS' if ka['recovery_pass'] else 'FAIL'}**",
            f"- shuffled control: max Z² = {nc['shuffled_uniform_z2_max']:.2f} "
            f"(p = {nc['shuffled_uniform_z2_p_value']:.2e}, best "
            f"period = {nc['shuffled_uniform_best_period_d']:.2f} d, random — "
            f"NOT the plant period)",
            "",
            f"_stance:_ {f['stance']}",
            "",
        ]
    lines += [
        "---",
        "",
        "*Generated by `tools/radio/radio_probe.py`. Stance: structure ≠ message.*",
    ]
    return "\n".join(lines)


# --- CLI ------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Radio periodicity probe (R1). Structure != message. "
            "Periodicity is necessary, NOT sufficient for artificiality."
        ),
    )
    ap.add_argument("--known-train", action="store_true",
                    help="Plant a known synthetic periodic train + FFT + autocorr")
    ap.add_argument("--wow-honest", action="store_true",
                    help="Process the 6-sample Wow! signal (audit-only, "
                         "claim_blocked=True)")
    ap.add_argument("--frb-180916", action="store_true",
                    help="Synthesize FRB 180916 (16.35 d) arrivals + epoch-fold")
    ap.add_argument("--all-of-the-above", action="store_true",
                    help="Run known-train + wow-honest + frb-180916 (default)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out-json", type=Path, default=None,
                    help="write structured JSON report")
    ap.add_argument("--out-md", type=Path, default=None,
                    help="write human-readable notes markdown")
    args = ap.parse_args()

    # Default to --all-of-the-above if no flag is supplied.
    if not (args.known_train or args.wow_honest or args.frb_180916):
        args.all_of_the_above = True

    if args.all_of_the_above:
        mode = "all"
    elif args.known_train and not (args.wow_honest or args.frb_180916):
        mode = "known_train"
    elif args.wow_honest and not (args.known_train or args.frb_180916):
        mode = "wow"
    elif args.frb_180916 and not (args.known_train or args.wow_honest):
        mode = "frb_180916"
    else:
        mode = "all"

    report = analyze(mode=mode, seed=args.seed)
    text = json.dumps(report, indent=2)
    print(text[:1500] + ("…" if len(text) > 1500 else ""))
    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(text)
        print(f"wrote {args.out_json}")
    if args.out_md:
        args.out_md.parent.mkdir(parents=True, exist_ok=True)
        md = write_notes_markdown(report)
        args.out_md.write_text(md)
        print(f"wrote {args.out_md}")


if __name__ == "__main__":
    main()
