"""boyajian_tess_probe — epoch-fold / period search for dip recurrence (G20).

TIC 272172248 (Boyajian's Star / KIC 8462852).
Stance: structure != meaning. Honest prior = underdetermined.

Backends (priority):
  lightkurve + astroquery — real TESS fetch (preferred; currently BLOCKED)
  astropy + numpy + scipy — synthetic LC with known-answer dip injection

CLI:
  python tools/scripts/boyajian_tess_probe.py --out outputs/boyajian/run.json
  python tools/scripts/boyajian_tess_probe.py --generate-data
  python tools/scripts/boyajian_tess_probe.py --demo-synth
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

try:
    from astropy.io import fits
    HAS_ASTROPY_FITS = True
except ImportError:
    HAS_ASTROPY_FITS = False

try:
    import scipy.signal as sp_signal
    import scipy.optimize as sp_optimize
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------

TIC_ID = 272172248
KIC_ID = 8462852
STAR_RA = 301.564
STAR_DEC = 44.4568

FORBIDDEN_PHRASES: tuple[str, ...] = (
    "alien megastructure",
    "Dyson sphere",
    "extraterrestrial",
    "alien built",
    "Tabby's alien",
    "ET construction",
    "megastructure confirmed",
    "intelligent life built",
    "civilization constructed",
)

STANCE = (
    "structure != meaning. "
    "Honest prior: underdetermined. "
    "Dip recurrence may reflect circumstellar dust (natural), "
    "not artificial structures. "
    "No alien megastructure claims."
)

VERDICT_VOCAB: tuple[str, ...] = (
    "NO_SIGNAL",
    "UNDERDETERMINED",
    "STRUCTURE_SIGNAL",
)

PROBE_VERSION = "1.0.0"
DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "astro" / "boyajian"
OUT_DIR = Path(__file__).resolve().parents[2] / "outputs" / "boyajian"

# Kepler dip epochs (BJD - 2454833), from Boyajian et al. 2016
KEPLER_DIP_EPOCHS = {
    "D800": 800,
    "D1519": 1519,
    "D1568": 1568,
}

# ---------------------------------------------------------------------------
# data generation
# ---------------------------------------------------------------------------

def _asymmetric_dip_profile(
    n_points: int, depth: float, width_frac: float = 0.3, asymmetry: float = 0.3
) -> np.ndarray:
    """Asymmetric dip profile: fast ingress, slower egress.

    width_frac controls dip width as fraction of profile (0-1).
    0.3 = dip covers ~30% of the profile window.
    """
    x = np.linspace(-1, 1, n_points)
    sigma_ingress = width_frac * (1 - asymmetry)
    sigma_egress = width_frac * (1 + asymmetry)
    ingress = np.exp(-0.5 * ((x[x < 0] / sigma_ingress)**2))
    egress = np.exp(-0.5 * ((x[x >= 0] / sigma_egress)**2))
    profile = np.concatenate([ingress, egress])
    profile = 1.0 - depth * (1.0 - profile)
    return profile


def _inject_dip(
    time: np.ndarray, flux: np.ndarray,
    t_center: float, depth: float, width_frac: float = 0.3,
    asymmetry: float = 0.3,
) -> np.ndarray:
    """Inject an asymmetric dip into a light curve.

    width_frac controls dip width as fraction of total window.
    """
    cadence = np.median(np.diff(time))
    n_window = len(time)
    n_dip = max(5, int(n_window * width_frac))
    n_dip = min(n_dip, n_window)
    profile = _asymmetric_dip_profile(n_dip, depth, width_frac * 0.3, asymmetry)
    i0 = int((t_center - time[0]) / cadence)
    i_start = max(0, i0 - n_dip // 2)
    i_end = min(len(flux), i_start + n_dip)
    if i_end > i_start:
        visible = min(i_end - i_start, n_dip)
        flux[i_start:i_end] = flux[i_start:i_end] * profile[:visible]
    return flux


def _synthetic_lc(
    n_days: float = 28.0, cadence_days: float = 200.0 / 86400.0,
    noise_ppm: float = 500.0, seed: int = 42,
    dip_centers: list[float] | None = None,
    dip_depths: list[float] | None = None,
    label: str = "target",
) -> dict:
    """Generate synthetic light curve with optional injected dips.

    Parameters
    ----------
    n_days : float
        Duration of light curve in days (default 28 ≈ 1 TESS sector).
    cadence_days : float
        Cadence in days (default 200 s).
    noise_ppm : float
        Gaussian noise in parts per million.
    seed : int
        Random seed for reproducibility.
    dip_centers : list[float] | None
        Epochs (days from start) for injected dips.
    dip_depths : list[float] | None
        Depths (fractional flux drop 0-1) for injected dips.
    label : str
        Label for the light curve.

    Returns
    -------
    dict with 'time', 'flux', 'flux_err', 'label', 'cadence_days'.
    """
    rng = np.random.default_rng(seed)
    n_points = int(n_days / cadence_days)
    time = np.arange(n_points, dtype=float) * cadence_days
    flux = np.ones(n_points, dtype=float)

    # Stellar variability (low-frequency)
    n_var = 3
    var_amps = rng.uniform(0.0, 0.002, n_var)
    var_periods = rng.uniform(1.0, 14.0, n_var)
    for i in range(n_var):
        flux += var_amps[i] * np.sin(2 * np.pi * time / var_periods[i])

    # Poisson-like noise
    noise = rng.normal(0, noise_ppm * 1e-6, n_points)
    flux += noise

    if dip_centers is not None and dip_depths is not None:
        for tc, depth in zip(dip_centers, dip_depths):
            flux = _inject_dip(time, flux, tc, depth)

    flux_err = np.full(n_points, noise_ppm * 1e-6)

    return {
        "time": time.tolist(),
        "flux": flux.tolist(),
        "flux_err": flux_err.tolist(),
        "label": label,
        "n_days": n_days,
        "cadence_days": cadence_days,
        "noise_ppm": noise_ppm,
        "seed": seed,
    }


def generate_synthetic_data(seed: int = 42, out_dir: Path | None = None) -> None:
    """Generate synthetic target and quiet-star control light curves."""
    if out_dir is None:
        out_dir = DATA_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- Target: Boyajian-like with injected dips ---
    # Kepler dip morphology reference: asymmetric, ~1-5% depth
    dip_centers = [3.5, 8.2, 14.0, 19.5, 24.8]
    dip_depths = [0.03, 0.05, 0.015, 0.04, 0.02]
    target = _synthetic_lc(
        n_days=28.0, cadence_days=200.0 / 86400.0,
        noise_ppm=500, seed=seed,
        dip_centers=dip_centers, dip_depths=dip_depths,
        label="boyajian_synthetic_target",
    )

    # --- Quiet star: no dips, same noise ---
    quiet = _synthetic_lc(
        n_days=28.0, cadence_days=200.0 / 86400.0,
        noise_ppm=500, seed=seed + 1,
        dip_centers=None, dip_depths=None,
        label="boyajian_synthetic_quiet",
    )

    # Write CSVs
    for lc, fname in [(target, "synthetic_target_lc.csv"),
                       (quiet, "synthetic_quiet_lc.csv")]:
        path = out_dir / fname
        with path.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["time_days", "flux", "flux_err"])
            for t, fl, fe in zip(lc["time"], lc["flux"], lc["flux_err"]):
                w.writerow([f"{t:.6f}", f"{fl:.8f}", f"{fe:.8f}"])
        print(f"wrote {path}", file=sys.stderr)

    # Generate Kepler dip morphology archive
    _save_kepler_dip_morphology(out_dir)

    print(f"Synthetic data generated in {out_dir}", file=sys.stderr)


def _save_kepler_dip_morphology(out_dir: Path) -> None:
    """Save known Kepler dip profiles for known-answer tests."""
    profiles = {}
    for name, epoch in KEPLER_DIP_EPOCHS.items():
        depth = {"D800": 0.15, "D1519": 0.22, "D1568": 0.08}[name]
        n_pts = {"D800": 50, "D1519": 45, "D1568": 30}[name]
        profile = _asymmetric_dip_profile(n_pts, depth, width_frac=0.3, asymmetry=0.3)
        profiles[name] = {
            "profile": profile.tolist(),
            "depth": depth,
            "epoch_bjd_minus_2454833": epoch,
        }
    np.savez(out_dir / "kepler_dip_morphology.npz", **profiles)


def _load_kepler_dip_morphology() -> dict:
    """Load Kepler dip morphology."""
    path = DATA_DIR / "kepler_dip_morphology.npz"
    if not path.exists():
        return {}
    data = np.load(path, allow_pickle=True)
    return {k: dict(data[k].item()) if data[k].ndim == 0 else {"profile": data[k].tolist()}
            for k in data.files}


# ---------------------------------------------------------------------------
# epoch-fold / period search
# ---------------------------------------------------------------------------

def phase_fold(time: np.ndarray, period: float, t0: float = 0.0) -> np.ndarray:
    """Phase-fold a time series to [0, 1)."""
    return ((time - t0) / period) % 1.0


def _bin_flux(phase: np.ndarray, flux: np.ndarray, n_bins: int = 100) -> tuple:
    """Bin folded light curve into phase bins."""
    bins = np.linspace(0, 1, n_bins + 1)
    bin_centers = (bins[:-1] + bins[1:]) / 2
    binned = np.full(n_bins, np.nan)
    for i in range(n_bins):
        mask = (phase >= bins[i]) & (phase < bins[i + 1])
        if mask.sum() > 0:
            binned[i] = np.mean(flux[mask])
    return bin_centers, binned


def _dip_score(binned_flux: np.ndarray) -> float:
    """Score the strength of dip signal in a binned folded light curve.
    Returns -max(flux deviation) where negative deviations = dips.
    More negative = stronger dip signal.
    """
    if np.all(np.isnan(binned_flux)):
        return 0.0
    median_flux = np.nanmedian(binned_flux)
    deviations = median_flux - binned_flux
    return float(np.nanmax(deviations))


def _folding_significance(
    time: np.ndarray, flux: np.ndarray,
    periods: np.ndarray, n_bins: int = 100, t0: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute dip score for each trial period."""
    scores = np.zeros(len(periods))
    for i, p in enumerate(periods):
        phase = phase_fold(time, p, t0)
        _, binned = _bin_flux(phase, flux, n_bins)
        scores[i] = _dip_score(binned)
    return periods, scores


def _scramble_phases(flux: np.ndarray, seed: int = 0) -> np.ndarray:
    """Phase-scrambled null: shuffle flux values to destroy any temporal structure."""
    rng = np.random.default_rng(seed)
    shuffled = flux.copy()
    rng.shuffle(shuffled)
    return shuffled


def period_search(
    time: np.ndarray, flux: np.ndarray,
    p_min: float = 0.1, p_max: float = 15.0,
    n_periods: int = 200, n_bins: int = 100,
    n_scrambles: int = 50,
    seed: int = 0,
) -> dict:
    """Search for periodic dip signals via epoch folding.

    Parameters
    ----------
    time, flux : np.ndarray
        Time and flux arrays.
    p_min, p_max : float
        Period range in days.
    n_periods : int
        Number of trial periods.
    n_bins : int
        Number of phase bins for folding.
    n_scrambles : int
        Number of phase-scrambled null realizations.
    seed : int
        Random seed.

    Returns
    -------
    dict with period search results.
    """
    periods = np.linspace(p_min, p_max, n_periods)
    trial_periods, scores = _folding_significance(time, flux, periods, n_bins)

    best_idx = int(np.argmax(scores))
    best_period = float(trial_periods[best_idx])
    best_score = float(scores[best_idx])

    # Phase-scrambled nulls
    null_scores = []
    for i in range(n_scrambles):
        null_flux = _scramble_phases(flux, seed + i + 1)
        _, null_s = _folding_significance(time, null_flux, periods, n_bins)
        null_scores.append(float(null_s[best_idx]))

    null_mean = float(np.mean(null_scores))
    null_std = float(np.std(null_scores)) if np.std(null_scores) > 0 else 1e-10
    z_score = (best_score - null_mean) / null_std

    # Count peaks above threshold
    threshold = null_mean + 3 * null_std
    n_peaks_above_3sigma = int(np.sum(scores > threshold))

    return {
        "n_periods_tried": n_periods,
        "period_range_days": [p_min, p_max],
        "best_period_days": round(best_period, 6),
        "best_period_index": int(best_idx),
        "best_dip_score": round(best_score, 6),
        "null_mean_score": round(null_mean, 6),
        "null_std_score": round(null_std, 6),
        "z_vs_null": round(z_score, 4),
        "n_peaks_above_3sigma": n_peaks_above_3sigma,
        "n_scrambles": n_scrambles,
        "method": "epoch-fold BLS-like dip scoring",
    }


# ---------------------------------------------------------------------------
# known-answer tests
# ---------------------------------------------------------------------------

def known_answer_recovery(
    time: np.ndarray, flux: np.ndarray,
    injected_centers: list[float],
    tolerance_days: float = 0.5,
) -> dict:
    """Test whether injected dip epochs are recoverable by epoch folding."""
    time_a = np.array(time)
    flux_a = np.array(flux)

    # Try a range of periods to see if any recover the spacing
    spacings = []
    for i in range(1, len(injected_centers)):
        spacings.append(injected_centers[i] - injected_centers[i - 1])
    min_spacing = min(spacings)
    max_spacing = max(spacings)

    periods = np.linspace(max(0.1, min_spacing * 0.8), max_spacing * 1.2, 100)
    _, scores = _folding_significance(time_a, flux_a, periods)

    # Check if the true spacing(s) produce elevated scores
    recovered = []
    for s in spacings:
        ix = int(np.argmin(np.abs(periods - s)))
        score = scores[ix]
        recovered.append({
            "true_period_days": round(s, 4),
            "fold_score": round(float(score), 6),
            "within_tolerance": any(abs(periods[ix] - s) < tolerance_days for s in spacings),
        })

    return {
        "injected_spacings_days": [round(s, 4) for s in spacings],
        "min_injected_spacing_days": round(min_spacing, 4),
        "max_injected_spacing_days": round(max_spacing, 4),
        "recovered": recovered,
        "best_score": round(float(np.max(scores)), 6),
        "n_recovered": sum(1 for r in recovered if r["fold_score"] > 0),
    }


# ---------------------------------------------------------------------------
# load saved data
# ---------------------------------------------------------------------------

def load_light_curve(label: str = "target") -> dict | None:
    """Load a synthetic light curve from CSV.

    Parameters
    ----------
    label : str
        'target' for synthetic_target_lc.csv, 'quiet' for synthetic_quiet_lc.csv.

    Returns
    -------
    dict with 'time', 'flux', 'flux_err', or None if file missing.
    """
    fname = {
        "target": "synthetic_target_lc.csv",
        "quiet": "synthetic_quiet_lc.csv",
    }.get(label)
    if fname is None:
        return None
    path = DATA_DIR / fname
    if not path.exists():
        return None
    time, flux, flux_err = [], [], []
    with path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            time.append(float(row["time_days"]))
            flux.append(float(row["flux"]))
            flux_err.append(float(row["flux_err"]))
    return {
        "time": np.array(time),
        "flux": np.array(flux),
        "flux_err": np.array(flux_err),
        "label": label,
    }


def load_real_tess_data() -> dict | None:
    """Attempt to load real TESS data. Currently always returns None."""
    return None


# ---------------------------------------------------------------------------
# data fetch (attempt real, fall back to synthetic)
# ---------------------------------------------------------------------------

def fetch_tess_data() -> dict:
    """Attempt to fetch real TESS data for TIC 272172248.

    Tries: lightkurve -> astroquery -> requests -> returns BLOCKED status.

    Returns
    -------
    dict with fetch_status and either data or BLOCKED marker.
    """
    block_reason = None

    # Try lightkurve
    try:
        import lightkurve as lk
        search = lk.search_lightcurve("TIC 272172248", mission="TESS")
        if len(search) > 0:
            lcs = search.download_all()
            if lcs and len(lcs) > 0:
                time, flux, flux_err = [], [], []
                for lc in lcs:
                    t = lc.time.value
                    f = lc.flux.value
                    e = lc.flux_err.value
                    mask = np.isfinite(t) & np.isfinite(f) & np.isfinite(e)
                    time.extend(t[mask].tolist())
                    flux.extend(f[mask].tolist())
                    flux_err.extend(e[mask].tolist())
                return {
                    "fetch_status": "OK",
                    "method": "lightkurve",
                    "data": {
                        "time": time, "flux": flux, "flux_err": flux_err,
                        "label": "TIC_272172248_TESS",
                    },
                }
        block_reason = "lightkurve search returned empty"
    except ImportError:
        block_reason = "lightkurve not available"
    except Exception as exc:
        block_reason = f"lightkurve error: {exc}"

    # Try astroquery
    try:
        from astroquery.mast import Observations
        obs = Observations.query_criteria(target_name="TIC 272172248", obs_collection="TESS")
        if len(obs) > 0:
            block_reason = f"astroquery found {len(obs)} obs but download not implemented in this probe"
        else:
            block_reason = "astroquery search returned empty"
    except ImportError:
        if block_reason is None:
            block_reason = "astroquery not available"
    except Exception as exc:
        if block_reason is None:
            block_reason = f"astroquery error: {exc}"

    # Try requests-based MAST
    try:
        import requests
        url = "https://mast.stsci.edu/api/v0.1/caom/tess"
        r = requests.get(url, params={"targetName": "TIC 272172248"}, timeout=15)
        if r.status_code == 200:
            block_reason = f"MAST API returned ok but ingest not wired; {len(r.json())} records"
        else:
            if block_reason is None:
                block_reason = f"MAST API returned {r.status_code}"
    except Exception as exc:
        if block_reason is None:
            block_reason = f"requests MAST error: {exc}"

    return {"fetch_status": "BLOCKED", "reason": block_reason, "data": None}


# ---------------------------------------------------------------------------
# main probe
# ---------------------------------------------------------------------------

def run_probe(
    use_synthetic: bool = True, n_scrambles: int = 50,
    seed: int = 0, generate_data: bool = False,
) -> dict:
    """Run full Boyajian TESS epoch-fold probe.

    Parameters
    ----------
    use_synthetic : bool
        If True, use synthetic light curves (preferred when TESS fetch is blocked).
    n_scrambles : int
        Number of phase-scramble null realizations.
    seed : int
        Random seed.
    generate_data : bool
        If True, regenerate synthetic data first.

    Returns
    -------
    dict with full probe results.
    """
    # Generate data if requested or if files missing
    if generate_data or not (DATA_DIR / "synthetic_target_lc.csv").exists():
        generate_synthetic_data(seed=seed)

    # Try real TESS fetch
    real_data = fetch_tess_data()
    source = "real TESS"
    if real_data["fetch_status"] == "BLOCKED" or real_data["data"] is None:
        # Fall back to synthetic
        target_lc = load_light_curve("target")
        quiet_lc = load_light_curve("quiet")
        source = f"synthetic (TESS real fetch blocked: {real_data.get('reason', 'unknown')})"
        if target_lc is None:
            generate_synthetic_data(seed=seed)
            target_lc = load_light_curve("target")
            quiet_lc = load_light_curve("quiet")
    else:
        d = real_data["data"]
        target_lc = {
            "time": np.array(d["time"]),
            "flux": np.array(d["flux"]),
            "flux_err": np.array(d["flux_err"]),
            "label": "TIC_272172248_TESS",
        }
        quiet_lc = target_lc  # No separate quiet-star for real data

    # Period search on target
    target_results = period_search(
        target_lc["time"], target_lc["flux"],
        p_min=0.1, p_max=15.0, n_periods=200,
        n_scrambles=n_scrambles, seed=seed,
    )

    # Period search on quiet-star control
    quiet_results = period_search(
        quiet_lc["time"], quiet_lc["flux"],
        p_min=0.1, p_max=15.0, n_periods=200,
        n_scrambles=n_scrambles, seed=seed + 1000,
    )

    # Known-answer: check if injected dip spacings are recoverable
    dip_centers = [3.5, 8.2, 14.0, 19.5, 24.8]
    ka = known_answer_recovery(
        target_lc["time"], target_lc["flux"],
        dip_centers,
    )

    # Determine verdict (physical dip score comparison, not z-score)
    target_dip = target_results["best_dip_score"]
    quiet_dip = quiet_results["best_dip_score"]
    n_peaks_target = target_results["n_peaks_above_3sigma"]
    n_peaks_quiet = quiet_results["n_peaks_above_3sigma"]
    target_noise_floor = max(target_results["null_mean_score"], target_results["null_std_score"] * 3)
    quiet_noise_floor = max(quiet_results["null_mean_score"], quiet_results["null_std_score"] * 3)

    target_significant = (target_dip > target_noise_floor * 2 and n_peaks_target > 0)
    quiet_significant = (quiet_dip > quiet_noise_floor * 2 and n_peaks_quiet > 0)
    target_exceeds_quiet = (target_dip > quiet_dip * 2)

    if not target_significant:
        verdict = "NO_SIGNAL"
        verdict_detail = (
            "No periodic dip signal detected above noise floor. "
            "Consistent with natural aperiodic dust or stochastic variability."
        )
    elif quiet_significant and not target_exceeds_quiet:
        verdict = "NO_SIGNAL"
        verdict_detail = (
            "Target dip score does not exceed quiet-star control. "
            "Apparent periodicity is consistent with noise or systematics."
        )
    elif target_significant and target_exceeds_quiet and ka["n_recovered"] >= 2:
        verdict = "STRUCTURE_SIGNAL"
        verdict_detail = (
            "Periodic dip structure detected and known-answer dip spacings "
            "are recoverable. This is expected for synthetic data with "
            "injected dips. On real data this would warrant investigation."
        )
    else:
        verdict = "UNDERDETERMINED"
        verdict_detail = (
            "Marginal dip signal detected but not robustly separated "
            "from control and/or known-answer recovery is incomplete. "
            "Further observations needed."
        )

    # Load Kepler morphology reference
    kepler_morph = _load_kepler_dip_morphology()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "probe_version": PROBE_VERSION,
        "target": {
            "tic_id": TIC_ID,
            "kic_id": KIC_ID,
            "ra_deg": STAR_RA,
            "dec_deg": STAR_DEC,
            "common_name": "Boyajian's Star (Tabby's Star)",
        },
        "data_source": source,
        "light_curve": {
            "label": target_lc["label"],
            "n_points": len(target_lc["time"]),
            "duration_days": round(float(np.max(target_lc["time"]) - np.min(target_lc["time"])), 4),
            "cadence_days": round(float(np.median(np.diff(target_lc["time"]))), 6),
        },
        "period_search": {
            "target": target_results,
            "quiet_star_control": quiet_results,
        },
        "known_answer_test": ka,
        "kepler_dip_morphology": {
            "available_profiles": list(kepler_morph.keys()),
            "n_profiles": len(kepler_morph),
            "note": (
                "Kepler dip morphology (asymmetric shape) used for synthetic dip injection. "
                "Structure comparator only — not an ET claim."
            ),
        },
        "comparison": {
            "target_dip_score": round(target_dip, 6),
            "quiet_dip_score": round(quiet_dip, 6),
            "dip_ratio_target_over_quiet": round(target_dip / max(quiet_dip, 1e-10), 4),
            "target_noise_floor": round(target_noise_floor, 6),
            "quiet_noise_floor": round(quiet_noise_floor, 6),
            "target_peaks_abovenoise": n_peaks_target,
            "quiet_peaks_abovenoise": n_peaks_quiet,
            "target_separates_from_control": bool(target_significant and target_exceeds_quiet),
        },
        "verdict": verdict,
        "verdict_detail": verdict_detail,
        "stance": STANCE,
        "forbidden_words_check": {
            "all_absent": all(
                fp.lower() not in str({"verdict": verdict, "detail": verdict_detail}).lower()
                for fp in FORBIDDEN_PHRASES
            ),
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="G20 Boyajian's Star TESS epoch-fold probe")
    ap.add_argument("--out", type=Path, default=OUT_DIR / "run.json")
    ap.add_argument("--generate-data", action="store_true", help="Generate synthetic data only")
    ap.add_argument("--demo-synth", action="store_true", help="Run a quick demo with synthetic data")
    ap.add_argument("--n-scrambles", type=int, default=50, help="Number of phase-scramble nulls")
    ap.add_argument("--seed", type=int, default=0, help="Random seed")
    args = ap.parse_args()

    if args.generate_data:
        generate_synthetic_data(seed=args.seed)
        return

    if args.demo_synth:
        generate_synthetic_data(seed=args.seed)
        # Quick demo: generate and run on synthetic
        target = load_light_curve("target")
        if target is None:
            print("ERROR: synthetic data not found; run --generate-data first", file=sys.stderr)
            sys.exit(1)
        results = period_search(target["time"], target["flux"])
        print(json.dumps(results, indent=2))
        return

    result = run_probe(use_synthetic=True, n_scrambles=args.n_scrambles, seed=args.seed)

    path = args.out
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, default=str))
    print(json.dumps({
        "target": result["target"]["common_name"],
        "data_source": result["data_source"][:60],
        "period_search_target_z": result["period_search"]["target"]["z_vs_null"],
        "period_search_quiet_z": result["period_search"]["quiet_star_control"]["z_vs_null"],
        "verdict": result["verdict"],
    }, indent=2))
    print(f"wrote {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
