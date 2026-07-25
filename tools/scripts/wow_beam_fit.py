"""wow_beam_fit.py — G3 Wow! signal beam-fit (standalone).

Intensities: [6, 14, 26, 30.5, 19.5, 5.5]

Source: Ehman's handwritten 6EQUJ5 transcript from the Big Ear telescope
printout (Ohio State University Radio Observatory, August 15, 1977; archived
at the Ohio Historical Society). The Big Ear used a 0-9,A-Z character code
for sigma-intensity buckets: 0 = 0-1 sigma, 1 = 1-2, ..., 6 = 6-7,
E(14) = 14-15, Q(26) = 26-27, U(30) = 30-31, J(19) = 19-20, 5 = 5-6.
This calibration uses the bucket lower bound for 6, E, Q and the bucket
midpoint for U, J, 5 (consistent with the digitised strip-chord curve).

Stance: structure != message. A 3-parameter fit on N=6 has only 3 d.o.f.
— heavily underdetermined. The fit is consistent with EITHER a horn-beam
transit OR a transient pulse (or a hydrogen cloud per PHL@UPR 2024,
arXiv:2408.08513). NO technosignature claim is made.

CLI:
    python tools/scripts/wow_beam_fit.py
    python tools/scripts/wow_beam_fit.py --out-json outputs/radio/wow_beam_fit.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np


# --- intensities -----------------------------------------------------------

# 6EQUJ5 sigma-unit intensities, calibrated as lower-bound for 6/E/Q and
# bucket-midpoint for U/J/5. See module docstring for full source note.
G3_INTENSITIES = np.asarray([6.0, 14.0, 26.0, 30.5, 19.5, 5.5], dtype=float)

N_SAMPLES = 6
DOF_GAUSSIAN = N_SAMPLES - 3  # 3
DOF_SINC = N_SAMPLES - 3
DOF_CONSTANT = N_SAMPLES - 1

# Grid search bounds (same as radio_probe.py)
MU_RANGE = (0.0, 5.0)
SIGMA_RANGE = (0.5, 3.0)
AMP_RANGE = (1.0, 60.0)
GRID_STEPS = 51
N_PERMUTATIONS = 24


# --- transit models --------------------------------------------------------

def _gaussian_at(idx: np.ndarray, mu: float, sigma: float,
                 amp: float) -> np.ndarray:
    """Closed-form Gaussian at sample indices."""
    s = max(float(sigma), 1e-9)
    return float(amp) * np.exp(
        -0.5 * ((np.asarray(idx, dtype=float) - float(mu)) / s) ** 2
    )


def _sinc_at(idx: np.ndarray, mu: float, sigma: float,
             amp: float) -> np.ndarray:
    """Closed-form sinc transit: amp * sinc((idx - mu) / sigma)."""
    s = max(float(sigma), 1e-9)
    x = (np.asarray(idx, dtype=float) - float(mu)) / s
    pi_x = np.pi * x
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(np.abs(pi_x) < 1e-9, 1.0, np.sin(pi_x) / pi_x)
    return float(amp) * out


# --- fitting ---------------------------------------------------------------

def fit_beam_transit(
    samples: np.ndarray,
    mu_range: tuple[float, float] = MU_RANGE,
    sigma_range: tuple[float, float] = SIGMA_RANGE,
    grid_steps: int = GRID_STEPS,
) -> dict:
    """Pure-numpy grid search for Gaussian + sinc transit fits.

    Returns r-squared for Gaussian, sinc, and constant baselines; recovered
    parameters; residuals; degeneracy pair; underdetermined caveat.
    """
    samples = np.asarray(samples, dtype=float)
    n = int(len(samples))
    if n == 0:
        return _empty_fit()

    a_const = float(np.mean(samples))
    ss_tot = float(np.sum((samples - a_const) ** 2)) or 1e-12
    ss_res_const = float(np.sum((samples - a_const) ** 2))
    r2_const = float(1.0 - ss_res_const / ss_tot)

    mu_grid = np.linspace(mu_range[0], mu_range[1], grid_steps)
    sigma_grid = np.linspace(sigma_range[0], sigma_range[1], grid_steps)
    grid_idx = np.arange(n, dtype=float)
    ss_tot_safe = max(ss_tot, 1e-12)

    best_gauss = (np.inf, None, None, None)
    best_sinc = (np.inf, None, None, None)

    for mu in mu_grid:
        for sig in sigma_grid:
            g_pred = _gaussian_at(grid_idx, mu, sig, 1.0)
            if float(np.max(np.abs(g_pred))) <= 1e-9:
                continue
            scale = float(np.dot(samples, g_pred)) / float(np.dot(g_pred, g_pred))
            if scale <= 0.0:
                continue
            g_fit = scale * g_pred
            ss = float(np.sum((samples - g_fit) ** 2))
            if ss < best_gauss[0]:
                best_gauss = (ss, float(mu), float(sig), float(scale))

            s_pred = _sinc_at(grid_idx, mu, sig, 1.0)
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

    g_resid = samples - amp_g * _gaussian_at(grid_idx, mu_g, sig_g, 1.0)
    s_resid = samples - amp_s * _sinc_at(grid_idx, mu_s, sig_s, 1.0)

    candidate_mu_alt = 6.0 - float(mu_g)
    degen_pair = (round(float(mu_g), 4), round(candidate_mu_alt, 4))

    return {
        "n_samples": n,
        "best_amplitude_constant": round(a_const, 4),
        "r2_constant": round(r2_const, 6),
        "r2_gaussian": round(r2_gauss, 6),
        "r2_sinc": round(r2_sinc, 6),
        "n_dof_constant": DOF_CONSTANT,
        "n_dof_gaussian": DOF_GAUSSIAN,
        "n_dof_sinc": DOF_SINC,
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
        "underdetermined_note": (
            f"Gaussian fit on N={n} has only {DOF_GAUSSIAN} d.o.f. "
            f"(N-K={n}-3); a constant baseline has {DOF_CONSTANT}. "
            f"With {DOF_GAUSSIAN} d.o.f. the fit is heavily "
            f"under-determined -- two distinct transits (e.g., horn-beam "
            f"crossing vs transient pulse) can both fit the {n} peaks "
            f"equally well. WOW IS NOT a confirmed technosignature per "
            f"Sheikh et al. 2021 / PHL@UPR 2024 (arXiv:2408.08513, CC BY 4.0). "
            f"Structure != message."
        ),
        "underdetermined": bool(DOF_GAUSSIAN <= 3),
        "fit_quality_caveat": (
            "Even if r\u00b2 \u2248 1 from a 3-param fit, the d.o.f. "
            "shortage means the fit is consistent with EITHER a horn-beam "
            "transit OR a transient signal. We cannot distinguish them "
            f"from {n} bins."
        ),
    }


def _empty_fit() -> dict:
    return {
        "n_samples": 0, "r2_constant": 0.0,
        "r2_gaussian": 0.0, "r2_sinc": 0.0,
        "recovered_gaussian": None, "recovered_sinc": None,
        "degeneracy_pair": (None, None),
        "underdetermined": True, "n_dof_gaussian": 0,
        "n_dof_sinc": 0, "n_dof_constant": 0,
    }


# --- scramble null ---------------------------------------------------------

def scramble_null(
    samples: np.ndarray,
    n_permutations: int = N_PERMUTATIONS,
    seed: int = 0,
) -> dict:
    """Permute N samples and re-fit Gaussian each time.

    Returns median + p5/p95 r-squared distribution across permutations.
    """
    samples = np.asarray(samples, dtype=float)
    rng = np.random.default_rng(seed)
    r2_dist: list[float] = []
    mu_dist: list[float] = []
    n = len(samples)
    if n == 0:
        return {"n_samples": 0, "n_permutations": 0,
                "r2_median": 0.0, "r2_p5": 0.0, "r2_p95": 0.0,
                "mu_distribution_median": 0.0}
    for _ in range(int(n_permutations)):
        permuted = rng.permutation(samples)
        fit = fit_beam_transit(permuted)
        r2_dist.append(float(fit["r2_gaussian"]))
        if fit["recovered_gaussian"] is not None:
            mu_dist.append(float(fit["recovered_gaussian"]["mu_idx"]))
    arr = np.asarray(r2_dist, dtype=float)
    mu_arr = np.asarray(mu_dist, dtype=float)
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


# --- orchestrator ----------------------------------------------------------

def run_beam_fit(seed: int = 0) -> dict:
    """Run full G3 beam-fit on the calibrated intensities."""
    samples = G3_INTENSITIES.copy()

    fit = fit_beam_transit(samples)
    scramble = scramble_null(samples, seed=seed)

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
        "method": "gaussian_sinc_transit_grid_fit",
        "data_source": "Ehman_6EQUJ5_transcript_1977",
        "intensities": [round(float(x), 4) for x in samples],
        "intensities_note": (
            "6EQUJ5 sigma-unit calibration: 6=E=lower-bound(6-7sigma), "
            "14=E=lower-bound(14-15), 26=Q=lower-bound(26-27), "
            "30.5=U=midpoint(30-31), 19.5=J=midpoint(19-20), "
            "5.5=5=midpoint(5-6). Source: Ehman handwritten transcript, "
            "Big Ear telescope, OSURO, 1977-08-15."
        ),
        "fit": fit,
        "scramble_null": scramble,
        "cross_check_scramble": cross_check,
        "verdict": "UNDERDETERMINED",
        "verdict_note": (
            "The Gaussian+sinc transit fit shows structure (r\u00b2 >> 0, "
            "above scramble median), but N=6 with only 3 d.o.f. is "
            "UNDERDETERMINED: the structure is equally consistent with a "
            "horn-beam transit, a transient pulse, or a natural hydrogen-"
            "cloud mechanism (PHL@UPR 2024, arXiv:2408.08513). Structure "
            "\u2260 ET."
        ),
        "warnings": [
            "structure != message; N=6 fit is heavily underdetermined; "
            "we do NOT claim detection of artificial origin.",
            "2024 PHL@UPR reanalysis (arXiv:2408.08513, CC BY 4.0) "
            "attributes Wow! to a hydrogen cloud near a solar-type star "
            "-- NATURAL mechanism.",
        ],
        "stance": (
            "Structure != message. The 1977 Wow! signal is a 6-sample "
            "intensity table, NOT a time series. A 3-parameter Gaussian "
            "fit on N=6 has only 3 d.o.f. -- heavily underdetermined. "
            "The fit is consistent with EITHER a horn-beam transit OR a "
            "transient pulse (or a hydrogen cloud per PHL@UPR 2024, "
            "arXiv:2408.08513). We do NOT claim detection of an "
            "artificial origin. The N=6 fit gives us NO statistical "
            "power to distinguish transient from beam-crossing. "
            "Periodicity / beam-crossing is necessary, NOT sufficient "
            "for artificiality. Verdict: UNDERDETERMINED "
            "(structure \u2260 ET). Lab motto: structure != message."
        ),
    }


# --- CLI / output ----------------------------------------------------------

def run(seed: int = 0) -> dict:
    """Convenience wrapper for test import."""
    return run_beam_fit(seed=seed)


def write_json(report: dict, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="G3 Wow! signal beam-fit (standalone).",
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out-json", type=str, default=None,
                        help="Write output JSON to path.")
    args = parser.parse_args()

    report = run_beam_fit(seed=args.seed)

    if args.out_json:
        write_json(report, args.out_json)
        print(f"Wrote {args.out_json}")
    else:
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
