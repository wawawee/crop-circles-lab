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
  * **FRB 180916 16.35-d SCAFFOLD (synthetic) vs REAL-DATA path**:
      - `--frb-180916` / `--frb-180916-synthetic` plants 30 synthetic
        arrivals around multiples of 16.35 d. This is a math-validation
        tool (epoch-fold math recovers the plant). It tells us nothing
        about the real FRB. Structure != message.
      - `--frb-180916-real` calls chime_frb_fetcher + frb_real_sources to
        fetch the actual CHIME/FRB Catalog 1 CSV. As of 2026-07-25 the
        canonical mirror is offline (HTML parking page). The fetcher
        surfaces `fetch_status: UNREACHABLE/PARKING` -- it NEVER silently
        fabricates. Use `--bundled-mjd-json <file>` to inject a real
        transcribed table.

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

# Real-data path supports (best-effort imports so the script remains
# runnable in older environments without the sub-modules).
try:
    import chime_frb_fetcher as CFF  # noqa: E402
except ImportError:  # pragma: no cover
    CFF = None
try:
    import frb_real_sources as FRS  # noqa: E402
except ImportError:  # pragma: no cover
    FRS = None
try:
    import pulsar_fetcher as PUL  # noqa: E402
except ImportError:  # pragma: no cover
    PUL = None


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

# Vela pulsar (PSR B0833-45 / J0835-4510) constants.
# Source: ATNF Pulsar Catalogue (Manchester et al. 2005 AJ 129 1993,
# DOI 10.1086/428488). We hardcode the canonical period + bibliographic
# metadata (public-domain knowledge); we do NOT hardcode bulk arrival
# times (that would be silent fabrication). Vela has spin-down and
# occasional glitches; the canonical P0 below is the catalogue mean at
# the epoch. Manchester+2005 + PPTA DR3 (Zic et al. 2023) for context.
VELA_PSR_B1950 = "B0833-45"
VELA_PSR_J2000 = "J0835-4510"
VELA_P0_PUBLISHED_S = 0.089328385507       # ~89.328 ms
VELA_F0_PUBLISHED_HZ = 1.0 / VELA_P0_PUBLISHED_S  # ~11.192 Hz
VELA_BIBCODE_PSRCAT = "2005AJ....129.1993M"
VELA_BIBCODE_PPTA_DR3 = "2023PASA...40...49Z"
VELA_DATA_LICENSE = "CC BY 4.0 (ATNF Pulsar Catalogue; PPTA Data Releases)"

# Vela synthetic-plant defaults. The jitter is exactly 1 microsecond,
# well below Vela's known timing noise floor (~50 microseconds typical,
# due to intrinsic noise and DM smearing). This means synthetic
# arrivals are MORE coherent than real Vela, which deliberately biases
# even harder toward "the math detects structure". The lab motto
# insists we do NOT mistake that for "ET".
DEFAULT_VELA_N_ARRIVALS = 30
DEFAULT_VELA_OBS_WINDOW_DAYS = 365.0   # ~1 year of pulses
DEFAULT_VELA_JITTER_S = 1e-6           # ±1 microsecond synthetic jitter
DEFAULT_VELA_GRID_DELTA_S = 1e-5      # ±10 microseconds around VELA_P0
DEFAULT_VELA_GRID_STEPS = 1001


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


# --- Vela pulsar synthetic plant + real-data path ------------------------
# Vela's role is the lab-motto NATURAL-CLOCK ANCHOR: even when the math
# detects its period cleanly, the canonical conclusion is "this is a
# natural pulsar", NOT "this is artificial". Periodicity is necessary,
# NOT sufficient for artificiality.

def synth_pulsar_vela_arrivals(
    period_s: float = VELA_P0_PUBLISHED_S,
    n_arrivals: int = DEFAULT_VELA_N_ARRIVALS,
    obs_window_d: float = DEFAULT_VELA_OBS_WINDOW_DAYS,
    jitter_s: float = DEFAULT_VELA_JITTER_S,
    seed: int = 0,
    mjd0: float = 58000.0,
) -> np.ndarray:
    """Plant N arrival MJDs at multiples of VELA_P0 (strictly periodic).

    Synthetic Vela WITHOUT glue: no spin-down, no glitches, no DM
    smearing, no intrinsic timing noise. The plant is therefore MORE
    coherent than real Vela, deliberately biasing the math detection
    (Z² = 2N) toward maximum. Real Vela has ~50 microsecond timing
    noise and ~hour-long spin-down fringes over years.

    Returns sorted MJDs. Period in SECONDS; we convert from MJDs to
    seconds at the orchestrator level (since P0 is sub-millisecond).
    """
    rng = np.random.default_rng(seed)
    phases = np.arange(1, n_arrivals + 1).astype(float)
    times_s = phases * float(period_s)
    times_s = times_s + rng.normal(loc=0.0, scale=float(jitter_s),
                                     size=n_arrivals)
    mjds = float(mjd0) + times_s / 86400.0
    return np.sort(mjds)


def run_pulsar_vela_synthetic(
    seed: int = 0,
    n_arrivals: int = DEFAULT_VELA_N_ARRIVALS,
    obs_window_d: float = DEFAULT_VELA_OBS_WINDOW_DAYS,
    jitter_s: float = DEFAULT_VELA_JITTER_S,
    period_grid_delta_s: float = DEFAULT_VELA_GRID_DELTA_S,
    period_grid_steps: int = DEFAULT_VELA_GRID_STEPS,
) -> dict:
    """Vela positive-control known-answer plant.

    Plants 30 synthetic arrival MJDs at multiples of VELA_P0 and runs
    the standard epoch-fold on (mjd * 86400) in SECONDS with a tight
    grid around VELA_P0. Recovery tolerance: |best - P0| <= 5e-6 s
    (~5 microseconds, well below the synthetic jitter envelope).

    Lab motto: a PASS proves the math; it tells us NOTHING about real
    Vela, AND it does NOT imply artificial origin. Vela's period is
    real and natural (Manchester+2005; PPTA DR3).
    """
    mjds = synth_pulsar_vela_arrivals(
        n_arrivals=n_arrivals,
        obs_window_d=obs_window_d,
        jitter_s=jitter_s,
        seed=seed,
    )
    times_s = mjds * 86400.0
    obs_window_s = float(times_s.max() - times_s.min()) \
        if len(times_s) >= 2 else float(times_s.max()) * 2.0
    grid = np.linspace(
        VELA_P0_PUBLISHED_S - float(period_grid_delta_s),
        VELA_P0_PUBLISHED_S + float(period_grid_delta_s),
        int(period_grid_steps),
    )
    fold = epoch_fold(times_s, grid)
    rng = np.random.default_rng(seed + 17)
    shuf_s = rng.uniform(0.0, obs_window_s, size=len(times_s))
    shuf_fold = epoch_fold(shuf_s, grid)
    recovery_err_s = abs(fold["best_period"] - VELA_P0_PUBLISHED_S)
    return {
        "label": "radio_pulsar_vela_synthetic",
        "method": "vela_synthetic_epoch_fold_z2",
        "plant": {
            "psr_b1950": VELA_PSR_B1950,
            "psr_j2000": VELA_PSR_J2000,
            "true_period_s": float(VELA_P0_PUBLISHED_S),
            "true_freq_hz": float(VELA_F0_PUBLISHED_HZ),
            "n_arrivals": int(n_arrivals),
            "obs_window_d": float(obs_window_d),
            "jitter_s": float(jitter_s),
            "decoy_period_s_grb_afterglow": 0.0897,  # NOT used; FRB-like
        },
        "epochfold": fold,
        "negative_controls": {
            "shuffled_uniform_z2_max": shuf_fold["best_z2"],
            "shuffled_uniform_z2_p_value": shuf_fold["best_p_value"],
            "shuffled_uniform_best_period_s": shuf_fold["best_period"],
        },
        "known_answer": {
            "recovered_period_s": fold["best_period"],
            "recovered_z2": fold["best_z2"],
            "recovered_p_value": fold["best_p_value"],
            "recovery_error_s": float(recovery_err_s),
            "recovery_pass": bool(recovery_err_s <= 5e-6),
        },
        "lab_motto_anchor": (
            "Structure != message. Vela is the universe's most "
            "famous NATURAL clock. Periodicity (here detected at "
            "P0 with high Z²) is NECESSARY, NOT SUFFICIENT, for "
            "artificiality. A recovery_pass here proves the FFT/"
            "autocorr/epoch-fold math is implemented correctly; "
            "it does NOT mean we have detected an artificial signal."
        ),
        "stance": (
            "SYNTHETIC Vela positive-control known-answer. Plant "
            "EXCLUDES Vela's real-world spin-down and glitches "
            "(1988/1991/1994/1996/1997/1998/1999/2000/2003). "
            "Lab motto: periodicity is necessary, NOT sufficient "
            "for artificiality. Manchester+2005; PPTA DR3 (Zic+2023)."
        ),
    }


def run_pulsar_vela(
    bundled_csv_path: Path | None = None,
    seed: int = 0,
    period_grid_delta_s: float = DEFAULT_VELA_GRID_DELTA_S,
    period_grid_steps: int = DEFAULT_VELA_GRID_STEPS,
    force_status_for_tests: str | None = None,
) -> dict:
    """REAL-DATA Vela positive-control path.

    Loads Vela arrival MJDs from pulsar_fetcher (or --bundled-pulsar-csv
    override). Converts to seconds, runs epoch-fold around the
    published P0. NEVER fabricates: if the live fetch failed AND no
    bundled fallback is given, returns the warnings-block WITHOUT
    running the math.
    """
    if PUL is None:
        return _vela_module_missing()
    result = PUL.try_fetch_atnf_pulsar_vela_timing(
        force_status_for_tests=force_status_for_tests,
    )
    base_plant = {
        "psr_b1950": VELA_PSR_B1950,
        "psr_j2000": VELA_PSR_J2000,
        "true_period_s": float(VELA_P0_PUBLISHED_S),
        "true_freq_hz": float(VELA_F0_PUBLISHED_HZ),
        "period_grid_delta_s": float(period_grid_delta_s),
        "period_grid_steps": int(period_grid_steps),
        "license": VELA_DATA_LICENSE,
        "data_units": "arrival MJDs converted to seconds: t_s = mjd * 86400",
    }
    # Bundled override path
    if bundled_csv_path is not None:
        bundle = PUL.load_bundled_pulsar_csv(Path(bundled_csv_path))
        if bundle.error is not None:
            return {
                "label": "pulsar_vela_real_data",
                "method": "vela_real_epoch_fold_z2",
                "data_source": f"bundled_csv={bundled_csv_path}",
                "source_type": "bundled_attempt",
                "fetch_status": "USER_OVERRIDE_INVALID",
                "ref_bibcode": VELA_BIBCODE_PSRCAT,
                "ref_url": "https://www.atnf.csiro.au/research/pulsar/psrcat/",
                "fetched_from": str(bundled_csv_path),
                "fetch_attempts": [],
                "n_arrivals": 0,
                "license": VELA_DATA_LICENSE,
                "provenance_note": (
                    f"--bundled-pulsar-csv {bundled_csv_path} failed to "
                    f"parse: {bundle.error}. Falling back to empty. "
                    "NO synthetic plant was used."
                ),
                "plant": base_plant,
                "epochfold": None,
                "negative_controls": None,
                "known_answer": None,
                "warnings": [f"--bundled-pulsar-csv {bundled_csv_path} did not "
                              "parse. Honest empty fallback."],
                "stance": _vela_motto_stance(),
            }
        if bundle.has_mjds:
            return _vela_run_epoch_fold(
                mjds=np.asarray(bundle.mjds, dtype=float),
                data_source=str(bundled_csv_path),
                source_type="bundled_override",
                fetch_status="USER_OVERRIDE",
                seed=seed,
                base_plant=base_plant,
                period_grid_delta_s=period_grid_delta_s,
                period_grid_steps=period_grid_steps,
            )
    # Empty-MJDs branch (live fetch failed, no override given)
    if not result.arrival_mjds_vela:
        return {
            "label": "pulsar_vela_real_data",
            "method": "vela_real_epoch_fold_z2",
            "data_source": "ATNF Pulsar Catalogue (Manchester+ 2005)",
            "source_type": "empty",
            "fetch_status": result.fetch_status,
            "ref_bibcode": VELA_BIBCODE_PSRCAT,
            "ref_url": "https://www.atnf.csiro.au/research/pulsar/psrcat/",
            "fetched_from": result.fetched_from,
            "fetch_attempts": [
                a if isinstance(a, dict) else a.to_dict()
                for a in result.attempts
            ],
            "n_arrivals": 0,
            "license": VELA_DATA_LICENSE,
            "provenance_note": (
                f"Live ATNF/Parkes Vela fetch returned "
                f"{result.fetch_status}. NO MJDs obtained. Fetched: "
                f"{len(result.attempts)} canonical URL(s); no structured "
                "CSV was returned. The bundled PPTA table is "
                "intentionally empty (extraction pending, manual "
                "transcription required)."
            ),
            "plant": base_plant,
            "epochfold": None,
            "negative_controls": None,
            "known_answer": None,
            "warnings": [
                "no real-data path attempted because the Vela arrival "
                "source returned zero MJDs. NO synthetic plant was used.",
                f"live fetch_status: {result.fetch_status}",
                "to populate: pass --bundled-pulsar-csv with a CSV "
                "header `name,mjd` of arrival MJDs transcribed from a "
                "PPTA data-release paper (e.g., Manchester+2005 AJ 129 "
                "1993 cita at DOI 10.1086/428488).",
            ],
            "stance": _vela_motto_stance(),
        }
    # Got MJDs from the live fetch path.
    return _vela_run_epoch_fold(
        mjds=np.asarray(result.arrival_mjds_vela, dtype=float),
        data_source=result.fetched_from or "ATNF Pulsar Catalogue",
        source_type="atnf_pulsar_catalogue",
        fetch_status=result.fetch_status,
        seed=seed,
        base_plant=base_plant,
        period_grid_delta_s=period_grid_delta_s,
        period_grid_steps=period_grid_steps,
    )


def _vela_run_epoch_fold(
    mjds, data_source, source_type, fetch_status, seed,
    base_plant, period_grid_delta_s, period_grid_steps,
) -> dict:
    """Inner helper: given Vela MJDs, run the second-precision epoch-fold."""
    times_s = mjds * 86400.0
    obs_window_s = float(times_s.max() - times_s.min()) \
        if len(times_s) >= 2 else float(times_s.max()) * 2.0
    grid = np.linspace(
        VELA_P0_PUBLISHED_S - float(period_grid_delta_s),
        VELA_P0_PUBLISHED_S + float(period_grid_delta_s),
        int(period_grid_steps),
    )
    fold = epoch_fold(times_s, grid)
    rng = np.random.default_rng(seed + 23)
    shuf_s = rng.uniform(0.0, obs_window_s, size=len(times_s))
    shuf_fold = epoch_fold(shuf_s, grid)
    recovery_err_s = abs(fold["best_period"] - VELA_P0_PUBLISHED_S)
    return {
        "label": "pulsar_vela_real_data",
        "method": "vela_real_epoch_fold_z2",
        "data_source": data_source,
        "source_type": source_type,
        "fetch_status": fetch_status,
        "ref_bibcode": VELA_BIBCODE_PSRCAT,
        "ref_url": "https://www.atnf.csiro.au/research/pulsar/psrcat/",
        "fetched_from": data_source,
        "fetch_attempts": [],
        "n_arrivals": int(len(mjds)),
        "arrival_mjd_first": float(mjds.min()),
        "arrival_mjd_last": float(mjds.max()),
        "license": VELA_DATA_LICENSE,
        "provenance_note": (
            f"Real-data path with N={len(mjds)} Vela arrival MJDs from "
            f"`{data_source}`. License: {VELA_DATA_LICENSE}. Vela = "
            "NATURAL clock (Manchester+2005; PPTA DR3 Zic+2023). "
            "lab motto: structure != message."
        ),
        "plant": base_plant,
        "epochfold": fold,
        "negative_controls": {
            "shuffled_uniform_z2_max": shuf_fold["best_z2"],
            "shuffled_uniform_z2_p_value": shuf_fold["best_p_value"],
            "shuffled_uniform_best_period_s": shuf_fold["best_period"],
            "obs_window_s_for_shuffle": float(obs_window_s),
        },
        "known_answer": {
            "recovered_period_s": float(fold["best_period"]),
            "recovered_z2": float(fold["best_z2"]),
            "recovered_p_value": float(fold["best_p_value"]),
            "recovery_error_s": float(recovery_err_s),
            "recovery_pass": bool(recovery_err_s <= 1e-5),
        },
        "warnings": [],
        "stance": _vela_motto_stance_with_recovered(float(recovery_err_s)),
    }


def _vela_module_missing() -> dict:
    return {
        "label": "pulsar_vela_real_data",
        "method": "vela_real_epoch_fold_z2",
        "data_source": "(no source obtained)",
        "source_type": "empty",
        "fetch_status": "MODULE_MISSING",
        "ref_bibcode": VELA_BIBCODE_PSRCAT,
        "ref_url": "https://www.atnf.csiro.au/research/pulsar/psrcat/",
        "fetched_from": None,
        "fetch_attempts": [],
        "n_arrivals": 0,
        "license": VELA_DATA_LICENSE,
        "provenance_note": (
            "pulsar_fetcher module not importable in this environment; "
            "real-data Vela path disabled. Synthetic scaffold remains."
        ),
        "plant": {
            "psr_b1950": VELA_PSR_B1950, "psr_j2000": VELA_PSR_J2000,
            "true_period_s": float(VELA_P0_PUBLISHED_S),
            "true_freq_hz": float(VELA_F0_PUBLISHED_HZ),
        },
        "epochfold": None,
        "negative_controls": None,
        "known_answer": None,
        "warnings": ["no real-data path attempted because the Vela "
                      "fetcher module is unavailable. NO synthetic "
                      "plant was used."],
        "stance": _vela_motto_stance(),
    }


def _vela_motto_stance() -> str:
    return (
        "Structure != message. Vela is the universe's most famous "
        "NATURAL clock (Manchester+2005 AJ 129 1993; PPTA DR3 Zic+2023). "
        "Periodicity is necessary, NOT sufficient for artificiality. "
        "We do NOT fabricate arrival MJDs; we surface honest fetch failure."
    )


def _vela_motto_stance_with_recovered(err_s: float) -> str:
    return (
        f"Vela P0 {VELA_P0_PUBLISHED_S} s recovered from real arrival "
        f"MJDs with err |recovered - P0| = {err_s:.3e} s. Vela is "
        "the universe's most famous NATURAL clock. Lab motto: "
        "PERIODICITY IS NECESSARY, NOT SUFFICIENT FOR ARTIFICIALITY. "
        "We do NOT claim this implies ET. Structure != message."
    )


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


def run_frb_180916_real(
    bundled_json_path: Path | None = None,
    seed: int = 0,
    period_grid_lo: float = 10.0,
    period_grid_hi: float = 30.0,
    grid_step: float = 0.05,
    force_status_for_tests: str | None = None,
    use_chime_fetcher: bool = True,
) -> dict:
    """REAL-DATA path. Loads published FRB 180916 burst MJDs via FRS and
    runs the standard epoch-fold + shuffled-negative-control pipeline on
    them. NO synthetic plant injection -- if no MJDs are available the
    function returns an honest-empty result with no epoch-fold attempt.

    Parameters
    ----------
    bundled_json_path
        Optional path to a JSON file containing a flat list of MJD floats
        (or `[{name, mjd}, ...]`). When provided and parseable, this
        override skips the network fetch entirely and tags
        `data_source = "user_provided"`.
    seed
        Used by the negative-control generator (shuffled uniform null).
    period_grid_lo/hi/grid_step
        Same sweep grid as the synthetic path. We default to 10-30 d so
        FRB 121102's ~157-d cycle lies outside the search.
    force_status_for_tests
        Test hook passed through to chime_frb_fetcher. Use None in
        production; UNREACHABLE/PARKING_PAGE/FETCHED for deterministic
        tests.
    use_chime_fetcher
        When False and no bundled override is given, the path returns an
        empty `DISABLED` source without contacting the network.

    Returns
    -------
    dict  with keys:
        label, method="real_frb_180916_epoch_fold_z2",
        data_source, source_type, fetch_status, ref_bibcode, ref_url,
        n_bursts, fetched_from,
        fetch_attempts (list of dicts),
        provenance_note,
        plant (period, bounds),
        epochfold (None when no bursts; else the full epoch_fold dict),
        negative_controls (shuffled uniform null; only when n_bursts>0),
        known_answer (None when no bursts), stance, warnings.
    """
    if FRS is None:
        return {
            "label": "frb_180916_real_data",
            "method": "real_frb_180916_epoch_fold_z2",
            "data_source": "(no source obtained)",
            "source_type": "empty",
            "fetch_status": "MODULE_MISSING",
            "ref_bibcode": None,
            "ref_url": None,
            "fetched_from": None,
            "fetch_attempts": [],
            "n_bursts": 0,
            "burst_mjd_first": None,
            "burst_mjd_last": None,
            "provenance_note": (
                "frb_real_sources module not importable in this environment; "
                "real-data path disabled. Synthetic frb_180916 mode remains "
                "as a math-validation tool."
            ),
            "plant": {
                "true_period_d": float(FRB_180916_PERIOD_DAYS),
                "decoy_period_d_for_frb_121102": 157.0,
                "period_grid_lo_d": float(period_grid_lo),
                "period_grid_hi_d": float(period_grid_hi),
                "period_grid_step_d": float(grid_step),
                "frb_name_variants_tried": [],
            },
            "epochfold": None,
            "negative_controls": None,
            "known_answer": None,
            "warnings": ["no real-data path attempted because the burst source "
                         "module is unavailable. NO synthetic plant was used."],
            "stance": (
                "Structure != message. The real-data module is unavailable "
                "in this environment. Synthetic frb_180916 path remains "
                "as a math-validation tool only."
            ),
        }
    src = FRS.load_published_frb_180916_bursts(
        bundled_json_path=bundled_json_path,
        force_status_for_tests=force_status_for_tests,
        use_chime_fetcher=use_chime_fetcher,
    )
    base_plant = {
        "true_period_d": float(FRB_180916_PERIOD_DAYS),
        "decoy_period_d_for_frb_121102": 157.0,  # explicitly NOT used
        "period_grid_lo_d": float(period_grid_lo),
        "period_grid_hi_d": float(period_grid_hi),
        "period_grid_step_d": float(grid_step),
        "frb_name_variants_tried": list(FRS_PASTOR_PUBLIC if FRS is not None
                                        else []),
    }
    if not src.has_mjds:
        return {
            "label": "frb_180916_real_data",
            "method": "real_frb_180916_epoch_fold_z2",
            "data_source": src.source_name,
            "source_type": src.source_type,
            "fetch_status": src.fetch_status,
            "ref_bibcode": src.reference_bibcode,
            "ref_url": src.reference_url,
            "fetched_from": src.fetched_from,
            "fetch_attempts": src.fetch_attempts,
            "n_bursts": 0,
            "burst_mjd_first": None,
            "burst_mjd_last": None,
            "provenance_note": src.provenance_note,
            "plant": base_plant,
            "epochfold": None,
            "negative_controls": None,
            "known_answer": None,
            "warnings": [
                "no real-data path attempted because the burst source "
                "returned zero MJDs. NO synthetic plant was used.",
                "to populate: (a) wait for chime-frb.ca to come back online and "
                "rerun; (b) pass --bundled-mjd-json with a JSON flat list of "
                "MJDs transcribed from the Pastor-Marazuela 2021 table; or "
                "(c) populate data/radio/published_tables/"
                "pastor_marazuela_2021_frb_180916_mjds.json and refactor "
                "frb_real_sources.load_published_frb_180916_bursts() to read it."
            ],
            "stance": (
                "Structure != message. The real CHIME/FRB Catalog 1 mirror "
                "is currently offline; the bundled Pastor-Marazuela 2021 table "
                "is intentionally empty (extraction pending). We do NOT "
                "fabricate MJDs. If `fetch_status` is UNREACHABLE/PARKING/, "
                "the JSON `data_source` and `provenance_note` tell callers "
                "exactly what was attempted."
            ),
        }

    # Have MJDs -> run the standard epoch-fold pipeline.
    mjds = np.asarray(src.burst_mjds, dtype=float)
    grid = np.arange(period_grid_lo, period_grid_hi + 1e-9, grid_step)
    fold = epoch_fold(mjds, grid)
    rng = np.random.default_rng(seed + 11)
    obs_window_d = float(mjds.max() - mjds.min() + 1.0) if len(mjds) >= 2 \
        else max(float(mjds.max()), 1.0) * 2.0
    shuf = rng.uniform(0.0, obs_window_d, size=len(mjds))
    shuf_fold = epoch_fold(shuf, grid)
    recovery_err_d = abs(fold["best_period"] - FRB_180916_PERIOD_DAYS)
    return {
        "label": "frb_180916_real_data",
        "method": "real_frb_180916_epoch_fold_z2",
        "data_source": src.source_name,
        "source_type": src.source_type,
        "fetch_status": src.fetch_status,
        "ref_bibcode": src.reference_bibcode,
        "ref_url": src.reference_url,
        "fetched_from": src.fetched_from,
        "fetch_attempts": src.fetch_attempts,
        "n_bursts": int(len(mjds)),
        "burst_mjd_first": float(mjds.min()),
        "burst_mjd_last": float(mjds.max()),
        "provenance_note": src.provenance_note,
        "plant": base_plant,
        "epochfold": fold,
        "negative_controls": {
            "shuffled_uniform_z2_max": shuf_fold["best_z2"],
            "shuffled_uniform_z2_p_value": shuf_fold["best_p_value"],
            "shuffled_uniform_best_period_d": shuf_fold["best_period"],
            "obs_window_d_for_shuffle": round(obs_window_d, 4),
        },
        "known_answer": {
            "recovered_period_d": fold["best_period"],
            "recovered_z2": fold["best_z2"],
            "recovered_p_value": fold["best_p_value"],
            "recovery_error_d": round(recovery_err_d, 5),
            "recovery_pass": bool(recovery_err_d <= 1.0),
        },
        "warnings": [],
        "stance": (
            f"Real-data path executed with N={len(mjds)} burst MJDs from "
            f"`{src.source_name}` (source_type={src.source_type}, "
            f"fetch_status={src.fetch_status}). Recovery of the published "
            f"{FRB_180916_PERIOD_DAYS}-d cycle is a math-validation outcome -- "
            "the natural precession-of-companion explanation is favoured. "
            "Structure != message."
        ),
    }


# Sentinel used to gate writing `frb_name_variants_tried` even if FRS is None.
FRS_PASTOR_PUBLIC = (
    "Pastor-Marazuela et al. 2020/2021 (ApJ 923 L6, arXiv:2001.08645)",
)


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


def analyze(
    mode: str = "all",
    seed: int = 0,
    bundled_real_json: Path | None = None,
    bundled_pulsar_csv: Path | None = None,
) -> dict:
    """Orchestrator: returns a single dict containing all sub-runs.

    `mode ∈ {'all', 'known_train', 'wow', 'frb_180916',
             'frb_180916_real'}`.

    `bundled_real_json` is forwarded to `run_frb_180916_real` when mode
    includes 'frb_180916_real'. It is ignored otherwise.
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
    if mode == "frb_180916_real":
        out["frb_180916_real_data"] = run_frb_180916_real(
            bundled_json_path=bundled_real_json,
            seed=seed,
        )
    if mode == "pulsar_vela_synthetic":
        out["pulsar_vela_synthetic"] = run_pulsar_vela_synthetic(seed=seed)
    if mode == "pulsar_vela_real":
        out["pulsar_vela_real_data"] = run_pulsar_vela(
            bundled_csv_path=bundled_pulsar_csv,
            seed=seed,
        )
    if mode == "pulsar_vela":
        # Fall-through: prefer real-data if a CSV override was given,
        # else default to synthetic known-answer plant (proves math).
        if bundled_pulsar_csv is not None:
            out["pulsar_vela_real_data"] = run_pulsar_vela(
                bundled_csv_path=bundled_pulsar_csv,
                seed=seed,
            )
        else:
            out["pulsar_vela_synthetic"] = run_pulsar_vela_synthetic(
                seed=seed,
            )
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
    if "frb_180916_real_data" in report:
        rd = report["frb_180916_real_data"]
        lines += [
            "## FRB 180916 16.35-d — REAL-DATA path (NOT 121102)",
            "",
            f"- data source: **{rd.get('data_source', '?')}** "
            f"(source_type=`{rd.get('source_type', '?')}`, "
            f"fetch_status=`{rd.get('fetch_status', '?')}`)",
            f"- reference: bibcode=`{rd.get('ref_bibcode') or '-'}`, "
            f"url=`{rd.get('ref_url') or '-'}`",
            f"- N bursts: **{rd.get('n_bursts', 0)}** "
            f"(mjd first={rd.get('burst_mjd_first')}, "
            f"last={rd.get('burst_mjd_last')})",
            "",
        ]
        if rd.get("warnings"):
            lines += ["### YELLOW BANNER - real-data path could NOT obtain MJDs", ""]
            for w in rd["warnings"]:
                lines.append(f"  - {w}")
            lines.append("")
            note = (rd.get("provenance_note") or "")[:600]
            lines.append(f"_provenance:_ {note}")
            lines.append("")
            attempts = rd.get("fetch_attempts") or []
            if attempts:
                lines += ["### Fetch attempts", ""]
                for i, a in enumerate(attempts[:6], start=1):
                    lines.append(
                        f"  {i}. `{a.get('url', '?')[:80]}` -> "
                        f"{a.get('verdict', '?')} "
                        f"(http={a.get('http_status')}, "
                        f"bytes={a.get('content_bytes', 0)}, "
                        f"err={a.get('error') or '-'})"
                    )
                if len(attempts) > 6:
                    lines.append(f"  ... and {len(attempts) - 6} more")
                lines.append("")
        else:
            ka = rd.get("known_answer") or {}
            nc = rd.get("negative_controls") or {}
            lines += [
                f"- recovered period: **{ka.get('recovered_period_d')}** "
                f"(err {ka.get('recovery_error_d')}, Z^2 = "
                f"{ka.get('recovered_z2')}, p = "
                f"{ka.get('recovered_p_value')}); "
                f"**{'PASS' if ka.get('recovery_pass') else 'FAIL'}**",
                f"- shuffled control: max Z^2 = "
                f"{nc.get('shuffled_uniform_z2_max')}, "
                f"p = {nc.get('shuffled_uniform_z2_p_value')}, best "
                f"period = {nc.get('shuffled_uniform_best_period_d')} d, "
                f"random - NO fabrication",
                "",
                f"_stance:_ {rd.get('stance', '')}",
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
                    help="(DEPRECATED alias for --frb-180916-synthetic) "
                         "Synthesize 30 fake arrivals around 16.35 d + "
                         "epoch-fold. Math-validation only; nothing about "
                         "the real FRB.")
    ap.add_argument("--frb-180916-synthetic", action="store_true",
                    help="Same as --frb-180916: synthetic-plant known-answer.")
    ap.add_argument("--frb-180916-real", action="store_true",
                    help="REAL-DATA path: fetch CHIME/FRB Catalog 1 CSV "
                         "(or --bundled-mjd-json) and run epoch-fold on "
                         "the actual burst MJDs. If no MJDs can be "
                         "obtained, the run reports fetch_status and "
                         "exits without fabrication.")
    ap.add_argument("--bundled-mjd-json", type=Path, default=None,
                    help="Override the live fetch with a JSON file "
                         "containing a flat list of MJD floats. "
                         "Schema: [58700.1, 58716.5, ...] OR "
                         "[{\"name\": \"...\", \"mjd\": ...}, ...]. "
                         "Only honoured when combined with "
                         "--frb-180916-real.")
    ap.add_argument("--pulsar-vela", action="store_true",
                    help="REAL-DATA Vela positive-control path: load "
                         "PSR B0833-45 arrival MJDs (live ATNF/Parkes "
                         "fetch OR --bundled-pulsar-csv override) and "
                         "run epoch-fold around the published P0 "
                         "(~89.328 ms). Lab motto: periodicity is "
                         "necessary, NOT sufficient, for artificiality "
                         "-- we do NOT claim detection implies ET.")
    ap.add_argument("--pulsar-vela-synthetic", action="store_true",
                    help="Vela synthetic positive-control: plant 30 "
                         "arrival MJDs at multiples of P0 with 1 us "
                         "jitter; run epoch-fold in SECONDS. This is "
                         "a math-validation tool (no glitches, no "
                         "spin-down) ONLY.")
    ap.add_argument("--pulsar-vela-real", action="store_true",
                    help="Explicit real-data Vela fetch (same as "
                         "--pulsar-vela but never falls through to "
                         "the synthetic plant). Use this when you "
                         "want honest-empty-on-fetch-failure semantics.")
    ap.add_argument("--bundled-pulsar-csv", type=Path, default=None,
                    help="Override the ATNF/Parkes live fetch with a "
                         "CSV file of Vela arrival MJDs. Schema: "
                         "header `name,mjd` (Vela-row filter is "
                         "applied automatically) OR a flat list of "
                         "MJD floats (treated as Vela). Only honoured "
                         "when combined with --pulsar-vela*.")
    ap.add_argument("--fetch-status-test-force",
                    choices=["UNREACHABLE", "PARKING_PAGE", "FETCHED"],
                    default=None,
                    help="TEST HOOK: synthesize fetcher result without "
                         "network contact. UNREACHABLE / PARKING_PAGE / "
                         "FETCHED. Production users must omit this flag. "
                         "Only applies to --frb-180916-real.")
    ap.add_argument("--all-of-the-above", action="store_true",
                    help="Run known-train + wow-honest + frb-180916 (synthetic)"
                         " (default)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out-json", type=Path, default=None,
                    help="write structured JSON report")
    ap.add_argument("--out-md", type=Path, default=None,
                    help="write human-readable notes markdown")
    args = ap.parse_args()

    # Default to --all-of-the-above if no flag is supplied AND no real-data
    # override is present.
    if not (args.known_train or args.wow_honest
            or args.frb_180916 or args.frb_180916_synthetic
            or args.frb_180916_real):
        args.all_of_the_above = True

    if args.frb_180916_real:
        mode = "frb_180916_real"
    elif args.pulsar_vela_synthetic:
        mode = "pulsar_vela_synthetic"
    elif args.pulsar_vela_real:
        mode = "pulsar_vela_real"
    elif args.pulsar_vela:
        mode = "pulsar_vela"
    elif args.all_of_the_above:
        mode = "all"
    elif (args.frb_180916 or args.frb_180916_synthetic) and not (
            args.known_train or args.wow_honest
            or args.pulsar_vela or args.pulsar_vela_synthetic
            or args.pulsar_vela_real):
        mode = "frb_180916"
    elif args.known_train and not (args.wow_honest
                                   or args.frb_180916 or args.frb_180916_synthetic
                                   or args.frb_180916_real
                                   or args.pulsar_vela or args.pulsar_vela_synthetic
                                   or args.pulsar_vela_real):
        mode = "known_train"
    elif args.wow_honest and not (args.known_train
                                  or args.frb_180916 or args.frb_180916_synthetic
                                  or args.frb_180916_real
                                  or args.pulsar_vela or args.pulsar_vela_synthetic
                                  or args.pulsar_vela_real):
        mode = "wow"
    else:
        mode = "all"

    report = analyze(
        mode=mode,
        seed=args.seed,
        bundled_real_json=args.bundled_mjd_json if mode == "frb_180916_real"
        else None,
        bundled_pulsar_csv=args.bundled_pulsar_csv
        if mode in ("pulsar_vela", "pulsar_vela_real", "pulsar_vela_synthetic")
        else None,
    )
    if mode == "frb_180916_real" and args.fetch_status_test_force:
        # Re-run with the test hook applied to the real-data path layer.
        # The hook is propagated by patching analyze() to pass the force
        # argument to run_frb_180916_real. We do that via a thin shim here
        # so production users don't have to know about force_status_for_tests.
        if FRS is not None and "frb_180916_real_data" in report:
            report["frb_180916_real_data"] = run_frb_180916_real(
                bundled_json_path=args.bundled_mjd_json
                if mode == "frb_180916_real" else None,
                seed=args.seed,
                force_status_for_tests=args.fetch_status_test_force,
            )
    if mode == "pulsar_vela_real" and args.fetch_status_test_force:
        # Same thin-shim pattern as FRB 180916: re-run with the
        # fetch-status test hook applied to the pulsar_vela real path
        # layer so production users don't have to know about
        # force_status_for_tests.
        if PUL is not None and "pulsar_vela_real_data" in report:
            report["pulsar_vela_real_data"] = run_pulsar_vela(
                bundled_csv_path=args.bundled_pulsar_csv
                if mode == "pulsar_vela_real" else None,
                seed=args.seed,
                force_status_for_tests=args.fetch_status_test_force,
            )
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
