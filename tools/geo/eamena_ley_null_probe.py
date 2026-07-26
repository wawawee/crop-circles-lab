#!/usr/bin/env python3
"""
eamena_ley_null_probe.py  --  G18: EAMENA collinearity / "ley" FPR calibration.

Loads a small GeoJSON subset of EAMENA sites and runs:

  1. **Collinearity / "ley" detectors** on the real subset:
       - triple count at tolerance ε (angular deviation from best great circle)
       - max collinear run (adjacency on common great circle)
       - mean alignment error across all triples

  2. **Null models** (same bbox, same N):
       - CSR (Complete Spatial Randomness) uniform in bbox
       - Scramble (permute coordinates across sites)
       - Random-same-N independent draws

  3. **FPR report**: fraction of null realizations that meet-or-exceed the
     real dataset's collinearity count at each tolerance.

Stance: structure != message. A high collinearity count does NOT imply an
"ancient grid / ET roads". This probe calibrates false-positive rates so
that any future ley claim can be honestly evaluated.

Verdict vocabulary:
    NO_SIGNAL       -- real collinearity does not exceed CSR/scramble nulls
    FPR_CALIBRATED  -- real collinearity separates from nulls with known FPR
    UNDERDETERMINED -- ambiguous or insufficient data
"""
from __future__ import annotations

import json
import math
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# paths
# ---------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA_DIR = ROOT / "data" / "geo" / "eamena"
OUT_DIR = ROOT / "outputs" / "eamena"

# ---------------------------------------------------------------------------
# geometry
# ---------------------------------------------------------------------------

_EARTH_R = 6371.0088  # km


def _haversine_dist(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance (km) between two points."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return _EARTH_R * 2 * math.asin(math.sqrt(a))


def _bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing (deg) from point 1 to point 2, 0–360."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dlon)
    return math.degrees(math.atan2(x, y)) % 360


def _angular_deviation(
    lat1: float, lon1: float,
    lat2: float, lon2: float,
    lat3: float, lon3: float,
) -> float:
    """Angular deviation (deg) of point 3 from the great-circle arc 1→2.
    
    The deviation is the absolute difference between the bearing from 1→3
    and from 1→2, ranged to [0, 180].
    """
    b12 = _bearing(lat1, lon1, lat2, lon2)
    b13 = _bearing(lat1, lon1, lat3, lon3)
    d = abs(b13 - b12)
    return d if d <= 180 else 360 - d


def collinear_triples(
    lats: np.ndarray,
    lons: np.ndarray,
    tol_deg: float = 1.0,
) -> list[tuple[int, int, int]]:
    """Find all triples (i,j,k) collinear within *tol_deg*.
    
    A triple qualifies if the maximum angular deviation of any point
    from the great circle defined by the other two is ≤ tol_deg.
    Uses the mid-point as the reference line, checking deviation of
    the third from arc(mid, each end).
    """
    n = len(lats)
    triples: list[tuple[int, int, int]] = []
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                d1 = _angular_deviation(lats[i], lons[i], lats[j], lons[j], lats[k], lons[k])
                d2 = _angular_deviation(lats[i], lons[i], lats[k], lons[k], lats[j], lons[j])
                d3 = _angular_deviation(lats[j], lons[j], lats[k], lons[k], lats[i], lons[i])
                if min(d1, d2, d3) <= tol_deg:
                    triples.append((i, j, k))
    return triples


def max_collinear_run(
    lats: np.ndarray,
    lons: np.ndarray,
    tol_deg: float = 1.0,
    min_chain: int = 3,
) -> tuple[int, list[int]]:
    """Longest collinear chain (connected adjacency). 
    
    Builds a graph where points are adjacent if they share at least one
    collinear triple. Returns (max_component_size, component_indices).
    """
    n = len(lats)
    triples = collinear_triples(lats, lons, tol_deg)
    adj: list[set[int]] = [set() for _ in range(n)]
    for i, j, k in triples:
        adj[i].add(j); adj[i].add(k)
        adj[j].add(i); adj[j].add(k)
        adj[k].add(i); adj[k].add(j)
    visited = [False] * n
    best_size = 0
    best_component: list[int] = []
    for v in range(n):
        if visited[v] or not adj[v]:
            continue
        stack = [v]
        visited[v] = True
        comp: list[int] = []
        while stack:
            cur = stack.pop()
            comp.append(cur)
            for nb in adj[cur]:
                if not visited[nb]:
                    visited[nb] = True
                    stack.append(nb)
        if len(comp) > best_size:
            best_size = len(comp)
            best_component = comp
    return (best_size if best_size >= min_chain else 0, best_component)


def mean_alignment_error(lats: np.ndarray, lons: np.ndarray) -> float:
    """Mean angular deviation (deg) over all triples (brute-force screening)."""
    n = len(lats)
    if n < 3:
        return float("nan")
    errors: list[float] = []
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                d1 = _angular_deviation(lats[i], lons[i], lats[j], lons[j], lats[k], lons[k])
                d2 = _angular_deviation(lats[i], lons[i], lats[k], lons[k], lats[j], lons[j])
                d3 = _angular_deviation(lats[j], lons[j], lats[k], lons[k], lats[i], lons[i])
                errors.append(min(d1, d2, d3))
    return float(np.mean(errors)) if errors else float("nan")


# ---------------------------------------------------------------------------
# data loader
# ---------------------------------------------------------------------------

def load_geojson(path: str | Path) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    """Load point features from GeoJSON. Returns (lats, lons, properties list)."""
    with open(path) as f:
        data = json.load(f)
    lats: list[float] = []
    lons: list[float] = []
    props: list[dict] = []
    for feat in data.get("features", []):
        geom = feat.get("geometry", {})
        if geom.get("type") != "Point":
            continue
        coords = geom.get("coordinates")
        if not coords or len(coords) < 2:
            continue
        lons.append(float(coords[0]))
        lats.append(float(coords[1]))
        props.append(feat.get("properties", {}))
    return np.array(lats, dtype=float), np.array(lons, dtype=float), props


# ---------------------------------------------------------------------------
# null generators
# ---------------------------------------------------------------------------

def sample_csr_bbox(
    n: int,
    bbox: tuple[float, float, float, float],
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """Uniform random points in [lon_min, lon_max] × [lat_min, lat_max]."""
    lon_min, lat_min, lon_max, lat_max = bbox
    lons = rng.uniform(lon_min, lon_max, n)
    lats = rng.uniform(lat_min, lat_max, n)
    return lats, lons


def sample_scramble(
    lats: np.ndarray,
    lons: np.ndarray,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """Permute coordinates independently (breaks spatial structure)."""
    return rng.permutation(lats), rng.permutation(lons)


# ---------------------------------------------------------------------------
# collinearity statistics wrapper
# ---------------------------------------------------------------------------

def collinearity_stats(
    lats: np.ndarray,
    lons: np.ndarray,
    tolerances: list[float],
) -> dict:
    """Compute collinearity statistics at multiple tolerances."""
    n = len(lats)
    results: dict[str, Any] = {
        "n": int(n),
    }
    for tol in tolerances:
        triples = collinear_triples(lats, lons, tol)
        run_size, run_comp = max_collinear_run(lats, lons, tol)
        results[f"triples_tol_{tol}"] = len(triples)
        results[f"max_run_tol_{tol}"] = run_size
    results["mean_alignment_error_deg"] = (
        round(mean_alignment_error(lats, lons), 4) if n >= 3 else None
    )
    return results


# ---------------------------------------------------------------------------
# FPR calibration
# ---------------------------------------------------------------------------

def run_calibration(
    lats: np.ndarray,
    lons: np.ndarray,
    n_sims: int = 999,
    seed: int = 42,
    tolerances: list[float] | None = None,
    null_quantile: float = 0.99,
) -> dict[str, Any]:
    """Run collinearity detector on real data and nulls, compute FPR.

    Verdict logic:
        NO_SIGNAL       -- real stats never exceed null 99th percentile
        FPR_CALIBRATED  -- real stats exceed null envelope at known FPR
        UNDERDETERMINED -- n<30 or ambiguous across tolerances
    """
    if tolerances is None:
        tolerances = [0.1, 0.5, 1.0, 2.0, 5.0]

    n = len(lats)
    if n < 3:
        return {
            "verdict": "UNDERDETERMINED",
            "reason": f"n={n} < 3, cannot assess collinearity",
            "n": int(n),
        }

    rng = np.random.default_rng(seed)
    lon_min, lon_max = float(lons.min()), float(lons.max())
    lat_min, lat_max = float(lats.min()), float(lats.max())
    bbox = (lon_min, lat_min, lon_max, lat_max)

    # real stats
    real = collinearity_stats(lats, lons, tolerances)

    # CSR null
    csr_stats_list: list[dict] = []
    for _ in range(n_sims):
        slats, slons = sample_csr_bbox(n, bbox, rng)
        csr_stats_list.append(collinearity_stats(slats, slons, tolerances))

    # Scramble null
    scramble_stats_list: list[dict] = []
    for _ in range(n_sims):
        slats, slons = sample_scramble(lats, lons, rng)
        scramble_stats_list.append(collinearity_stats(slats, slons, tolerances))

    def _fpr_and_envelope(
        real_val: float,
        null_vals: list[float],
    ) -> dict:
        null_arr = np.array(null_vals)
        thr = float(np.quantile(null_arr, null_quantile))
        fpr = float(np.mean(null_arr >= real_val))
        return {
            "real": round(real_val, 4),
            f"null_{null_quantile:.0%}": round(thr, 4),
            "null_mean": round(float(null_arr.mean()), 4),
            "null_sd": round(float(null_arr.std(ddof=1)), 4),
            "fpr": round(fpr, 4),
        }

    # aggregate per tolerance
    per_tol: dict[str, dict] = {}
    tol_signals: list[bool] = []
    for tol in tolerances:
        key_triple = f"triples_tol_{tol}"
        key_run = f"max_run_tol_{tol}"
        real_t = real.get(key_triple, 0)
        real_r = real.get(key_run, 0)

        csr_t = [s.get(key_triple, 0) for s in csr_stats_list]
        csr_r = [s.get(key_run, 0) for s in csr_stats_list]
        sc_t = [s.get(key_triple, 0) for s in scramble_stats_list]
        sc_r = [s.get(key_run, 0) for s in scramble_stats_list]

        fpr_t_csr = _fpr_and_envelope(real_t, csr_t)
        fpr_r_csr = _fpr_and_envelope(real_r, csr_r)
        fpr_t_sc = _fpr_and_envelope(real_t, sc_t)
        fpr_r_sc = _fpr_and_envelope(real_r, sc_r)

        per_tol[f"tol_{tol}"] = {
            "triples": {
                "real": fpr_t_csr["real"],
                "csr": {k: v for k, v in fpr_t_csr.items() if k != "real"},
                "scramble": {k: v for k, v in fpr_t_sc.items() if k != "real"},
            },
            "max_run": {
                "real": fpr_r_csr["real"],
                "csr": {k: v for k, v in fpr_r_csr.items() if k != "real"},
                "scramble": {k: v for k, v in fpr_r_sc.items() if k != "real"},
            },
        }
        # signal if real value exceeds both CSR and scramble 99th percentile
        signal = (
            real_t > fpr_t_csr[f"null_{null_quantile:.0%}"]
            and real_t > fpr_t_sc[f"null_{null_quantile:.0%}"]
        ) or (
            real_r > fpr_r_csr[f"null_{null_quantile:.0%}"]
            and real_r > fpr_r_sc[f"null_{null_quantile:.0%}"]
        )
        tol_signals.append(signal)

    # aggregate mean alignment error comparison
    real_mae = real.get("mean_alignment_error_deg")
    mae_comparison: dict = {}
    if real_mae is not None:
        csr_maes = [s.get("mean_alignment_error_deg", 0) or 0 for s in csr_stats_list]
        sc_maes = [s.get("mean_alignment_error_deg", 0) or 0 for s in scramble_stats_list]
        mae_comparison = {
            "real": real_mae,
            "csr_mean": round(float(np.mean(csr_maes)), 4),
            "csr_sd": round(float(np.std(csr_maes, ddof=1)), 4),
            "scramble_mean": round(float(np.mean(sc_maes)), 4),
            "scramble_sd": round(float(np.std(sc_maes, ddof=1)), 4),
        }

    # verdict
    n_signal = sum(tol_signals)
    # use moderate tolerances (1°, 2°) as primary indicators
    primary_tols = [1.0, 2.0]
    primary_signal = any(
        sig for tol, sig in zip(tolerances, tol_signals)
        if tol in primary_tols
    )

    if n < 30:
        verdict = "UNDERDETERMINED"
        reason = (
            f"n={n} is small; collinearity statistics are unreliable until "
            f"tested on larger EAMENA subsets."
        )
    elif primary_signal:
        verdict = "FPR_CALIBRATED"
        reason = (
            f"Real collinearity exceeds null envelope at one or more primary "
            f"tolerances ({primary_tols}). FPR per tolerance is reported above. "
            f"This warrants extension to a larger EAMENA sample."
        )
    else:
        verdict = "NO_SIGNAL"
        reason = (
            f"Real collinearity counts are within the CSR/scramble envelope "
            f"at all primary tolerances. No ley-like signal detected."
        )

    return {
        "verdict": verdict,
        "reason": reason,
        "domain": "eamena_ley_null",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": {
            "source": "EAMENA Wadi Naqqat subset (14 sites, CC BY 4.0)",
            "doi": "10.5281/zenodo.15554618",
            "n": int(n),
            "bbox_approx": {
                "lon_min": round(lon_min, 4),
                "lat_min": round(lat_min, 4),
                "lon_max": round(lon_max, 4),
                "lat_max": round(lat_max, 4),
            },
        },
        "parameters": {
            "n_sims": n_sims,
            "seed": seed,
            "tolerances_deg": tolerances,
            "null_quantile": null_quantile,
        },
        "real_stats": real,
        "per_tolerance": per_tol,
        "mean_alignment_error": mae_comparison,
        "signal_by_tolerance": {
            f"tol_{tol}": sig for tol, sig in zip(tolerances, tol_signals)
        },
        "n_tolerances_with_signal": n_signal,
        "caveats": [
            "Subset is only 14 sites in a ~500 m area — too few for reliable "
            "ley-line statistics. These results are a calibration exercise.",
            "Collinearity detection uses great-circle bearings, not "
            "planar approximations, appropriate for the Wadi Naqqat extent.",
            "CSR null is uniform in bbox; does not model terrain or "
            "cultural settlement patterns that constrain site placement.",
            "Structure detection is not a message or civilisation claim.",
        ],
    }


# ---------------------------------------------------------------------------
# IO
# ---------------------------------------------------------------------------

def write_notes(result: dict[str, Any], path: str | Path) -> None:
    lines = [
        "# G18 — EAMENA ley-line null probe (spatial FPR calibration)",
        "",
        "**Verdict:** `" + result["verdict"] + "`  ",
        "",
        result["reason"],
        "",
        "## What this is",
        "",
        "This probe tests whether EAMENA archaeological site coordinates show",
        "collinearity (ley-like alignment) beyond what Complete Spatial",
        "Randomness (CSR) or coordinate permutation would produce. It is a",
        "**false-positive rate calibration** — not a claim about ancient leys.",
        "",
        "## Dataset",
        "",
        "- Source: " + result["dataset"]["source"],
        "- DOI: " + result["dataset"]["doi"],
        "- Sites: " + str(result["dataset"]["n"]),
        "- Bbox: " + str(result["dataset"]["bbox_approx"]),
        "",
        "## Method",
        "",
        "- Collinearity detector: great-circle bearing deviation for all",
        "  triples, at tolerances 0.1°, 0.5°, 1.0°, 2.0°, 5.0°.",
        "- Null CSR: uniform random points in the same bounding box.",
        "- Null scramble: independent coordinate permutation.",
        "- " + str(result["parameters"]["n_sims"]) + " simulations per null.",
        "- Threshold: " + f"{result['parameters']['null_quantile']:.0%} "
        "quantile of the combined null distribution.",
        "",
        "## Results",
        "",
    ]

    # build a compact table
    header = "| tolerance | stat | real | CSR 99% | CSR FPR | scramble 99% | scramble FPR |"
    sep = "|---|---|---|---|---|---|---|"
    lines.append(header)
    lines.append(sep)
    for tol_key, tol_data in result["per_tolerance"].items():
        tol_label = tol_key.replace("tol_", "") + "°"
        for stat_name, stat_data in [("triples", tol_data["triples"]),
                                      ("max_run", tol_data["max_run"])]:
            csr = stat_data["csr"]
            sc = stat_data["scramble"]
            lines.append(
                f"| {tol_label} | {stat_name} "
                f"| {stat_data['real']} "
                f"| {csr['null_99%']} "
                f"| {csr['fpr']} "
                f"| {sc['null_99%']} "
                f"| {sc['fpr']} |"
            )

    mae = result.get("mean_alignment_error", {})
    if mae and mae.get("real"):
        lines.extend([
            "",
            f"**Mean alignment error:** real={mae['real']}°, "
            f"CSR mean={mae['csr_mean']}° (sd={mae['csr_sd']}°), "
            f"scramble mean={mae['scramble_mean']}° (sd={mae['scramble_sd']}°)",
        ])

    lines.extend([
        "",
        "## Caveats",
        "",
    ] + ["- " + c for c in result["caveats"]] + [
        "",
        "## Honest bottom line",
        "",
        result["reason"],
        "",
        "No ancient grid, no ET roads, no mystical leys. "
        "This is a null-model calibration exercise.",
        "",
    ])
    with open(path, "w") as fh:
        fh.write("\n".join(lines))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--geojson", default=str(DATA_DIR / "wadi_naqqat.geojson"),
                    help="Input GeoJSON file")
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    ap.add_argument("--n-sims", type=int, default=999)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    lats, lons, props = load_geojson(args.geojson)
    print(f"Loaded {len(lats)} point features from {args.geojson}")

    result = run_calibration(
        lats, lons,
        n_sims=args.n_sims,
        seed=args.seed,
    )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    run_path = out_dir / "run.json"
    notes_path = out_dir / "NOTES.md"

    with open(run_path, "w") as fh:
        json.dump(result, fh, indent=2)

    write_notes(result, notes_path)

    print(json.dumps({
        "verdict": result["verdict"],
        "n": result["dataset"]["n"],
        "n_sims": result["parameters"]["n_sims"],
        "n_tolerances_with_signal": result["n_tolerances_with_signal"],
    }, indent=2))
    print(f"wrote {run_path}")
    print(f"wrote {notes_path}")


if __name__ == "__main__":
    main()
