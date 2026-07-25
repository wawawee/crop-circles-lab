"""constants_stress -- Tolerance sweep for N3 constants probe (Hermes).

Asks: "as we tighten the diatonic tolerance, how does the real hit rate
degrade against the two null models?" If the real hit rate falls with
the nulls in lockstep, the apparent signal is just rounding; if it falls
*faster* than the nulls, the early hits were biases (watchlist / look-
elsewhere); if it *outlives* the nulls across the sweep, you have an
honest basis for pointing at specific pairs.

Reuses `tools/astro/constants_probe.py` literals verbatim:
  - get_table(constant_set)
  - pairwise_ratios(constants, tol_cents=...)
  - filter_for_hits(pairs, constants)
  - random_constants_control(...)  (Null A -- log-uniform within decade)
  - pair_permutation_control(...)  (Null B -- reciprocal-arrangement)

NEW (2026-07-25): scale-invariant degeneracy score + bootstrap calibration.

The old absolute gap (perm_max - perm_mean <= 1.0) broke down across orders
of magnitude: at strict 5c the perm-null might produce ~3 hits, so a gap
of 1.0 is the entire range; at wide 50c it might produce ~134 hits, so a
gap of 1.0 is essentially zero. We replaced it with a Z-gap:

    gap_z = (perm_max - perm_mean) / sqrt(max(perm_mean, 1))

Dividing by sqrt(mean) is the Poisson-flavored normalisation -- std scales
with sqrt(mean), not mean. For a healthy N-sample Poisson distribution the
maximum is roughly z_max * sqrt(mean) above the mean, giving gap_z ~ 2 to 4
(typical healthy N=200 hole: z_max ~ 3.4). A 'degenerate' distribution
clusters tightly near the mean and gives gap_z ~ 0 regardless of scale.

By default we use DEGENERACY_Z_DEFAULT = 2.0 as a heuristic floor any
gap_z below this is suspicious. Pass --calibrate to empirically derive
the floor at each tol via subsample bootstrapping of a larger null.

Stance: NEVER claim a "music of the spheres". ALWAYS report
tol -> real hits -> null p95 -> p-value side by side.

CLI:
  python tools/astro/constants_stress.py --set core --trials 200
  python tools/astro/constants_stress.py --set mixings --trials 200
  python tools/astro/constants_stress.py --small-control          # N=50
  python tools/astro/constants_stress.py --calibrate             # empirical floors
  python tools/astro/constants_stress.py --calibrate --small-control
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))  # for `import constants_probe as CP`
import constants_probe as CP  # noqa: E402


# Sweep points: 5c (very strict), 8c (half-semitone), 10c (HARMONIC BAR),
# 15c, 20c (Hawkins default), 30c (one minor third tolerance), 50c (wide).
SWEEP_TOLS = (5.0, 8.0, 10.0, 15.0, 20.0, 30.0, 50.0)
TOL_COLORS = {5.0: "5c ref", 8.0: "8c", 10.0: "10c ref",
              15.0: "15c", 20.0: "20c ref", 30.0: "30c", 50.0: "50c"}

# Verdict thresholds, hoisted so they survive SWEEP_TOLS length changes
# and so the Bonferroni caveat adjusts itself automatically.
DEGENERACY_FRACTION = 0.6  # fraction of tols degenerate -> "magnitude clustering"
BONFERRONI_DENOMINATOR = len(SWEEP_TOLS)  # simultaneous comparisons vs SAME set
BONFERRONI_THRESHOLD = 0.05 / BONFERRONI_DENOMINATOR

# Default Z-gap degeneracy floor. Healthy nulls typically give gap_z ~ 2 to 4
# (Poisson N=200 -> ~3.4). Below DEGENERACY_Z_DEFAULT = 2.0, treat the null
# as suspiciously tight. Use --calibrate to compute per-tol floors
# empirically from the actual null distribution.
DEGENERACY_Z_DEFAULT = 2.0


def gap_z(hits: np.ndarray | list) -> float:
    """Scale-invariant degeneracy score (Z-gap).

    Z-gap = (max - mean) / sqrt(max(mean, 1)).

    For a healthy N-sample Poisson distribution, max ≈ mean + z_max * sqrt(mean)
    with z_max ~ 2-4 for moderate N. A degenerate (clustered-tightly) 
    distribution gives gap_z ~ 0 regardless of magnitude scale.

    Returns a float >= 0. Higher = wider spread; lower = tighter cluster.
    """
    arr = np.asarray(hits, dtype=float)
    mu = float(arr.mean())
    sd = math.sqrt(max(mu, 1.0))
    if sd <= 0:
        return 0.0
    return float((arr.max() - mu) / sd)


def calibrate_degeneracy_threshold(constants: list[dict], tol: float,
                                   n_trials: int, seed: int,
                                   n_bootstrap: int = 100,
                                   multiplier: int = 8) -> dict:
    """Empirically derive a per-tol Z-gap degeneracy floor via bootstrap.

    Procedure:
      1. Run one LARGER permutation null (n_bootstrap * multiplier trials) 
         at the given tol. This is the pool we subsample from.
      2. Draw n_bootstrap subsamples of EXACTLY n_trials indices WITHOUT 
         replacement from the pool (or WITH replacement if pool is smaller).
      3. Compute gap_z for each subsample.
      4. Return the empirical p05 + observed mean + observed max.

    Why p05: this is the floor under random sampling variance. Any actual
    sweep-gap_z below this is unlikely to arise from a healthy null. The
    threshold is anchored in the (constants, tol, n_trials) of the run, 
    NOT pulled from thin air.

    Returns dict with keys: {tol_cents, n_bootstrap, multiplier, 
    pool_size, p05_gap_z, p25_gap_z, mean_gap_z, max_gap_z, seed}.
    """
    pool_size = max(n_bootstrap * multiplier, n_trials + 10)
    pool = CP.pair_permutation_control(
        constants, n_trials=pool_size, tol_cents=tol, seed=seed
    )
    rng = np.random.default_rng(seed + 1000)
    n_pool = len(pool)
    sample_gap_zs = []
    for _ in range(n_bootstrap):
        # When the pool has fewer trials than n_trials (very small n_trials),
        # we must sample WITH replacement. Otherwise without (cheaper).
        idx = rng.choice(n_pool, size=n_trials, replace=(n_pool < n_trials))
        sample_gap_zs.append(gap_z(pool[idx]))
    arr = np.array(sample_gap_zs, dtype=float)
    return {
        "tol_cents": float(tol),
        "n_bootstrap": int(n_bootstrap),
        "multiplier": int(multiplier),
        "pool_size": int(n_pool),
        "p05_gap_z": float(np.percentile(arr, 5)),
        "p25_gap_z": float(np.percentile(arr, 25)),
        "p50_gap_z": float(np.percentile(arr, 50)),
        "mean_gap_z": float(arr.mean()),
        "max_gap_z": float(arr.max()),
        "seed": int(seed),
    }


def _sweep_row(constants: list[dict], tol: float,
               n_trials: int, seed: int) -> dict:
    pairs = CP.pairwise_ratios(constants, tol_cents=tol)
    filt = CP.filter_for_hits(pairs, constants)
    nd = CP.random_constants_control(constants, n_trials=n_trials,
                                      tol_cents=tol, seed=seed)
    np_ = CP.pair_permutation_control(constants, n_trials=n_trials,
                                      tol_cents=tol, seed=seed + 1)
    hits_all = sum(1 for p in pairs if p.within_tol)
    hits_filt = sum(1 for p in filt if p.within_tol)
    return {
        "tol_cents": tol,
        "n_pairs_all": len(pairs),
        "n_pairs_for_hits": len(filt),
        "hits_real_all": hits_all,
        "hits_real_filt": hits_filt,
        "decade_mean": float(nd.mean()),
        "decade_p50": float(np.percentile(nd, 50)),
        "decade_p95": float(np.percentile(nd, 95)),
        "decade_p99": float(np.percentile(nd, 99)),
        "decade_max": int(nd.max()),
        "perm_mean": float(np_.mean()),
        "perm_p50": float(np.percentile(np_, 50)),
        "perm_p95": float(np.percentile(np_, 95)),
        "perm_p99": float(np.percentile(np_, 99)),
        "perm_max": int(np_.max()),
        # New scale-invariant degeneracy stats per row
        "perm_gap_z": gap_z(np_),
        "p_decade_gte_real_filt": float((nd >= hits_filt).mean()),
        "p_perm_gte_real_filt": float((np_ >= hits_filt).mean()),
    }


def run_sweep(constants: list[dict], tols=SWEEP_TOLS,
              n_trials: int = 200, seed: int = 20260725) -> list[dict]:
    return [_sweep_row(constants, t, n_trials, seed) for t in tols]


def _is_degenerate(row: dict, calibrated_threshold: float | None) -> bool:
    """A row is degenerate if its perm_gap_z falls below threshold OR 
    if real_filt ties perm_p95 (null saturated)."""
    threshold = calibrated_threshold if calibrated_threshold is not None \
        else DEGENERACY_Z_DEFAULT
    return (row["perm_gap_z"] < threshold) \
        or (row["hits_real_filt"] == row["perm_p95"])


def _render_markdown(rows: list[dict], constant_set: str,
                     n_constants_total: int,
                     n_constants_for_hits: int,
                     tol_cents: float, n_trials: int,
                     seed: int, used_small: bool,
                     calibration: list[dict] | None = None) -> str:
    # Decide per-row threshold: use calibrated if available, else default.
    cal_by_tol = {round(c["tol_cents"], 2): c for c in (calibration or [])}
    line_threshold_for = lambda r: (
        cal_by_tol.get(round(r["tol_cents"], 2), {}).get("p05_gap_z",
                                                          DEGENERACY_Z_DEFAULT)
    )

    lines = [
        "# Hermes / N3 -- Tolerance Stress Test",
        "",
        "Question: how does the diatonic hit rate degrade as the cents bar tightens?  ",
        "If real hit rate drops with the nulls in lockstep, the signal is rounding.  ",
        "If real hit rate drops *faster* than the nulls, the apparent signal was  ",
        "selection bias. If real hit rate *outlives* both nulls across the sweep, ",
        "specific pair-cells are doing work -- not just magnitude structure.",
        "",
        f"Constant set: `{constant_set}`",
        f"({n_constants_total} total constants, {n_constants_for_hits} after "
        f"dropping derived rows)",
        f"Trials per null per tol: **{n_trials}**  ",
        f"Seed: {seed} " + ("(small-control=ON)" if used_small else ""),
        f"Degeneracy floor: gap_z < **{DEGENERACY_Z_DEFAULT}** "
        f"(Poisson N=200 ~ 3.4 healthy){'  (per-tol calibrated below)' if calibration else ''}",
        "",
        "## Hit-rate degradation table",
        "",
        "Real hit columns use the *filtered* total (watchlist/derived rows EXCLUDED).  ",
        "p-value = Pr(null >= real_filt). Smaller p = signal more unusual under that null.  ",
        "ref = designated reference points: 5c (very strict), 10c (HARMONIC BAR), 20c (Hawkins).",
        "",
        "| tol (cents) | n_pairs | real_filt | real_all | Null A mean | Null A p95 | "
        "Null B mean | Null B p95 | perm_gap_z | p(B) |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        tag = TOL_COLORS.get(r["tol_cents"], "")
        lines.append(
            f"| {tag} {r['tol_cents']:.1f} | {r['n_pairs_for_hits']} | "
            f"{r['hits_real_filt']} | {r['hits_real_all']} | "
            f"{r['decade_mean']:.2f} | {r['decade_p95']:.1f} | "
            f"{r['perm_mean']:.2f} | {r['perm_p95']:.1f} | "
            f"{r['perm_gap_z']:.3f} | "
            f"{r['p_perm_gte_real_filt']:.4f} |"
        )

    if calibration:
        lines += [
            "",
            "## Calibration (--calibrate; bootstrap p05 floors for gap_z)",
            "",
            "Each row's `perm_gap_z` is compared against the **per-tol empirical "
            "floor** below (computed by drawing 100 subsamples of size "
            f"{n_trials} from a {calibration[0]['pool_size']}-trial pool at "
            "each tol, and taking the 5th percentile of the resulting gap_z "
            "distribution). Numbers are scale-invariant -- a floor of 1.5 at "
            "the strict 5c bar and 1.5 at the loose 50c bar both apply the "
            "same statistical standard.",
            "",
            "| tol (cents) | pool size | p05(gap_z) | p25 | median | mean | max | threshold used |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for c in calibration:
            used = c["p05_gap_z"]
            lines.append(
                f"| {c['tol_cents']:.0f} | {c['pool_size']} | "
                f"{c['p05_gap_z']:.3f} | {c['p25_gap_z']:.3f} | "
                f"{c['p50_gap_z']:.3f} | {c['mean_gap_z']:.3f} | "
                f"{c['max_gap_z']:.3f} | {used:.3f} |"
            )

    # Pick out reference points for headline summary. Use exact float
    # equality on SWEEP_TOLS values so floating-point drift from arithmetic
    # can't silently drop a row.
    ref_targets = (5.0, 10.0, 20.0, 50.0)
    ref = {t: next((r for r in rows if r["tol_cents"] == t), None)
           for t in ref_targets}
    lines += ["", "## Headline (filtered real hits at reference tol points)", ""]
    for t, r in ref.items():
        if not r:
            continue
        above_b = "above" if r["hits_real_filt"] > r["perm_p95"] else (
            "ties" if r["hits_real_filt"] == r["perm_p95"] else "below"
        )
        threshold_used = line_threshold_for(r)
        lines.append(
            f"- **{t:.0f}c**: real_filt = {r['hits_real_filt']} vs "
            f"Null B p95 = {r['perm_p95']:.1f}  "
            f"({above_b} Null B 95th; "
            f"p(B) = {r['p_perm_gte_real_filt']:.4f}; "
            f"perm_gap_z = {r['perm_gap_z']:.3f} < {threshold_used:.3f}? "
            f"{'YES (degenerate)' if r['perm_gap_z'] < threshold_used else 'no'})"
        )

    # Survival analysis -- STRICT `>` not `>=` so perm_max / real_filt ties
    # don't get credited. When the permutation null degenerates (perm_mean
    # ~= perm_max, i.e. perm_gap_z small), real_filt tying with perm_p95 is
    # statistically uninformative.
    beats_a_strict = sum(1 for r in rows
                         if r["hits_real_filt"] > r["decade_p95"])
    beats_b_strict = sum(1 for r in rows
                         if r["hits_real_filt"] > r["perm_p95"])
    low_p_b = sum(1 for r in rows if r["p_perm_gte_real_filt"] < 0.05)
    degenerate_count = sum(
        1 for r in rows
        if _is_degenerate(r, cal_by_tol.get(round(r["tol_cents"], 2), {}).get(
            "p05_gap_z"))
    )
    n_calibrated = len(cal_by_tol)
    lines += [
        "",
        "## Survival across tol -- 5-case verdict (strict >)",
        "",
        f"Real_filt **strict >** Null A p95 in **{beats_a_strict}/{len(rows)}** "
        f"tol points  ",
        f"Real_filt **strict >** Null B p95 in **{beats_b_strict}/{len(rows)}** "
        f"tol points  ",
        f"Real_filt has p(B) < 0.05 in **{low_p_b}/{len(rows)}** tol points  ",
        f"Null B degenerate (gap_z < threshold OR real_filt ties p95) at "
        f"**{degenerate_count}/{len(rows)}** tol points"
        + (f" (per-tol thresholds via --calibrate)" if n_calibrated
            else f" (gap_z < {DEGENERACY_Z_DEFAULT} default floor)"),
        "",
        "INTERPRETATION (necessary, not sufficient):",
        "  * STRICT > is the right bar: ties with perm_max mean the null has",
        "    saturated, not that real is special. >= over-counts luck.",
        "  * A non-degenerate null with multiple STRICT > + low p(B) is the",
        "    only configuration that earns a quiet lab-internal follow-up.",
    ]
    if beats_b_strict == 0 and low_p_b == 0:
        if degenerate_count >= len(rows) * DEGENERACY_FRACTION:
            lines.append("  -> No STRICT beat AND no sub-0.05 p-value, AND null distribution")
            lines.append("     degenerates across most tol points. The real_filt rate sits")
            lines.append("     INSIDE the permutation null at every tol -- magnitude")
            lines.append("     clustering (close-magnitude constants producing similar")
            lines.append("     diatonic densities under any pairing) dominates any apparent")
            lines.append("     signal. NOT a defensible 'pair-cells matter' finding.")
        else:
            lines.append("  -> No STRICT beats NOR sub-0.05 p-value across the sweep.")
            lines.append("     Filtered real-rate is INSIDE Null B at every tol point.")
            lines.append("     NOT a defensible 'pair-cells matter' signal at the filtered bar.")
    elif beats_b_strict <= 2 and low_p_b <= 1:
        lines.append("  -> Single-pass-fortune region: at most a couple of strict beats.")
        lines.append("     NOT a defensible signal at the filtered bar.")
    elif beats_b_strict <= 4 and low_p_b <= 3:
        lines.append("  -> Suggestive: middle-band strict beats. Largest-tol hits are")
        lines.append("     likely the (already excluded) watchlist leaking back in via")
        lines.append("     closely-clustered magnitudes. INSIDE the lab only -- quiet")
        lines.append("     manual review of the top pairs, do NOT interpret as discovery.")
    elif low_p_b >= max(1, len(rows) * DEGENERACY_FRACTION):
        lines.append("  -> SUB-0.05 p(B) at the MAJORITY of tol points with multiple")
        lines.append("     STRICT beats. Direct (still-conditional) indication that")
        lines.append("     specific pair-cells matter beyond magnitude structure.")
        lines.append("     Lab-internal follow-up only. NOT a global claim.")
        lines.append(
            f"     CAVEAT: {BONFERRONI_DENOMINATOR} simultaneous comparisons against "
            f"the SAME"
        )
        lines.append("     constant set. Naive p<0.05 is liberal; promote only if")
        lines.append(
            f"     Bonferroni-corrected p<{BONFERRONI_THRESHOLD:.4f} holds AND a"
        )
        lines.append("     permutation-of-tols null confirms.")
    else:
        lines.append("  -> Mixed picture -- not enough STRICT beats to warrant a")
        lines.append("     lab-internal claim. Re-run with --trials 2000 to test")
        lines.append("     whether the strict-beat count moves; if not, apparent")
        lines.append("     signal is sampling variance.")
    lines += [
        "",
        "---",
        "",
        "*Generated by `tools/astro/constants_stress.py`. Stance unchanged.*",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--set", default="core",
                    help="constant set: core | large | mixings | everything")
    ap.add_argument("--trials", type=int, default=200,
                    help="trials per null per tol point (default 200)")
    ap.add_argument("--small-control", action="store_true",
                    help="fast iteration: pin n_trials=50 (default in this sweep is 200)")
    ap.add_argument("--calibrate", action="store_true",
                    help="empirically bootstrap per-tol gap_z floors via subsampling "
                         "(default uses DEGENERACY_Z_DEFAULT = 2.0)")
    ap.add_argument("--calibrate-trials", type=int, default=200,
                    help="size of bootstrapped sub-samples for --calibrate (default 200)")
    ap.add_argument("--calibrate-bootstrap", type=int, default=100,
                    help="number of bootstrap subsamples per tol (default 100)")
    ap.add_argument("--tol-list", type=str, default=",".join(str(t) for t in SWEEP_TOLS),
                    help="comma-separated tolerance values (default 5,8,10,15,20,30,50)")
    ap.add_argument("--seed", type=int, default=20260725)
    ap.add_argument("--out", type=Path, default=Path("outputs/constants"),
                    help="output dir (default outputs/constants)")
    args = ap.parse_args()
    if args.small_control:
        args.trials = 50

    if args.tol_list == ",".join(str(t) for t in SWEEP_TOLS):
        tols = list(SWEEP_TOLS)
    else:
        tols = [float(x) for x in args.tol_list.split(",") if x.strip()]
    constants = CP.get_table(args.set)
    derived_names = {c["name"] for c in constants if c.get("derived", False)}
    n_total = len(constants)
    n_for_hits = n_total - len(derived_names)

    args.out.mkdir(parents=True, exist_ok=True)

    # Optional bootstrapped calibration -- runs BEFORE sweep so its result
    # can be embedded in the sweep's JSON + markdown.
    calibration: list[dict] = []
    if args.calibrate:
        sys.stderr.write(
            f"[calibrate] running bootstrap at {len(tols)} tols "
            f"(N_bootstrap={args.calibrate_bootstrap}, "
            f"sub_size={args.calibrate_trials}, "
            f"pool_size={max(args.calibrate_bootstrap*8, args.calibrate_trials+10)})\n"
        )
        for t in tols:
            calibration.append(
                calibrate_degeneracy_threshold(
                    constants, tol=t,
                    n_trials=args.calibrate_trials,
                    seed=args.seed,
                    n_bootstrap=args.calibrate_bootstrap,
                )
            )
        sys.stderr.write("[calibrate] done.\n")

    rows = run_sweep(constants, tols=tuple(tols), n_trials=args.trials, seed=args.seed)

    csv_path = args.out / "stress_sweep.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    json_path = args.out / "stress_sweep.json"
    json_path.write_text(json.dumps({
        "constant_set": args.set,
        "n_constants_total": n_total,
        "n_constants_for_hits": n_for_hits,
        "n_trials": args.trials,
        "seed": args.seed,
        "tol_list": list(tols),
        "degeneracy_floor_used": {
            "default": DEGENERACY_Z_DEFAULT,
            "calibrated": calibration,
        },
        "rows": rows,
    }, indent=2))
    md_path = args.out / "stress_sweep_notes.md"
    md_path.write_text(_render_markdown(
        rows, args.set, n_total, n_for_hits,
        tol_cents=20.0, n_trials=args.trials, seed=args.seed,
        used_small=args.small_control, calibration=calibration,
    ))

    def _safe(p):
        try:
            return str(p.resolve().relative_to(ROOT.resolve()))
        except ValueError:
            return str(p)

    print(f"Wrote {_safe(csv_path)}  ({len(rows)} rows)")
    print(f"Wrote {_safe(json_path)}")
    print(f"Wrote {_safe(md_path)}")
    print()
    print("Headline:")
    ref_printed = (5.0, 10.0, 20.0, 50.0)
    for t in ref_printed:
        r = next((rr for rr in rows if rr["tol_cents"] == t), None)
        if not r:
            continue
        threshold_used = DEGENERACY_Z_DEFAULT
        cal_match = next((c for c in calibration
                          if round(c["tol_cents"], 2) == round(t, 2)), None)
        if cal_match:
            threshold_used = cal_match["p05_gap_z"]
        deg = "DEGEN" if r["perm_gap_z"] < threshold_used else "ok    "
        print(
            f"  {t:>4.0f}c: real_filt={r['hits_real_filt']:>3}  "
            f"nullB p95={r['perm_p95']:.1f}  "
            f"p(B)={r['p_perm_gte_real_filt']:.4f}  "
            f"gap_z={r['perm_gap_z']:.3f} < {threshold_used:.3f}? [{deg}]"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
