"""
spatial_pattern.py — reusable spatial point-pattern analysis ("beyond wheat").

The EAMENA ley-line FPR probe generalises to any spatial point set: archaeological
sites, megaliths, geoglyphs, star maps, crop formations. This module packages the
analysis pipeline for reuse — Clark-Evans nearest-neighbour screening, collinear
triple ("ley line") detection, and false-positive rate (FPR) calibration against
CSR (Complete Spatial Randomness) and scrambled-coordinate nulls.

Metrics:
  1. haversine_km      — great-circle distance
  2. perpendicular_distance_km — collinearity check (local Cartesian)
  3. mean_nn_km        — mean nearest-neighbour distance
  4. clark_evans_analysis — Clark-Evans R statistic with MC CSR null
  5. count_collinear_triples — collinear triple detection
  6. ley_line_fpr_analysis — FPR under scrambled-coord + CSR nulls
  7. generate_synthetic_csr — synthetic point cloud for calibration

Pure standard library. Validated in tools/ccat/tests/test_spatial_pattern.py.

CAVEAT: "ley line" collinearity above CSR baseline is NECESSARY for intentional
alignment but NOT SUFFICIENT — spatial clustering from environmental covariates
(rivers, soils, topography) produces collinear triples at rates far above naive
CSR. Always run an inhomogeneous Poisson (Cox process) null for real data.
"""

from __future__ import annotations

import math
import random as rnd

DEG = math.pi / 180.0
KM_PER_DEG_LAT = 110.574

N_SIMS_DEFAULT = 199
N_TRIPLES_DEFAULT = 2000
TOLERANCE_KM_DEFAULT = 0.5


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance (km) between two lon/lat points."""
    phi1, phi2 = lat1 * DEG, lat2 * DEG
    dphi = (lat2 - lat1) * DEG
    dlambda = (lon2 - lon1) * DEG
    a = (math.sin(dphi / 2.0) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2)
    return 2.0 * 6371.0 * math.asin(min(1.0, math.sqrt(a)))


def perpendicular_distance_km(
    lat0: float, lon0: float,
    lat1: float, lon1: float,
    lat2: float, lon2: float,
) -> float:
    """Perpendicular distance (km) from point (lat0,lon0) to the great-circle
    line through (lat1,lon1)-(lat2,lon2). Uses equirectangular projection
    (cos(lat) scaling) to local Cartesian km — accurate for distances < 50 km.
    """
    cm = math.cos(math.radians((lat0 + lat1 + lat2) / 3.0))
    km_per_lon = 111.320 * cm
    x0, y0 = lon0 * km_per_lon, lat0 * KM_PER_DEG_LAT
    x1, y1 = lon1 * km_per_lon, lat1 * KM_PER_DEG_LAT
    x2, y2 = lon2 * km_per_lon, lat2 * KM_PER_DEG_LAT
    dx = x2 - x1
    dy = y2 - y1
    if abs(dx) < 1e-12 and abs(dy) < 1e-12:
        return haversine_km(lat0, lon0, lat1, lon1)
    return abs(dy * x0 - dx * y0 + x2 * y1 - y2 * x1) / math.hypot(dx, dy)


# ---------------------------------------------------------------------------
# Nearest-neighbour (Clark-Evans)
# ---------------------------------------------------------------------------

def mean_nn_km(coords: list[tuple[float, float]]) -> float:
    """Mean nearest-neighbour distance (km) for a list of (lat, lon) tuples."""
    n = len(coords)
    if n < 2:
        return float("nan")
    total = 0.0
    for i, (lat1, lon1) in enumerate(coords):
        best = float("inf")
        for j, (lat2, lon2) in enumerate(coords):
            if i == j:
                continue
            d = haversine_km(lat1, lon1, lat2, lon2)
            if d < best:
                best = d
        total += best
    return total / n


def clark_evans_analysis(
    coords: list[tuple[float, float]],
    n_sims: int = N_SIMS_DEFAULT,
    seed: int = 0,
) -> dict:
    """Clark-Evans nearest-neighbour ratio R = obs_mean_NN / expected_NN_CSR.

    Returns dict with observed, null mean, R, and z-score. Negative z indicates
    clustering; positive z indicates dispersion/regularity.
    """
    n = len(coords)
    obs_nn = mean_nn_km(coords)

    # Approximate area in km²
    bbox = _bbox_from_coords(coords)
    mid_lat = (bbox[1] + bbox[3]) / 2.0
    km_per_lon = 111.320 * math.cos(math.radians(mid_lat))
    area_km2 = (bbox[2] - bbox[0]) * km_per_lon * (bbox[3] - bbox[1]) * KM_PER_DEG_LAT
    density = n / area_km2 if area_km2 > 0 else 0
    expected_nn_csr = 0.5 / math.sqrt(density) if density > 0 else float("nan")

    # Monte Carlo CSR null
    rng = rnd.Random(seed)
    sim_nns = []
    for _ in range(n_sims):
        sim = [(rng.uniform(bbox[1], bbox[3]), rng.uniform(bbox[0], bbox[2]))
               for _ in range(n)]
        sim_nns.append(mean_nn_km(sim))

    mu = sum(sim_nns) / len(sim_nns)
    var = sum((s - mu) ** 2 for s in sim_nns) / max(1, len(sim_nns))
    sd = math.sqrt(var) if var > 0 else 1e-12
    z = (obs_nn - mu) / sd
    R = obs_nn / mu if mu > 0 else float("nan")

    return {
        "n": n,
        "area_km2_approx": round(area_km2, 1),
        "density_sites_per_km2": round(density, 6),
        "obs_mean_nn_km": round(obs_nn, 4),
        "expected_nn_csr_formula_km": round(expected_nn_csr, 4),
        "csr_null_mean_km": round(mu, 4),
        "csr_null_sd_km": round(sd, 4),
        "clark_evans_R": round(R, 4),
        "z_vs_csr": round(z, 3),
        "n_sims": n_sims,
    }


# ---------------------------------------------------------------------------
# Collinear triple ("ley line") detection
# ---------------------------------------------------------------------------

def count_collinear_triples(
    coords: list[tuple[float, float]],
    tolerance_km: float = TOLERANCE_KM_DEFAULT,
    n_triple_samples: int = N_TRIPLES_DEFAULT,
    seed: int = 0,
) -> dict:
    """Count points collinear with sampled pairs within *tolerance_km*.

    For performance, evaluates a random sample of pairs (i,j) and counts how
    many other points k fall within the tolerance corridor. Each collinear
    triple (i,j,k) is counted **3×** (once per constituent pair). This is
    internally consistent between observed and null statistics, so it cancels
    in the FPR.

    Returns a dict with counts, rate, and tolerance metadata.
    """
    n = len(coords)
    if n < 3:
        return {"pairs_evaluated": 0, "collinear_triples_per_pair": 0.0,
                "total_collinear_triple_instances": 0, "note": "n < 3"}

    rng = rnd.Random(seed)
    all_indices = list(range(n))
    n_pairs_eval = min(n_triple_samples, n * (n - 1) // 2)
    pairs = []
    for _ in range(n_pairs_eval):
        i, j = rng.sample(all_indices, 2)
        pairs.append((i, j))

    collinear_count = 0
    total_evaluated = 0
    for i, j in pairs:
        lat1, lon1 = coords[i]
        lat2, lon2 = coords[j]
        if haversine_km(lat1, lon1, lat2, lon2) < 0.1:
            continue  # skip near-identical points
        for k in range(n):
            if k == i or k == j:
                continue
            if perpendicular_distance_km(coords[k][0], coords[k][1],
                                          lat1, lon1, lat2, lon2) <= tolerance_km:
                collinear_count += 1
        total_evaluated += 1

    return {
        "n_sites": n,
        "pairs_evaluated": total_evaluated,
        "total_collinear_triple_instances": collinear_count,
        "collinear_triples_per_pair": round(
            collinear_count / max(1, total_evaluated), 6),
        "tolerance_km": tolerance_km,
        "max_triples_sampled": n_triple_samples,
    }


def ley_line_fpr_analysis(
    coords: list[tuple[float, float]],
    n_sims: int = N_SIMS_DEFAULT,
    n_triple_samples: int = N_TRIPLES_DEFAULT,
    tolerance_km: float = TOLERANCE_KM_DEFAULT,
    seed: int = 0,
) -> dict:
    """False-positive rate (FPR) of collinear triple detection under two nulls:

    1. **Scrambled-coordinate null** — permute lon/lat independently.
    2. **CSR Monte-Carlo null** — draw N uniform points in the bounding box.

    Returns dict with observed rate, null statistics, z-scores, and empirical
    FPR for each null. If FPR < 0.05, the observed collinearity exceeds the
    null expectation.
    """
    n = len(coords)
    if n < 3:
        return {"verdict": "UNDERDETERMINED", "n": n}

    bbox = _bbox_from_coords(coords)

    # Observed
    obs = count_collinear_triples(coords, tolerance_km=tolerance_km,
                                   n_triple_samples=n_triple_samples, seed=seed)
    obs_rate = obs["collinear_triples_per_pair"]

    # Scrambled-coordinate null
    rng = rnd.Random(seed + 1)
    scrambled_rates = []
    for s in range(n_sims):
        lats = [c[0] for c in coords]
        lons = [c[1] for c in coords]
        rng.shuffle(lats)
        rng.shuffle(lons)
        scrambled = list(zip(lats, lons))
        sc = count_collinear_triples(scrambled, tolerance_km=tolerance_km,
                                      n_triple_samples=n_triple_samples,
                                      seed=seed + s + 100)
        scrambled_rates.append(sc["collinear_triples_per_pair"])

    sc_mu = sum(scrambled_rates) / len(scrambled_rates)
    sc_var = sum((s - sc_mu) ** 2 for s in scrambled_rates) / max(1, len(scrambled_rates))
    sc_sd = math.sqrt(sc_var) if sc_var > 0 else 1e-12
    sc_z = (obs_rate - sc_mu) / sc_sd
    sc_fpr = sum(1 for s in scrambled_rates if s >= obs_rate) / n_sims

    # CSR Monte-Carlo null
    csr_rates = []
    for s in range(n_sims):
        csr = [(rng.uniform(bbox[1], bbox[3]), rng.uniform(bbox[0], bbox[2]))
               for _ in range(n)]
        cc = count_collinear_triples(csr, tolerance_km=tolerance_km,
                                      n_triple_samples=n_triple_samples,
                                      seed=seed + s + 200)
        csr_rates.append(cc["collinear_triples_per_pair"])

    csr_mu = sum(csr_rates) / len(csr_rates)
    csr_var = sum((s - csr_mu) ** 2 for s in csr_rates) / max(1, len(csr_rates))
    csr_sd = math.sqrt(csr_var) if csr_var > 0 else 1e-12
    csr_z = (obs_rate - csr_mu) / csr_sd
    csr_fpr = sum(1 for s in csr_rates if s >= obs_rate) / n_sims

    return {
        "n_sites": n,
        "tolerance_km": tolerance_km,
        "pairs_evaluated": obs["pairs_evaluated"],
        "observed": {
            "collinear_triples_per_pair": obs_rate,
            "total_collinear_instances": obs["total_collinear_triple_instances"],
        },
        "null_scrambled_coord": {
            "mean_per_pair": round(sc_mu, 6),
            "sd_per_pair": round(sc_sd, 6),
            "z": round(sc_z, 3),
            "fpr_empirical": round(sc_fpr, 4),
            "n_sims": n_sims,
        },
        "null_csr": {
            "mean_per_pair": round(csr_mu, 6),
            "sd_per_pair": round(csr_sd, 6),
            "z": round(csr_z, 3),
            "fpr_empirical": round(csr_fpr, 4),
            "n_sims": n_sims,
        },
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bbox_from_coords(
    coords: list[tuple[float, float]],
) -> tuple[float, float, float, float]:
    """(lon_min, lat_min, lon_max, lat_max) for a list of (lat, lon) tuples."""
    return (
        min(c[1] for c in coords), min(c[0] for c in coords),
        max(c[1] for c in coords), max(c[0] for c in coords),
    )


def generate_synthetic_csr(
    n: int = 500,
    bbox: tuple[float, float, float, float] = (34.0, 30.0, 35.5, 32.5),
    seed: int = 0,
) -> tuple[list[tuple[float, float]], dict]:
    """Generate N random points uniformly within bounding box (CSR).

    Returns (coords, metadata) where coords is a list of (lat, lon) tuples
    and metadata contains n_sites, distribution, bbox, and generator info.
    """
    rng = rnd.Random(seed)
    coords = [(rng.uniform(bbox[1], bbox[3]), rng.uniform(bbox[0], bbox[2]))
              for _ in range(n)]
    return coords, {
        "n_sites": n,
        "distribution": "csr",
        "bbox": list(bbox),
        "generator": f"synthetic CSR, seed={seed}",
    }


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    # Self-contained sanity run: planted cluster must register as clustered.
    rng = rnd.Random(0)
    # Planted cluster: 50 points in a tight region
    clustered = [(30.0 + rng.gauss(0, 0.01), 35.0 + rng.gauss(0, 0.01))
                  for _ in range(50)]
    # 50 uniform points
    uniform, _ = generate_synthetic_csr(n=50, seed=1)

    print("=== Clark-Evans: planted cluster ===")
    ce = clark_evans_analysis(clustered, n_sims=49)
    print(json.dumps({k: ce[k] for k in ("clark_evans_R", "z_vs_csr",
          "density_sites_per_km2")}, indent=2))

    print("\n=== Clark-Evans: uniform CSR ===")
    ce2 = clark_evans_analysis(uniform, n_sims=49)
    print(json.dumps({k: ce2[k] for k in ("clark_evans_R", "z_vs_csr")}, indent=2))

    print("\n=== Ley-line FPR: clustered data ===")
    fpr = ley_line_fpr_analysis(clustered, n_sims=29, n_triple_samples=200)
    print(f"  observed collinear per pair: {fpr['observed']['collinear_triples_per_pair']}")
    print(f"  scrambled FPR: {fpr['null_scrambled_coord']['fpr_empirical']}")
    print(f"  CSR FPR:       {fpr['null_csr']['fpr_empirical']}\n")
    print("(Clustered data should beat both nulls -> low FPR)")
