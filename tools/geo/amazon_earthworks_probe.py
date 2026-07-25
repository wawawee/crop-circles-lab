#!/usr/bin/env python3
"""
amazon_earthworks_probe.py  --  G-Amazon, Mode A (spatial point-process screen)

Lab stance: structure != meaning. This probe measures whether a set of
earthwork / geoglyph *coordinates* shows spatial STRUCTURE (clustering or
regularity) relative to Complete Spatial Randomness (CSR) inside the SAME
study mask. Anthropogenic sites are expected to cluster because settlement
follows rivers, terra firme and soils -- that is environmental/cultural
structure, NOT a message, and NOT a "lost civilisation" signal.

Two statistics, one shared CSR Monte-Carlo null:
  1. Clark-Evans nearest-neighbour ratio  R = mean_NN_obs / mean_NN_csr
       R < 1  -> clustered ; R ~ 1 -> random ; R > 1 -> regular/dispersed
  2. Ripley's K / L(r) vs the CSR envelope built by re-drawing N uniform
       points inside the identical convex-hull mask (matched N, matched edge
       effects -- the envelope carries the same hull-boundary bias as the data,
       which is the honest way to compare when the true window is unknown).

Geometry: lon/lat are projected to a local equirectangular km frame around the
centroid so hull area, NN distances and K are all self-consistent. This is a
screening approximation over a ~15 deg latitude band -- documented, not hidden.

No scipy. numpy only. Verdict string is one of:
    STRUCTURE_ONLY | NO_SIGNAL | UNDERDETERMINED | BLOCKED
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
from datetime import datetime, timezone

import numpy as np

# ----------------------------------------------------------------------------
# geometry helpers
# ----------------------------------------------------------------------------

_KM_PER_DEG_LAT = 110.574


def project_km(lat: np.ndarray, lon: np.ndarray):
    """Local equirectangular projection (km) about the point-set centroid."""
    lat = np.asarray(lat, dtype=float)
    lon = np.asarray(lon, dtype=float)
    lat0 = float(np.mean(lat))
    lon0 = float(np.mean(lon))
    km_per_deg_lon = 111.320 * math.cos(math.radians(lat0))
    x = (lon - lon0) * km_per_deg_lon
    y = (lat - lat0) * _KM_PER_DEG_LAT
    return np.column_stack([x, y]), (lat0, lon0)


def convex_hull(points: np.ndarray) -> np.ndarray:
    """Andrew's monotone chain. points: (N,2). Returns hull vertices CCW."""
    pts = sorted(map(tuple, points))
    pts = [p for i, p in enumerate(pts) if i == 0 or p != pts[i - 1]]
    if len(pts) <= 2:
        return np.array(pts, dtype=float)

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return np.array(lower[:-1] + upper[:-1], dtype=float)


def polygon_area(hull: np.ndarray) -> float:
    """Shoelace area (km^2) for a hull given in projected km."""
    x, y = hull[:, 0], hull[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def _points_in_poly(pts: np.ndarray, hull: np.ndarray) -> np.ndarray:
    """Vectorised ray-casting; pts (M,2), hull (K,2) -> bool (M,)."""
    x, y = pts[:, 0], pts[:, 1]
    inside = np.zeros(len(pts), dtype=bool)
    n = len(hull)
    j = n - 1
    for i in range(n):
        xi, yi = hull[i]
        xj, yj = hull[j]
        cond = ((yi > y) != (yj > y)) & (
            x < (xj - xi) * (y - yi) / (yj - yi + 1e-18) + xi
        )
        inside ^= cond
        j = i
    return inside


def sample_csr(n: int, hull: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """N uniform points inside the hull (rejection in bbox), equal-area in km."""
    minx, miny = hull[:, 0].min(), hull[:, 1].min()
    maxx, maxy = hull[:, 0].max(), hull[:, 1].max()
    out = np.empty((0, 2))
    while len(out) < n:
        m = int((n - len(out)) * 1.8) + 16
        cand = np.column_stack([
            rng.uniform(minx, maxx, m),
            rng.uniform(miny, maxy, m),
        ])
        cand = cand[_points_in_poly(cand, hull)]
        out = np.vstack([out, cand])
    return out[:n]


# ----------------------------------------------------------------------------
# statistics (chunked, memory-safe for a few thousand points)
# ----------------------------------------------------------------------------

def mean_nn(points: np.ndarray, chunk: int = 512) -> float:
    """Mean nearest-neighbour distance (km), self excluded."""
    n = len(points)
    if n < 2:
        return float("nan")
    total = 0.0
    for s in range(0, n, chunk):
        block = points[s:s + chunk]
        d2 = ((block[:, None, :] - points[None, :, :]) ** 2).sum(-1)
        idx = np.arange(s, s + len(block))
        d2[np.arange(len(block)), idx] = np.inf
        total += np.sqrt(d2.min(1)).sum()
    return total / n


def k_counts(points: np.ndarray, radii: np.ndarray, chunk: int = 512) -> np.ndarray:
    """Sum over i of #{j != i : d_ij <= r} for each r. Returns len(radii)."""
    n = len(points)
    counts = np.zeros(len(radii))
    r2 = radii ** 2
    for s in range(0, n, chunk):
        block = points[s:s + chunk]
        d2 = ((block[:, None, :] - points[None, :, :]) ** 2).sum(-1)
        idx = np.arange(s, s + len(block))
        d2[np.arange(len(block)), idx] = np.inf
        for k, rr in enumerate(r2):
            counts[k] += (d2 <= rr).sum()
    return counts


def ripley_L(points: np.ndarray, radii: np.ndarray, area: float) -> np.ndarray:
    """L(r) - r  (centred). Zero under CSR; >0 clustered, <0 dispersed."""
    n = len(points)
    counts = k_counts(points, radii)
    K = area * counts / (n * (n - 1))
    L = np.sqrt(np.maximum(K, 0) / math.pi)
    return L - radii


# ----------------------------------------------------------------------------
# core analysis
# ----------------------------------------------------------------------------

def analyze(lat, lon, n_sims: int = 199, seed: int = 1337, n_radii: int = 8) -> dict:
    lat = np.asarray(lat, float)
    lon = np.asarray(lon, float)
    n = len(lat)
    if n < 30:
        return {"verdict": "UNDERDETERMINED",
                "reason": f"n={n} too small for a stable CSR null",
                "n": int(n)}

    xy, (lat0, lon0) = project_km(lat, lon)
    hull = convex_hull(xy)
    area = polygon_area(hull)
    if area <= 0:
        return {"verdict": "UNDERDETERMINED", "reason": "degenerate hull",
                "n": int(n)}

    span = math.sqrt(area)
    radii = np.linspace(span * 0.02, span * 0.25, n_radii)

    obs_nn = mean_nn(xy)
    obs_L = ripley_L(xy, radii, area)

    rng = np.random.default_rng(seed)
    sim_nn = np.empty(n_sims)
    sim_L = np.empty((n_sims, len(radii)))
    for i in range(n_sims):
        s = sample_csr(n, hull, rng)
        sim_nn[i] = mean_nn(s)
        sim_L[i] = ripley_L(s, radii, area)

    nn_mu, nn_sd = float(sim_nn.mean()), float(sim_nn.std(ddof=1))
    clark_evans_R = obs_nn / nn_mu
    nn_z = (obs_nn - nn_mu) / nn_sd if nn_sd > 0 else 0.0

    L_mu = sim_L.mean(0)
    L_sd = sim_L.std(0, ddof=1)
    L_z = np.where(L_sd > 0, (obs_L - L_mu) / L_sd, 0.0)
    # two-sided empirical envelope exceedance (CSR points that beat observed)
    L_hi = sim_L.max(0)
    L_lo = sim_L.min(0)
    outside = (obs_L > L_hi) | (obs_L < L_lo)

    # verdict logic -------------------------------------------------------
    clustered = clark_evans_R < 1 and nn_z <= -3
    dispersed = clark_evans_R > 1 and nn_z >= 3
    k_structure = bool(np.any(np.abs(L_z) >= 3) and np.any(outside))
    if clustered or dispersed or k_structure:
        verdict = "STRUCTURE_ONLY"
        kind = ("clustered" if clustered else
                "dispersed/regular" if dispersed else "K-structure")
    else:
        verdict = "NO_SIGNAL"
        kind = "indistinguishable from CSR"

    return {
        "verdict": verdict,
        "structure_kind": kind,
        "n": int(n),
        "study_mask": "convex hull of the point set (screening approximation "
                      "of the paper's basin window)",
        "projection": f"local equirectangular km about ({lat0:.3f},{lon0:.3f})",
        "hull_area_km2": round(area, 1),
        "clark_evans": {
            "obs_mean_nn_km": round(obs_nn, 4),
            "csr_mean_nn_km": round(nn_mu, 4),
            "csr_sd_km": round(nn_sd, 4),
            "R": round(clark_evans_R, 4),
            "z": round(nn_z, 3),
            "n_sims": n_sims,
        },
        "ripleyL": {
            "radii_km": [round(float(r), 3) for r in radii],
            "obs_L_minus_r": [round(float(v), 4) for v in obs_L],
            "csr_mean": [round(float(v), 4) for v in L_mu],
            "z": [round(float(v), 3) for v in L_z],
            "outside_envelope": [bool(v) for v in outside],
            "n_sims": n_sims,
        },
        "caveats": [
            "CSR window = convex hull, not the paper's true basin polygon; "
            "this inflates apparent clustering slightly near the boundary.",
            "Equirectangular km projection over a wide latitude band is a "
            "screening approximation (area distortion at the edges).",
            "STRUCTURE_ONLY means spatial clustering exists; it does NOT imply "
            "intent, message, geometry-by-design, or any 'civilisation' claim.",
        ],
    }


# ----------------------------------------------------------------------------
# IO
# ----------------------------------------------------------------------------

def load_csv(path: str):
    lat, lon, typ = [], [], []
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                la = float(row.get("lat") or row.get("Latitude"))
                lo = float(row.get("lon") or row.get("Longitude"))
            except (TypeError, ValueError):
                continue
            lat.append(la); lon.append(lo)
            typ.append((row.get("type") or row.get("Database") or "").strip())
    return np.array(lat), np.array(lon), typ


def _demo():
    """Self-contained sanity run: a planted cluster must read STRUCTURE_ONLY."""
    rng = np.random.default_rng(0)
    lat = np.concatenate([rng.normal(-10, 0.3, 200), rng.normal(-9, 0.25, 200)])
    lon = np.concatenate([rng.normal(-67, 0.3, 200), rng.normal(-66, 0.25, 200)])
    print(json.dumps(analyze(lat, lon, n_sims=99), indent=2))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", help="input coords csv (lat,lon[,type])")
    ap.add_argument("--out", default="outputs/amazon/run.json")
    ap.add_argument("--n-sims", type=int, default=199)
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--label", default="zenodo_peripato")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()

    if a.demo or not a.csv:
        _demo(); return

    lat, lon, typ = load_csv(a.csv)
    res = analyze(lat, lon, n_sims=a.n_sims, seed=a.seed)
    res["source_label"] = a.label
    res["source_csv"] = os.path.basename(a.csv)
    res["generated_utc"] = datetime.now(timezone.utc).isoformat()
    # type-stratified counts (structure != meaning; just describe the mix)
    from collections import Counter
    res["type_counts"] = dict(Counter(t for t in typ if t))
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w") as fh:
        json.dump(res, fh, indent=2)
    print(json.dumps({k: res[k] for k in ("verdict", "structure_kind", "n",
          "clark_evans")}, indent=2))
    print("wrote", a.out)


if __name__ == "__main__":
    main()
