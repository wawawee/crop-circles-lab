#!/usr/bin/env python3
"""vasco_probe — VASCO optical transient clustering (G13).

Sky clustering + galactic-latitude tests with plate-artifact nulls.

Usage:
    python tools/scripts/vasco_probe.py
    python tools/scripts/vasco_probe.py --data data/astro/vasco/vasco_candidates.csv
    python tools/scripts/vasco_probe.py --n-null 1000 --out outputs/vasco/run.json
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random as rnd
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.spatial import Delaunay, cKDTree

try:
    from skyfield.api import load as _sf_load
    from skyfield.positionlib import _to_xyz

    HAS_SKYFIELD = True
except ImportError:
    HAS_SKYFIELD = False

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DEFAULT_DATA = ROOT / "data" / "astro" / "vasco" / "vasco_candidates.csv"
DEFAULT_OUT = ROOT / "outputs" / "vasco" / "run.json"

# Forbidden phrases — probe must never output these.
FORBIDDEN = {"dyson sphere", "dyson sphere claim", "alien", "extraterrestrial",
             "et claim", "technosignature confirmed", "artificial origin",
             "deciphered", "translated"}

# ---------------------------------------------------------------------------
# Coordinate helpers
# ---------------------------------------------------------------------------

def radec_to_galactic(ra_deg, dec_deg):
    """Convert equatorial (RA, Dec) J2000 to Galactic (l, b) in degrees.

    IAU 1958 transformation using spherical trig (Green, Spherical Astronomy).
    Galactic north pole (NGP) in J2000 equatorial:
      α_NGP = 192.8595°, δ_NGP = 27.1284°
    Ascending node of Galactic plane on equator:
      l_Ω = 32.93192°
    """
    a = np.radians(ra_deg)
    d = np.radians(dec_deg)

    a_ngp = math.radians(192.8595)
    d_ngp = math.radians(27.1284)
    l_omega = math.radians(32.93192)

    sinb = np.sin(d) * math.sin(d_ngp) + np.cos(d) * math.cos(d_ngp) * np.cos(a - a_ngp)
    sinb = np.clip(sinb, -1.0, 1.0)
    b = np.arcsin(sinb)

    num = np.cos(d) * np.sin(a - a_ngp)
    den = (np.sin(d) * math.cos(d_ngp)
           - np.cos(d) * math.sin(d_ngp) * np.cos(a - a_ngp))
    l = (np.degrees(np.arctan2(den, num)) + 32.93192) % 360

    return l, np.degrees(b)


def angular_sep(ra1, dec1, ra2, dec2):
    """Haversine angular separation in degrees."""
    d1, d2 = np.radians(dec1), np.radians(dec2)
    dra = np.radians(ra2 - ra1)
    a = np.sin((d2 - d1) / 2) ** 2 + np.cos(d1) * np.cos(d2) * np.sin(dra / 2) ** 2
    return np.degrees(2 * np.arcsin(np.sqrt(np.clip(a, 0, 1))))


# ---------------------------------------------------------------------------
# Null generators
# ---------------------------------------------------------------------------

def uniform_sphere(n, seed=42):
    """Generate n uniform random points on sphere (RA, Dec degrees)."""
    rng = rnd.Random(seed)
    ras = []
    decs = []
    for _ in range(n):
        u = rng.random()
        v = rng.random()
        ra = 360 * u
        dec = np.degrees(np.arcsin(2 * v - 1))
        ras.append(ra)
        decs.append(dec)
    return np.array(ras), np.array(decs)


def scramble_coords(ra, dec, seed=42):
    """Independently permute RA and Dec to break spatial correlation."""
    rng = rnd.Random(seed)
    ra_shuf = ra.copy()
    dec_shuf = dec.copy()
    rng.shuffle(ra_shuf)
    rng.shuffle(dec_shuf)
    return ra_shuf, dec_shuf


def plate_artifact_null(n, seed=42):
    """Simulate plate-artifact distribution.

    Artifacts cluster along a few RA bands (plate boundaries) with
    scattered outliers — mimics emulsion flaws / plate edges.
    """
    rng = rnd.Random(seed)
    ras = []
    decs = []
    n_bands = 4
    band_ras = [rng.uniform(0, 360) for _ in range(n_bands)]
    band_width = 3.0

    for i in range(n):
        if rng.random() < 0.7:
            band = rng.randint(0, n_bands - 1)
            ra = band_ras[band] + rng.gauss(0, band_width)
            dec = rng.uniform(-40, 90)
        else:
            ra = rng.uniform(0, 360)
            dec = rng.uniform(-40, 90)
        ra %= 360
        ras.append(ra)
        decs.append(dec)
    return np.array(ras), np.array(decs)


# ---------------------------------------------------------------------------
# Statistics — all use cKDTree for O(N log N) performance
# ---------------------------------------------------------------------------

def radec_to_xyz(ra_deg, dec_deg):
    """Convert RA/Dec degrees to 3D unit vectors."""
    ra = np.radians(ra_deg)
    dec = np.radians(dec_deg)
    return np.column_stack([
        np.cos(dec) * np.cos(ra),
        np.cos(dec) * np.sin(ra),
        np.sin(dec),
    ])


def nearest_neighbor_stats(ra, dec):
    """Compute mean, median, min nearest-neighbor angular distances (deg)."""
    n = len(ra)
    if n < 2:
        return {"mean": None, "median": None, "min": None, "n": n}
    xyz = radec_to_xyz(ra, dec)
    tree = cKDTree(xyz)
    # query 2 nearest (k=2 because self-distance is 0)
    dists_3d, _ = tree.query(xyz, k=min(3, n))
    nn_3d = dists_3d[:, 1]  # 2nd nearest = actual NN (self = 0)

    # Convert 3D chord distance to angular separation: d_ang = 2 * arcsin(d_chord / 2)
    nn_3d = np.clip(nn_3d, 0, 2)
    nn_deg = np.degrees(2 * np.arcsin(nn_3d / 2))
    nn_deg = nn_deg[np.isfinite(nn_deg)]
    if len(nn_deg) == 0:
        return {"mean": None, "median": None, "min": None, "n": n}
    return {
        "mean": float(np.mean(nn_deg)),
        "median": float(np.median(nn_deg)),
        "min": float(np.min(nn_deg)),
        "n": n,
    }


def close_pairs(ra, dec, threshold_deg=1.0):
    """Count pairs with angular separation < threshold_deg using cKDTree."""
    n = len(ra)
    if n < 2:
        return 0
    xyz = radec_to_xyz(ra, dec)
    tree = cKDTree(xyz)
    # Chord distance for given angular threshold: d_chord = 2 * sin(thresh_rad/2)
    thresh_rad = np.radians(threshold_deg)
    max_chord = 2 * math.sin(thresh_rad / 2)
    pairs = tree.query_ball_tree(tree, r=max_chord)
    count = sum(len(p) - 1 for p in pairs) // 2  # subtract self, divide by 2
    return count


def gal_lat_stats(b):
    """Compute stats on Galactic latitudes (degrees)."""
    b_abs = np.abs(b)
    return {
        "mean_abs_b": float(np.mean(b_abs)),
        "median_abs_b": float(np.median(b_abs)),
        "frac_plane_20": float(np.mean(b_abs < 20)),
        "frac_plane_10": float(np.mean(b_abs < 10)),
        "frac_plane_5": float(np.mean(b_abs < 5)),
    }


def delaunay_areas(ra, dec):
    """Delaunay triangulation: mean triangle area on sky (deg²)."""
    n = len(ra)
    if n < 4:
        return {"mean_area": None, "n": n}

    ra_r = np.radians(ra)
    dec_r = np.radians(dec)
    x = np.cos(dec_r) * np.cos(ra_r)
    y = np.cos(dec_r) * np.sin(ra_r)
    z = np.sin(dec_r)

    try:
        tri = Delaunay(np.column_stack([x, y, z]))
        areas = []
        for simplex in tri.simplices:
            p = np.array([x[simplex], y[simplex], z[simplex]]).T
            a = np.linalg.norm(np.cross(p[1] - p[0], p[2] - p[0])) / 2.0
            areas.append(a)

        # Convert to solid angle (steradians → deg²)
        areas_sr = np.array(areas)
        areas_deg2 = areas_sr * (180 / np.pi) ** 2
        return {
            "mean_area_deg2": float(np.mean(areas_deg2)),
            "std_area_deg2": float(np.std(areas_deg2)),
            "median_area_deg2": float(np.median(areas_deg2)),
            "n_triangles": len(areas),
        }
    except Exception:
        return {"mean_area": None, "error": "delaunay_failed"}


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def compute_z(observed, null_values):
    """Compute z = (obs - mean(null)) / std(null)."""
    arr = np.array(null_values, dtype=float)
    mu = np.mean(arr)
    sigma = np.std(arr, ddof=1)
    if sigma == 0:
        return 0.0
    return (observed - mu) / sigma


def run_null(ra, dec, null_gen, n_null, label, seed_base=1000):
    """Run a null distribution for all metrics."""
    metrics = ["nn_mean", "nn_median", "close_pairs_1deg", "close_pairs_5deg",
               "mean_abs_b", "median_abs_b", "frac_plane_20", "frac_plane_10"]
    null_results = {m: [] for m in metrics}

    n = len(ra)
    for i in range(n_null):
        r, d = null_gen(n, seed=seed_base + i)
        l, b = radec_to_galactic(r, d)
        nn = nearest_neighbor_stats(r, d)
        null_results["nn_mean"].append(nn["mean"])
        null_results["nn_median"].append(nn["median"])
        null_results["close_pairs_1deg"].append(close_pairs(r, d, 1.0))
        null_results["close_pairs_5deg"].append(close_pairs(r, d, 5.0))
        gs = gal_lat_stats(b)
        null_results["mean_abs_b"].append(gs["mean_abs_b"])
        null_results["median_abs_b"].append(gs["median_abs_b"])
        null_results["frac_plane_20"].append(gs["frac_plane_20"])
        null_results["frac_plane_10"].append(gs["frac_plane_10"])

    return null_results


def main():
    ap = argparse.ArgumentParser(
        description="VASCO optical transient clustering — G13 probe")
    ap.add_argument("--data", default=str(DEFAULT_DATA),
                    help=f"CSV path (default: {DEFAULT_DATA})")
    ap.add_argument("--out", default=str(DEFAULT_OUT),
                    help=f"Output JSON path (default: {DEFAULT_OUT})")
    ap.add_argument("--n-null", type=int, default=500,
                    help="Number of null realizations (default: 500)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--dry-run", action="store_true",
                    help="Print plan and exit")
    args = ap.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        print(f"ERROR: data file not found: {data_path}", file=sys.stderr)
        sys.exit(1)

    # Load data
    ra_list, dec_list = [], []
    with open(data_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                ra_list.append(float(row["RA"]))
                dec_list.append(float(row["DEC"]))
            except (ValueError, KeyError):
                continue

    ra = np.array(ra_list)
    dec = np.array(dec_list)
    n = len(ra)

    if args.dry_run:
        print(json.dumps({
            "status": "dry_run",
            "candidates": n,
            "source": str(data_path),
            "null_realizations": args.n_null,
            "reuse": ["tools/scripts/vasco_probe.py",
                      "tools/ccat/spatial_report.py",
                      "tools/astro/astro_probe.py"],
        }, indent=2))
        return

    print(f"VASCO probe: {n} candidates from {data_path}")
    print(f"Null realizations: {args.n_null}")

    # Compute Galactic coordinates
    print("Computing Galactic coordinates...")
    l, b = radec_to_galactic(ra, dec)

    # Observed stats
    print("Computing observed statistics...")
    obs_nn = nearest_neighbor_stats(ra, dec)
    obs_cp1 = close_pairs(ra, dec, 1.0)
    obs_cp5 = close_pairs(ra, dec, 5.0)
    obs_glat = gal_lat_stats(b)
    obs_delaunay = delaunay_areas(ra, dec)

    obs = {
        "candidate_count": n,
        "nearest_neighbor": obs_nn,
        "close_pairs_1deg": obs_cp1,
        "close_pairs_5deg": obs_cp5,
        "galactic_latitude": obs_glat,
        "delaunay": obs_delaunay,
    }

    # Null controls
    print("Running null controls...")
    null_labels = [
        ("uniform_random", uniform_sphere),
        ("scramble_coords", lambda n, seed=42: scramble_coords(ra[:n], dec[:n], seed)),
        ("plate_artifact", plate_artifact_null),
    ]

    nulls = {}
    z_scores = {}
    verdict_parts = []

    for label, gen in null_labels:
        print(f"  {label}...")
        nr = run_null(ra, dec, gen, args.n_null, label, seed_base=args.seed + 100)

        nn_mean = obs_nn["mean"]
        null_mean_nn = np.array(nr["nn_mean"])
        z_nn_mean = compute_z(nn_mean, null_mean_nn)
        z_cp1 = compute_z(obs_cp1, nr["close_pairs_1deg"])
        z_cp5 = compute_z(obs_cp5, nr["close_pairs_5deg"])
        z_glat = compute_z(obs_glat["mean_abs_b"], nr["mean_abs_b"])
        z_frac20 = compute_z(obs_glat["frac_plane_20"], nr["frac_plane_20"])

        nulls[label] = {
            "nn_mean": {"mean": float(np.mean(null_mean_nn)),
                        "std": float(np.std(null_mean_nn, ddof=1))},
            "close_pairs_1deg": {"mean": float(np.mean(nr["close_pairs_1deg"])),
                                 "std": float(np.std(nr["close_pairs_1deg"], ddof=1))},
            "close_pairs_5deg": {"mean": float(np.mean(nr["close_pairs_5deg"])),
                                 "std": float(np.std(nr["close_pairs_5deg"], ddof=1))},
            "mean_abs_b": {"mean": float(np.mean(nr["mean_abs_b"])),
                           "std": float(np.std(nr["mean_abs_b"], ddof=1))},
            "frac_plane_20": {"mean": float(np.mean(nr["frac_plane_20"])),
                              "std": float(np.std(nr["frac_plane_20"], ddof=1))},
        }
        z_scores[label] = {
            "nn_mean": z_nn_mean,
            "close_pairs_1deg": z_cp1,
            "close_pairs_5deg": z_cp5,
            "mean_abs_b": z_glat,
            "frac_plane_20": z_frac20,
        }

    # Determine verdict
    all_zs = []
    for label in null_labels:
        label_name = label[0]
        for metric, zval in z_scores[label_name].items():
            all_zs.append(abs(zval))

    max_abs_z = max(all_zs) if all_zs else 0

    # Key test: does the signal separate from plate_artifact null?
    plate_art_zs = z_scores.get("plate_artifact", {})
    max_pa_abs_z = max(abs(v) for v in plate_art_zs.values()) if plate_art_zs else 0

    # Check separation from plate-artifact null
    if max_pa_abs_z < 3.0:
        verdict_parts.append("DOES_NOT_SEPARATE_FROM_PLATE_ARTIFACT")

    # Check separation from uniform random
    uniform_zs = z_scores.get("uniform_random", {})
    max_uniform_abs_z = max(abs(v) for v in uniform_zs.values()) if uniform_zs else 0

    if max_uniform_abs_z >= 3.0 and max_pa_abs_z < 3.0:
        verdict_parts.append("UNDERDETERMINED")
    elif max_uniform_abs_z >= 5.0 and max_pa_abs_z >= 3.0:
        verdict_parts.append("STRUCTURE_SIGNAL")
    elif max_uniform_abs_z < 3.0:
        verdict_parts.append("NO_SIGNAL")
    else:
        verdict_parts.append("UNDERDETERMINED")

    # Check forbidden phrases
    forbidden_hits = []
    for phrase in FORBIDDEN:
        for key in obs:
            if isinstance(obs[key], str) and phrase in obs[key].lower():
                forbidden_hits.append(phrase)
        for label in null_labels:
            for key in z_scores.get(label[0], {}):
                val = str(z_scores[label[0]][key])
                if phrase in val.lower():
                    forbidden_hits.append(phrase)

    if forbidden_hits:
        verdict_parts.append("WARNING_FORBIDDEN_PHRASE")

    verdict = " | ".join(verdict_parts)

    output = {
        "mission_id": "G13",
        "probe": "tools/scripts/vasco_probe.py",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_source": {
            "file": str(data_path),
            "doi": "10.5281/zenodo.14563521",
            "catalog": "Solano et al. 2022 (VASCO POSS-I vanishing sources)",
            "license": "CC-BY 4.0",
        },
        "n_candidates": n,
        "n_null_realizations": args.n_null,
        "observed": obs,
        "nulls": nulls,
        "z_scores": z_scores,
        "max_abs_z": max_abs_z,
        "verdict": verdict,
        "forbidden_hits": len(forbidden_hits),
        "stance": "structure != meaning. no-signal prior. plate artifacts first.",
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nResults written to {out_path}")
    print(f"Verdict: {verdict}")
    print(f"Max |z| across all metrics × nulls: {max_abs_z:.2f}")

    # Brief summary
    print(f"\n  Observed mean NN distance: {obs_nn['mean']:.3f}°")
    print(f"  Close pairs <1°: {obs_cp1}")
    print(f"  Mean |b|: {obs_glat['mean_abs_b']:.1f}°")
    print(f"  Fraction in |b|<20°: {obs_glat['frac_plane_20']:.3f}")

    for label, _ in null_labels:
        zs = z_scores[label]
        print(f"\n  {label} z-scores:")
        for metric, z in zs.items():
            print(f"    {metric}: {z:+.2f}")


if __name__ == "__main__":
    main()
