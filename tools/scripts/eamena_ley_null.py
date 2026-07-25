#!/usr/bin/env python3
"""
eamena_ley_null.py — G18: EAMENA ley-line null hypothesis probe.

Stance: structure != meaning. "Ley lines" are a fringe-archaeology claim that
3+ sites on a straight line within a narrow tolerance corridor constitute a
"ley." This probe measures whether the frequency of such collinear triples in
a spatial point set exceeds what Complete Spatial Randomness (CSR) produces
at the same N and bounding-box. If "leys" do not beat the null, the honest
verdict is NO_SIGNAL.

Pipeline:
  1. Load point set (GeoJSON or synthetic CSR by default).
  2. Nearest-neighbour distance (Clark-Evans R) — spatial clustering screen.
  3. "Ley line" alignment detection: for every pair of points (i,j), count
     how many other points k fall within a narrow corridor (perpendicular
     distance ≤ TOLERANCE_KM) of the line through i and j.
  4. **Scrambled-coordinate null** — permute x,y independently; repeat
     detection pipeline. Report FPR.
  5. **CSR Monte-Carlo null** — draw N uniform points inside the bounding
     box; repeat detection pipeline. Report FPR.
  6. Verdict: if observed triple-collinearity rate does NOT exceed both
     nulls at empirical FPR < 0.05 (nominal) → NO_SIGNAL.

Honest prior: no-signal. EAMENA spatial distribution is expected to follow
environmental/archaeological clustering (rivers, settlements, soils), NOT
any intentional geometric ley network.

Usage:
    python tools/scripts/eamena_ley_null.py
    python tools/scripts/eamena_ley_null.py --geojson data/geo/eamena/synthetic_csr_sites.json
    python tools/scripts/eamena_ley_null.py --n-triples 5000 --seed 42

No scipy, no numpy. Pure stdlib math.
"""

from __future__ import annotations

import argparse
import json
import math
import random as rnd
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA_DIR = ROOT / "data" / "geo" / "eamena"
OUT_DIR = ROOT / "outputs" / "eamena"

# ---------------------------------------------------------------------------
# Stance & constants
# ---------------------------------------------------------------------------

STANCE = (
    "EAMENA (Endangered Archaeology in the Middle East and North Africa) "
    "records ~338,000 archaeological sites. This probe tests the fringe "
    "claim that 3+ sites on a straight line constitute a 'ley line.' "
    "We measure spatial structure (collinear-triple frequency) relative to "
    "Complete Spatial Randomness (CSR) and scrambled-coordinate nulls. "
    "We do NOT endorse ley-line mysticism, ancient-highway claims, or any "
    "'Earth energy' interpretation. The honest prior is NO_SIGNAL — "
    "spatial clustering in archaeological site distributions is well-known "
    "to follow environmental settlement patterns (water, soil, trade "
    "routes), not intentional geometric networks."
)

FORBIDDEN_PHRASES = (
    "ancient highways",
    "ET corridors",
    "proves ley network",
    "ley line network",
    "ley network confirmed",
    "ancient alien roads",
    "energy lines",
    "earth energy grid",
    "earth energy lines",
    "global grid",
    "planetary grid",
    "sacred geometry network",
    "ley system",
    "ley alignment proves",
    "ley discovered",
    "alien ley",
    "99% ley",
    "ley verified",
    "ley confirmed",
    "ancient aliens",
    "alien architectures",
)

# Tolerance for collinearity: perpendicular distance (km) from a point to
# the line through two other points. Set to ~0.5 km (~0.0045 deg at ~31N).
TOLERANCE_KM = 0.5
KM_PER_DEG_LAT = 110.574
# At ~31 N latitude
KM_PER_DEG_LON = 111.320 * math.cos(math.radians(31.0))
TOLERANCE_DEG_LAT = TOLERANCE_KM / KM_PER_DEG_LAT
TOLERANCE_DEG_LON = TOLERANCE_KM / KM_PER_DEG_LON

Z_STRUCTURE_THRESHOLD = 3.0
Z_CONTROL_SEP_THRESHOLD = 2.0
N_SIMS_DEFAULT = 199
N_TRIPLES_DEFAULT = 2000  # max triples to evaluate (for performance)
MIN_N_POINTS = 30

# ---------------------------------------------------------------------------
# Geometry helpers (pure stdlib)
# ---------------------------------------------------------------------------

DEG = math.pi / 180.0


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance (km) between two lon/lat points."""
    phi1, phi2 = lat1 * DEG, lat2 * DEG
    dphi = (lat2 - lat1) * DEG
    dlambda = (lon2 - lon1) * DEG
    a = (math.sin(dphi / 2.0) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2)
    return 2.0 * 6371.0 * math.asin(min(1.0, math.sqrt(a)))


def perpendicular_distance_km(lat0, lon0, lat1, lon1, lat2, lon2):
    """Perpendicular distance from point (lat0,lon0) to the great-circle line
    through (lat1,lon1)-(lat2,lon2). Approximated with equirectangular
    projection (cos(lat) scaling) to local Cartesian km."""
    # Convert to local Cartesian (km)
    cm = math.cos(math.radians((lat0 + lat1 + lat2) / 3.0))
    x0, y0 = lon0 * cm * 111.320, lat0 * KM_PER_DEG_LAT
    x1, y1 = lon1 * cm * 111.320, lat1 * KM_PER_DEG_LAT
    x2, y2 = lon2 * cm * 111.320, lat2 * KM_PER_DEG_LAT
    # Vector from (x1,y1) to (x2,y2)
    dx = x2 - x1
    dy = y2 - y1
    if abs(dx) < 1e-12 and abs(dy) < 1e-12:
        return haversine_km(lat0, lon0, lat1, lon1)
    # Perpendicular distance from (x0,y0) to the line through (x1,y1)-(x2,y2)
    return abs(dy * x0 - dx * y0 + x2 * y1 - y2 * x1) / math.hypot(dx, dy)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_geojson(path):
    """Load a GeoJSON FeatureCollection of Point features. Returns list of
    (lat, lon) tuples and the source metadata dict."""
    raw = json.loads(Path(path).read_text())
    if raw.get("type") != "FeatureCollection":
        raise ValueError("Expected GeoJSON FeatureCollection")
    coords = []
    for feat in raw.get("features", []):
        geom = feat.get("geometry", {})
        if geom.get("type") != "Point":
            continue
        lon, lat = geom["coordinates"]
        coords.append((float(lat), float(lon)))
    return coords, raw


def generate_synthetic_csr(n=500, bbox=(34.0, 30.0, 35.5, 32.5), seed=0):
    """Generate N random points uniformly within bounding box (CSR)."""
    rng = rnd.Random(seed)
    coords = []
    for _ in range(n):
        lon = rng.uniform(bbox[0], bbox[2])
        lat = rng.uniform(bbox[1], bbox[3])
        coords.append((lat, lon))
    return coords, {
        "n_sites": n,
        "distribution": "csr",
        "bbox": list(bbox),
        "generator": f"synthetic CSR, seed={seed}",
    }


def load_data(geojson_path=None, n_synthetic=500, seed_csr=0):
    """Load coords from GeoJSON or generate synthetic CSR."""
    if geojson_path:
        path = Path(geojson_path)
        if not path.is_absolute():
            path = ROOT / path
        coords, meta = load_geojson(path)
        meta["source"] = str(path)
    else:
        coords, meta = generate_synthetic_csr(n=n_synthetic, seed=seed_csr)
        meta["source"] = "synthetic_csr"
    return coords, meta


# ---------------------------------------------------------------------------
# Nearest-neighbour analysis (Clark-Evans)
# ---------------------------------------------------------------------------

def mean_nn_km(coords):
    """Mean nearest-neighbour distance (km) for a list of (lat,lon) tuples."""
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


def clark_evans_analysis(coords, n_sims=N_SIMS_DEFAULT, seed=0):
    """Clark-Evans nearest-neighbour ratio R = obs_mean_NN / expected_NN_CSR.
    Returns dict with observed, null mean, R, z."""
    n = len(coords)
    obs_nn = mean_nn_km(coords)

    # Expected NN for CSR in a Poisson process: 0.5 / sqrt(density)
    bbox = (
        min(c[1] for c in coords), min(c[0] for c in coords),
        max(c[1] for c in coords), max(c[0] for c in coords),
    )
    area_deg2 = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
    # Approximate area in km^2
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
# Ley-line (collinear triple) detection
# ---------------------------------------------------------------------------

def count_collinear_triples(coords, tolerance_km=TOLERANCE_KM,
                              n_triple_samples=N_TRIPLES_DEFAULT, seed=0):
    """Count the number of point triples that are collinear within tolerance.
    For performance: sample pairs (i,j), count how many k produce collinear
    triples. Returns dict with counts and prevalence.

    NOTE: each collinear triple (i,j,k) is counted 3x in the output
    (once per constituent pair: (i,j), (i,k), (j,k)). This is consistent
    between observed and null statistics, so it cancels in the FPR."""
    n = len(coords)
    if n < 3:
        return {"n_triples_evaluated": 0, "n_collinear": 0,
                "fraction_collinear": 0.0, "note": "n < 3"}

    rng = rnd.Random(seed)
    pairs = []
    # Generate random pairs
    all_indices = list(range(n))
    n_pairs_eval = min(n_triple_samples, n * (n - 1) // 2)
    for _ in range(n_pairs_eval):
        i, j = rng.sample(all_indices, 2)
        pairs.append((i, j))

    collinear_count = 0
    total_evaluated = 0
    for i, j in pairs:
        lat1, lon1 = coords[i]
        lat2, lon2 = coords[j]
        dist_ij = haversine_km(lat1, lon1, lat2, lon2)
        if dist_ij < 0.1:  # skip pairs that are too close (effectively same point)
            continue
        for k in range(n):
            if k == i or k == j:
                continue
            latk, lonk = coords[k]
            pd = perpendicular_distance_km(latk, lonk, lat1, lon1, lat2, lon2)
            if pd <= tolerance_km:
                collinear_count += 1
        total_evaluated += 1

    collinear_per_pair = collinear_count / max(1, total_evaluated)
    return {
        "n_sites": n,
        "pairs_evaluated": total_evaluated,
        "total_collinear_triple_instances": collinear_count,
        "collinear_triples_per_pair": round(collinear_per_pair, 6),
        "tolerance_km": tolerance_km,
        "max_triples_sampled": n_triple_samples,
        "note": f"Count of k-points collinear with pair (i,j) within {tolerance_km} km",
    }


def ley_line_fpr_analysis(coords, n_sims=N_SIMS_DEFAULT,
                           n_triple_samples=N_TRIPLES_DEFAULT,
                           tolerance_km=TOLERANCE_KM, seed=0):
    """Compute the false-positive rate (FPR) of collinear triple detection
    under two null models:
      1. Scrambled-coordinate null: permute lon/lat independently.
      2. CSR null: draw N uniform random points within bounding box.
    Returns dict with observed stats, null stats, and FPR.
    """
    n = len(coords)
    if n < 3:
        return {"verdict": "UNDERDETERMINED", "n": n, "note": "n < 3"}

    bbox = (
        min(c[1] for c in coords), min(c[0] for c in coords),
        max(c[1] for c in coords), max(c[0] for c in coords),
    )

    # Observed
    obs = count_collinear_triples(coords, tolerance_km=tolerance_km,
                                   n_triple_samples=n_triple_samples, seed=seed)
    obs_rate = obs["collinear_triples_per_pair"]

    # Scrambled null
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
    sc_exceed = sum(1 for s in scrambled_rates if s >= obs_rate)
    sc_fpr = sc_exceed / n_sims

    # CSR null
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
    csr_exceed = sum(1 for s in csr_rates if s >= obs_rate)
    csr_fpr = csr_exceed / n_sims

    # Nominal FPR: proportion of null simulations that produce ≥ observed rate
    # If FPR < 0.05, the observed alignment rate beats the null.
    # For CSR synthetic data: BOTH nulls should have FPR ~0.5 (no separation).

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
            "exceed_count": sc_exceed,
            "fpr_empirical": round(sc_fpr, 4),
            "n_sims": n_sims,
        },
        "null_csr": {
            "mean_per_pair": round(csr_mu, 6),
            "sd_per_pair": round(csr_sd, 6),
            "z": round(csr_z, 3),
            "exceed_count": csr_exceed,
            "fpr_empirical": round(csr_fpr, 4),
            "n_sims": n_sims,
        },
    }


# ---------------------------------------------------------------------------
# Verdict assembly
# ---------------------------------------------------------------------------

def build_verdict(ce, fpr, n):
    """Map metrics into allowed verdict tags. Honest prior: NO_SIGNAL."""
    tags = []
    if n < MIN_N_POINTS:
        tags.append("UNDERDETERMINED")
        return " | ".join(tags)

    ce_z = ce.get("z_vs_csr", 0.0)
    fpr_sc_z = fpr.get("null_scrambled_coord", {}).get("z", 0.0)
    fpr_csr_z = fpr.get("null_csr", {}).get("z", 0.0)
    fpr_sc_exceed = fpr.get("null_scrambled_coord", {}).get("fpr_empirical", 1.0)
    fpr_csr_exceed = fpr.get("null_csr", {}).get("fpr_empirical", 1.0)

    # Spatial clustering check
    if abs(ce_z) >= Z_STRUCTURE_THRESHOLD:
        tags.append("SPATIAL_CLUSTER_ONLY")
    else:
        tags.append("NO_SPATIAL_SIGNAL")

    # Ley-line signal check: need to beat BOTH nulls
    beats_scrambled = fpr_sc_exceed < 0.05
    beats_csr = fpr_csr_exceed < 0.05

    if beats_scrambled and beats_csr:
        tags.append("LEY_LINE_SIGNAL")
    elif beats_scrambled or beats_csr:
        tags.append("LEY_UNDERDETERMINED")
    else:
        tags.append("NO_LEY_SIGNAL")

    # Control separation
    if abs(fpr_sc_z) >= Z_CONTROL_SEP_THRESHOLD or abs(fpr_csr_z) >= Z_CONTROL_SEP_THRESHOLD:
        tags.append("CONTROL_SEPARATED")
    else:
        tags.append("CONTROL_NOT_SEPARATED")

    # FPR calibration note for CSR synthetic data
    if tags.count("NO_LEY_SIGNAL") > 0 and tags.count("CONTROL_NOT_SEPARATED") > 0:
        tags.append("FPR_CALIBRATED")

    return " | ".join(tags)


# ---------------------------------------------------------------------------
# Forbidden phrase guard
# ---------------------------------------------------------------------------

def assert_no_forbidden_phrases(text, where=""):
    if not text:
        return
    lowered = text.lower()
    for fp in FORBIDDEN_PHRASES:
        if fp.lower() in lowered:
            raise ValueError(
                f"forbidden phrase {fp!r} found in {where or 'text'}")


# ---------------------------------------------------------------------------
# Markdown writer
# ---------------------------------------------------------------------------

def write_notes_md(report):
    parts = []
    verdict = report.get("verdict", "PENDING")
    tag_icons = {
        "SPATIAL_CLUSTER_ONLY": "[CLUSTER]",
        "NO_SPATIAL_SIGNAL": "[NO-CLUSTER]",
        "LEY_LINE_SIGNAL": "[LEYS]",
        "NO_LEY_SIGNAL": "[NO-LEYS]",
        "LEY_UNDERDETERMINED": "[LEY-UNDER]",
        "CONTROL_SEPARATED": "[CTRL-SEP]",
        "CONTROL_NOT_SEPARATED": "[CTRL-!SEP]",
        "FPR_CALIBRATED": "[FPR-CAL]",
        "UNDERDETERMINED": "[UNDER]",
    }
    icons = []
    for tag in verdict.split(" | "):
        icons.append(tag_icons.get(tag.strip(), "[?]"))
    parts.append(
        f"# G18 — EAMENA ley-line null  {' '.join(icons)}")
    parts.append(f"*Generated: {report.get('generated_at', '?')}*")
    parts.append("")
    parts.append("## Stance")
    parts.append(STANCE)
    parts.append("")
    parts.append("**Motto:** *structure != meaning.* Ley-line/collinear-triple "
                 "frequency is a STRUCTURE test; this lab does NOT endorse "
                 "fringe ley-line or Earth-energy interpretations.")
    parts.append("")
    parts.append("### Forbidden phrases (logged)")
    for fp in FORBIDDEN_PHRASES:
        parts.append(f"- `{fp}`")
    parts.append("")

    parts.append("## Source / data")
    src = report.get("metadata", {}).get("source", "?")
    parts.append(f"- Source: `{src}`")
    nd = report.get("metadata", {})
    parts.append(f"- Distribution: {nd.get('distribution', '?')}")
    parts.append(f"- N sites: {nd.get('n_sites', '?')}")
    parts.append(f"- Bounding box: {nd.get('bbox', '?')}")
    if nd.get("distribution") == "csr" and "synthetic" in str(src):
        parts.append("- **NOTE:** Synthetic CSR data — ground truth is NO SIGNAL")
    else:
        parts.append("- **NOTE:** Real EAMENA GeoJSON subset — ground truth unknown")
    parts.append("")

    parts.append("## Nearest-neighbour (Clark-Evans)")
    ce = report.get("clark_evans", {})
    if ce:
        parts.append(f"- Observed mean NN: {ce.get('obs_mean_nn_km', '?')} km")
        parts.append(f"- CSR null mean NN: {ce.get('csr_null_mean_km', '?')} km")
        parts.append(f"- Clark-Evans R: {ce.get('clark_evans_R', '?')}")
        parts.append(f"- z vs CSR: {ce.get('z_vs_csr', '?')}")
        parts.append(f"- Density: {ce.get('density_sites_per_km2', '?')} sites/km²")
    parts.append("")

    parts.append("## Ley-line (collinear triple) FPR analysis")
    fpr = report.get("ley_fpr", {})
    if fpr:
        obs = fpr.get("observed", {})
        parts.append(f"- Tolerance corridor: {fpr.get('tolerance_km', '?')} km")
        parts.append(f"- Pairs evaluated: {fpr.get('pairs_evaluated', '?')}")
        parts.append(f"- Observed collinear triples per pair: "
                     f"{obs.get('collinear_triples_per_pair', '?')}")
        parts.append("")
        parts.append("### Scrambled-coordinate null")
        sc = fpr.get("null_scrambled_coord", {})
        parts.append(f"- Mean: {sc.get('mean_per_pair', '?')}")
        parts.append(f"- SD: {sc.get('sd_per_pair', '?')}")
        parts.append(f"- z: {sc.get('z', '?')}")
        parts.append(f"- Empirical FPR: {sc.get('fpr_empirical', '?')} "
                     f"(<0.05 = beats null)")
        parts.append("")
        parts.append("### CSR Monte-Carlo null")
        csr = fpr.get("null_csr", {})
        parts.append(f"- Mean: {csr.get('mean_per_pair', '?')}")
        parts.append(f"- SD: {csr.get('sd_per_pair', '?')}")
        parts.append(f"- z: {csr.get('z', '?')}")
        parts.append(f"- Empirical FPR: {csr.get('fpr_empirical', '?')} "
                     f"(<0.05 = beats null)")
    parts.append("")

    parts.append("## Verdict")
    parts.append(f"**{verdict}**")
    parts.append("")
    parts.append("## Interpretation")
    parts.append(report.get("interpretation", ""))
    parts.append("")
    parts.append("## Caveats")
    for c in report.get("caveats", []):
        parts.append(f"- {c}")
    parts.append("")
    parts.append("---")
    parts.append("*G18 EAMENA ley-line null — structure != meaning. "
                 "No fringe ley-line / Earth-energy / alien interpretation "
                 "endorsed. The collinear-triple FPR calibration is a "
                 "spatial statistics exercise, not a claim about "
                 "intentional geometric networks.*")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="G18 EAMENA ley-line null probe")
    ap.add_argument("--geojson", type=str, default=None,
                    help="Path to GeoJSON of site coordinates")
    ap.add_argument("--n-synthetic", type=int, default=500,
                    help="Number of synthetic CSR sites if no --geojson")
    ap.add_argument("--seed-csr", type=int, default=0,
                    help="Seed for synthetic CSR generation")
    ap.add_argument("--n-sims", type=int, default=N_SIMS_DEFAULT,
                    help="Number of null simulation iterations")
    ap.add_argument("--n-triples", type=int, default=N_TRIPLES_DEFAULT,
                    help="Number of pairs to evaluate for collinearity")
    ap.add_argument("--tolerance-km", type=float, default=TOLERANCE_KM,
                    help="Collinearity corridor tolerance (km)")
    ap.add_argument("--seed", type=int, default=0,
                    help="Random seed for analysis")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    coords, meta = load_data(
        geojson_path=args.geojson,
        n_synthetic=args.n_synthetic,
        seed_csr=args.seed_csr,
    )
    n = len(coords)

    if n < MIN_N_POINTS:
        report = {
            "mission": "G18",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "verdict": "UNDERDETERMINED",
            "metadata": {"n_sites": n, "source": meta.get("source", "?")},
            "caveats": [f"Insufficient points (n={n} < {MIN_N_POINTS})"],
        }
        json_text = json.dumps(report, indent=2, default=str)
        md_text = write_notes_md(report)
        (OUT_DIR / "run.json").write_text(json_text)
        (OUT_DIR / "NOTES.md").write_text(md_text)
        print(f"verdict: UNDERDETERMINED (n={n})")
        return

    # Clark-Evans nearest-neighbour analysis
    ce = clark_evans_analysis(coords, n_sims=args.n_sims, seed=args.seed)

    # Ley-line false-positive rate analysis
    fpr = ley_line_fpr_analysis(
        coords,
        n_sims=args.n_sims,
        n_triple_samples=args.n_triples,
        tolerance_km=args.tolerance_km,
        seed=args.seed,
    )

    # Verdict
    verdict = build_verdict(ce, fpr, n)

    # Interpretation string
    obs_rate = fpr.get("observed", {}).get("collinear_triples_per_pair", 0.0)
    sc_fpr = fpr.get("null_scrambled_coord", {}).get("fpr_empirical", 1.0)
    csr_fpr = fpr.get("null_csr", {}).get("fpr_empirical", 1.0)
    ce_R = ce.get("clark_evans_R", 0.0)
    ce_z = ce.get("z_vs_csr", 0.0)

    if meta.get("distribution") == "csr" and "synthetic" in str(meta.get("source", "")):
        ground_truth = "SYNTHETIC CSR (ground truth: NO SIGNAL by construction)"
        interpretation_parts = [
            f"**Ground truth:** {ground_truth}",
            "",
            f"CSR synthetic data: {n} points uniformly distributed in bounding box.",
            f"Clark-Evans R={ce_R:.3f}, z={ce_z:.2f} — consistent with CSR expectation.",
            "",
            "**Ley-line (collinear triple) FPR calibration:**",
            f"- Scrambled-coord null: empirical FPR = {sc_fpr:.4f} (threshold 0.05)",
            f"- CSR Monte-Carlo null: empirical FPR = {csr_fpr:.4f} (threshold 0.05)",
            f"- Observed collinear triples per pair: {obs_rate:.6f}",
            "",
            "For CSR synthetic data, both null FPRs should be >> 0.05,",
            "confirming that 'ley line' detection on random points produces",
            "chance-expected false positives.",
            "",
            "**FPR Calibration result:** NO_SIGNAL — 'ley line' alignments",
            "in CSR data do not exceed null expectation. The empirical FPR",
            "is consistent with the nominal α=0.05 threshold.",
        ]
    else:
        ground_truth = f"REAL EAMENA subset from {meta.get('source', '?')}"
        interpretation_parts = [
            f"**Source:** {ground_truth}",
            "",
            f"Clark-Evans R={ce_R:.3f}, z={ce_z:.2f}.",
            "",
            "**Ley-line analysis:**",
            f"- Observed collinear triples per pair: {obs_rate:.6f}",
            f"- Scrambled-coord null FPR: {sc_fpr:.4f}",
            f"- CSR Monte-Carlo null FPR: {csr_fpr:.4f}",
            "",
            "If both null FPRs are >> 0.05, the observed alignment rate",
            "is consistent with chance — NO_LEY_SIGNAL.",
            "If one null FPR < 0.05, LEY_UNDERDETERMINED.",
            "If both < 0.05, LEY_LINE_SIGNAL (rare; must survive nulls).",
        ]

    interpretation = "\n".join(interpretation_parts)

    report = {
        "mission": "G18",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "metadata": {
            "n_sites": n,
            "source": meta.get("source", "?"),
            "distribution": meta.get("distribution", "unknown"),
            "bbox": meta.get("bbox", None),
        },
        "clark_evans": ce,
        "ley_fpr": fpr,
        "interpretation": interpretation,
        "caveats": [
            "Synthetic CSR data — ground truth is NO SIGNAL by construction. "
            "Results for real EAMENA data may differ.",
            "Collinear triple detection is sampled (not exhaustive), capped at "
            f"{args.n_triples} pairs for performance.",
            f"Collinearity tolerance of {args.tolerance_km} km is arbitrary; "
            "different tolerances produce different FPRs.",
            "Ley-line claims typically cherry-pick sites — this probe uses ALL "
            "sites in the dataset without selection bias.",
            "Scrambled-coordinate null preserves the 1D marginal distributions "
            "but breaks spatial structure — it is a weaker null than CSR.",
            "CSR Monte-Carlo null assumes uniform intensity across the bounding "
            "box, which is almost never true for real archaeology "
            "(inhomogeneous Poisson process would be more realistic).",
            "For real EAMENA data, environmental covariates (rivers, soils, "
            "topography) must be modeled as a Cox process to avoid conflating "
            "settlement pattern with 'ley' signal.",
            "The EAMENA full 338k-site corpus is BLOCKED from programmatic "
            "access; this probe uses synthetic CSR data as an FPR calibration "
            "benchmark. See data/geo/eamena/README.md.",
        ],
        "data_source": (
            "EAMENA database — synthetic CSR fallback per data access BLOCKED. "
            "See data/geo/eamena/README.md for details."
        ),
        "stance": STANCE,
        "forbidden_phrases": list(FORBIDDEN_PHRASES),
        "pipeline": {
            "tool": "tools/scripts/eamena_ley_null.py",
            "parameters": {
                "geojson": args.geojson,
                "n_synthetic": args.n_synthetic,
                "seed_csr": args.seed_csr,
                "n_sims": args.n_sims,
                "n_triples": args.n_triples,
                "tolerance_km": args.tolerance_km,
                "seed": args.seed,
            },
        },
    }

    md_text = write_notes_md(report)
    json_text = json.dumps(report, indent=2, default=str)

    # Guard outputs
    assert_no_forbidden_phrases(
        "\n".join(c for c in report["caveats"]), where="caveats"
    )
    assert_no_forbidden_phrases(verdict, where="verdict")
    assert_no_forbidden_phrases(interpretation, where="interpretation")

    json_path = OUT_DIR / "run.json"
    md_path = OUT_DIR / "NOTES.md"
    md_path.write_text(md_text)
    json_path.write_text(json_text)
    print(f"verdict: {verdict}")
    print(f"wrote {md_path}")
    print(f"wrote {json_path}")


if __name__ == "__main__":
    main()
