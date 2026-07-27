#!/usr/bin/env python3
"""alpha_variation_probe — Fine-structure constant α directional variation (G21).

Re-analysis of King et al. (2012) VLT+Keck quasar absorption Δα/α
measurements. Brute-force dipole search + scramble null +
instrument-systematics null.

Stance:
    structure != meaning. No-signal prior. Instrument-systematics null
    mandatory.

Usage:
    python tools/scripts/alpha_variation_probe.py
    python tools/scripts/alpha_variation_probe.py --data data/astro/alpha_variation/king_2012_vlt_keck.dat
    python tools/scripts/alpha_variation_probe.py --n-null 300
"""
from __future__ import annotations

import argparse
import json
import math
import random as rnd
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA_DIR = ROOT / "data" / "astro" / "alpha_variation"
OUT_DIR = ROOT / "outputs" / "alpha_variation"
DEFAULT_DATA = DATA_DIR / "king_2012_vlt_keck.dat"
DEFAULT_OUT = OUT_DIR / "run.json"

# sigma_rand for weighted-mean model (King+2012 Table 2)
SIGMA_RAND = {1: 0.000, 2: 1.743, 3: 0.905}  # flag: sigma_rand (×10⁻⁵)

FORBIDDEN_PHRASES = (
    "new physics proven",
    "varying constant confirmed",
    "beyond the Standard Model",
    "fifth force",
    "cosmological crisis",
    "aliens",
    "extraterrestrial",
    "we found a dipole",
    "dipole confirmed",
)

STANCE = (
    "Fine-structure constant α directional variation is a controversial "
    "result from quasar absorption spectroscopy (Webb et al. 2011; King et al. "
    "2012). The claimed dipole may reflect unknown systematic effects in "
    "wavelength calibration, temperature/pressure shifts in spectrographs, "
    "or isotopic abundance variations. This probe measures directional "
    "structure ONLY. It does NOT claim new physics. "
    "STRUCTURE != MEANING. Honest prior: NO_SIGNAL."
)


# ---------------------------------------------------------------------------
# J2000 name parser
# ---------------------------------------------------------------------------


def parse_j2000(name: str) -> tuple[float, float]:
    """Parse a J2000 quasar name into RA (deg) and Dec (deg).

    Format: JHHMMSS±DDMMSS
    Examples: J000520+052410 → RA=1.3333°, Dec=5.4028°
              J042315-012033 → RA=65.8125°, Dec=-1.3425°
    """
    # Strip leading 'J'
    s = name.upper().strip()
    if s.startswith("J"):
        s = s[1:]

    # Find sign position (± in the RA portion)
    if "+" in s:
        sign_idx = s.index("+")
        ra_str = s[:sign_idx]
        dec_sign = "+"
        dec_str = s[sign_idx + 1 :]
    elif "-" in s:
        # Could be in first 6 chars (RA) or later
        sign_idx = s.index("-")
        ra_str = s[:sign_idx]
        dec_sign = "-"
        dec_str = s[sign_idx + 1 :]
    else:
        raise ValueError(f"Cannot parse J2000 name: {name}")

    # RA: HHMMSS (hours, minutes, seconds)
    if len(ra_str) == 6:
        hh = int(ra_str[0:2])
        mm = int(ra_str[2:4])
        ss = int(ra_str[4:6])
    elif len(ra_str) == 5:
        # Rare: HHMMm
        hh = int(ra_str[0:2])
        mm = int(ra_str[2:4])
        ss = int(ra_str[4:5]) * 10
    else:
        raise ValueError(f"Cannot parse RA from: {name} ({ra_str})")

    ra_deg = (hh + mm / 60.0 + ss / 3600.0) * 15.0

    # Dec: DDMMSS
    if len(dec_str) >= 6:
        dd = int(dec_str[0:2])
        dm = int(dec_str[2:4])
        ds = int(dec_str[4:6])
    elif len(dec_str) == 5:
        dd = int(dec_str[0:2])
        dm = int(dec_str[2:4])
        ds = int(dec_str[4:5]) * 10
    else:
        raise ValueError(f"Cannot parse Dec from: {name} ({dec_str})")

    dec_deg = dd + dm / 60.0 + ds / 3600.0
    if dec_sign == "-":
        dec_deg = -dec_deg

    return ra_deg, dec_deg



# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_data(data_path: str | Path) -> dict:
    """Load the King+2012 dataset.

    Returns dict with keys: ra_deg, dec_deg, da_a, err, source,
    sig_rand_flag, outlier, n
    """
    data_path = Path(data_path)
    lines = data_path.read_text().strip().split("\n")

    ras, decs, da_as, errs, sources, flags, outliers = [], [], [], [], [], [], []

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 10:
            continue

        try:
            name = parts[1]
            da_a = float(parts[4])
            err = float(parts[5])
            source = parts[7]
            flag = int(parts[8])
            outlier = int(parts[9])

            ra, dec = parse_j2000(name)

            ras.append(ra)
            decs.append(dec)
            da_as.append(da_a)
            errs.append(err)
            sources.append(source)
            flags.append(flag)
            outliers.append(outlier)
        except (ValueError, IndexError):
            continue

    return {
        "ra_deg": np.array(ras),
        "dec_deg": np.array(decs),
        "da_a": np.array(da_as),
        "err": np.array(errs),
        "source": np.array(sources),
        "sig_rand_flag": np.array(flags),
        "outlier": np.array(outliers),
        "n": len(ras),
    }


def total_error(err, flag, sigma_rand_map=None):
    """Compute total error: sqrt(err^2 + sigma_rand(flag)^2)."""
    if sigma_rand_map is None:
        sigma_rand_map = SIGMA_RAND
    sr = sigma_rand_map.get(int(flag), 0.0)
    return math.sqrt(err**2 + sr**2)


# ---------------------------------------------------------------------------
# Angular separation and dipole model
# ---------------------------------------------------------------------------


def angular_distance(ra1_deg, dec1_deg, ra2_deg, dec2_deg):
    """Haversine angular distance in degrees between two sky positions."""
    d1 = math.radians(dec1_deg)
    d2 = math.radians(dec2_deg)
    dra = math.radians(ra2_deg - ra1_deg)
    a = (
        math.sin((d2 - d1) / 2.0) ** 2
        + math.cos(d1) * math.cos(d2) * math.sin(dra / 2.0) ** 2
    )
    a = min(max(a, 0.0), 1.0)
    return math.degrees(2.0 * math.asin(math.sqrt(a)))


def angular_distance_array(ra1_arr, dec1_arr, ra2_deg, dec2_deg):
    """Vectorised angular distance (numpy) between arrays and a point."""
    d1 = np.radians(dec1_arr)
    d2 = math.radians(dec2_deg)
    dra = np.radians(ra1_arr - ra2_deg)
    a = np.sin((d2 - d1) / 2.0) ** 2 + np.cos(d1) * math.cos(d2) * np.sin(
        dra / 2.0
    ) ** 2
    a = np.clip(a, 0.0, 1.0)
    return np.degrees(2.0 * np.arcsin(np.sqrt(a)))


def dipole_fit(ra_arr, dec_arr, da_a_arr, err_arr, ra0_deg, dec0_deg):
    """Fit dipole model at a given axis (ra0, dec0).

    Returns dict with best-fit parameters and statistics.
    Uses weighted linear regression: Δα/α = A * cos(θ) + m
    """
    n = len(ra_arr)
    if n < 3:
        return {"error": "too_few_points", "n": n}

    # Angular distances to dipole axis
    theta = angular_distance_array(ra_arr, dec_arr, ra0_deg, dec0_deg)
    x = np.cos(np.radians(theta))

    # Weighted least squares
    w = 1.0 / (err_arr**2)
    w_sum = np.sum(w)
    wx_sum = np.sum(w * x)
    wy_sum = np.sum(w * da_a_arr)
    wxx_sum = np.sum(w * x * x)
    wxy_sum = np.sum(w * x * da_a_arr)

    denom = w_sum * wxx_sum - wx_sum**2
    if abs(denom) < 1e-30:
        return {"error": "singular_matrix"}

    # Amplitude (A) and monopole (m)
    amplitude = (w_sum * wxy_sum - wx_sum * wy_sum) / denom
    monopole = (wxx_sum * wy_sum - wx_sum * wxy_sum) / denom

    # Residuals
    y_pred = amplitude * x + monopole
    residuals = da_a_arr - y_pred
    chi2 = np.sum(w * residuals**2)

    # Standard errors on parameters
    var_amp = w_sum / denom
    var_m = wxx_sum / denom
    amplitude_err = math.sqrt(var_amp)
    monopole_err = math.sqrt(var_m)

    # Pearson correlation
    x_bar = np.average(x, weights=w)
    y_bar = np.average(da_a_arr, weights=w)
    cov_xy = np.sum(w * (x - x_bar) * (da_a_arr - y_bar))
    var_x = np.sum(w * (x - x_bar) ** 2)
    var_y = np.sum(w * (da_a_arr - y_bar) ** 2)
    r = (
        cov_xy / math.sqrt(var_x * var_y)
        if var_x > 0 and var_y > 0
        else 0.0
    )

    return {
        "amplitude_x1e5": round(amplitude, 4),
        "amplitude_err": round(amplitude_err, 4),
        "monopole_x1e5": round(monopole, 4),
        "monopole_err": round(monopole_err, 4),
        "chi2": round(chi2, 2),
        "dof": n - 2,
        "chi2_nu": round(chi2 / max(n - 2, 1), 2),
        "correlation_r": round(r, 4),
        "n": n,
    }


# ---------------------------------------------------------------------------
# Brute-force dipole search
# ---------------------------------------------------------------------------


def search_dipole(ra_arr, dec_arr, da_a_arr, err_arr, n_ra=36, n_dec=18):
    """Brute-force search over all dipole directions.

    Args:
        n_ra: Number of RA grid points (0° to 360°)
        n_dec: Number of Dec grid points (-90° to +90°)

    Returns:
        Best-fit dipole result, and full grid of results.
    """
    best = {"score": -1e30, "ra_deg": 0, "dec_deg": 0,
            "amplitude_x1e5": 0, "correlation_r": 0, "chi2_nu": 1e30}
    grid = []

    for i in range(n_ra):
        ra0 = 360.0 * i / n_ra
        for j in range(n_dec):
            dec0 = -90.0 + 180.0 * j / max(n_dec - 1, 1)

            fit = dipole_fit(ra_arr, dec_arr, da_a_arr, err_arr, ra0, dec0)
            if "error" in fit:
                continue

            # Score: |r| (absolute correlation) × sqrt(n) for significance
            score = abs(fit["correlation_r"]) * math.sqrt(fit["n"])

            entry = {
                "ra_deg": round(ra0, 1),
                "dec_deg": round(dec0, 1),
                "amplitude_x1e5": fit["amplitude_x1e5"],
                "correlation_r": fit["correlation_r"],
                "chi2_nu": fit["chi2_nu"],
                "score": round(score, 2),
            }
            grid.append(entry)

            if score > best["score"]:
                best = {
                    "score": round(score, 2),
                    "ra_deg": round(ra0, 1),
                    "dec_deg": round(dec0, 1),
                    "amplitude_x1e5": fit["amplitude_x1e5"],
                    "correlation_r": fit["correlation_r"],
                    "chi2_nu": fit["chi2_nu"],
                }

    return best, grid


# ---------------------------------------------------------------------------
# Null controls
# ---------------------------------------------------------------------------


def scramble_coordinates_null(
    ra_arr, dec_arr, da_a_arr, err_arr, sources, flags,
    n_null=200, seed=42, n_ra_grid=24, n_dec_grid=12
):
    """Null: independently permute RA and Dec to break spatial correlation.

    Preserves all data values (da_a, err, source, flag), only shuffles
    coordinate pairs.
    """
    rng = rnd.Random(seed)
    null_best_scores = []
    null_best_ras = []
    null_best_decs = []
    null_best_amps = []
    null_best_rs = []
    n_total = len(ra_arr)

    for s in range(n_null):
        # Shuffle RA and Dec independently
        ra_shuf = list(ra_arr)
        dec_shuf = list(dec_arr)
        rng.shuffle(ra_shuf)
        rng.shuffle(dec_shuf)

        ra_np = np.array(ra_shuf)
        dec_np = np.array(dec_shuf)

        best, _grid = search_dipole(
            ra_np, dec_np, da_a_arr, err_arr,
            n_ra=n_ra_grid, n_dec=n_dec_grid
        )
        null_best_scores.append(best["score"])
        null_best_ras.append(best["ra_deg"])
        null_best_decs.append(best["dec_deg"])
        null_best_amps.append(best["amplitude_x1e5"])
        null_best_rs.append(best["correlation_r"])

    return {
        "scores": null_best_scores,
        "mean_score": round(np.mean(null_best_scores), 2),
        "std_score": round(np.std(null_best_scores, ddof=1), 2),
        "median_score": round(np.median(null_best_scores), 2),
        "max_score": round(max(null_best_scores), 2),
        "mean_amplitude": round(np.mean(null_best_amps), 4),
        "mean_correlation_r": round(np.mean(null_best_rs), 4),
        "n_null": n_null,
    }


def scramble_coordinates_preserve_pairing_null(
    ra_arr, dec_arr, da_a_arr, err_arr, sources, flags,
    n_null=200, seed=43, n_ra_grid=24, n_dec_grid=12
):
    """Null: shuffle the (RA, Dec) pairs as tuples.

    Preserves physical pairing of coordinates but breaks the assignment
    of coordinates to Δα/α values. This tests whether the spatial
    distribution of quasars (which is non-uniform) combined with the
    Δα/α distribution produces a spurious dipole.
    """
    rng = rnd.Random(seed)
    null_best_scores = []

    for s in range(n_null):
        # Create list of (ra, dec, da_a, err) and shuffle
        pairs = list(zip(ra_arr, dec_arr, da_a_arr, err_arr, sources, flags))
        rng.shuffle(pairs)

        ra_shuf = np.array([p[0] for p in pairs])
        dec_shuf = np.array([p[1] for p in pairs])
        da_a_shuf = np.array([p[2] for p in pairs])
        err_shuf = np.array([p[3] for p in pairs])

        best, _grid = search_dipole(
            ra_shuf, dec_shuf, da_a_shuf, err_shuf,
            n_ra=n_ra_grid, n_dec=n_dec_grid
        )
        null_best_scores.append(best["score"])

    return {
        "scores": null_best_scores,
        "mean_score": round(np.mean(null_best_scores), 2),
        "std_score": round(np.std(null_best_scores, ddof=1), 2),
        "median_score": round(np.median(null_best_scores), 2),
        "max_score": round(max(null_best_scores), 2),
        "n_null": n_null,
    }


def uniform_random_null(
    n_absorbers, da_a_arr, err_arr, sources, flags,
    n_null=200, seed=44, n_ra_grid=24, n_dec_grid=12
):
    """Null: assign uniform random positions on the sky.

    Tests whether the observed Δα/α distribution combined with a
    uniform spatial sampling produces a dipole at chance levels.
    """
    rng = rnd.Random(seed)
    null_best_scores = []

    for s in range(n_null):
        # Uniform random on sphere: RA ~ U(0,360), Dec ~ arcsin(U(-1,1))
        ra_unif = np.array([rng.uniform(0, 360) for _ in range(n_absorbers)])
        dec_unif = np.array([math.degrees(math.asin(rng.uniform(-1, 1)))
                             for _ in range(n_absorbers)])

        best, _grid = search_dipole(
            ra_unif, dec_unif, da_a_arr, err_arr,
            n_ra=n_ra_grid, n_dec=n_dec_grid
        )
        null_best_scores.append(best["score"])

    return {
        "scores": null_best_scores,
        "mean_score": round(np.mean(null_best_scores), 2),
        "std_score": round(np.std(null_best_scores, ddof=1), 2),
        "median_score": round(np.median(null_best_scores), 2),
        "max_score": round(max(null_best_scores), 2),
        "n_null": n_null,
    }


def instrument_systematics_null(
    ra_arr, dec_arr, da_a_arr, err_arr, sources, flags,
    n_null=200, seed=45, n_ra_grid=24, n_dec_grid=12
):
    """Instrument-systematics null: bootstrap resample within telescopes.

    Resamples with replacement, separately for Keck and VLT subsamples,
    preserving the telescope-specific error distributions. If the dipole
    is an artefact of instrument-specific systematics, this null should
    reproduce it.
    """
    rng = rnd.Random(seed)
    null_best_scores = []

    # Split by source
    is_keck = sources == "Keck"
    is_vlt = sources == "VLT"

    ra_keck = ra_arr[is_keck]
    dec_keck = dec_arr[is_keck]
    da_a_keck = da_a_arr[is_keck]
    err_keck = err_arr[is_keck]

    ra_vlt = ra_arr[is_vlt]
    dec_vlt = dec_arr[is_vlt]
    da_a_vlt = da_a_arr[is_vlt]
    err_vlt = err_arr[is_vlt]

    n_keck = len(ra_keck)
    n_vlt = len(ra_vlt)

    for s in range(n_null):
        # Bootstrap resample within each telescope
        idx_keck = [rng.randint(0, n_keck - 1) for _ in range(n_keck)]
        idx_vlt = [rng.randint(0, n_vlt - 1) for _ in range(n_vlt)]

        ra_boot = np.concatenate([ra_keck[idx_keck], ra_vlt[idx_vlt]])
        dec_boot = np.concatenate([dec_keck[idx_keck], dec_vlt[idx_vlt]])
        da_a_boot = np.concatenate([da_a_keck[idx_keck], da_a_vlt[idx_vlt]])
        err_boot = np.concatenate([err_keck[idx_keck], err_vlt[idx_vlt]])

        best, _grid = search_dipole(
            ra_boot, dec_boot, da_a_boot, err_boot,
            n_ra=n_ra_grid, n_dec=n_dec_grid
        )
        null_best_scores.append(best["score"])

    return {
        "scores": null_best_scores,
        "mean_score": round(np.mean(null_best_scores), 2),
        "std_score": round(np.std(null_best_scores, ddof=1), 2),
        "median_score": round(np.median(null_best_scores), 2),
        "max_score": round(max(null_best_scores), 2),
        "n_null": n_null,
    }


# ---------------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------------


def compute_z(obs, null_values):
    """z = (obs - mean(null)) / std(null)."""
    arr = np.array(null_values, dtype=float)
    mu = np.mean(arr)
    sigma = np.std(arr, ddof=1)
    if sigma < 1e-12:
        return 0.0
    return (obs - mu) / sigma


def percentile_rank(obs, null_values):
    """Fraction of null values less than obs (0-1)."""
    arr = np.array(null_values, dtype=float)
    return float(np.mean(arr < obs))


# ---------------------------------------------------------------------------
# Verdict logic
# ---------------------------------------------------------------------------


def determine_verdict(z_scores_dict, best_fit):
    """Determine overall verdict from z-scores."""
    verdict_parts = []

    all_abs_z = [abs(v) for v in z_scores_dict.values()]
    max_abs_z = max(all_abs_z) if all_abs_z else 0.0

    # Check instrument-systematics separation first (paramount null)
    inst_z = z_scores_dict.get("instrument_systematics", 0)
    inst_rejected = abs(inst_z) >= 2.0

    if not inst_rejected:
        verdict_parts.append("INSTRUMENT_SYSTEMATICS_NULL_NOT_REJECTED")
        # If instrument systematics null is NOT rejected, the signal is
        # underdetermined regardless of other nulls
        verdict_parts.append("UNDERDETERMINED")
    elif max_abs_z >= 4.0:
        verdict_parts.append("STRUCTURE_SIGNAL")
    elif max_abs_z >= 2.0:
        verdict_parts.append("UNDERDETERMINED")
    else:
        verdict_parts.append("NO_SIGNAL")

    # Check if best-fit dipole direction matches King+2012
    if best_fit:
        bf_ra = best_fit.get("ra_deg", 0)
        bf_dec = best_fit.get("dec_deg", 0)
        sep = angular_distance(bf_ra, bf_dec, 262.5, -58.0)
        if sep < 45:
            verdict_parts.append("BEST_FIT_NEAR_KNOWN_DIPOLE")

    # How many nulls separate?
    n_strong = sum(1 for v in all_abs_z if abs(v) >= 3.0)
    n_marginal = sum(1 for v in all_abs_z if 2.0 <= abs(v) < 3.0)

    if n_strong > 1:
        verdict_parts.append(f"STRONG_NULL_SEPARATION_{n_strong}OF{len(all_abs_z)}")
    elif n_marginal > 1:
        verdict_parts.append(f"MARGINAL_NULL_SEPARATION_{n_marginal}OF{len(all_abs_z)}")

    return " | ".join(verdict_parts), max_abs_z


# ---------------------------------------------------------------------------
# Notes writer
# ---------------------------------------------------------------------------


def write_notes_md(report):
    """Generate NOTES.md content."""
    verdict = report.get("verdict", "PENDING")
    max_z = report.get("max_abs_z", 0)

    if "NO_SIGNAL" in verdict:
        icon = "🔇"
    elif "STRUCTURE_SIGNAL" in verdict:
        icon = "📡"
    else:
        icon = "🟡"

    parts = [
        f"# G21 — Fine-structure α directional variation (King+2012 re-run CLEAN)  {icon}",
        f"Generated: {report.get('generated_at', '?')}",
        "",
        "## Stance",
        STANCE,
        "",
        "### Forbidden phrases (logged so a code-reviewer catches drift)",
    ]
    for fp in FORBIDDEN_PHRASES:
        parts.append(f"- `{fp}`")
    parts += ["", "## Data", ""]
    parts.append(
        "King et al. (2012) VLT+Keck quasar absorption Δα/α measurements. "
        "295 absorption systems from 153 quasars. "
        "See `data/astro/alpha_variation/README.md` for full provenance."
    )
    parts += [
        f"- N absorbers (clean): {report.get('data_source', {}).get('n_absorbers_clean', '?')}",
        f"- N Keck: {report.get('data_source', {}).get('n_keck', '?')}",
        f"- N VLT: {report.get('data_source', {}).get('n_vlt', '?')}",
        "", "## Observed dipole fit", "",
    ]

    bf = report.get("best_fit_dipole", {})
    if bf and "error" not in bf:
        parts += [
            f"### Best-fit dipole (brute-force grid search)",
            f"- RA: **{bf.get('ra_deg', '?'):.1f}°**",
            f"- Dec: **{bf.get('dec_deg', '?'):.1f}°**",
            f"- Amplitude: **{bf.get('amplitude_x1e5', '?'):.4f}** × 10⁻⁵",
            f"- Correlation r: **{bf.get('correlation_r', '?'):.4f}**",
            f"- χ²/ν: **{bf.get('chi2_nu', '?'):.2f}**",
            f"- Score: **{bf.get('score', '?'):.2f}**",
            "",
        ]

    # Known dipole comparison
    parts += ["### Comparison with King+2012 published dipole", ""]
    bf_ra = bf.get("ra_deg", 0) if bf else 0
    bf_dec = bf.get("dec_deg", 0) if bf else 0
    sep = angular_distance(bf_ra, bf_dec, 262.5, -58.0)
    parts += [
        f"- King+2012 dipole: RA=262.5°, Dec=-58.0°",
        f"- Angular separation from our best fit: **{sep:.1f}°**",
        f"- Our recovered amplitude: **{bf.get('amplitude_x1e5', '?'):.4f}** × 10⁻⁵ "
        f"(King+2012: 0.97 ± 0.12 × 10⁻⁵)",
        "",
    ]

    parts += ["## Null controls", ""]
    nulls = report.get("nulls", {})
    zs = report.get("z_scores", {})

    for null_label, null_data in nulls.items():
        parts += [f"### {null_label}", ""]
        parts += [
            f"- Mean score: **{null_data.get('mean_score', '?'):.2f}**",
            f"- Std score: {null_data.get('std_score', '?'):.2f}",
            f"- Median score: {null_data.get('median_score', '?'):.2f}",
            f"- Max score: {null_data.get('max_score', '?'):.2f}",
            f"- N realizations: {null_data.get('n_null', '?')}",
            "",
        ]

    parts += ["## z-scores (observed vs null)", ""]
    parts += ["| Null | z(score) |", "|------|----------|"]
    for null_label, z_val in zs.items():
        parts.append(f"| {null_label} | {z_val:+.2f} |")

    parts += ["", "## Verdict", ""]
    parts.append(f"**{verdict}**")
    parts.append(f"Max |z| across all nulls: **{max_z:.2f}**")
    parts += ["", "## Caveats", ""]
    parts += [
        "1. The King+2012 dataset uses two different telescopes (Keck HIRES, VLT UVES)",
        "   with different wavelength calibrations. A joint fit may introduce",
        "   telescope-specific systematics.",
        "2. sigma_rand (added in quadrature to photon-counting errors) depends on",
        "   the model being tested. We use the weighted-mean model values.",
        "3. The brute-force search uses a coarse grid (36×18 = 648 points).",
        "   Finer sampling may yield slightly different best-fit parameters.",
        "4. We do NOT fit for a dipole + monopole simultaneously with the",
        "   full covariance treatment of the King+2012 analysis.",
        "5. structure != meaning. A recovered dipole does NOT imply new physics.",
        "",
    ]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser(
        description="Fine-structure α directional variation — G21 probe"
    )
    ap.add_argument("--data", default=str(DEFAULT_DATA),
                    help=f"Data path (default: {DEFAULT_DATA})")
    ap.add_argument("--out", default=str(DEFAULT_OUT),
                    help=f"Output JSON path (default: {DEFAULT_OUT})")
    ap.add_argument("--n-null", type=int, default=200,
                    help="Number of null realizations (default: 200)")
    ap.add_argument("--n-ra", type=int, default=36,
                    help="RA grid points (default: 36)")
    ap.add_argument("--n-dec", type=int, default=18,
                    help="Dec grid points (default: 18)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--dry-run", action="store_true",
                    help="Print plan and exit")
    args = ap.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        print(f"ERROR: data file not found: {data_path}", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        print(json.dumps({
            "status": "dry_run",
            "data": str(data_path),
            "n_null": args.n_null,
            "grid_resolution": f"{args.n_ra}×{args.n_dec}",
        }, indent=2))
        return

    # Load data
    print(f"Loading data from {data_path}...")
    data = load_data(data_path)
    n = data["n"]
    print(f"Loaded {n} absorbers ({sum(data['source'] == 'Keck')} Keck, "
          f"{sum(data['source'] == 'VLT')} VLT)")

    # Exclude known outliers
    mask = data["outlier"] == 0
    ra_arr = data["ra_deg"][mask]
    dec_arr = data["dec_deg"][mask]
    da_a_arr = data["da_a"][mask]
    err_arr = data["err"][mask]
    sources = data["source"][mask]
    flags = data["sig_rand_flag"][mask]
    n_clean = len(ra_arr)
    print(f"After outlier removal: {n_clean} absorbers")

    n_keck = int(np.sum(sources == "Keck"))
    n_vlt = int(np.sum(sources == "VLT"))

    # Apply sigma_rand to errors
    err_total = np.array([
        total_error(err_arr[i], flags[i]) for i in range(n_clean)
    ])

    # Brute-force dipole search
    print(f"Brute-force dipole search ({args.n_ra}×{args.n_dec} grid)...")
    best_fit, grid = search_dipole(
        ra_arr, dec_arr, da_a_arr, err_total,
        n_ra=args.n_ra, n_dec=args.n_dec
    )
    print(f"Best-fit dipole: RA={best_fit['ra_deg']}°, "
          f"Dec={best_fit['dec_deg']}°, "
          f"A={best_fit['amplitude_x1e5']}, "
          f"r={best_fit['correlation_r']}")

    # Also fit at the known King+2012 dipole
    fit_known = dipole_fit(
        ra_arr, dec_arr, da_a_arr, err_total, 262.5, -58.0
    )

    # Null controls
    print(f"Running null controls ({args.n_null} realizations each)...")

    print("  scramble_coordinates...")
    null_scramble = scramble_coordinates_null(
        ra_arr, dec_arr, da_a_arr, err_total, sources, flags,
        n_null=args.n_null, seed=args.seed,
        n_ra_grid=args.n_ra // 2, n_dec_grid=args.n_dec // 2
    )

    print("  scramble_preserve_pairs...")
    null_pairs = scramble_coordinates_preserve_pairing_null(
        ra_arr, dec_arr, da_a_arr, err_total, sources, flags,
        n_null=args.n_null, seed=args.seed + 1,
        n_ra_grid=args.n_ra // 2, n_dec_grid=args.n_dec // 2
    )

    print("  uniform_random...")
    null_uniform = uniform_random_null(
        n_clean, da_a_arr, err_total, sources, flags,
        n_null=args.n_null, seed=args.seed + 2,
        n_ra_grid=args.n_ra // 2, n_dec_grid=args.n_dec // 2
    )

    print("  instrument_systematics (telescope bootstrap)...")
    null_instr = instrument_systematics_null(
        ra_arr, dec_arr, da_a_arr, err_total, sources, flags,
        n_null=args.n_null, seed=args.seed + 3,
        n_ra_grid=args.n_ra // 2, n_dec_grid=args.n_dec // 2
    )

    # Compute z-scores
    z_scores = {
        "scramble_coordinates": round(
            compute_z(best_fit["score"], null_scramble["scores"]), 2),
        "scramble_preserve_pairs": round(
            compute_z(best_fit["score"], null_pairs["scores"]), 2),
        "uniform_random": round(
            compute_z(best_fit["score"], null_uniform["scores"]), 2),
        "instrument_systematics": round(
            compute_z(best_fit["score"], null_instr["scores"]), 2),
    }

    # Percentile ranks
    pct_ranks = {
        "scramble_coordinates": round(
            percentile_rank(best_fit["score"], null_scramble["scores"]), 4),
        "scramble_preserve_pairs": round(
            percentile_rank(best_fit["score"], null_pairs["scores"]), 4),
        "uniform_random": round(
            percentile_rank(best_fit["score"], null_uniform["scores"]), 4),
        "instrument_systematics": round(
            percentile_rank(best_fit["score"], null_instr["scores"]), 4),
    }

    # Determine verdict
    verdict, max_abs_z = determine_verdict(z_scores, best_fit)

    # Build output (forbidden_hits initialized as 0, updated below)
    forbidden_hits = []
    output = {
        "mission_id": "G21",
        "probe": "tools/scripts/alpha_variation_probe.py",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_source": {
            "file": str(data_path),
            "citation": "King et al. (2012) MNRAS 422, 3370",
            "arxiv": "arXiv:1202.4758",
            "n_absorbers_raw": n,
            "n_absorbers_clean": n_clean,
            "n_keck": int(n_keck),
            "n_vlt": int(n_vlt),
            "n_outliers_removed": int(n - n_clean),
        },
        "n_null_realizations": args.n_null,
        "grid_resolution": f"{args.n_ra}×{args.n_dec}",
        "best_fit_dipole": best_fit,
        "fit_at_known_dipole": fit_known,
        "nulls": {
            "scramble_coordinates": null_scramble,
            "scramble_preserve_pairs": null_pairs,
            "uniform_random": null_uniform,
            "instrument_systematics": null_instr,
        },
        "z_scores": z_scores,
        "percentile_ranks": pct_ranks,
        "max_abs_z": max_abs_z,
        "verdict": verdict,
        "forbidden_hits": 0,
        "stance": STANCE,
    }

    # Check forbidden phrases against the output
    out_str = json.dumps(output).lower()
    for fp in FORBIDDEN_PHRASES:
        if fp.lower() in out_str:
            forbidden_hits.append(fp)
    output["forbidden_hits"] = len(forbidden_hits)

    # Write output
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    # Write NOTES.md
    notes_md = write_notes_md(output)
    notes_path = out_path.parent / "NOTES.md"
    with open(notes_path, "w") as f:
        f.write(notes_md)

    print(f"\nResults written to {out_path}")
    print(f"NOTES.md written to {notes_path}")
    print(f"Verdict: {verdict}")
    print(f"Max |z|: {max_abs_z:.2f}")

    print(f"\n  Best-fit dipole: RA={best_fit['ra_deg']:.1f}°, "
          f"Dec={best_fit['dec_deg']:.1f}°")
    print(f"  Amplitude: {best_fit['amplitude_x1e5']:.4f} × 10⁻⁵")
    print(f"  Correlation: r={best_fit['correlation_r']:.4f}")
    print(f"\n  z-scores:")
    for label, z in z_scores.items():
        print(f"    {label}: {z:+.2f}")


if __name__ == "__main__":
    main()
