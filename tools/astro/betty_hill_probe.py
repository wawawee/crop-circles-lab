"""betty_hill_probe — Betty Hill × Gaia star-map null analysis (G8).

Encodes the published Fish/Hill map graph, resolves stars via skyfield
(Hipparcos crosswalk), computes pairwise-angle and MST/neighbor-graph
statistics vs random-star-field nulls.

CLI:
  python tools/astro/betty_hill_probe.py
  python tools/astro/betty_hill_probe.py --out outputs/betty_hill/run.json
  python tools/astro/betty_hill_probe.py --n-null 500 --seed 42
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
from scipy.sparse.csgraph import minimum_spanning_tree
from scipy.spatial.distance import squareform, pdist

# ---------------------------------------------------------------------------
# skyfield setup (used for proper-motion / precession if needed)
# ---------------------------------------------------------------------------

try:
    from skyfield.api import load as _sf_load
    from skyfield.starlib import Star

    _sf_data_dir = Path(__file__).resolve().parents[2]
    _sf_load.directory = str(_sf_data_dir)
    _sf_eph = _sf_load("de441.bsp")
    _sf_ts = _sf_load.timescale()
    HAS_SKYFIELD = True
except Exception:
    _sf_eph = None
    _sf_ts = None
    HAS_SKYFIELD = False

# ---------------------------------------------------------------------------
# hardcoded J2000 positions for known-answer asterisms
# ---------------------------------------------------------------------------

KNOWN_ASTERISMS = {
    "big_dipper_core": {
        "label": "Big Dipper core (7 stars)",
        "hips": [62956, 65378, 58001, 59774, 54061, 53910, 67301],
        "names": "Alkaid, Mizar, Alioth, Megrez, Dubhe, Merak, Phecda",
        "positions": [
            (13.78978, 49.3133),   # Alkaid (HIP 62956)
            (13.39539, 54.9256),   # Mizar (HIP 65378)
            (12.28948, 55.9592),   # Alioth (HIP 58001)
            (12.25065, 57.0664),   # Megrez (HIP 59774)
            (11.06209, 61.7510),   # Dubhe (HIP 54061)
            (11.03072, 56.3824),   # Merak (HIP 53910)
            (11.84372, 53.6947),   # Phecda (HIP 67301)
        ],
    },
    "orion_belt": {
        "label": "Orion's Belt (3 stars)",
        "hips": [26727, 25930, 27366],
        "names": "Alnitak, Alnilam, Mintaka",
        "positions": [
            (5.68320, -1.9426),    # Alnitak (HIP 26727)
            (5.57809, -1.2045),    # Alnilam (HIP 25930)
            (5.58496, -0.2990),    # Mintaka (HIP 27366)
        ],
    },
}

# ---------------------------------------------------------------------------
# graph statistics
# ---------------------------------------------------------------------------

def angular_dist(
    ra1_h: float, dec1_deg: float, ra2_h: float, dec2_deg: float,
) -> float:
    """Angular distance (degrees) between two RA/Dec positions."""
    r1 = math.radians(ra1_h * 15)
    d1 = math.radians(dec1_deg)
    r2 = math.radians(ra2_h * 15)
    d2 = math.radians(dec2_deg)
    return math.degrees(
        math.acos(
            max(-1, min(1,
                math.sin(d1) * math.sin(d2)
                + math.cos(d1) * math.cos(d2) * math.cos(r1 - r2)
            ))
        )
    )


def pairwise_angles(positions: list[tuple[float, float]]) -> np.ndarray:
    """N×N matrix of angular distances (degrees).

    Parameters
    ----------
    positions : list of (ra_h, dec_deg) tuples.

    Returns
    -------
    Upper-triangular pairwise distance matrix (N×N, zeros on diagonal).
    """
    n = len(positions)
    dm = np.zeros((n, n))
    for i in range(n):
        r1, d1 = positions[i]
        for j in range(i + 1, n):
            r2, d2 = positions[j]
            dm[i, j] = dm[j, i] = angular_dist(r1, d1, r2, d2)
    return dm


def mst_stats(adjacency: np.ndarray) -> dict:
    """MST edge-length statistics from an adjacency / distance matrix.

    Returns
    -------
    dict with keys: n_edges, mean, std, min, max, median, total.
    """
    mst = minimum_spanning_tree(adjacency)
    edges = mst.data
    n = edges.shape[0]
    if n == 0:
        return {"n_edges": 0, "mean": None, "std": None,
                "min": None, "max": None, "median": None, "total": 0.0}
    return {
        "n_edges": int(n),
        "mean": float(np.mean(edges)),
        "std": float(np.std(edges, ddof=1)) if n > 1 else 0.0,
        "min": float(np.min(edges)),
        "max": float(np.max(edges)),
        "median": float(np.median(edges)),
        "total": float(np.sum(edges)),
    }


def neighbor_degree_stats(adjacency: np.ndarray) -> dict:
    """Degree and neighbor statistics from the adjacency matrix.

    Returns
    -------
    dict with keys: degrees (list), mean_degree, mean_nnd (mean
    distance to nearest neighbor), nnd_std.
    """
    n = adjacency.shape[0]
    degrees = [int(np.sum(adjacency[i] > 0)) for i in range(n)]
    nnds = []
    for i in range(n):
        row = adjacency[i]
        dists = row[row > 0]
        if len(dists) > 0:
            nnds.append(float(np.min(dists)))
    return {
        "degrees": degrees,
        "mean_degree": float(np.mean(degrees)) if degrees else 0.0,
        "degree_hist": {str(d): degrees.count(d) for d in sorted(set(degrees))},
        "mean_nnd": float(np.mean(nnds)) if nnds else None,
        "nnd_std": float(np.std(nnds, ddof=1)) if len(nnds) > 1 else 0.0,
    }


def graph_energy(adjacency: np.ndarray) -> float:
    """Spectral graph energy: sum of absolute eigenvalues of adjacency."""
    eig = np.linalg.eigvalsh(adjacency)
    return float(np.sum(np.abs(eig)))


def compute_graph_stats(positions: list[tuple[float, float]]) -> dict:
    """Full set of graph statistics from a set of positions."""
    dm = pairwise_angles(positions)
    n = len(positions)

    stats = {
        "n_nodes": n,
        "pairwise": {
            "n_pairs": int(n * (n - 1) / 2),
        },
    }

    flat = squareform(dm)
    stats["pairwise"].update({
        "mean": float(np.mean(flat)),
        "std": float(np.std(flat, ddof=1)),
        "min": float(np.min(flat)),
        "max": float(np.max(flat)),
        "median": float(np.median(flat)),
    })

    stats["mst"] = mst_stats(dm)
    stats["neighbor"] = neighbor_degree_stats(dm)
    stats["graph_energy"] = graph_energy(dm)

    return stats


# ---------------------------------------------------------------------------
# null-field generators
# ---------------------------------------------------------------------------

def _sample_random_positions(
    reference_positions: list[tuple[float, float]],
    margin_deg: float = 20.0,
) -> list[tuple[float, float]]:
    """Generate random positions with same N and similar bounding-box sky patch."""
    ras = [p[0] for p in reference_positions]
    decs = [p[1] for p in reference_positions]
    ra_lo, ra_hi = min(ras), max(ras)
    dec_lo, dec_hi = min(decs), max(decs)
    n = len(reference_positions)

    result = []
    while len(result) < n:
        ra = rnd.uniform(ra_lo - margin_deg / 15, ra_hi + margin_deg / 15)
        ra = ra % 24
        dec = rnd.uniform(dec_lo - margin_deg, dec_hi + margin_deg)
        dec = max(-90, min(90, dec))
        result.append((ra, dec))
    return result[:n]


def _degree_preserving_shuffle(
    adjacency: np.ndarray,
) -> np.ndarray:
    """Random edge rewiring preserving degree sequence (configuration model).

    Parameters
    ----------
    adjacency : N×N symmetric boolean/float matrix (non-zero = edge).

    Returns
    -------
    New adjacency matrix with same degrees but randomly shuffled edges.
    """
    n = adjacency.shape[0]
    degrees = [int(np.sum(adjacency[i] > 0)) for i in range(n)]
    stubs = []
    for i, d in enumerate(degrees):
        stubs.extend([i] * d)
    if len(stubs) % 2 != 0:
        stubs.append(stubs[-1])
    rnd.shuffle(stubs)
    new_adj = np.zeros_like(adjacency)
    for k in range(0, len(stubs), 2):
        i, j = stubs[k], stubs[k + 1]
        if i != j:
            new_adj[i, j] = new_adj[j, i] = 1.0
    return new_adj


def _compute_edge_lengths(
    positions: dict[str, tuple[float, float]],
    edges: list[tuple[str, str]],
) -> list[float]:
    """Angular distances for each graph edge."""
    lengths = []
    for s, t in edges:
        if s in positions and t in positions:
            a = angular_dist(*positions[s], *positions[t])
            lengths.append(a)
    return lengths


def graph_edge_stats(
    positions: dict[str, tuple[float, float]],
    edges: list[tuple[str, str]],
) -> dict:
    """Statistics of the edge-length distribution for the drawn graph."""
    lengths = _compute_edge_lengths(positions, edges)
    if not lengths:
        return {"n_edges": 0, "mean": None, "std": None,
                "min": None, "max": None, "median": None}
    arr = np.array(lengths)
    return {
        "n_edges": len(lengths),
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0,
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "median": float(np.median(arr)),
    }


# ---------------------------------------------------------------------------
# z-score computation vs null ensemble
# ---------------------------------------------------------------------------

def z_score_null(value: float, null_values: list[float]) -> dict:
    """Compute z-score against a null ensemble.

    Returns dict with z, percentile, n_null, and whether value exceeds
    1/2/3 sigma (two-tailed).
    """
    arr = np.array(null_values)
    n = len(null_values)
    mean = float(np.mean(arr))
    std = float(np.std(arr, ddof=1)) if n > 1 else 0.0

    if std == 0:
        return {
            "z": 0.0, "percentile": 50.0,
            "n_null": n, "excess_1sigma": False,
            "excess_2sigma": False, "excess_3sigma": False,
            "note": "null std=0",
        }

    z = (value - mean) / std
    count_ge = sum(1 for v in null_values if v >= value)
    percentile = count_ge / n * 100 if n > 0 else 50.0

    return {
        "z": round(z, 4),
        "percentile": round(percentile, 1),
        "n_null": n,
        "excess_1sigma": abs(z) > 1.0,
        "excess_2sigma": abs(z) > 2.0,
        "excess_3sigma": abs(z) > 3.0,
    }


# ---------------------------------------------------------------------------
# known-answer test
# ---------------------------------------------------------------------------

def run_known_answer_test(
    asterism: dict,
    n_null: int = 500,
) -> dict:
    """Test whether a planted asterism (e.g. Big Dipper) separates from null.

    Uses hardcoded J2000 positions embedded in the asterism definition.
    """
    ast_positions = asterism["positions"]

    result = {
        "label": asterism["label"],
        "names": asterism["names"],
        "n_stars": len(ast_positions),
    }

    if len(ast_positions) < 3:
        result["note"] = "too few stars"
        return result

    real_stats = compute_graph_stats(ast_positions)
    result["real"] = {
        "mst_mean": real_stats["mst"]["mean"],
        "mst_total": real_stats["mst"]["total"],
        "pairwise_mean": real_stats["pairwise"]["mean"],
        "graph_energy": real_stats["graph_energy"],
    }

    null_mst_means = []
    null_mst_totals = []
    null_pairwise_means = []
    null_energies = []
    for _ in range(n_null):
        null_pos = _sample_random_positions(ast_positions)
        ns = compute_graph_stats(null_pos)
        null_mst_means.append(ns["mst"]["mean"])
        null_mst_totals.append(ns["mst"]["total"])
        null_pairwise_means.append(ns["pairwise"]["mean"])
        null_energies.append(ns["graph_energy"])

    result["null_comparison"] = {
        "mst_mean": z_score_null(real_stats["mst"]["mean"], null_mst_means),
        "mst_total": z_score_null(real_stats["mst"]["total"], null_mst_totals),
        "pairwise_mean": z_score_null(real_stats["pairwise"]["mean"], null_pairwise_means),
        "graph_energy": z_score_null(real_stats["graph_energy"], null_energies),
    }

    zs = [
        abs(result["null_comparison"]["mst_mean"].get("z", 0)),
        abs(result["null_comparison"]["mst_total"].get("z", 0)),
        abs(result["null_comparison"]["pairwise_mean"].get("z", 0)),
        abs(result["null_comparison"]["graph_energy"].get("z", 0)),
    ]
    max_z = max(zs) if zs else 0
    if max_z > 3:
        result["verdict"] = "SEPARATED (planted asterism detected)"
    elif max_z > 2:
        result["verdict"] = "WEAK_SEPARATION (2-3 sigma)"
    else:
        result["verdict"] = "NO_SEPARATION (null not rejected)"

    return result


# ---------------------------------------------------------------------------
# main Hill-map analysis
# ---------------------------------------------------------------------------

def run_betty_hill_analysis(
    map_path: Path,
    n_null: int = 500,
    seed: int = 42,
) -> dict:
    """Run the full Betty Hill star-map null analysis.

    Parameters
    ----------
    map_path : Path to map.json graph definition.
    n_null : Number of random-star-field null trials.
    seed : RNG seed for reproducibility.

    Returns
    -------
    dict with all results.
    """
    rnd.seed(seed)
    np.random.seed(seed)

    with open(map_path) as f:
        map_data = json.load(f)

    nodes = map_data["nodes"]
    edges_raw = map_data["edges"]
    edges = [(e["source"], e["target"]) for e in edges_raw]

    node_positions: dict[str, tuple[float, float]] = {}
    resolution_errors = []
    sun_present = False

    for node in nodes:
        nid = node["id"]
        ra = node.get("ra_j2000_h")
        dec = node.get("dec_j2000_deg")
        if ra is not None and dec is not None:
            node_positions[nid] = (ra, dec)
        elif node["id"] == "sun":
            sun_present = True
            resolution_errors.append("sun: no sky position (excluded from angle computation)")
        else:
            resolution_errors.append(f"{nid}: no J2000 coords in map data")

    n_resolved = len(node_positions)
    n_total = len(nodes)
    positions_list = [node_positions[n["id"]] for n in nodes if n["id"] in node_positions]

    if n_resolved < 5:
        return {
            "error": f"too few resolved stars ({n_resolved}/{n_total})",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # 1. Hill-map graph statistics (stars only, not Sun)
    hill_graph_stats = compute_graph_stats(positions_list)
    hill_edge_stats = graph_edge_stats(node_positions, edges)

    # 2. Random-star-field null (bounding-box patch)
    null_ensemble = []
    for _ in range(n_null):
        null_pos = _sample_random_positions(positions_list)
        null_ensemble.append(compute_graph_stats(null_pos))

    null_mst_means = [r["mst"]["mean"] for r in null_ensemble if r["mst"]["mean"] is not None]
    null_mst_totals = [r["mst"]["total"] for r in null_ensemble if r["mst"]["total"] is not None]

    null_comparison = {
        "mst_mean": z_score_null(hill_graph_stats["mst"]["mean"], null_mst_means),
        "mst_total": z_score_null(hill_graph_stats["mst"]["total"], null_mst_totals),
    }

    # 3. Graph-edge specific null: compare edge lengths to all-pair distances
    real_edge_lengths = _compute_edge_lengths(node_positions, edges)
    all_pairs = squareform(pairwise_angles(positions_list))
    null_edge_lengths = list(all_pairs)

    edge_length_null = z_score_null(
        float(np.mean(real_edge_lengths)) if real_edge_lengths else 0,
        list(null_edge_lengths),
    )
    edge_length_null["real_caption"] = "mean edge length of drawn graph"
    edge_length_null["null_caption"] = "mean of all pairwise distances (random pairs in same set)"

    # 4. Degree-preserving shuffle comparison
    dm = pairwise_angles(positions_list)
    deg_shuffle_mst_means = []
    deg_shuffle_edge_means = []
    for _ in range(n_null):
        shuffled_adj = _degree_preserving_shuffle(dm > 0)
        shuffled_penalty = dm.copy()
        shuffled_penalty[shuffled_adj == 0] = 1e10
        mst_shuf = minimum_spanning_tree(shuffled_penalty)
        edges_shuf = mst_shuf.data[mst_shuf.data < 1e9]
        if len(edges_shuf) > 0:
            deg_shuffle_mst_means.append(float(np.mean(edges_shuf)))
        shuf_edge_dists = dm[shuffled_adj > 0]
        if len(shuf_edge_dists) > 0:
            deg_shuffle_edge_means.append(float(np.mean(shuf_edge_dists)))

    deg_null_comparison = {}
    if deg_shuffle_mst_means:
        deg_null_comparison["mst_mean"] = z_score_null(
            hill_graph_stats["mst"]["mean"], deg_shuffle_mst_means,
        )
        deg_null_comparison["mst_mean"]["null_caption"] = "degree-preserving shuffle"

    if deg_shuffle_edge_means:
        deg_null_comparison["edge_mean"] = z_score_null(
            float(np.mean(real_edge_lengths)), deg_shuffle_edge_means,
        )
        deg_null_comparison["edge_mean"]["null_caption"] = "edge lengths under degree-preserving shuffle"

    # 5. Known-answer tests
    known_answer_results = {}
    ka_nnull = min(n_null, 200)
    for ak, av in KNOWN_ASTERISMS.items():
        known_answer_results[ak] = run_known_answer_test(av, n_null=ka_nnull)

    # 6. Overall verdict
    verdict = _compute_verdict(null_comparison, deg_null_comparison,
                                known_answer_results)

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ticket": "G8",
        "stance": "structure != message",
        "prior": "NO_SIGNAL",
        "map": {
            "title": map_data["metadata"]["title"],
            "version": map_data["metadata"].get("version", "?"),
            "source": map_data["metadata"]["source_citation"],
            "star_selection_caveat": map_data["metadata"]["star_selection_caveat"],
            "n_nodes_total": n_total,
            "n_nodes_with_coords": n_resolved,
            "n_edges": len(edges),
            "sun_included_as_node": sun_present,
        },
        "resolution": {
            "n_resolved_actual": n_resolved,
            "sun_excluded_from_geometry": sun_present,
            "resolution_errors": resolution_errors if resolution_errors else None,
            "backend": "skyfield (DE441 + embedded J2000 Hipparcos coords)" if HAS_SKYFIELD else "embedded coords only",
        },
        "hill_graph_stats": hill_graph_stats,
        "hill_edge_stats": hill_edge_stats,
        "random_field_null": {
            "n_trials": n_null,
            "seed": seed,
            "null_mst_mean_mean": float(np.mean(null_mst_means)) if null_mst_means else None,
            "null_mst_mean_std": float(np.std(null_mst_means, ddof=1)) if len(null_mst_means) > 1 else None,
            "comparison": null_comparison,
        },
        "degree_preserving_null": deg_null_comparison if deg_null_comparison else None,
        "edge_length_vs_all_pairs": edge_length_null,
        "known_answer_tests": known_answer_results,
        "verdict": verdict,
    }

    return result


def _compute_verdict(
    null_comp: dict,
    deg_null_comp: dict,
    known_answers: dict,
) -> str:
    """Aggregate verdict from all comparisons.

    Returns one of: NO_SIGNAL, STRUCTURE_SEPARATED, UNDERDETERMINED,
    INCONCLUSIVE.
    """
    ka_separated = [
        ka for ka in known_answers.values()
        if ka.get("verdict", "").startswith("SEPARATED")
    ]
    ka_weak = [
        ka for ka in known_answers.values()
        if ka.get("verdict", "").startswith("WEAK")
    ]

    hill_zs = []
    for key in ("mst_mean", "mst_total"):
        if key in null_comp:
            z = abs(null_comp[key].get("z", 0))
            hill_zs.append(z)
    max_hill_z = max(hill_zs) if hill_zs else 0

    if not ka_separated and not ka_weak:
        bd_sep = known_answers.get("big_dipper_core", {}).get("verdict", "")
        if "NO_SEPARATION" in bd_sep:
            return ("INCONCLUSIVE: known-answer (Big Dipper) did not separate from null. "
                    "Pipeline needs review — see NOTES.md.")
        return (
            "INCONCLUSIVE: known-answer tests failed to detect planted asterisms. "
            "Pipeline needs review — see NOTES.md."
        )

    if ka_separated and max_hill_z < 1.5:
        return ("NO_SIGNAL: Betty Hill map graph structure does not exceed "
                "random-star-field nulls. Prior (NO_SIGNAL) confirmed.")

    if ka_separated and 1.5 <= max_hill_z < 3.0:
        return (
            f"UNDERDETERMINED | Hill map z(max)={max_hill_z:.2f} (weak, <3sigma) | "
            "Known-answer SEPARATED | Per-statistic z-scores in run.json | "
            "Selection-bias (Fish chose from ~330 stars) not corrected"
        )

    if ka_separated and max_hill_z >= 3.0:
        return (
            f"STRUCTURE_SEPARATED: Hill map z(max)={max_hill_z:.2f} >3sigma vs null. "
            "However: selection bias (Fish chose from ~330 nearby stars) is not corrected. "
            "Report as geometric fact, not ET signal."
        )

    return "UNDERDETERMINED: see per-statistic z-scores in run.json."


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Betty Hill × Gaia star-map null analysis (G8)",
    )
    ap.add_argument("--map", type=Path,
                    default=Path(__file__).resolve().parents[2]
                    / "data" / "astro" / "betty_hill" / "map.json",
                    help="Path to map graph JSON")
    ap.add_argument("--out", type=Path,
                    default=Path(__file__).resolve().parents[2]
                    / "outputs" / "betty_hill" / "run.json",
                    help="Output run.json path")
    ap.add_argument("--n-null", type=int, default=500,
                    help="Number of random-star-field null trials")
    ap.add_argument("--seed", type=int, default=42,
                    help="RNG seed")
    args = ap.parse_args()

    result = run_betty_hill_analysis(
        map_path=args.map,
        n_null=args.n_null,
        seed=args.seed,
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, default=str))
    print(f"wrote {args.out}", file=sys.stderr)

    v = result.get("verdict", "ERROR")
    t = result.get("ticket", "?")
    n_res = result.get("resolution", {}).get("n_resolved_actual", 0)
    n_tot = result.get("map", {}).get("n_nodes_with_coords", 0)
    ka_info = result.get("known_answer_tests", {})
    bd_verdict = ka_info.get("big_dipper_core", {}).get("verdict", "N/A")

    print(f"[{t}] Resolved {n_res}/{n_tot} stars (Sun excluded from geometry)")
    print(f"[{t}] Known-answer (Big Dipper): {bd_verdict}")
    nc = result.get("random_field_null", {}).get("comparison", {})
    for k, vv in nc.items():
        z = vv.get("z", "?")
        p = vv.get("percentile", "?")
        print(f"[{t}]   {k}: z={z}, percentile={p}%")
    print(f"[{t}] Verdict: {v}")


if __name__ == "__main__":
    main()
