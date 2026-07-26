#!/usr/bin/env python3
"""Per-telescope split: run dipole search separately on Keck and VLT.

Usage:
    python tools/scripts/alpha_variation_telescope_split.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA_DIR = ROOT / "data" / "astro" / "alpha_variation"
DEFAULT_DATA = DATA_DIR / "king_2012_vlt_keck.dat"

SIGMA_RAND = {1: 0.000, 2: 1.743, 3: 0.905}

# ---------------------------------------------------------------------------
# Reuse probe functions (import where available)
# ---------------------------------------------------------------------------
sys.path.insert(0, str(HERE))
from alpha_variation_probe import (
    load_data, total_error, dipole_fit, search_dipole,
    scramble_coordinates_null, uniform_random_null,
    compute_z, determine_verdict, angular_distance, STANCE,
)


def main():
    data = load_data(DEFAULT_DATA)
    mask = data["outlier"] == 0
    ra = data["ra_deg"][mask]
    dec = data["dec_deg"][mask]
    da_a = data["da_a"][mask]
    err = data["err"][mask]
    sources = data["source"][mask]
    flags = data["sig_rand_flag"][mask]
    n = len(ra)

    # Apply sigma_rand
    err_total = np.array([total_error(err[i], flags[i]) for i in range(n)])

    # Split
    is_keck = sources == "Keck"
    is_vlt = sources == "VLT"
    n_keck = int(np.sum(is_keck))
    n_vlt = int(np.sum(is_vlt))

    results = {}
    grid_res = (36, 18)
    n_null = 500

    for label, mask_sel, n_pts in [
        ("Keck", is_keck, n_keck),
        ("VLT", is_vlt, n_vlt),
        ("Combined", np.ones(n, dtype=bool), n),
    ]:
        print(f"\n{'='*60}")
        print(f"=== {label} (N={n_pts}) ===")
        print(f"{'='*60}")

        ra_s = ra[mask_sel]
        dec_s = dec[mask_sel]
        da_a_s = da_a[mask_sel]
        err_s = err_total[mask_sel]
        sources_s = sources[mask_sel]
        flags_s = flags[mask_sel]

        # Dipole search
        best, _grid = search_dipole(ra_s, dec_s, da_a_s, err_s,
                                      n_ra=grid_res[0], n_dec=grid_res[1])
        print(f"  Best-fit: RA={best['ra_deg']:.1f}°, Dec={best['dec_deg']:.1f}°")
        print(f"  Amplitude: {best['amplitude_x1e5']:.4f} × 10⁻⁵")
        print(f"  r={best['correlation_r']:.4f}, score={best['score']:.2f}")

        # Fit at the known dipole
        fit_known = dipole_fit(ra_s, dec_s, da_a_s, err_s, 262.5, -58.0)
        print(f"  At King+2012 dipole: A={fit_known.get('amplitude_x1e5','?'):.4f} ± {fit_known.get('amplitude_err','?'):.4f}, χ²/ν={fit_known.get('chi2_nu','?'):.2f}")

        # Fit at the other's best-fit
        # (will compute for combined below)
        sep_king = angular_distance(best['ra_deg'], best['dec_deg'], 262.5, -58.0)
        print(f"  Angular separation from King+2012: {sep_king:.1f}°")

        # Null: scramble_coordinates
        print(f"  Running scramble_coordinates null ({n_null} realizations)...")
        null_scramble = scramble_coordinates_null(
            ra_s, dec_s, da_a_s, err_s, sources_s, flags_s,
            n_null=n_null, seed=42,
            n_ra_grid=grid_res[0] // 2, n_dec_grid=grid_res[1] // 2,
        )
        z_scramble = compute_z(best['score'], null_scramble['scores'])
        print(f"    z = {z_scramble:+.2f} (mean={null_scramble['mean_score']:.2f}, std={null_scramble['std_score']:.2f})")

        # Null: uniform_random
        print(f"  Running uniform_random null ({n_null} realizations)...")
        null_uniform = uniform_random_null(
            n_pts, da_a_s, err_s, sources_s, flags_s,
            n_null=n_null, seed=44,
            n_ra_grid=grid_res[0] // 2, n_dec_grid=grid_res[1] // 2,
        )
        z_uniform = compute_z(best['score'], null_uniform['scores'])
        print(f"    z = {z_uniform:+.2f} (mean={null_uniform['mean_score']:.2f}, std={null_uniform['std_score']:.2f})")

        results[label] = {
            "n": n_pts,
            "best_fit": best,
            "fit_at_king_dipole": fit_known,
            "sep_from_king_deg": round(sep_king, 1),
            "z_scramble": round(z_scramble, 2),
            "z_uniform": round(z_uniform, 2),
            "null_scramble": null_scramble,
            "null_uniform": null_uniform,
        }

    # Cross-fit: Keck best on VLT data and vice versa
    print(f"\n{'='*60}")
    print(f"=== Cross-telescope consistency ===")
    print(f"{'='*60}")

    k_best = results["Keck"]["best_fit"]
    v_best = results["VLT"]["best_fit"]

    # Fit Keck dipole on VLT data
    fit_k_on_v = dipole_fit(ra[is_vlt], dec[is_vlt], da_a[is_vlt],
                             err_total[is_vlt], k_best["ra_deg"], k_best["dec_deg"])
    print(f"  Keck dipole on VLT data:")
    print(f"    A={fit_k_on_v.get('amplitude_x1e5','?'):.4f} ± {fit_k_on_v.get('amplitude_err','?'):.4f}, χ²/ν={fit_k_on_v.get('chi2_nu','?'):.2f}")

    # Fit VLT dipole on Keck data
    fit_v_on_k = dipole_fit(ra[is_keck], dec[is_keck], da_a[is_keck],
                             err_total[is_keck], v_best["ra_deg"], v_best["dec_deg"])
    print(f"  VLT dipole on Keck data:")
    print(f"    A={fit_v_on_k.get('amplitude_x1e5','?'):.4f} ± {fit_v_on_k.get('amplitude_err','?'):.4f}, χ²/ν={fit_v_on_k.get('chi2_nu','?'):.2f}")

    # Angular separation between telescopes
    sep_tel = angular_distance(k_best["ra_deg"], k_best["dec_deg"],
                                v_best["ra_deg"], v_best["dec_deg"])
    print(f"  Angular separation between Keck and VLT best-fit dipoles: {sep_tel:.1f}°")

    results["cross"] = {
        "keck_vlt_separation_deg": round(sep_tel, 1),
        "keck_on_vlt": fit_k_on_v,
        "vlt_on_keck": fit_v_on_k,
    }

    # Save results
    out_path = ROOT / "outputs" / "alpha_variation" / "telescope_split.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {out_path}")

    # Summary table
    print(f"\n{'='*70}")
    print(f"SUMMARY TABLE")
    print(f"{'='*70}")
    print(f"{'Subset':<12} {'N':>5} {'RA':>7} {'Dec':>7} {'A(×10⁻⁵)':>10} {'r':>6} {'sep°':>5} {'z_scram':>8} {'z_unif':>8}")
    print(f"{'-'*70}")
    for label in ["Keck", "VLT", "Combined"]:
        r = results[label]
        b = r["best_fit"]
        print(f"{label:<12} {r['n']:>5} {b['ra_deg']:>7.1f} {b['dec_deg']:>7.1f} {b['amplitude_x1e5']:>10.4f} {b['correlation_r']:>6.4f} {r['sep_from_king_deg']:>5.1f} {r['z_scramble']:>+8.2f} {r['z_uniform']:>+8.2f}")


if __name__ == "__main__":
    main()
