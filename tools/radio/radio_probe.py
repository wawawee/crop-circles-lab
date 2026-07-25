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
try:
    import blc1_fetcher as BLC  # noqa: E402
except ImportError:  # pragma: no cover
    BLC = None
try:
    import cat2_real_sources as C2S  # noqa: E402
except ImportError:  # pragma: no cover
    C2S = None


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

# G3 (Wow! beam-fit) constants. The synthetic plant below uses 6 evenly-
# spaced sample indices (0..5) and exact Gaussian values at each index.
# All fit math is pure-numpy (no scipy) to match the codebase's zero-
# dependency style on the radio path.
WOW_TRANSIT_PLANT_MU_IDX = 2.5      # sample-index, midpoint 2-3
WOW_TRANSIT_PLANT_SIGMA_IDX = 1.5    # sample-index width
WOW_TRANSIT_PLANT_AMP = 30.0         # central peak amplitude (sigma units)
WOW_TRANSIT_PERMUTATIONS = 24        # 6! = 720 -> 24 is enough for median+p95
WOW_TRANSIT_RECOVERY_TOL_IDX = 0.5   # |recovered_mu - plant_mu| <= 0.5 indices

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

# BLC1 (Breakthrough Listen Candidate 1) constants.
# Source: Sheikh et al. 2021, Nature Astronomy, 5, 1169,
# DOI 10.1038/s41550-021-01508-8. BLC1 was detected at Parkes L-band
# ~982.002 MHz with drift rate -0.26 Hz/s. Sheikh 2021 concluded
# BLC1 was an INTERMODULATION PRODUCT of clock-oscillator RFI, NOT a
# confirmed technosignature.
BLC1_FREQ_MHZ = 982.002
BLC1_DRIFT_HZ_PER_S = -0.26
BLC1_CLOCK_MHZ = 2.0                    # fundamental clock spacing (Sheikh 2021)
BLC1_COMB_TOLERANCE_MHZ = 0.01          # |f_peak - n*f_clock| <= 0.01 MHz
BLC1_BIBCODE = "2021NatAs...5.1169S"
BLC1_REFERENCE_URL = "https://doi.org/10.1038/s41550-021-01508-8"
BLC1_DATA_LICENSE = "CC BY 4.0 (Sheikh 2021 supplementary tables)"

# Known Parkes RFI comb (per ATNF RFI characterisation page). A peak
# detected at one of these freqs is LABELED RFI_COMB_DETECTED and
# treated as a natural artefact, not a technosignature hit.
PARKES_KNOWN_RFI_FREQS_MHZ: tuple[float, ...] = (
    137.0, 440.0, 715.0, 982.002, 1217.0, 1616.0,
)
PARKES_KNOWN_RFI_TOLERANCE_MHZ = 0.5

# BLC1 synthetic plant defaults.
DEFAULT_BLC1_HARMONICS = 5               # n peaks at f_center +/- i*clock for i in -(H-1)//2..H//2
DEFAULT_BLC1_SNR_BASE_DB = 25.0          # strongest peak SNR
DEFAULT_BLC1_SNR_DECAY_DB = 3.0          # each harmonic weaker by 3 dB
DEFAULT_BLC1_LABEL_PREFIX = "BLC1_SYNTH"


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


# --- BLC1 (Breakthrough Listen Candidate 1) scaffold -------------------
# BLC1 was detected at Parkes L-band ~982.002 MHz with drift rate
# -0.26 Hz/s. Sheikh 2021 concluded it was an INTERMODULATION PRODUCT of
# clock-oscillator RFI, NOT a confirmed technosignature. The lab-motto:
# "structure != message" applies: a positive comb-hit here IS RFI, NOT ET.
#
# Per the G-BLC1 mission brief, the LIVE probe is DISABLED by default
# (the "no TB mirror" stance). The bundled override `--bundled-blc1-csv`
# is the realistic landing today. The synthetic comb plant is a math-
# validation tool only.

def synth_blc1_comb_peaks(
    f_center_mhz: float = BLC1_FREQ_MHZ,
    f_clock_mhz: float = BLC1_CLOCK_MHZ,
    drift_hz_per_s: float = BLC1_DRIFT_HZ_PER_S,
    harmonics: int = DEFAULT_BLC1_HARMONICS,
    snr_base_db: float = DEFAULT_BLC1_SNR_BASE_DB,
    snr_decay_db: float = DEFAULT_BLC1_SNR_DECAY_DB,
    label_prefix: str = DEFAULT_BLC1_LABEL_PREFIX,
) -> list:
    """Plant N harmonically-spaced peaks around f_center at multiples of f_clock.

    Mirrors the Vela synthetic plant pattern: deterministic, no jitter
    (since the plant is meant to be RECOVERABLE by the comb detector).
    Returns a list of BLC1PeakRow objects (from blc1_fetcher when
    available; raises ModuleNotFoundError otherwise).

    The peak SNR decays by `snr_decay_db` per harmonic step away from
    the carrier (i.e., the central peak is loudest). Drift is uniform
    across the comb (matching Sheikh 2021's signature).
    """
    if BLC is None:
        raise ModuleNotFoundError("blc1_fetcher module not importable")
    rows = []
    half = max(harmonics // 2, 0)
    for i, offset in enumerate(range(-half, harmonics - half)):
        freq = f_center_mhz + float(offset) * float(f_clock_mhz)
        snr = float(snr_base_db) - abs(offset) * float(snr_decay_db)
        label = f"{label_prefix}_{offset:+d}"
        rows.append(BLC.BLC1PeakRow(
            raw_freq_mhz=float(freq),
            raw_snr_db=float(snr),
            raw_drift_hz_per_s=float(drift_hz_per_s),
            raw_t_start_mjd=None, raw_t_end_mjd=None,
            raw_label=label,
        ))
    return rows


def _blc1_run_peak_detector(
    peak_rows: list,
    clock_guess_mhz: float = BLC1_CLOCK_MHZ,
    tolerance_mhz: float = BLC1_COMB_TOLERANCE_MHZ,
    scramble_seed: int = 0,
) -> dict:
    """Detect clock-oscillator comb structure in a peak list.

    Strategy
    --------
    For each peak `f_i`, compute residuals `r_i = f_i mod clock_guess`
    (modulo the candidate clock frequency). A peak whose residual is
    within `tolerance_mhz` of 0 OR within `tolerance_mhz` of
    `clock_guess` (=complement) is counted as a CLOCK HARMONIC HIT.

    A peak whose freq is within PARKES_KNOWN_RFI_TOLERANCE_MHZ of any
    known Parkes RFI comb freq is flagged as `KNOWN_RFI`.

    Scramble null
    -------------
    Permute the freq_mhz values uniformly within the observed band
    (min..max of the input peaks) and re-count CLOCK HARMONIC HITS.
    Under the null hypothesis, hits should drop to roughly the
    uniform-rate expectation (for N peaks and a fractional band of
    `2*tolerance_mhz / clock_guess_mhz`, expected ~N*p hits).
    """
    # numpy is imported at module level (line 49). No lazy re-import here.
    freqs = np.asarray([float(r.raw_freq_mhz) for r in peak_rows], dtype=float)
    n_in = int(len(freqs))
    if n_in == 0:
        return {
            "clock_guess_mhz": float(clock_guess_mhz),
            "tolerance_mhz": float(tolerance_mhz),
            "n_peaks": 0,
            "hits_at_clock": 0,
            "hits_at_clock_fraction": 0.0,
            "peaks_at_known_rfi": 0,
            "scramble_null_hits": 0,
            "scramble_null_p_value": 1.0,
            "rfi_comb_detected": False,
        }
    # Hits at clock: |freq mod clock - 0| <= tol  OR  |freq mod clock - clock| <= tol
    mod_residuals = np.mod(freqs, float(clock_guess_mhz))
    dist_to_zero = np.minimum(mod_residuals,
                                float(clock_guess_mhz) - mod_residuals)
    hits_mask = dist_to_zero <= float(tolerance_mhz)
    hits_at_clock = int(np.sum(hits_mask))
    # Known RFI flags
    rfi_mask = np.zeros(n_in, dtype=bool)
    for rfi_freq in PARKES_KNOWN_RFI_FREQS_MHZ:
        rfi_mask |= np.abs(freqs - float(rfi_freq)) <= PARKES_KNOWN_RFI_TOLERANCE_MHZ
    peaks_at_known_rfi = int(np.sum(rfi_mask))
    # Scramble null
    rng = np.random.default_rng(scramble_seed)
    f_low = float(freqs.min())
    f_high = float(freqs.max())
    if f_high <= f_low:
        f_high = f_low + 1.0
    shuf = rng.uniform(f_low, f_high, size=n_in)
    shuf_mod = np.mod(shuf, float(clock_guess_mhz))
    shuf_dist = np.minimum(shuf_mod, float(clock_guess_mhz) - shuf_mod)
    scramble_null_hits = int(np.sum(shuf_dist <= float(tolerance_mhz)))
    # P(Z > hits_at_clock | null has rate scramble_null_hits / N) under
    # binomial. Use rate = scramble_null_hits / max(N, 1) for the null.
    p_rate = scramble_null_hits / max(n_in, 1)
    if p_rate <= 0.0:
        p_value = 1.0 if hits_at_clock < n_in else 0.0
    else:
        from math import comb as _comb
        k = hits_at_clock
        # P(X >= k) under Binomial(n, p)
        try:
            tail = sum(_comb(n_in, j) * (p_rate ** j) * ((1 - p_rate) ** (n_in - j))
                        for j in range(k, n_in + 1))
        except Exception:
            tail = 1.0
        p_value = float(min(max(tail, 0.0), 1.0))
    return {
        "clock_guess_mhz": float(clock_guess_mhz),
        "tolerance_mhz": float(tolerance_mhz),
        "n_peaks": int(n_in),
        "hits_at_clock": int(hits_at_clock),
        "hits_at_clock_fraction": float(hits_at_clock / max(n_in, 1)),
        "peaks_at_known_rfi": peaks_at_known_rfi,
        "peaks_at_known_rfi_label": [
            float(freqs[i]) for i in range(n_in) if rfi_mask[i]
        ],
        "scramble_null_hits": scramble_null_hits,
        "scramble_null_p_value": p_value,
        "rfi_comb_detected": bool(
            hits_at_clock >= max(2, n_in // 3) or peaks_at_known_rfi >= 1
        ),
    }


def blc1_delta_f_regularity(freqs_mhz) -> dict:
    """Harmonic-family test: are the lookalike peaks equally spaced in freq?

    Sheikh et al. 2021 killed BLC1 not by the ON/OFF cadence alone but by
    the *lookalike* analysis: a family of signals-of-interest whose
    frequencies form an equally-spaced comb (Δf ≈ constant) is the
    signature of intermodulation between local-oscillator clocks — i.e.
    terrestrial electronics, NOT an astrophysical/ET source.

    Given the sorted peak frequencies, compute the successive spacings
    Δf_i = f_{i+1} - f_i and report their mean, std and coefficient of
    variation (CV = std/mean). A LOW CV (regular comb) is the RFI
    fingerprint. This is a *descriptive* structure statistic — structure
    ≠ message: a regular comb is evidence FOR terrestrial RFI, never for
    ET.
    """
    f = np.asarray(sorted(float(x) for x in freqs_mhz), dtype=float)
    if len(f) < 3:
        return {
            "n_peaks": int(len(f)),
            "delta_f_mhz": [float(d) for d in np.diff(f)] if len(f) >= 2 else [],
            "mean_delta_f_mhz": float(np.diff(f).mean()) if len(f) >= 2 else None,
            "std_delta_f_mhz": None,
            "cv_delta_f": None,
            "regular_comb": None,
            "note": "need >=3 peaks to test Δf regularity",
        }
    dfs = np.diff(f)
    mean_df = float(dfs.mean())
    std_df = float(dfs.std(ddof=0))
    cv = float(std_df / mean_df) if mean_df != 0 else None
    # CV <= 0.05 => spacings agree to ~5% => regular intermodulation comb.
    regular = bool(cv is not None and cv <= 0.05)
    return {
        "n_peaks": int(len(f)),
        "delta_f_mhz": [round(float(d), 6) for d in dfs],
        "mean_delta_f_mhz": round(mean_df, 6),
        "std_delta_f_mhz": round(std_df, 6),
        "cv_delta_f": None if cv is None else round(cv, 6),
        "regular_comb": regular,
        "note": (
            "LOW CV => equally-spaced comb => intermodulation RFI family "
            "(terrestrial). Structure != message: regularity is evidence "
            "for RFI, never for ET."
        ),
    }


def blc1_on_off_cadence(on_freqs_mhz, off_freqs_mhz,
                        clock_guess_mhz: float = BLC1_CLOCK_MHZ,
                        tolerance_mhz: float = BLC1_COMB_TOLERANCE_MHZ,
                        seed: int = 0) -> dict:
    """ON/OFF discrimination — the first-line SETI cadence test.

    A genuine celestial source is present when the telescope points at
    the target (ON) and ABSENT when it nods off-source (OFF). Terrestrial
    RFI leaks into both. This helper runs the comb detector on the ON and
    OFF peak lists and reports:

      - `on_hits`, `off_hits`  : clock-comb hits in each pointing
      - `persists_in_off`      : True if the comb is still present in OFF
      - `cadence_consistent_with_source` : True only if ON has the comb
                                           and OFF does NOT (i.e. ON-only)

    BLC1's lookalikes appeared in OFF pointings too (Sheikh 2021) ->
    `persists_in_off=True` -> terrestrial. The ON-only *contrast* control
    below shows the discriminator has real power (it would pass an
    ON-only injection), so a NEGATIVE result here is meaningful, not a
    dead detector. We never claim ET from an ON-only pass — cadence is
    necessary, NOT sufficient.
    """
    on_rows = [type("R", (), {"raw_freq_mhz": float(x)})() for x in on_freqs_mhz]
    off_rows = [type("R", (), {"raw_freq_mhz": float(x)})() for x in off_freqs_mhz]
    on_detect = _blc1_run_peak_detector(
        on_rows, clock_guess_mhz=clock_guess_mhz,
        tolerance_mhz=tolerance_mhz, scramble_seed=seed,
    )
    off_detect = _blc1_run_peak_detector(
        off_rows, clock_guess_mhz=clock_guess_mhz,
        tolerance_mhz=tolerance_mhz, scramble_seed=seed,
    )
    on_hits = int(on_detect["hits_at_clock"])
    off_hits = int(off_detect["hits_at_clock"])
    persists_in_off = bool(off_hits >= 2)
    cadence_ok = bool(on_hits >= 2 and off_hits < 2)
    return {
        "on_hits_at_clock": on_hits,
        "off_hits_at_clock": off_hits,
        "persists_in_off": persists_in_off,
        "cadence_consistent_with_source": cadence_ok,
        "verdict": ("RFI_PRESENT_IN_OFF" if persists_in_off
                    else "ON_ONLY_would_pass_cadence"),
        "note": (
            "ON/OFF cadence is necessary, NOT sufficient. BLC1's lookalike "
            "family appeared in OFF pointings (Sheikh 2021) -> terrestrial. "
            "An ON-only pass would NOT prove ET."
        ),
    }


def run_blc1_synthetic(
    seed: int = 0,
    f_center_mhz: float = BLC1_FREQ_MHZ,
    f_clock_mhz: float = BLC1_CLOCK_MHZ,
    drift_hz_per_s: float = BLC1_DRIFT_HZ_PER_S,
    harmonics: int = DEFAULT_BLC1_HARMONICS,
    snr_base_db: float = DEFAULT_BLC1_SNR_BASE_DB,
    snr_decay_db: float = DEFAULT_BLC1_SNR_DECAY_DB,
    scramble_seed: int = 0,
) -> dict:
    """SYNTHETIC BLC1 clock-comb plant + comb detector + scramble null.

    Synthetic plant EXCLUDES Sheikh 2021's real Parkes RFI environment
    beyond the clock-oscillator comb itself. Recovery_pass = TRUE iff
    hits_at_clock fraction is well above the scramble-null rate.
    """
    if BLC is None:
        return _blc1_module_missing()
    try:
        peaks = synth_blc1_comb_peaks(
            f_center_mhz=f_center_mhz, f_clock_mhz=f_clock_mhz,
            drift_hz_per_s=drift_hz_per_s, harmonics=harmonics,
            snr_base_db=snr_base_db, snr_decay_db=snr_decay_db,
        )
    except Exception as e:
        return {
            "label": "blc1_synthetic",
            "method": "blc1_synthetic_comb_detector",
            "fetch_status": "MODULE_MISSING",
            "n_peaks": 0, "plant_combs": 0,
            "known_answer": None, "stance": _blc1_motto_stance(),
            "warnings": [f"synth_blc1_comb_peaks failed: {e}"],
        }
    detect = _blc1_run_peak_detector(
        peak_rows=peaks, clock_guess_mhz=f_clock_mhz,
        tolerance_mhz=BLC1_COMB_TOLERANCE_MHZ, scramble_seed=scramble_seed,
    )
    recovery_pass = bool(
        detect["n_peaks"] > 0 and detect["hits_at_clock"] >= max(
            2, int(0.5 * detect["n_peaks"])
        ) and detect["hits_at_clock"] > detect["scramble_null_hits"]
    )
    # --- interpretation controls (Ozma, G-BLC1) -----------------------
    # (1) Harmonic-family Δf regularity on the planted comb frequencies.
    plant_freqs = [float(p.raw_freq_mhz) for p in peaks]
    harmonic_family = blc1_delta_f_regularity(plant_freqs)
    # (2) ON/OFF cadence. RFI is local -> the SAME comb family leaks into
    #     the OFF pointing. We model that here: OFF carries the comb too.
    #     A separate ON-only *contrast* control shows the discriminator
    #     has power (it would flag an ON-only injection as cadence-OK).
    rng_off = np.random.default_rng(scramble_seed + 101)
    on_off = blc1_on_off_cadence(
        on_freqs_mhz=plant_freqs,
        off_freqs_mhz=plant_freqs,  # RFI persists into OFF -> terrestrial
        clock_guess_mhz=f_clock_mhz,
        tolerance_mhz=BLC1_COMB_TOLERANCE_MHZ,
        seed=scramble_seed,
    )
    # Contrast: a hypothetical ON-only source (OFF = off-comb noise). This
    # is NOT a claim of ET; it demonstrates the cadence test can separate.
    off_noise = list(rng_off.uniform(min(plant_freqs) - 5.0,
                                     max(plant_freqs) + 5.0, size=len(peaks)))
    on_off_contrast = blc1_on_off_cadence(
        on_freqs_mhz=plant_freqs, off_freqs_mhz=off_noise,
        clock_guess_mhz=f_clock_mhz, tolerance_mhz=BLC1_COMB_TOLERANCE_MHZ,
        seed=scramble_seed,
    )
    # Verdict: BLC1's real family persists in OFF AND is a regular comb ->
    # terrestrial RFI. For the real BLC1 path the honest verdict is
    # NO_SIGNAL; here (synthetic) we report the RFI classification the
    # controls produce.
    verdict = (
        "RFI_COMB_TERRESTRIAL"
        if (on_off["persists_in_off"] and bool(harmonic_family["regular_comb"]))
        else "INCONCLUSIVE_SYNTH"
    )
    return {
        "label": "blc1_synthetic",
        "method": "blc1_synthetic_comb_detector",
        "verdict": verdict,
        "on_off_control": on_off,
        "on_off_contrast_on_only": on_off_contrast,
        "harmonic_family": harmonic_family,
        "plant": {
            "f_center_mhz": float(f_center_mhz),
            "f_clock_mhz": float(f_clock_mhz),
            "drift_hz_per_s": float(drift_hz_per_s),
            "harmonics": int(harmonics),
            "snr_base_db": float(snr_base_db),
            "snr_decay_db": float(snr_decay_db),
            "rfi_conclusion": (
                "Sheikh 2021 (Nat. Astron. 5 1169, DOI "
                "10.1038/s41550-021-01508-8) concluded BLC1 was "
                "clock-oscillator intermodulation RFI, NOT ET. "
                "The synthetic plant mimics this signature for "
                "math-validation only."
            ),
        },
        "n_peaks": detect["n_peaks"],
        "comb_detection": detect,
        "negative_controls": {
            "scramble_null_hits": detect["scramble_null_hits"],
            "scramble_null_p_value": detect["scramble_null_p_value"],
            "scramble_null_band_mhz_lo": float(min(p.raw_freq_mhz for p in peaks)),
            "scramble_null_band_mhz_hi": float(max(p.raw_freq_mhz for p in peaks)),
        },
        "known_answer": {
            "recovered_clock_mhz": float(f_clock_mhz),
            "hits_at_clock": detect["hits_at_clock"],
            "rfi_comb_detected": bool(detect["rfi_comb_detected"]),
            "scramble_null_drop": bool(
                detect["hits_at_clock"] > detect["scramble_null_hits"]
            ),
            "recovery_pass": bool(recovery_pass),
        },
        "warnings": [],
        "stance": (
            "SYNTHETIC BLC1 clock-comb plant. Scaffolds detection math; "
            "tells us NOTHING about the real BLC1. Sheikh 2021 concluded "
            "BLC1 was clock-oscillator RFI; a positive comb-hit here is "
            "labeled RFI, NOT a technosignature. Lab motto: structure != "
            "message. Periodicity is necessary, NOT sufficient, for "
            "artificiality."
        ),
    }


def run_blc1_real(
    bundled_csv_path,
    seed: int = 0,
    force_status_for_tests: str | None = None,
) -> dict:
    """REAL-DATA BLC1 path. Lab motto: never scrape open archives.

    In production this surfaces a NEVER_ATTEMPTED + 🟡 YELLOW BANNER
    because the user brief forbids the "TB mirror" (Berkeley SETI
    opendata) path. The honest landing today is the bundled override
    `--bundled-blc1-csv` for hand-transcribed Sheikh 2021 supplementary
    tables.
    """
    if BLC is None:
        return _blc1_module_missing()
    result = BLC.try_fetch_blc1_peaks(
        force_status_for_tests=force_status_for_tests,
    )
    base_plant = {
        "f_center_mhz": float(BLC1_FREQ_MHZ),
        "f_clock_mhz": float(BLC1_CLOCK_MHZ),
        "drift_hz_per_s": float(BLC1_DRIFT_HZ_PER_S),
        "rfi_conclusion": (
            "Sheikh 2021: BLC1 = clock-oscillator RFI, NOT ET."
        ),
        "license": BLC1_DATA_LICENSE,
    }
    if bundled_csv_path is not None:
        try:
            bundle = BLC.load_bundled_blc1_csv(
                Path(bundled_csv_path) if not isinstance(
                    bundled_csv_path, Path) else bundled_csv_path
            )
        except Exception as e:
            bundle = BLC.BundledBLC1Override(
                peak_rows=[], source_path=str(bundled_csv_path),
                n_rows=0, error=str(e),
            )
        if bundle.error is not None:
            return {
                "label": "blc1_real_data",
                "method": "blc1_comb_detector",
                "verdict": "NO_SIGNAL",  # Sheikh 2021: terrestrial RFI (default)
                "data_source": f"bundled_csv={bundled_csv_path}",
                "source_type": "bundled_attempt",
                "fetch_status": "USER_OVERRIDE_INVALID",
                "ref_bibcode": BLC1_BIBCODE,
                "ref_url": BLC1_REFERENCE_URL,
                "fetched_from": str(bundled_csv_path),
                "fetch_attempts": [],
                "n_peaks": 0, "plant": base_plant,
                "comb_detection": None, "negative_controls": None,
                "known_answer": None,
                "warnings": [
                    f"--bundled-blc1-csv {bundled_csv_path} failed to "
                    f"parse: {bundle.error}. Honest empty fallback; "
                    f"NO synthetic plant used."
                ],
                "stance": _blc1_motto_stance(),
            }
        if bundle.has_peaks:
            detect = _blc1_run_peak_detector(
                peak_rows=bundle.peak_rows, clock_guess_mhz=BLC1_CLOCK_MHZ,
                tolerance_mhz=BLC1_COMB_TOLERANCE_MHZ, scramble_seed=seed,
            )
            return {
                "label": "blc1_real_data",
                "method": "blc1_comb_detector",
                "verdict": "NO_SIGNAL",  # Sheikh 2021: terrestrial RFI (default)
                "data_source": str(bundled_csv_path),
                "source_type": "bundled_override",
                "fetch_status": "USER_OVERRIDE",
                "ref_bibcode": BLC1_BIBCODE,
                "ref_url": BLC1_REFERENCE_URL,
                "fetched_from": str(bundled_csv_path),
                "fetch_attempts": [],
                "n_peaks": detect["n_peaks"],
                "license": BLC1_DATA_LICENSE,
                "provenance_note": (
                    f"Bundled override with N={detect['n_peaks']} peaks "
                    f"from {bundled_csv_path}. Lab motto: BLC1 is "
                    f"clock-oscillator RFI per Sheikh 2021; a positive "
                    f"comb-hit is RFI, NOT ET. License: {BLC1_DATA_LICENSE}."
                ),
                "plant": base_plant,
                "comb_detection": detect,
                "negative_controls": {
                    "scramble_null_hits": detect["scramble_null_hits"],
                    "scramble_null_p_value": detect["scramble_null_p_value"],
                },
                "known_answer": {
                    "recovered_clock_mhz": float(BLC1_CLOCK_MHZ),
                    "hits_at_clock": detect["hits_at_clock"],
                    "rfi_comb_detected": bool(detect["rfi_comb_detected"]),
                    "scramble_null_drop": bool(
                        detect["hits_at_clock"] > detect["scramble_null_hits"]
                    ),
                    "recovery_pass": bool(detect["rfi_comb_detected"]),
                },
                "warnings": [],
                "stance": _blc1_motto_stance_with_recovered(
                    detect["hits_at_clock"], detect["peaks_at_known_rfi"],
                ),
            }
    # No bundled CSV OR no peaks in bundle: use the fetcher result.
    if not result.peak_rows:
        return {
            "label": "blc1_real_data",
            "method": "blc1_comb_detector",
            "verdict": "NO_SIGNAL",  # Sheikh 2021: terrestrial RFI (default)
            "data_source": "Berkeley SETI opendata (NOT scraped)",
            "source_type": "empty",
            "fetch_status": result.fetch_status,
            "ref_bibcode": BLC1_BIBCODE,
            "ref_url": BLC1_REFERENCE_URL,
            "fetched_from": result.fetched_from,
            "fetch_attempts": [
                a if isinstance(a, dict) else a.to_dict()
                for a in result.attempts
            ],
            "n_peaks": 0,
            "license": BLC1_DATA_LICENSE,
            "provenance_note": (
                "Live probe disabled per user brief ('no TB mirror'). "
                "No MJDs/peak-rows obtained. NO synthetic plant used."
            ),
            "plant": base_plant,
            "comb_detection": None,
            "negative_controls": None,
            "known_answer": None,
            "warnings": [
                "no real-data path attempted because the G-BLC1 live "
                "probe is DISABLED by design (no TB mirror).",
                f"fetch_status: {result.fetch_status}; "
                f"see fetch_attempts[] for the {len(result.attempts)} "
                f"admin URLs that were NOT contacted.",
                "to populate: pass --bundled-blc1-csv with a CSV "
                "header `freq_mhz,snr_db,drift_hz_per_s,t_start_mjd,"
                "t_end_mjd,label` of peaks manually transcribed from "
                "Sheikh 2021 supplementary tables.",
            ],
            "stance": _blc1_motto_stance(),
        }
    # Live probe returned peaks (test_force FETCHED; never in production)
    detect = _blc1_run_peak_detector(
        peak_rows=result.peak_rows, clock_guess_mhz=BLC1_CLOCK_MHZ,
        tolerance_mhz=BLC1_COMB_TOLERANCE_MHZ, scramble_seed=seed,
    )
    return {
        "label": "blc1_real_data",
        "method": "blc1_comb_detector",
        "verdict": "NO_SIGNAL",  # Sheikh 2021: BLC1 = terrestrial RFI (default)
        "data_source": result.fetched_from or "Berkeley SETI opendata",
        "source_type": result.fetch_status.lower(),
        "fetch_status": result.fetch_status,
        "ref_bibcode": BLC1_BIBCODE,
        "ref_url": BLC1_REFERENCE_URL,
        "fetched_from": result.fetched_from,
        "fetch_attempts": [
            a if isinstance(a, dict) else a.to_dict()
            for a in result.attempts
        ],
        "n_peaks": detect["n_peaks"],
        "license": BLC1_DATA_LICENSE,
        "provenance_note": (
            f"Real-data path with N={detect['n_peaks']} peaks from "
            f"`{result.fetched_from}`. BLC1 = clock-oscillator RFI per "
            f"Sheikh 2021. License: {BLC1_DATA_LICENSE}. Lab motto: "
            f"comb-hit IS RFI, NOT ET."
        ),
        "plant": base_plant,
        "comb_detection": detect,
        "negative_controls": {
            "scramble_null_hits": detect["scramble_null_hits"],
            "scramble_null_p_value": detect["scramble_null_p_value"],
        },
        "known_answer": {
            "recovered_clock_mhz": float(BLC1_CLOCK_MHZ),
            "hits_at_clock": detect["hits_at_clock"],
            "rfi_comb_detected": bool(detect["rfi_comb_detected"]),
            "scramble_null_drop": bool(
                detect["hits_at_clock"] > detect["scramble_null_hits"]
            ),
            "recovery_pass": bool(detect["rfi_comb_detected"]),
        },
        "warnings": [],
        "stance": _blc1_motto_stance_with_recovered(
            detect["hits_at_clock"], detect["peaks_at_known_rfi"],
        ),
    }


def _blc1_module_missing() -> dict:
    return {
        "label": "blc1_(synthetic|real)",
        "method": "blc1_comb_detector",
        "verdict": "NO_SIGNAL",  # Sheikh 2021: terrestrial RFI (default)
        "data_source": "(no source obtained)",
        "source_type": "empty",
        "fetch_status": "MODULE_MISSING",
        "ref_bibcode": BLC1_BIBCODE,
        "ref_url": BLC1_REFERENCE_URL,
        "fetched_from": None,
        "fetch_attempts": [],
        "n_peaks": 0,
        "license": BLC1_DATA_LICENSE,
        "provenance_note": (
            "blc1_fetcher module not importable in this environment; "
            "G-BLC1 path disabled. Synthetic scaffold remains."
        ),
        "plant": {
            "f_center_mhz": float(BLC1_FREQ_MHZ),
            "f_clock_mhz": float(BLC1_CLOCK_MHZ),
            "drift_hz_per_s": float(BLC1_DRIFT_HZ_PER_S),
        },
        "comb_detection": None,
        "negative_controls": None,
        "known_answer": None,
        "warnings": [
            "no real-data path attempted because the BLC1 fetcher "
            "module is unavailable. NO synthetic plant used."
        ],
        "stance": _blc1_motto_stance(),
    }


def _blc1_motto_stance() -> str:
    return (
        "Structure != message. BLC1 (Breakthrough Listen Candidate 1) "
        "is NOT a confirmed technosignature per Sheikh et al. 2021 "
        "(Nature Astronomy 5 1169, DOI 10.1038/s41550-021-01508-8); "
        "it was an intermodulation product of clock-oscillator RFI at "
        "Parkes. We test period/peak-detection math against BLC1 for "
        "RFI comb detection, NOT for ET claims. Live probe DISABLED per "
        "user brief ('no TB mirror'); bundled-override only. "
        "PERIODICITY/COMB-HIT IS NECESSARY, NOT SUFFICIENT, FOR "
        "ARTIFICIALITY. We do NOT fabricate peak lists."
    )


def _blc1_motto_stance_with_recovered(hits_at_clock: int,
                                         peaks_at_known_rfi: int) -> str:
    return (
        f"BLC1 comb detector reports hits_at_clock={hits_at_clock} and "
        f"peaks_at_known_rfi={peaks_at_known_rfi} on the input peak "
        "list. Sheikh 2021 concluded BLC1 was clock-oscillator RFI; a "
        "positive comb-hit here IS RFI, NOT a technosignature. Lab "
        "motto: STRUCTURE != MESSAGE. COMB-HIT IS NECESSARY, NOT "
        "SUFFICIENT FOR ARTIFICIALITY. We do NOT claim ET."
    )


# --- G3 (Wow! beam-fit): sidereal transit Gaussian+sinc grid search -----
# Lab motto: structure != message. The 6-sample Wow! intensity table is
# genuinely underdetermined (3 DOF after a 3-param Gaussian fit). The
# 2024 PHL@UPR reanalysis (arXiv:2408.08513, CC BY 4.0) attributes Wow!
# to a hydrogen cloud near a solar-type star -- NATURAL. We DO NOT claim
# ET. We DO compute r² for Gaussian, sinc, and constant fits + a
# permutation baseline so the result is mathematically transparent.

def synth_wow_beam_transit(
    mu_idx: float = WOW_TRANSIT_PLANT_MU_IDX,
    sigma_idx: float = WOW_TRANSIT_PLANT_SIGMA_IDX,
    amplitude: float = WOW_TRANSIT_PLANT_AMP,
) -> np.ndarray:
    """Plant N=6 exact Gaussian beam-crossing samples at indices 0..5.

    No noise. Returns a length-6 ndarray. The plant is fully recoverable
    by `fit_wow_beam_transit` (modulo numerical precision and the μ ↔
    6-μ symmetry for a symmetric plant).

    shape: amplitude * exp(-0.5 * ((idx - mu) / sigma)^2)
    """
    idx = np.arange(6, dtype=float)
    return amplitude * np.exp(-0.5 * ((idx - float(mu_idx)) / float(sigma_idx)) ** 2)


def _wow_gaussian_at(idx_arr: np.ndarray, mu: float, sigma: float,
                       amp: float) -> np.ndarray:
    """Inner closed-form Gaussian at sample indices."""
    s = max(float(sigma), 1e-9)
    return float(amp) * np.exp(
        -0.5 * ((np.asarray(idx_arr, dtype=float) - float(mu)) / s) ** 2
    )


def _wow_sinc_at(idx_arr: np.ndarray, mu: float, sigma: float,
                   amp: float) -> np.ndarray:
    """Inner closed-form sinc at sample indices: amp * sinc((idx-mu)/sig)."""
    s = max(float(sigma), 1e-9)
    x = (np.asarray(idx_arr, dtype=float) - float(mu)) / s
    pi_x = np.pi * x
    # sinc(x) = sin(pi*x)/(pi*x) with continuous extension at 0 = 1.
    out = np.where(np.abs(pi_x) < 1e-9, 1.0, np.sin(pi_x) / pi_x)
    return float(amp) * out


def fit_wow_beam_transit(samples, mu_idx_range=(0.0, 5.0),
                          sigma_idx_range=(0.5, 3.0),
                          amp_range=(1.0, 60.0),
                          grid_steps: int = 51) -> dict:
    """Pure-numpy coarse grid search for Gaussian + sinc fits on N=6 samples.

    Returns r² for Gaussian, sinc, constant; recovered (mu, sigma, amp)
    for both fits; residuals; degeneracy_pair for the Gaussian (μ ↔
    6-μ symmetry on a symmetric plant: r² is identical for μ=k vs
    μ=6-k because the residuals are mirror-reflected); underdetermined
    caveat text. No scipy dependency.

    Parameters d.o.f. for any fit K-params on N=6 samples is N - K.
    A constant (K=1) has 5 d.o.f. -- a meaningful baseline.
    """
    samples = np.asarray(samples, dtype=float)
    n = int(len(samples))
    if n == 0:
        return {"n_samples": 0, "r2_constant": 0.0,
                "r2_gaussian": 0.0, "r2_sinc": 0.0,
                "recovered_gaussian": None, "recovered_sinc": None,
                "degeneracy_pair": (None, None),
                "underdetermined": True, "n_dof_gaussian": 0,
                "n_dof_sinc": 0, "n_dof_constant": 0}
    # Constant baseline: best A = mean(y). SS_res_const = sum((y - A)^2).
    a_const = float(np.mean(samples))
    ss_tot = float(np.sum((samples - a_const) ** 2)) or 1e-12
    ss_res_const = float(np.sum((samples - a_const) ** 2))
    r2_const = float(1.0 - ss_res_const / ss_tot)

    # Coarse grid search for Gaussian and sinc.
    mu_grid = np.linspace(float(mu_idx_range[0]), float(mu_idx_range[1]),
                            int(grid_steps))
    sigma_grid = np.linspace(float(sigma_idx_range[0]),
                                float(sigma_idx_range[1]),
                                int(grid_steps))
    grid_idx = np.arange(n, dtype=float)

    best_gauss = (np.inf, None, None, None)
    best_sinc = (np.inf, None, None, None)
    ss_tot_safe = max(ss_tot, 1e-12)
    for mu in mu_grid:
        for sig in sigma_grid:
            g_pred = _wow_gaussian_at(grid_idx, mu, sig, 1.0)
            if float(np.max(np.abs(g_pred))) <= 1e-9:
                continue
            # Closed-form best-amplitude for fixed shape: scale = y . g / g . g
            scale = float(np.dot(samples, g_pred)) / float(np.dot(g_pred, g_pred))
            if scale <= 0.0:
                continue
            g_fit = scale * g_pred
            ss = float(np.sum((samples - g_fit) ** 2))
            if ss < best_gauss[0]:
                best_gauss = (ss, float(mu), float(sig), float(scale))

            s_pred = _wow_sinc_at(grid_idx, mu, sig, 1.0)
            scale_s = float(np.dot(samples, s_pred)) / float(np.dot(s_pred, s_pred))
            if scale_s <= 0.0:
                continue
            s_fit = scale_s * s_pred
            ss_s = float(np.sum((samples - s_fit) ** 2))
            if ss_s < best_sinc[0]:
                best_sinc = (ss_s, float(mu), float(sig), float(scale_s))

    ss_gauss, mu_g, sig_g, amp_g = best_gauss
    ss_sinc, mu_s, sig_s, amp_s = best_sinc
    r2_gauss = float(1.0 - ss_gauss / ss_tot_safe)
    r2_sinc = float(1.0 - ss_sinc / ss_tot_safe)

    # Residuals at the best-fit params.
    g_resid = samples - amp_g * _wow_gaussian_at(grid_idx, mu_g, sig_g, 1.0)
    s_resid = samples - amp_s * _wow_sinc_at(grid_idx, mu_s, sig_s, 1.0)

    # μ ↔ 6-μ symmetry: a SYMMETRIC 6-sample Gaussian has IDENTICAL r² at
    # μ and at (6-μ). For an asymmetric plant (like real Wow!), this is
    # only APPROXIMATE -- surface both candidates.
    candidate_mu_alt = 6.0 - float(mu_g)
    degen_pair = (round(float(mu_g), 4), round(candidate_mu_alt, 4))

    # Underdetermined caveat based on d.o.f.
    n_dof_constant = n - 1
    n_dof_gaussian = n - 3
    n_dof_sinc = n - 3
    underdetermined_note = (
        f"Gaussian fit on N=6 has only {n_dof_gaussian} d.o.f. (N-K=6-3); "
        f"a constant baseline has {n_dof_constant}. With 3 d.o.f. the "
        f"fit is heavily under-determined -- two distinct transits "
        f"(e.g., horn-beam crossing vs transient pulse) can both fit "
        f"the 6 peaks equally well. WOW IS NOT a confirmed technosignature "
        f"per Sheikh et al. 2021 / PHL@UPR 2024 (arXiv:2408.08513, CC BY 4.0). "
        f"Structure != message."
    )

    return {
        "n_samples": n,
        "best_amplitude_constant": round(a_const, 4),
        "r2_constant": round(r2_const, 6),
        "r2_gaussian": round(r2_gauss, 6),
        "r2_sinc": round(r2_sinc, 6),
        "n_dof_constant": int(n_dof_constant),
        "n_dof_gaussian": int(n_dof_gaussian),
        "n_dof_sinc": int(n_dof_sinc),
        "recovered_gaussian": {
            "mu_idx": round(mu_g, 4),
            "sigma_idx": round(sig_g, 4),
            "amplitude": round(amp_g, 4),
            "ss_res": round(ss_gauss, 4),
            "residuals_gauss": [round(float(r), 4) for r in g_resid],
        },
        "recovered_sinc": {
            "mu_idx": round(mu_s, 4),
            "sigma_idx": round(sig_s, 4),
            "amplitude": round(amp_s, 4),
            "ss_res": round(ss_sinc, 4),
            "residuals_sinc": [round(float(r), 4) for r in s_resid],
        },
        "degeneracy_pair": degen_pair,
        "underdetermined_note": underdetermined_note,
        "underdetermined": bool(n_dof_gaussian <= 3),
        "fit_quality_caveat": (
            "Even if r² ≈ 1 from a 3-param fit, the d.o.f. shortage means "
            "the fit is consistent with EITHER a horn-beam transit OR a "
            "transient signal. We cannot distinguish them from 6 bins."
        ),
    }


def wow_beam_scramble_null(samples,
                            n_permutations: int = WOW_TRANSIT_PERMUTATIONS,
                            seed: int = 0) -> dict:
    """Permute the 6 samples (n_permutations times) and re-fit Gaussian each.

    Returns median + p5/p95 r² distribution across permutations.
    Wow!'s real-data r² should land either CLEARLY above the scramble
    distribution (structure) or roughly AT the scramble median (no
    structure). The fit MUST NOT silently claim structure when the
    scramble-null is comparable.
    """
    samples = np.asarray(samples, dtype=float)
    rng = np.random.default_rng(seed)
    r2_distribution: list[float] = []
    mu_distribution: list[float] = []
    n = len(samples)
    if n == 0:
        return {"n_samples": 0, "n_permutations": 0,
                "r2_median": 0.0, "r2_p5": 0.0, "r2_p95": 0.0,
                "mu_distribution_median": 0.0}
    for _ in range(int(n_permutations)):
        permuted = rng.permutation(samples)
        fit = fit_wow_beam_transit(permuted)
        r2_distribution.append(float(fit["r2_gaussian"]))
        if fit["recovered_gaussian"] is not None:
            mu_distribution.append(float(
                fit["recovered_gaussian"]["mu_idx"]
            ))
    arr = np.asarray(r2_distribution, dtype=float)
    mu_arr = np.asarray(mu_distribution, dtype=float)
    return {
        "n_samples": int(n),
        "n_permutations": int(n_permutations),
        "r2_median": round(float(np.median(arr)), 6),
        "r2_p5": round(float(np.percentile(arr, 5)), 6),
        "r2_p95": round(float(np.percentile(arr, 95)), 6),
        "r2_min": round(float(np.min(arr)), 6),
        "r2_max": round(float(np.max(arr)), 6),
        "mu_distribution_median": round(float(np.median(mu_arr)), 4)
            if len(mu_arr) else 0.0,
    }


def run_wow_beam_fit(mode: str = "synthetic", seed: int = 0) -> dict:
    """Orchestrator. mode ∈ {'synthetic', 'real'}.

    'synthetic' plants a noise-free 6-sample Gaussian at the canonical
    (μ=2.5, σ=1.5, A=30) and asserts recovery_pass=True (math-validation).

    'real' uses the WOW_SAMPLES_SIGMA tuple (Ehman's handwritten
    transcript); runs the same fits + scramble null + lab motto
    caveat; the recovery can NOT be PASS/FALL since the real data is
    not pre-planted -- instead we report r² + underdetermined caveat +
    2024 PHL@UPR cite.
    """
    if mode == "synthetic":
        samples = synth_wow_beam_transit(
            mu_idx=WOW_TRANSIT_PLANT_MU_IDX,
            sigma_idx=WOW_TRANSIT_PLANT_SIGMA_IDX,
            amplitude=WOW_TRANSIT_PLANT_AMP,
        )
        truth = {
            "mu_idx": float(WOW_TRANSIT_PLANT_MU_IDX),
            "sigma_idx": float(WOW_TRANSIT_PLANT_SIGMA_IDX),
            "amplitude": float(WOW_TRANSIT_PLANT_AMP),
        }
        data_source = "synthetic_plant"
        data_label = "synthetic"
    elif mode == "real":
        samples = np.asarray(WOW_SAMPLES_SIGMA, dtype=float)
        truth = None
        data_source = "Ehman_transcript_6EQUJ5"
        data_label = "real"
    else:
        return {
            "label": "wow_beam_fit",
            "method": "wow_beam_transit_fit",
            "data_source": "",
            "data_label": mode,
            "mode": mode,
            "fetch_status": "INVALID_MODE",
            "fit": None, "scramble_null": None,
            "known_answer": None, "warnings": ["unknown mode"],
            "stance": _wow_beam_motto_stance(),
        }

    fit = fit_wow_beam_transit(samples)
    scramble = wow_beam_scramble_null(samples, seed=seed)
    if truth is not None:
        mu_rec = fit["recovered_gaussian"]["mu_idx"]
        sig_rec = fit["recovered_gaussian"]["sigma_idx"]
        amp_rec = fit["recovered_gaussian"]["amplitude"]
        recovery_pass = bool(
            abs(mu_rec - truth["mu_idx"]) <= WOW_TRANSIT_RECOVERY_TOL_IDX
            and abs(sig_rec - truth["sigma_idx"]) <= WOW_TRANSIT_RECOVERY_TOL_IDX
            and abs(amp_rec - truth["amplitude"]) <= 1e-6
        )
        recovery_summary = {
            "mu_err_idx": round(abs(mu_rec - truth["mu_idx"]), 6),
            "sigma_err_idx": round(abs(sig_rec - truth["sigma_idx"]), 6),
            "amplitude_err": round(abs(amp_rec - truth["amplitude"]), 6),
            "recovery_pass": bool(recovery_pass),
        }
    else:
        recovery_summary = {
            "mu_err_idx": None, "sigma_err_idx": None,
            "amplitude_err": None,
            "recovery_pass": None,
            "note": "real data has no planted ground truth; r² + DOF + "
                     "scramble null are the only honest outputs.",
        }

    # cross-check: real-data r²_gaussian vs scramble median.
    cross_check = None
    if scramble["r2_median"] is not None:
        cross_check = {
            "structure_above_scramble_median": bool(
                fit["r2_gaussian"] > scramble["r2_median"]
            ),
            "delta_real_vs_scramble_median": round(
                fit["r2_gaussian"] - scramble["r2_median"], 6
            ),
        }

    return {
        "label": "wow_beam_fit",
        "method": "wow_beam_transit_grid_fit",
        "data_source": data_source,
        "data_label": data_label,
        "mode": mode,
        "fetch_status": "OK",
        "samples": [round(float(x), 4) for x in samples],
        "plant": truth,
        "fit": fit,
        "scramble_null": scramble,
        "cross_check_scramble": cross_check,
        "known_answer": recovery_summary,
        "warnings": [
            "structure != message; N=6 fit is heavily underdetermined; "
            "we do NOT claim detection of artificial origin.",
            "2024 PHL@UPR reanalysis (arXiv:2408.08513, CC BY 4.0) "
            "attributes Wow! to a hydrogen cloud near a solar-type star "
            "-- NATURAL mechanism.",
        ],
        "stance": _wow_beam_motto_stance(),
    }


def _wow_beam_motto_stance() -> str:
    """Lab motto + underdetermined caveat. Used by ALL G3 outputs."""
    return (
        "Structure != message. The 1977 Wow! signal is a 6-sample "
        "intensity table, NOT a time series. A 3-parameter Gaussian fit "
        "on N=6 has only 3 d.o.f. -- heavily underdetermined. The fit is "
        "consistent with EITHER a horn-beam transit OR a transient pulse "
        "(or a hydrogen cloud per PHL@UPR 2024, arXiv:2408.08513). We "
        "do NOT claim detection of an artificial origin. The 2024 "
        "PHL@UPR reanalysis (CC BY 4.0) attributes Wow! to a hydrogen "
        "cloud near a solar-type star -- NATURAL. The N=6 fit gives us "
        "NO statistical power to distinguish transient from beam-crossing. "
        "Periodicity / beam-crossing is necessary, NOT sufficient for "
        "artificiality. Lab motto: structure != message."
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


# --- Cat2 (CHIME/FRB Catalog 2) periodicity known-answer (R1++) ----------
# The Second CHIME/FRB Catalog (CHIME/FRB Collab. 2026, ApJS 283 34; AAS
# Open Access) lists 83 known repeaters. Two have well-published activity
# periods we treat as PUBLIC-DOMAIN FACTS (NOT fabricated arrival arrays):
#   FRB 20180916B ~ 16.35 d  (CHIME/FRB 2020; Pastor-Marazuela 2020)
#   FRB 20121102A ~ 157 d    (Rajwade 2020; Cruces 2021)
# run_cat2_synthetic plants recoverable multi-source schedules and asserts
# per-source epoch-fold recovery + a per-source scramble null.
# run_cat2_real parks honestly when the Cat 2 portal is offline; it NEVER
# fabricates MJDs. FRB activity periodicity is a NATURAL cycle, not a
# message: periodicity is necessary, NOT sufficient, for artificiality.

CAT2_BIBCODE = "2026ApJS..283...34C"
CAT2_REFERENCE_URL = "https://iopscience.iop.org/article/10.3847/1538-4365/ae3828"
CAT2_KNOWN_REPEATERS_D: dict = {
    "FRB 20180916B": 16.35,
    "FRB 20121102A": 157.0,
}
CAT2_TOLERANCE_D = 1.0
# Per-source synthetic-plant params: (n_arrivals, obs_window_d, jitter_d,
# grid_lo_d, grid_hi_d). Validated offline to recover the period within
# CAT2_TOLERANCE_D across seeds.
_CAT2_SYNTH_PARAMS: dict = {
    "FRB 20180916B": (30, 500.0, 0.3, 10.0, 30.0),
    "FRB 20121102A": (24, 4000.0, 0.5, 140.0, 175.0),
}


def _cat2_motto_stance() -> str:
    return (
        "Structure != message. The Second CHIME/FRB Catalog (CHIME/FRB "
        "Collab. 2026, ApJS 283 34) periodic repeaters have NATURAL "
        "activity cycles (e.g. FRB 20180916B ~16.35 d). Recovering a "
        "period is a math-validation outcome, NOT evidence of "
        "artificiality. We do NOT fabricate arrival MJDs; on a failed "
        "fetch the run reports fetch_status + attempts and stops. "
        "Periodicity is necessary, NOT sufficient, for artificiality."
    )


def _cat2_module_missing() -> dict:
    return {
        "label": "cat2_real_data",
        "method": "real_cat2_multisource_epoch_fold_z2",
        "data_source": "(no source obtained)",
        "source_type": "empty",
        "fetch_status": "MODULE_MISSING",
        "ref_bibcode": CAT2_BIBCODE,
        "ref_url": CAT2_REFERENCE_URL,
        "fetched_from": None,
        "fetch_attempts": [],
        "n_sources": 0,
        "n_bursts_total": 0,
        "provenance_note": (
            "cat2_real_sources module not importable in this environment; "
            "Cat 2 real-data path disabled. Synthetic Cat 2 known-answer "
            "remains as a math-validation tool."
        ),
        "plant": {
            "known_repeater_periods_d": dict(CAT2_KNOWN_REPEATERS_D),
            "tolerance_d": CAT2_TOLERANCE_D,
        },
        "per_source": {},
        "known_answer": None,
        "negative_controls": None,
        "warnings": [
            "no real-data path attempted because the Cat 2 source module "
            "is unavailable. NO synthetic plant was used."
        ],
        "stance": _cat2_motto_stance(),
    }


def _cat2_match_known_period(name: str):
    """Return the published period (d) if `name` matches a known repeater.

    Matches on the numeric core so 'FRB20180916B', 'FRB 20180916B',
    'J0158+65' variants etc. still line up with the published entry.
    """
    digits = "".join(ch for ch in str(name) if ch.isdigit())
    for kname, kper in CAT2_KNOWN_REPEATERS_D.items():
        kdigits = "".join(ch for ch in kname if ch.isdigit())
        if kdigits and kdigits in digits:
            return kper
    return None


def _cat2_grid_for_period(period_d: float) -> tuple:
    """A ±40% search window around a known period (floored at 2 d)."""
    return (max(2.0, period_d * 0.6), period_d * 1.4)


def run_cat2_synthetic(seed: int = 0, grid_step: float = 0.05) -> dict:
    """SYNTHETIC Cat 2 multi-source periodicity known-answer.

    Plants recoverable burst schedules for the two CHIME/FRB repeaters
    with published activity periods, runs a per-source epoch-fold and a
    per-source scramble null (uniform-in-window shuffle destroys the
    periodicity). A pass proves the epoch-fold + scramble-null math for
    the Cat 2 multi-source layer; it says NOTHING about the real FRBs.
    """
    per_source: dict = {}
    all_pass = True
    null_ok = True
    for i, (name, period) in enumerate(CAT2_KNOWN_REPEATERS_D.items()):
        n, window, jitter, glo, ghi = _CAT2_SYNTH_PARAMS[name]
        times = synth_frb_arrivals(
            period_d=period, n_arrivals=n, obs_window_d=window,
            jitter_d=jitter, seed=seed + i,
        )
        grid = np.arange(glo, ghi + 1e-9, grid_step)
        fold = epoch_fold(times, grid)
        rng = np.random.default_rng(seed + 7 + i)
        shuf = rng.uniform(0.0, window, size=len(times))
        shuf_fold = epoch_fold(shuf, grid)
        err = abs(fold["best_period"] - period)
        src_pass = bool(err <= CAT2_TOLERANCE_D
                        and fold["best_z2"] > shuf_fold["best_z2"])
        all_pass = all_pass and src_pass
        null_ok = null_ok and bool(shuf_fold["best_z2"] < fold["best_z2"])
        per_source[name] = {
            "published_period_d": float(period),
            "n_bursts": int(len(times)),
            "recovered_period_d": fold["best_period"],
            "recovered_z2": fold["best_z2"],
            "recovered_p_value": fold["best_p_value"],
            "recovery_error_d": round(err, 5),
            "recovery_pass": src_pass,
            "scramble_null_z2_max": shuf_fold["best_z2"],
            "scramble_null_best_period_d": shuf_fold["best_period"],
            "period_grid_d": [float(glo), float(ghi), float(grid_step)],
        }
    primary = per_source["FRB 20180916B"]
    return {
        "label": "cat2_synthetic",
        "method": "cat2_multisource_epoch_fold_z2",
        "n_sources": len(per_source),
        "per_source": per_source,
        "known_answer": {
            "primary_source": "FRB 20180916B",
            "primary_published_period_d": 16.35,
            "primary_recovered_period_d": primary["recovered_period_d"],
            "primary_recovery_error_d": primary["recovery_error_d"],
            "recovers_16p35d": bool(primary["recovery_pass"]),
            "all_sources_recovery_pass": bool(all_pass),
        },
        "negative_controls": {
            "method": "per-source uniform-in-window shuffle of arrival MJDs",
            "scramble_null_below_recovered": bool(null_ok),
        },
        "reference_bibcode": CAT2_BIBCODE,
        "reference_url": CAT2_REFERENCE_URL,
        "stance": (
            "SCAFFOLD / KNOWN-ANSWER. Multi-source arrival schedules are "
            "SYNTHESIZED around the published activity periods of two "
            "CHIME/FRB repeaters (FRB 20180916B ~16.35 d, Pastor-Marazuela "
            "2020; FRB 20121102A ~157 d, Cruces 2021). A pass proves the "
            "epoch-fold + scramble-null math for the Cat 2 multi-source "
            "layer; it says NOTHING about the real FRBs. FRB periodicity is "
            "a NATURAL activity cycle, not a message. Structure != message; "
            "periodicity is necessary, NOT sufficient, for artificiality."
        ),
    }


def run_cat2_real(
    bundled_csv_path: Path | None = None,
    seed: int = 0,
    grid_step: float = 0.05,
    force_status_for_tests: str | None = None,
    use_cat2_fetcher: bool = True,
) -> dict:
    """REAL-DATA Cat 2 path. Loads published multi-source burst MJDs via
    cat2_real_sources and runs a per-source epoch-fold + scramble null on
    the ACTUAL arrivals. NO synthetic plant injection -- if no MJDs are
    available (portal offline / parking), returns an honest-empty result
    with the full fetch history and no epoch-fold attempt.
    """
    if C2S is None:
        return _cat2_module_missing()
    src = C2S.load_published_cat2_bursts(
        bundled_csv_path=bundled_csv_path,
        use_cat2_fetcher=use_cat2_fetcher,
        force_status_for_tests=force_status_for_tests,
    )
    base_plant = {
        "known_repeater_periods_d": dict(CAT2_KNOWN_REPEATERS_D),
        "tolerance_d": CAT2_TOLERANCE_D,
    }
    if not src.has_any_mjds:
        return {
            "label": "cat2_real_data",
            "method": "real_cat2_multisource_epoch_fold_z2",
            "data_source": src.source_name,
            "source_type": src.source_type,
            "fetch_status": src.fetch_status,
            "ref_bibcode": src.reference_bibcode,
            "ref_url": src.reference_url,
            "fetched_from": src.fetched_from,
            "fetch_attempts": src.fetch_attempts,
            "n_sources": 0,
            "n_bursts_total": 0,
            "provenance_note": src.provenance_note,
            "plant": base_plant,
            "per_source": {},
            "known_answer": None,
            "negative_controls": None,
            "warnings": [
                "no real-data path attempted because the Cat 2 source "
                "returned zero MJDs across all sources. NO synthetic plant "
                "was used.",
                "to populate: (a) wait for the CHIME/FRB Cat 2 portal to "
                "come back online and rerun; or (b) pass --bundled-cat2-csv "
                "with a CSV of `name,mjd` rows transcribed from the "
                "published Second CHIME/FRB Catalog.",
            ],
            "stance": _cat2_motto_stance(),
        }
    # Have MJDs -> per-source epoch-fold pipeline.
    per_source: dict = {}
    n_bursts_total = 0
    for name, mjds in src.rows_by_source.items():
        arr = np.asarray(sorted(float(m) for m in mjds), dtype=float)
        n_bursts_total += int(len(arr))
        if len(arr) < 3:
            per_source[name] = {
                "n_bursts": int(len(arr)),
                "recovered_period_d": None,
                "note": "need >=3 bursts to epoch-fold; source skipped",
            }
            continue
        known = _cat2_match_known_period(name)
        glo, ghi = _cat2_grid_for_period(known) if known is not None \
            else (2.0, 400.0)
        grid = np.arange(glo, ghi + 1e-9, grid_step)
        fold = epoch_fold(arr, grid)
        rng = np.random.default_rng(seed + len(name))
        lo, hi = float(arr.min()), float(arr.max())
        shuf = rng.uniform(lo, hi if hi > lo else lo + 1.0, size=len(arr))
        shuf_fold = epoch_fold(shuf, grid)
        entry = {
            "n_bursts": int(len(arr)),
            "recovered_period_d": fold["best_period"],
            "recovered_z2": fold["best_z2"],
            "recovered_p_value": fold["best_p_value"],
            "scramble_null_z2_max": shuf_fold["best_z2"],
            "period_grid_d": [float(glo), float(ghi), float(grid_step)],
        }
        if known is not None:
            err = abs(fold["best_period"] - known)
            entry["published_period_d"] = float(known)
            entry["recovery_error_d"] = round(err, 5)
            entry["recovery_pass"] = bool(
                err <= CAT2_TOLERANCE_D
                and fold["best_z2"] > shuf_fold["best_z2"]
            )
        per_source[name] = entry
    recognised = {k: v for k, v in per_source.items()
                  if "recovery_pass" in v}
    return {
        "label": "cat2_real_data",
        "method": "real_cat2_multisource_epoch_fold_z2",
        "data_source": src.source_name,
        "source_type": src.source_type,
        "fetch_status": src.fetch_status,
        "ref_bibcode": src.reference_bibcode,
        "ref_url": src.reference_url,
        "fetched_from": src.fetched_from,
        "fetch_attempts": src.fetch_attempts,
        "n_sources": int(len(per_source)),
        "n_bursts_total": int(n_bursts_total),
        "provenance_note": src.provenance_note,
        "plant": base_plant,
        "per_source": per_source,
        "negative_controls": {
            "method": "per-source uniform-in-window shuffle of arrival MJDs",
        },
        "known_answer": {
            "n_recognised_repeaters": int(len(recognised)),
            "recognised_recovery_pass": {
                k: bool(v.get("recovery_pass")) for k, v in recognised.items()
            },
        } if recognised else None,
        "warnings": [],
        "stance": (
            f"Real-data Cat 2 path executed with N_sources="
            f"{len(per_source)} ({n_bursts_total} bursts) from "
            f"`{src.source_name}` (source_type={src.source_type}, "
            f"fetch_status={src.fetch_status}). Any recovered activity "
            f"cycle is a NATURAL FRB phenomenon, NOT a message. "
            f"Structure != message."
        ),
    }


def analyze(
    mode: str = "all",
    seed: int = 0,
    bundled_real_json: Path | None = None,
    bundled_pulsar_csv: Path | None = None,
    bundled_blc1_csv: Path | None = None,
    bundled_cat2_csv: Path | None = None,
) -> dict:
    """Orchestrator: returns a single dict containing all sub-runs.

    `mode ∈ {'all', 'known_train', 'wow', 'frb_180916',
             'frb_180916_real', 'pulsar_vela_synthetic',
             'pulsar_vela_real', 'pulsar_vela',
             'blc1_synthetic', 'blc1_real', 'blc1',
             'cat2_synthetic', 'cat2_real', 'cat2',
             'wow_beam_fit', 'wow_beam_fit_synthetic',
             'wow_beam_fit_real'}`.

    `bundled_real_json` is forwarded to `run_frb_180916_real` when mode
    includes 'frb_180916_real'.
    `bundled_pulsar_csv` is forwarded to `run_pulsar_vela` when mode
    includes `pulsar_vela*`.
    `bundled_blc1_csv` is forwarded to `run_blc1_real` when mode
    includes `blc1*`.
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
    if mode == "blc1_synthetic":
        out["blc1_synthetic"] = run_blc1_synthetic(seed=seed)
    if mode == "wow_beam_fit_synthetic":
        out["wow_beam_fit"] = run_wow_beam_fit(mode="synthetic", seed=seed)
    if mode == "wow_beam_fit_real":
        out["wow_beam_fit"] = run_wow_beam_fit(mode="real", seed=seed)
    if mode == "wow_beam_fit":
        out["wow_beam_fit"] = run_wow_beam_fit(mode="synthetic", seed=seed)
    if mode == "blc1_real":
        out["blc1_real_data"] = run_blc1_real(
            bundled_csv_path=bundled_blc1_csv,
            seed=seed,
        )
    if mode == "blc1":
        # Fall-through: prefer real-data if a CSV override was given,
        # else default to synthetic known-answer plant (proves math).
        if bundled_blc1_csv is not None:
            out["blc1_real_data"] = run_blc1_real(
                bundled_csv_path=bundled_blc1_csv,
                seed=seed,
            )
        else:
            out["blc1_synthetic"] = run_blc1_synthetic(seed=seed)
    if mode == "cat2_synthetic":
        out["cat2_synthetic"] = run_cat2_synthetic(seed=seed)
    if mode == "cat2_real":
        out["cat2_real_data"] = run_cat2_real(
            bundled_csv_path=bundled_cat2_csv,
            seed=seed,
        )
    if mode == "cat2":
        # Fall-through: prefer real-data if a CSV override was given,
        # else default to the synthetic multi-source known-answer.
        if bundled_cat2_csv is not None:
            out["cat2_real_data"] = run_cat2_real(
                bundled_csv_path=bundled_cat2_csv,
                seed=seed,
            )
        else:
            out["cat2_synthetic"] = run_cat2_synthetic(seed=seed)
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
    if "pulsar_vela_synthetic" in report:
        pv = report["pulsar_vela_synthetic"]
        ka = pv.get("known_answer") or {}
        nc = pv.get("negative_controls") or {}
        plant = pv.get("plant") or {}
        lines += [
            "## Vela pulsar (PSR B0833-45 / J0835-4510) — SYNTHETIC positive-control",
            "",
            f"- source: **synthetic plant** (no real MJDs injected; "
            "pulsar_fetcher NEVER fabricates arrival times)",
            f"- plant: PSR **{plant.get('psr_b1950', '?')}** / "
            f"**{plant.get('psr_j2000', '?')}**, P0 = "
            f"**{plant.get('true_period_s', 0):.9f} s** "
            f"(freq ~{plant.get('true_freq_hz', 0):.4f} Hz), "
            f"N={plant.get('n_arrivals', '?')} arrivals over "
            f"{plant.get('obs_window_d', '?')} d, jitter "
            f"{plant.get('jitter_s', '?')} s "
            f"(synthetic coherence is BETTER than real Vela — see motto)",
            f"- recovery: best period **{ka.get('recovered_period_s')}** "
            f"(err |P - P0| = {ka.get('recovery_error_s')} s, "
            f"Z^2 = {ka.get('recovered_z2')}, "
            f"p = {ka.get('recovered_p_value')}); "
            f"**{'PASS' if ka.get('recovery_pass') else 'FAIL'}** "
            "(proves the math; does NOT imply artificial origin)",
            f"- shuffled uniform null: max Z^2 = "
            f"{nc.get('shuffled_uniform_z2_max')}, "
            f"p = {nc.get('shuffled_uniform_z2_p_value')}, "
            f"best period = {nc.get('shuffled_uniform_best_period_s')} s — "
            "no signal",
            "",
            "_lab motto:_ Structure != message. Vela is the universe's most "
            "famous NATURAL clock (Manchester+2005 AJ 129 1993; PPTA DR3 "
            "Zic+2023). Synthetic fits a perfect plant and proves the epoch-"
            "fold implementation works. It tells us NOTHING about the real "
            "pulsar, and it does NOT imply artificial origin. Periodicity "
            "is necessary, NOT sufficient, for artificiality.",
            "",
        ]
    if "pulsar_vela_real_data" in report:
        rd = report["pulsar_vela_real_data"]
        plant = rd.get("plant") or {}
        lines += [
            "## Vela pulsar (PSR B0833-45 / J0835-4510) — REAL-DATA path",
            "",
            f"- data source: **{rd.get('data_source', '?')}** "
            f"(source_type=`{rd.get('source_type', '?')}`, "
            f"fetch_status=`{rd.get('fetch_status', '?')}`)",
            f"- reference: bibcode=`{rd.get('ref_bibcode') or '-'}`, "
            f"url=`{rd.get('ref_url') or '-'}`",
            f"- published P0: **{plant.get('true_period_s', 0):.9f} s** "
            f"(Manchester+2005 AJ 129 1993, DOI 10.1086/428488)",
            f"- N arrivals: **{rd.get('n_arrivals', 0)}** "
            f"(mjd first={rd.get('arrival_mjd_first')}, "
            f"last={rd.get('arrival_mjd_last')})",
            "",
        ]
        if rd.get("warnings"):
            lines += [
                "### YELLOW BANNER - real-data path could NOT obtain MJDs",
                "",
            ]
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
                    if isinstance(a, dict):
                        url = a.get("url", "?")
                        verdict = a.get("verdict", "?")
                        http = a.get("http_status", "?")
                        err = a.get("error") or a.get("error_msg") or "-"
                        nbytes = a.get("content_bytes", 0)
                    else:
                        url = getattr(a, "url", "?")
                        verdict = getattr(a, "verdict", "?")
                        http = getattr(a, "http_status", "?")
                        err = getattr(a, "error", None) or "-"
                        nbytes = getattr(a, "content_bytes", 0)
                    lines.append(
                        f"  {i}. `{str(url)[:80]}` -> {verdict} "
                        f"(http={http}, bytes={nbytes}, err={err})"
                    )
                if len(attempts) > 6:
                    lines.append(f"  ... and {len(attempts) - 6} more")
                lines.append("")
        else:
            ka = rd.get("known_answer") or {}
            nc = rd.get("negative_controls") or {}
            lines += [
                f"- recovered period: **{ka.get('recovered_period_s')}** "
                f"(err |P - P0| = {ka.get('recovery_error_s')} s, "
                f"Z^2 = {ka.get('recovered_z2')}, "
                f"p = {ka.get('recovered_p_value')}); "
                f"**{'PASS' if ka.get('recovery_pass') else 'FAIL'}** "
                "(math-validation only)",
                f"- shuffled uniform null: max Z^2 = "
                f"{nc.get('shuffled_uniform_z2_max')}, "
                f"p = {nc.get('shuffled_uniform_z2_p_value')}, "
                f"best period = {nc.get('shuffled_uniform_best_period_s')} s — "
                "no signal (real Vela P0 is the PLANT)",
                "",
                f"_stance:_ {rd.get('stance', '')}",
                "",
            ]
    if "wow_beam_fit" in report:
        wb = report["wow_beam_fit"]
        fit = wb.get("fit") or {}
        rb = fit.get("recovered_gaussian") or {}
        rs = fit.get("recovered_sinc") or {}
        sn = wb.get("scramble_null") or {}
        cross = wb.get("cross_check_scramble") or {}
        ka = wb.get("known_answer") or {}
        plant = wb.get("plant") or {}
        lines += [
            "## Wow! (1977) — SIDEREAL TRANSIT fit (underdetermined)",
            "",
            f"- data source: **{wb.get('data_source','?')}** "
            f"(data_label=`{wb.get('data_label','?')}`)",
            f"- samples: {[round(float(x), 4) for x in (wb.get('samples') or [])]} "
            "(Ehman's handwritten 6EQUJ5 transcript if real)",
            (
                f"- plant (synthetic only): mu={plant.get('mu_idx')}, "
                f"sigma={plant.get('sigma_idx')}, "
                f"amp={plant.get('amplitude')} (exact 6-bin Gaussian, "
                "no noise)"
                if wb.get('data_label') == 'synthetic' else
                "- plant: n/a (real data; no ground truth)"
            ),
            f"- r² for constant baseline: **{fit.get('r2_constant', 0):.6f}** "
            f"(DO={fit.get('n_dof_constant', 0)})",
            f"- r² for Gaussian fit:  **{fit.get('r2_gaussian', 0):.6f}** "
            f"(DO={fit.get('n_dof_gaussian', 0)}) -- recovered (mu_idx="
            f"{rb.get('mu_idx')}, sigma_idx={rb.get('sigma_idx')}, "
            f"amp={rb.get('amplitude')})",
            f"- r² for sinc fit:       **{fit.get('r2_sinc', 0):.6f}** "
            f"(DO={fit.get('n_dof_sinc', 0)}) -- recovered (mu_idx="
            f"{rs.get('mu_idx')}, sigma_idx={rs.get('sigma_idx')}, "
            f"amp={rs.get('amplitude')})",
            (
                f"- recovery_pass (synthetic): "
                f"**{'PASS' if ka.get('recovery_pass') else 'FAIL'}** "
                f"(mu_err={ka.get('mu_err_idx')}, "
                f"sigma_err={ka.get('sigma_err_idx')}, "
                f"amp_err={ka.get('amplitude_err')})"
                if ka.get('recovery_pass') is not None else
                "- recovery_pass: n/a (real data has no planted ground truth)"
            ),
            f"- degeneracy_pair (μ ↔ 6-μ symmetry on symmetric plants): "
            f"{fit.get('degeneracy_pair')}",
            f"- scrambled-null permutation baseline: n={sn.get('n_permutations', 0)}, "
            f"r² median={sn.get('r2_median', 0):.6f}, "
            f"r² p5={sn.get('r2_p5', 0):.6f}, "
            f"r² p95={sn.get('r2_p95', 0):.6f}",
            (
                f"- structure vs scramble: real r²_gaussian "
                f"{'is ABOVE' if cross.get('structure_above_scramble_median') else 'is AT/UNDER'} "
                f"scramble median by "
                f"{cross.get('delta_real_vs_scramble_median', 0):.6f}"
                if cross else
                "- structure vs scramble: n/a"
            ),
            "",
            "_Underdetermined caveat:_ " + (
                str(fit.get('underdetermined_note', ''))
            ),
            "",
            "_stance:_ " + str(wb.get('stance', '')),
            "",
        ]
    if "blc1_synthetic" in report:
        bs = report["blc1_synthetic"]
        plant = bs.get("plant") or {}
        ka = bs.get("known_answer") or {}
        cd = bs.get("comb_detection") or {}
        nc = bs.get("negative_controls") or {}
        lines += [
            "## BLC1 (Breakthrough Listen Candidate 1) — SYNTHETIC clock-comb known-answer",
            "",
            f"- source: **synthetic plant** (no live fetch attempted; per "
            "user brief 'no TB mirror' the G-BLC1 real-data path is "
            "DISABLED by default)",
            f"- plant: f_center = **{plant.get('f_center_mhz')} MHz**, "
            f"clock spacing = **{plant.get('f_clock_mhz')} MHz** "
            f"(Sheikh 2021 supplementary), drift = "
            f"**{plant.get('drift_hz_per_s')} Hz/s**, "
            f"{plant.get('harmonics')} harmonics, "
            f"central peak SNR = {plant.get('snr_base_db')} dB "
            f"decaying {plant.get('snr_decay_db')} dB/step",
            f"- commander: \u26a0\ufe0f Sheikh 2021 (Nat. Astron. 5 1169, "
            "DOI 10.1038/s41550-021-01508-8) concluded BLC1 was an "
            "INTERMODULATION PRODUCT of clock-oscillator RFI at Parkes, "
            "NOT a confirmed technosignature. The synthetic plant mimics "
            "this signature for math-validation only. A positive comb-hit "
            "here IS RFI, NOT ET.",
            f"- comb-detection: n_peaks = **{cd.get('n_peaks')}**, "
            f"hits_at_clock = **{cd.get('hits_at_clock')}** "
            f"(fraction {cd.get('hits_at_clock_fraction'):.3f}), "
            f"peaks_at_known_rfi = {cd.get('peaks_at_known_rfi')}",
            f"- recovery_pass: **{'PASS' if ka.get('recovery_pass') else 'FAIL'}** "
            f"(rfi_comb_detected={ka.get('rfi_comb_detected')}, "
            f"scramble_null_drop={ka.get('scramble_null_drop')})",
            f"- scrambled-null control: hits = "
            f"{nc.get('scramble_null_hits')} (band "
            f"{nc.get('scramble_null_band_mhz_lo'):.3f}.."
            f"{nc.get('scramble_null_band_mhz_hi'):.3f} MHz); "
            f"p-value = {nc.get('scramble_null_p_value'):.3e} -- "
            "permute the peak freqs uniformly and the comb-hit "
            "should DROP to noise.",
            "",
            "### ON/OFF cadence + harmonic-family (Sheikh 2021 interpretation)",
            "",
            (
                lambda oo, ha, vd: "\n".join([
                    f"- **verdict: `{vd}`** — the planted family persists in "
                    f"OFF and is a regular comb → terrestrial RFI. (The real "
                    f"BLC1 path defaults to `NO_SIGNAL`.)",
                    f"- ON/OFF cadence: ON hits_at_clock = "
                    f"**{oo.get('on_hits_at_clock')}**, OFF hits_at_clock = "
                    f"**{oo.get('off_hits_at_clock')}** → "
                    f"persists_in_off = **{oo.get('persists_in_off')}**. A "
                    f"genuine celestial source is ON-only; RFI leaks into "
                    f"OFF. Cadence is necessary, NOT sufficient.",
                    f"- ON-only *contrast* control (OFF = off-comb noise): "
                    f"cadence_consistent_with_source = "
                    f"**{report['blc1_synthetic'].get('on_off_contrast_on_only', {}).get('cadence_consistent_with_source')}** "
                    f"— shows the discriminator has real power (it is not a "
                    f"dead detector), yet an ON-only pass still would NOT "
                    f"prove ET.",
                    f"- harmonic-family Δf: mean = "
                    f"**{ha.get('mean_delta_f_mhz')} MHz**, "
                    f"CV = **{ha.get('cv_delta_f')}** → regular_comb = "
                    f"**{ha.get('regular_comb')}**. Equal spacing is the "
                    f"intermodulation fingerprint of local-oscillator "
                    f"clocks — the analysis that ultimately killed BLC1.",
                ])
            )(
                bs.get("on_off_control") or {},
                bs.get("harmonic_family") or {},
                bs.get("verdict", "?"),
            ),
            "",
            "_stance:_ Structure != message. BLC1 = clock-oscillator RFI "
            "per Sheikh 2021, NOT a confirmed technosignature. Periodicity "
            "(comb structure) IS NECESSARY, NOT SUFFICIENT, FOR "
            "ARTIFICIALITY. We do NOT fabricate peak lists. Lab motto: "
            "even a positive comb-hit is RFI until proven otherwise.",
            "",
        ]
    if "blc1_real_data" in report:
        rd = report["blc1_real_data"]
        plant = rd.get("plant") or {}
        lines += [
            "## BLC1 (Breakthrough Listen Candidate 1) — REAL-DATA path "
            "(DISABLED; bundled override only)",
            "",
            f"- data source: **{rd.get('data_source', '?')}** "
            f"(source_type=`{rd.get('source_type', '?')}`, "
            f"fetch_status=`{rd.get('fetch_status', '?')}`)",
            f"- reference: bibcode=`{rd.get('ref_bibcode') or '-'}`, "
            f"url=`{rd.get('ref_url') or '-'}`",
            f"- license: `{rd.get('license') or '-'}`",
            f"- f_center = **{plant.get('f_center_mhz')} MHz** "
            f"(BLC1 detection freq); clock = "
            f"**{plant.get('f_clock_mhz')} MHz**; drift = "
            f"**{plant.get('drift_hz_per_s')} Hz/s**",
            "",
        ]
        if rd.get("warnings"):
            lines += ["### 🟡 YELLOW BANNER - G-BLC1 live probe DISABLED "
                       "by design (no TB mirror)",
                       "",
                       ]
            for w in rd["warnings"]:
                lines.append(f"  - {w}")
            lines.append("")
            note = (rd.get("provenance_note") or "")[:600]
            lines.append(f"_provenance:_ {note}")
            lines.append("")
            attempts = rd.get("fetch_attempts") or []
            if attempts:
                lines += ["### Administrative URLs NOT contacted", ""]
                for i, a in enumerate(attempts[:6], start=1):
                    if isinstance(a, dict):
                        url = a.get("url", "?")
                        verdict = a.get("verdict", "?")
                        err = a.get("error") or "-"
                    else:
                        url = getattr(a, "url", "?")
                        verdict = getattr(a, "verdict", "?")
                        err = getattr(a, "error", None) or "-"
                    lines.append(
                        f"  {i}. `{str(url)[:90]}` -> {verdict} "
                        f"(err={err})"
                    )
                if len(attempts) > 6:
                    lines.append(f"  ... and {len(attempts) - 6} more")
                lines.append("")
        else:
            cd = rd.get("comb_detection") or {}
            ka = rd.get("known_answer") or {}
            nc = rd.get("negative_controls") or {}
            lines += [
                f"- comb-detection: n_peaks = **{cd.get('n_peaks')}**, "
                f"hits_at_clock = **{cd.get('hits_at_clock')}**, "
                f"peaks_at_known_rfi = {cd.get('peaks_at_known_rfi')}",
                f"- result: **{'RFI_COMB_DETECTED' if ka.get('rfi_comb_detected') else 'no hit'}** "
                f"(recovery_pass={ka.get('recovery_pass')}, "
                f"scramble_null_drop={ka.get('scramble_null_drop')})",
                f"- scrambled-null control: hits = "
                f"{nc.get('scramble_null_hits')}, "
                f"p-value = {nc.get('scramble_null_p_value'):.3e}",
                "",
                f"_stance:_ {rd.get('stance', '')}",
                "",
            ]
    if "cat2_synthetic" in report:
        cs = report["cat2_synthetic"]
        ka = cs.get("known_answer") or {}
        nc = cs.get("negative_controls") or {}
        lines += [
            "## CHIME/FRB Catalog 2 — R1++ multi-source periodicity known-answer (SYNTHETIC)",
            "",
            f"- sources: **{cs.get('n_sources')}** synthetic repeater "
            "schedules (no live fetch; portal offline at probe time)",
            f"- primary: **FRB 20180916B** published **16.35 d** → recovered "
            f"**{ka.get('primary_recovered_period_d')} d** "
            f"(err {ka.get('primary_recovery_error_d')} d); "
            f"recovers_16p35d = **{ka.get('recovers_16p35d')}**",
            f"- all-sources recovery_pass = "
            f"**{ka.get('all_sources_recovery_pass')}**; scramble-null "
            f"below recovered = **{nc.get('scramble_null_below_recovered')}** "
            "(per-source uniform-in-window shuffle destroys the periodicity)",
        ]
        for name, e in (cs.get("per_source") or {}).items():
            lines.append(
                f"  - `{name}`: N={e.get('n_bursts')}, "
                f"published {e.get('published_period_d')} d → recovered "
                f"{e.get('recovered_period_d')} d "
                f"(err {e.get('recovery_error_d')} d, "
                f"Z²={e.get('recovered_z2'):.1f} vs null "
                f"{e.get('scramble_null_z2_max'):.1f}) "
                f"→ {'PASS' if e.get('recovery_pass') else 'FAIL'}"
            )
        lines += [
            "",
            f"_stance:_ {cs.get('stance', '')}",
            "",
        ]
    if "cat2_real_data" in report:
        rd = report["cat2_real_data"]
        lines += [
            "## CHIME/FRB Catalog 2 — R1++ REAL-DATA path",
            "",
            f"- data source: **{rd.get('data_source', '?')}** "
            f"(source_type=`{rd.get('source_type', '?')}`, "
            f"fetch_status=`{rd.get('fetch_status', '?')}`)",
            f"- n_sources = **{rd.get('n_sources')}**, "
            f"n_bursts_total = **{rd.get('n_bursts_total')}**",
            f"- reference: bibcode=`{rd.get('ref_bibcode') or '-'}`, "
            f"url=`{rd.get('ref_url') or '-'}`",
            "",
        ]
        if rd.get("warnings"):
            lines += ["### 🟡 YELLOW BANNER — Cat 2 portal offline / no data; "
                      "NO synthetic fallback", ""]
            for w in rd["warnings"]:
                lines.append(f"  - {w}")
            note = (rd.get("provenance_note") or "")[:600]
            lines += ["", f"_provenance:_ {note}", ""]
        else:
            for name, e in (rd.get("per_source") or {}).items():
                lines.append(
                    f"  - `{name}`: N={e.get('n_bursts')}, recovered "
                    f"{e.get('recovered_period_d')} d"
                    + (f" (published {e.get('published_period_d')} d, err "
                       f"{e.get('recovery_error_d')} d, "
                       f"{'PASS' if e.get('recovery_pass') else 'FAIL'})"
                       if 'recovery_pass' in e else "")
                )
            lines += ["", f"_stance:_ {rd.get('stance', '')}", ""]
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
    ap.add_argument(
        "--fetch-status-test-force",
        choices=["UNREACHABLE", "PARKING_PAGE", "FETCHED"],
        default=None,
        help="TEST HOOK: synthesize fetcher result without "
             "network contact. UNREACHABLE / PARKING_PAGE / "
             "FETCHED. Production users must omit this flag. "
             "Applies to --frb-180916-real, --pulsar-vela-real, "
             "and --blc1-real."
    )
    ap.add_argument("--blc1", action="store_true",
                     help="BLC1 default mode: synthetic known-answer "
                          "(math-validation) UNLESS --bundled-blc1-csv "
                          "is given (then real-data path).")
    ap.add_argument("--blc1-synthetic", action="store_true",
                     help="BLC1 synthetic clock-comb + comb detector + "
                          "scramble null + positive-control RFI hit. "
                          "Plants 5 harmonically-spaced peaks around "
                          "982.002 MHz (BLC1 detection freq per Sheikh "
                          "2021).")
    ap.add_argument("--blc1-real", action="store_true",
                     help="BLC1 real-data path. Live probe DISABLED "
                          "per user brief ('no TB mirror'); use "
                          "--bundled-blc1-csv to inject hand-transcribed "
                          "Sheikh 2021 supplementary tables.")
    ap.add_argument("--bundled-blc1-csv", type=Path, default=None,
                     help="Override the (disabled) BLC1 live TB fetch "
                          "with a CSV file of peak rows. Schema: header "
                          "`freq_mhz,snr_db,drift_hz_per_s,t_start_mjd,"
                          "t_end_mjd,label`. Only honoured when combined "
                          "with --blc1*.")
    ap.add_argument("--cat2", action="store_true",
                     help="R1++ Cat 2 default mode: synthetic multi-source "
                          "periodicity known-answer (recover 16.35 d + "
                          "scramble null) UNLESS --bundled-cat2-csv is "
                          "given (then real-data path).")
    ap.add_argument("--cat2-synthetic", action="store_true",
                     help="R1++ SYNTHETIC: plant CHIME/FRB Cat 2 repeater "
                          "schedules (FRB 20180916B ~16.35 d; FRB 20121102A "
                          "~157 d) and recover each period per-source with a "
                          "per-source scramble null. Math-validation only.")
    ap.add_argument("--cat2-real", action="store_true",
                     help="R1++ REAL-DATA path: load published Cat 2 burst "
                          "MJDs (live/cached fetch OR --bundled-cat2-csv) and "
                          "epoch-fold per source. If no MJDs can be obtained "
                          "(portal offline), reports fetch_status and exits "
                          "without fabrication.")
    ap.add_argument("--bundled-cat2-csv", type=Path, default=None,
                     help="Override the Cat 2 live fetch with a CSV of "
                          "`name,mjd` rows (multi-source). Only honoured "
                          "when combined with --cat2*.")
    ap.add_argument("--wow-beam-fit", action="store_true",
                     help="G3: fit a Gaussian + sinc sidereal transit to "
                          "the 6EQUJ5 intensity table [6.5, 14.5, 26.5, "
                          "30.5, 19.5, 5.5]. Synthetic default; use "
                          "--wow-beam-fit-real for Ehman's handwritten "
                          "transcript. Underdetermined caveat enforced "
                          "(N=6 - K=3 -> 3 DOF).")
    ap.add_argument("--wow-beam-fit-synthetic", action="store_true",
                     help="G3 SYNTHETIC known-answer: plant a noise-free "
                          "6-sample Gaussian at (mu=2.5, sigma=1.5, amp=30) "
                          "and verify the fit recovers (|err_mu|<=0.5 idx, "
                          "|err_sigma|<=0.5 idx, |err_amp|<=1e-6).")
    ap.add_argument("--wow-beam-fit-real", action="store_true",
                     help="G3 REAL-DATA: run the Gaussian + sinc + constant "
                          "+ scramble-null pipeline on the Ehman transcript "
                          "values. Lab motto + PHL@UPR 2024 cite enforced.")
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
    elif args.blc1_real:
        mode = "blc1_real"
    elif args.blc1_synthetic:
        mode = "blc1_synthetic"
    elif args.blc1:
        mode = "blc1"
    elif args.cat2_real:
        mode = "cat2_real"
    elif args.cat2_synthetic:
        mode = "cat2_synthetic"
    elif args.cat2:
        mode = "cat2"
    elif args.wow_beam_fit_real:
        mode = "wow_beam_fit_real"
    elif args.wow_beam_fit_synthetic:
        mode = "wow_beam_fit_synthetic"
    elif args.wow_beam_fit:
        mode = "wow_beam_fit"
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
        bundled_blc1_csv=args.bundled_blc1_csv
        if mode in ("blc1", "blc1_real", "blc1_synthetic")
        else None,
        bundled_cat2_csv=args.bundled_cat2_csv
        if mode in ("cat2", "cat2_real", "cat2_synthetic")
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
    if mode == "blc1_real" and args.fetch_status_test_force:
        # Same thin-shim pattern: re-run with the fetch-status test hook
        # applied to the BLC1 real path layer so production users
        # don't have to know about force_status_for_tests. The "no TB
        # mirror" stance means in production this block fires only for
        # the FETCHED test_force == positive-control peaks.
        if BLC is not None and "blc1_real_data" in report:
            report["blc1_real_data"] = run_blc1_real(
                bundled_csv_path=args.bundled_blc1_csv
                if mode == "blc1_real" else None,
                seed=args.seed,
                force_status_for_tests=args.fetch_status_test_force,
            )
    if mode == "cat2_real" and args.fetch_status_test_force:
        # Same thin-shim pattern: re-run the Cat 2 real path with the
        # fetch-status test hook so production users never touch
        # force_status_for_tests. In production the portal is offline, so
        # this only fires for the deterministic UNREACHABLE/PARKING tests.
        if C2S is not None and "cat2_real_data" in report:
            report["cat2_real_data"] = run_cat2_real(
                bundled_csv_path=args.bundled_cat2_csv
                if mode == "cat2_real" else None,
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
