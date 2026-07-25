#!/usr/bin/env python3
"""
archaeo_probe.py — stdlib-only archaeoastronomy probe (control-first).

Reads data/catalog/formations.csv and runs ONE honest quantitative test —
the lunar-phase test — against a Monte-Carlo uniform-phase negative control,
plus a purely descriptive monument-proximity readout (no matched spatial null
yet) and the scatter dataset for the coordinate map.

Core rule of this lab: structure != meaning. The verdict is assigned STRICTLY
from the computed statistic. With n small and several approximate dates, the
honest outcome is very likely NO SIGNAL or UNDERDETERMINED — and that is fine.

Writes outputs/astro/archaeo_probe.json.

Usage: python3 tools/astro/archaeo_probe.py
"""
from __future__ import annotations

import csv
import json
import math
import random
import statistics
from datetime import datetime, timezone
from pathlib import Path

# Monte-Carlo settings
SEED = 1996
TRIALS = 20000

# Verdict thresholds (assigned strictly from the numbers)
P_STRUCTURE = 0.01          # two-sided empirical p must beat this
Z_STRUCTURE = 2.6           # |z| must exceed this
MIN_EXACT_SUBSET = 6        # exact-date subset smaller than this -> underdetermined


def _to_float(s: str):
    """Parse a float, returning None for blank/non-numeric cells."""
    if s is None:
        return None
    s = s.strip()
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def read_formations(csv_path: Path) -> list[dict]:
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows


def monte_carlo_null(n: int, trials: int, seed: int) -> dict:
    """
    Negative control for the lunar-phase test.

    Under random (uniform) dates, the Moon's illuminated fraction is
    f = (1 - cos(theta)) / 2 with phase theta ~ Uniform(0, 2*pi), so E[f] = 0.5.
    We draw `n` such f per trial and record the distribution of the trial means.
    """
    rng = random.Random(seed)
    two_pi = 2.0 * math.pi
    means = []
    for _ in range(trials):
        acc = 0.0
        for _ in range(n):
            theta = rng.uniform(0.0, two_pi)
            acc += (1.0 - math.cos(theta)) / 2.0
        means.append(acc / n)
    means.sort()

    def pct(p: float) -> float:
        # linear-interpolated percentile on the sorted sample
        if not means:
            return float("nan")
        k = (len(means) - 1) * p
        lo = math.floor(k)
        hi = math.ceil(k)
        if lo == hi:
            return means[int(k)]
        return means[lo] + (means[hi] - means[lo]) * (k - lo)

    null_mean = statistics.fmean(means)
    null_sd = statistics.pstdev(means)  # sd of the sampling distribution of the mean
    return {
        "means": means,
        "mean": null_mean,
        "sd": null_sd,
        "p2_5": pct(0.025),
        "p50": pct(0.50),
        "p97_5": pct(0.975),
        "trials": trials,
        "model": "f=(1-cosθ)/2, θ~U(0,2π)",
    }


def z_and_p(obs_mean: float, null: dict) -> tuple[float, float]:
    """z against the null sampling distribution, and a two-sided empirical p."""
    null_mean = null["mean"]
    null_sd = null["sd"]
    z = (obs_mean - null_mean) / null_sd if null_sd else float("nan")
    dev = abs(obs_mean - null_mean)
    means = null["means"]
    extreme = sum(1 for m in means if abs(m - null_mean) >= dev)
    p = extreme / len(means) if means else float("nan")
    return z, p


def classify(all_res: dict, exact_res: dict, n_exact: int) -> tuple[str, str]:
    """
    Assign the overall lunar verdict STRICTLY from the statistics.

    - STRUCTURE  : p < 0.01 AND |z| > ~2.6 (note: still not "meaning")
    - UNDERDETERMINED : exact-date subset too small (< ~6) OR results dominated
                        by approximate dates
    - NO SIGNAL  : otherwise (consistent with the uniform-phase control)
    """
    p_all = all_res["p"]
    z_all = all_res["z"]

    structure = (p_all < P_STRUCTURE) and (abs(z_all) > Z_STRUCTURE)
    if structure:
        return (
            "STRUCTURE",
            "Observed mean lunar illumination departs from the uniform-phase null "
            "beyond the control band (p<0.01, |z|>2.6). Structure only — NOT meaning, "
            "intent, or alignment; the effect is statistical and unexplained.",
        )

    if n_exact < MIN_EXACT_SUBSET:
        return (
            "UNDERDETERMINED",
            "Exact-date subset too small to decide (n_exact < 6); the full-set result "
            "leans on approximate (mid-month) dates that blur true lunar phase.",
        )

    # Full set consistent with control, and the exact subset is usable but still
    # weak given n and the fraction of approximate dates -> not enough to move
    # off the null with confidence.
    return (
        "NO SIGNAL",
        "Observed mean lunar illumination sits inside the uniform-phase control "
        "band (does not beat p<0.01 / |z|>2.6). Consistent with random dates; "
        "no lunar-phase signal. Small n and several approximate dates limit power.",
    )


def build_lunar(rows: list[dict]) -> dict:
    # --- observed (full numeric set) ---
    all_illum = []
    exact_illum = []
    n_approx_with_illum = 0
    for r in rows:
        f = _to_float(r.get("lunar_illum"))
        if f is None:
            continue
        all_illum.append(f)
        if (r.get("lunar_date_basis") or "").strip() == "exact":
            exact_illum.append(f)
        else:
            n_approx_with_illum += 1

    n_all = len(all_illum)
    n_exact = len(exact_illum)
    obs_all = statistics.fmean(all_illum) if all_illum else float("nan")
    obs_exact = statistics.fmean(exact_illum) if exact_illum else float("nan")

    # --- negative control (shared model; drawn per subset size) ---
    null_all = monte_carlo_null(n_all, TRIALS, SEED)
    # Redraw at the exact-subset size so its z/p use a size-matched null.
    null_exact = monte_carlo_null(n_exact, TRIALS, SEED + 1) if n_exact else None

    z_all, p_all = z_and_p(obs_all, null_all)
    all_res = {"z": round(z_all, 4), "p": round(p_all, 5)}

    if n_exact:
        z_ex, p_ex = z_and_p(obs_exact, null_exact)
        exact_res = {"z": round(z_ex, 4), "p": round(p_ex, 5)}
    else:
        exact_res = {"z": None, "p": None}

    verdict, caveat = classify(all_res, exact_res, n_exact)

    # per-subset verdicts (same strict rule, size-matched null already applied)
    def subset_verdict(res: dict, n: int) -> str:
        if res.get("p") is None:
            return "UNDERDETERMINED"
        if (res["p"] < P_STRUCTURE) and (abs(res["z"]) > Z_STRUCTURE):
            return "STRUCTURE"
        if n < MIN_EXACT_SUBSET:
            return "UNDERDETERMINED"
        return "NO SIGNAL"

    exact_block = {
        "observed_mean": round(obs_exact, 4) if n_exact else None,
        "n_used": n_exact,
        "z": exact_res["z"],
        "p": exact_res["p"],
        "verdict": subset_verdict(exact_res, n_exact),
    }
    all_block = {
        "observed_mean": round(obs_all, 4),
        "n_used": n_all,
        "z": all_res["z"],
        "p": all_res["p"],
        "verdict": subset_verdict(all_res, n_all),
    }

    approx_frac = round(n_approx_with_illum / n_all, 3) if n_all else None

    return {
        "observed_mean": round(obs_all, 4),
        "n_used": n_all,
        "n_approx_with_illum": n_approx_with_illum,
        "approx_fraction": approx_frac,
        "exact": exact_block,
        "all": all_block,
        "null": {
            "mean": round(null_all["mean"], 4),
            "sd": round(null_all["sd"], 4),
            "p2_5": round(null_all["p2_5"], 4),
            "p50": round(null_all["p50"], 4),
            "p97_5": round(null_all["p97_5"], 4),
            "trials": null_all["trials"],
            "model": null_all["model"],
        },
        "verdict": verdict,
        "caveat": caveat,
    }


def build_monument(rows: list[dict]) -> dict:
    """DESCRIPTIVE ONLY — no matched spatial null available, so no verdict/clustering claim."""
    kms = []
    for r in rows:
        km = _to_float(r.get("monument_km"))
        if km is not None:
            kms.append(km)
    n = len(kms)
    within_5 = sum(1 for k in kms if k <= 5.0)
    return {
        "mean_km": round(statistics.fmean(kms), 3) if kms else None,
        "median_km": round(statistics.median(kms), 3) if kms else None,
        "within_5km": within_5,
        "n": n,
        "verdict": "UNDERDETERMINED",
        "note": (
            "Descriptive only. No matched spatial null yet — needs monument "
            "coordinate set + bounding-box random points before any proximity or "
            "clustering claim can be made."
        ),
    }


def build_scatter(rows: list[dict]) -> tuple[list, dict]:
    scatter = []
    lats, lons = [], []
    for r in rows:
        lat = _to_float(r.get("lat"))
        lon = _to_float(r.get("lon"))
        illum = _to_float(r.get("lunar_illum"))
        km = _to_float(r.get("monument_km"))
        pr = _to_float(r.get("priority"))
        scatter.append({
            "id": r.get("id"),
            "name": r.get("name"),
            "lat": lat,
            "lon": lon,
            "priority": int(pr) if pr is not None else None,
            "coord_confidence": (r.get("coord_confidence") or "").strip(),
            "nearest_monument": (r.get("nearest_monument") or "").strip(),
            "monument_km": km,
            "lunar_illum": illum,
            "lunar_date_basis": (r.get("lunar_date_basis") or "").strip(),
        })
        if lat is not None:
            lats.append(lat)
        if lon is not None:
            lons.append(lon)
    bounds = {
        "lat_min": round(min(lats), 4) if lats else None,
        "lat_max": round(max(lats), 4) if lats else None,
        "lon_min": round(min(lons), 4) if lons else None,
        "lon_max": round(max(lons), 4) if lons else None,
    }
    return scatter, bounds


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    csv_path = root / "data" / "catalog" / "formations.csv"
    rows = read_formations(csv_path)

    lunar = build_lunar(rows)
    monument = build_monument(rows)
    scatter, bounds = build_scatter(rows)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = {
        "generated_at": generated_at,
        "n_formations": len(rows),
        "lunar": lunar,
        "monument": monument,
        "scatter": scatter,
        "bounds": bounds,
    }

    out_path = root / "outputs" / "astro" / "archaeo_probe.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"wrote {out_path}")
    print("\n=== LUNAR-PHASE PROBE (control-first) ===")
    print(f"null model              : {lunar['null']['model']}")
    print(f"null mean / sd          : {lunar['null']['mean']} / {lunar['null']['sd']}")
    print(f"null 95% band           : [{lunar['null']['p2_5']}, {lunar['null']['p97_5']}]")
    print(f"n_formations            : {result['n_formations']}")
    print(f"[ALL numeric]  n={lunar['all']['n_used']}  obs_mean={lunar['all']['observed_mean']}  "
          f"z={lunar['all']['z']}  p={lunar['all']['p']}  -> {lunar['all']['verdict']}")
    print(f"[EXACT subset] n={lunar['exact']['n_used']}  obs_mean={lunar['exact']['observed_mean']}  "
          f"z={lunar['exact']['z']}  p={lunar['exact']['p']}  -> {lunar['exact']['verdict']}")
    print(f"approx-date fraction    : {lunar['approx_fraction']} ({lunar['n_approx_with_illum']} approx of {lunar['all']['n_used']})")
    print(f"\n>>> OVERALL LUNAR VERDICT: {lunar['verdict']}")
    print(f"    caveat: {lunar['caveat']}")
    print("\n=== MONUMENT PROXIMITY (descriptive only) ===")
    print(f"mean/median km          : {monument['mean_km']} / {monument['median_km']}  "
          f"(within 5 km: {monument['within_5km']}/{monument['n']})  -> {monument['verdict']}")


if __name__ == "__main__":
    main()
