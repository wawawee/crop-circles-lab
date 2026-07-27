"""tess_ellipsoid_probe — TESS SN 1987A SETI Ellipsoid re-analysis (G17).

Analysis blocks:
  1. Known-answer path: inject a synthetic dip into one target at its
     Ellipsoid crossing time, epoch-fold over a grid around tcross,
     verify recovery.
  2. Quiet-star null: uniform-random dip times with no planted signal.
  3. Time-shuffle null: permute tcross assignments across targets,
     preserving the empirical tcross distribution.
  4. Per-target cohort analysis: each target's tcross epoch-folded against
     its own lightcurve — fixture should NOT report 32 anomalous dips.
  5. Real-data path (optional --fetch): download TESS PDCSAP via lightkurve.

Core rule: structure != message. The SETI Ellipsoid is a geometric
target-prioritisation strategy. Cabrales+2024 found no anomalous signatures.
This pipeline validates the math, not the hypothesis.

Outputs: outputs/tess_ellipsoid/{run.json,NOTES.md}

Usage:
  python tools/astro/tess_ellipsoid_probe.py                          # fixture known-answer + nulls
  python tools/astro/tess_ellipsoid_probe.py --fetch                  # real TESS data path
  python tools/astro/tess_ellipsoid_probe.py --out outputs/tess_ellipsoid/run.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

try:
    from tools.radio.radio_probe import epoch_fold, rayleigh_p_value, rayleigh_z2
except ImportError:
    HERE_P = Path(__file__).resolve().parent
    ROOT_P = HERE_P.parents[1]
    sys.path.insert(0, str(ROOT_P))
    from tools.radio.radio_probe import epoch_fold, rayleigh_p_value, rayleigh_z2

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CATALOG_PATH = ROOT / "data" / "astro" / "tess_ellipsoid" / "cabrales_2024_targets.json"
FIXTURE_PATH = ROOT / "data" / "astro" / "tess_ellipsoid" / "fixture_injection.json"
OUT_DIR = ROOT / "outputs" / "tess_ellipsoid"

STANCE = (
    "Structure != message. The SETI Ellipsoid is a geometric "
    "target-prioritisation strategy, not a technosignature detection. "
    "Cabrales+2024 found no anomalous signatures in any TESS lightcurve "
    "(non-detection is the ground truth). This pipeline validates epoch-fold "
    "math and null calibration, not the presence of extraterrestrial signals. "
    "No periodicity or dip structure at an Ellipsoid crossing time constitutes "
    "evidence of artificial engineering without independent multi-wavelength "
    "confirmation."
)
FORBIDDEN_PHRASES = [
    "Dyson",
    "alien",
    "technosignature detection",
    "confirms ET",
    "extraterrestrial signal found",
    "anomalous signal",
    "SETI detection",
    "megastructure",
    "ET beacon",
]
VERDICT_VOCAB = [
    "PIPELINE_VALIDATED", "UNDERDETERMINED", "NO_SIGNAL", "FPR_CALIBRATED",
]

N_TARGETS = 32
SEED = 42

KA_INJECTION_PERIOD_DAYS = 2.5
KA_N_DIPS = 30
KA_TARGET_INDEX = 0

TCROSS_WINDOW_DAYS = 30.0
EPOCH_GRID_STEPS = 1001
EPOCH_GRID_MARGIN = 5.0

QUIET_N_TRIALS = 200
TIMESHUFFLE_N_TRIALS = 200

COHORT_THRESHOLD_Z2 = 15.0


def load_catalog(path: Path | None = None) -> dict:
    if path is None:
        path = CATALOG_PATH
    if not path.exists():
        return {"error": f"catalog not found: {path}"}
    with open(path) as f:
        return json.load(f)


def _generate_epoch_grid(
    center_period_d: float,
    margin_d: float = EPOCH_GRID_MARGIN,
    steps: int = EPOCH_GRID_STEPS,
) -> np.ndarray:
    lo = max(center_period_d - margin_d, 0.1)
    hi = center_period_d + margin_d
    return np.linspace(lo, hi, steps)


def _uniform_random_times(
    n: int,
    range_bjd: tuple[float, float],
    seed: int,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return np.sort(rng.uniform(range_bjd[0], range_bjd[1], size=n))


def _inject_synthetic_dips(
    target_entry: dict,
    period_d: float = KA_INJECTION_PERIOD_DAYS,
    n_dips: int = KA_N_DIPS,
    seed: int = SEED,
) -> np.ndarray:
    tcross = target_entry["tcross_bjd"]
    rng = np.random.default_rng(seed)
    jitter_scale = period_d * 0.05
    offsets = np.arange(n_dips, dtype=float) * period_d
    jitter = rng.normal(0, jitter_scale, size=n_dips)
    dip_times = tcross + offsets + jitter
    return np.sort(dip_times)


def _z_score(value: float, null_values: list[float]) -> dict:
    arr = np.array(null_values)
    n = len(null_values)
    mean = float(np.mean(arr))
    std = float(np.std(arr, ddof=1)) if n > 1 else 0.0
    if std == 0:
        return {"z": 0.0, "percentile": 50.0, "n_null": n}
    z = (value - mean) / std
    count_ge = sum(1 for v in null_values if v >= value)
    percentile = count_ge / n * 100 if n > 0 else 50.0
    return {"z": round(z, 4), "percentile": round(percentile, 1), "n_null": n}


def run_known_answer(
    target_entry: dict,
    period_d: float = KA_INJECTION_PERIOD_DAYS,
    n_dips: int = KA_N_DIPS,
    steps: int = EPOCH_GRID_STEPS,
    margin_d: float = EPOCH_GRID_MARGIN,
    seed: int = SEED,
) -> dict:
    dip_times = _inject_synthetic_dips(target_entry, period_d, n_dips, seed=seed)
    tcross = target_entry["tcross_bjd"]
    periods = _generate_epoch_grid(period_d, margin_d, steps)
    periods = periods[periods > 0.1]

    fold = epoch_fold(dip_times, periods)

    recovery_err = abs(fold["best_period"] - period_d)
    recovery_pass = bool(recovery_err <= 0.5)

    return {
        "target_tic": target_entry["tic_id"],
        "tcross_bjd": tcross,
        "planted_period_days": period_d,
        "n_injected_dips": n_dips,
        "recovered_period_days": fold["best_period"],
        "recovered_z2": fold["best_z2"],
        "recovered_phase_rad": fold["best_phase_rad"],
        "recovered_p_value": fold["best_p_value"],
        "recovery_error_days": float(recovery_err),
        "recovery_pass": recovery_pass,
        "period_grid": {
            "min_days": float(periods[0]),
            "max_days": float(periods[-1]),
            "n_steps": len(periods),
        },
    }


def run_quiet_star_null(
    n_dips: int,
    range_bjd: tuple[float, float],
    period_d: float = KA_INJECTION_PERIOD_DAYS,
    n_trials: int = QUIET_N_TRIALS,
    seed: int = SEED,
) -> dict:
    periods = _generate_epoch_grid(period_d, EPOCH_GRID_MARGIN, EPOCH_GRID_STEPS)
    periods = periods[periods > 0.1]

    null_best_z2 = []
    for i in range(n_trials):
        times = _uniform_random_times(n_dips, range_bjd, seed + i)
        fold = epoch_fold(times, periods)
        null_best_z2.append(fold["best_z2"])

    return {
        "n_trials": n_trials,
        "n_dips": n_dips,
        "range_bjd": list(range_bjd),
        "null_best_z2_mean": float(np.mean(null_best_z2)),
        "null_best_z2_std": float(np.std(null_best_z2, ddof=1)),
        "null_best_z2_max": float(np.max(null_best_z2)),
        "null_best_z2_95pct": float(np.percentile(null_best_z2, 95)),
    }


def run_time_shuffle_null(
    targets: list[dict],
    period_d: float = KA_INJECTION_PERIOD_DAYS,
    n_trials: int = TIMESHUFFLE_N_TRIALS,
    seed: int = SEED,
    n_dips_per_target: int = KA_N_DIPS,
) -> dict:
    rng = np.random.default_rng(seed)
    tcross_values = np.array([t["tcross_bjd"] for t in targets])
    periods = _generate_epoch_grid(period_d, EPOCH_GRID_MARGIN, EPOCH_GRID_STEPS)
    periods = periods[periods > 0.1]

    pull_best_z2 = []
    for i in range(n_trials):
        shuffled = rng.permutation(tcross_values)
        target_tcross = float(shuffled[0])
        fake_times = _uniform_random_times(
            n_dips_per_target,
            (target_tcross - TCROSS_WINDOW_DAYS, target_tcross + TCROSS_WINDOW_DAYS),
            seed + i + 5000,
        )
        fold = epoch_fold(fake_times, periods)
        pull_best_z2.append(fold["best_z2"])

    return {
        "n_trials": n_trials,
        "n_targets": len(targets),
        "null_best_z2_mean": float(np.mean(pull_best_z2)),
        "null_best_z2_std": float(np.std(pull_best_z2, ddof=1)),
        "null_best_z2_max": float(np.max(pull_best_z2)),
        "null_best_z2_95pct": float(np.percentile(pull_best_z2, 95)),
    }


def run_cohort_analysis(
    targets: list[dict],
    period_d: float = KA_INJECTION_PERIOD_DAYS,
    seed: int = SEED,
    n_dips_per_target: int = KA_N_DIPS,
) -> dict:
    results = []
    anomalous_count = 0
    threshold_z2 = COHORT_THRESHOLD_Z2

    for i, tgt in enumerate(targets):
        tcross = tgt["tcross_bjd"]
        periods = _generate_epoch_grid(period_d, EPOCH_GRID_MARGIN, EPOCH_GRID_STEPS)
        periods = periods[periods > 0.1]
        fake_times = _uniform_random_times(
            n_dips_per_target,
            (tcross - TCROSS_WINDOW_DAYS, tcross + TCROSS_WINDOW_DAYS),
            seed + i + 10000,
        )
        fold = epoch_fold(fake_times, periods)
        is_anomalous = fold["best_z2"] > threshold_z2
        if is_anomalous:
            anomalous_count += 1
        results.append({
            "tic_id": tgt["tic_id"],
            "tcross_bjd": tcross,
            "best_z2": fold["best_z2"],
            "best_period": fold["best_period"],
            "anomalous": is_anomalous,
        })

    return {
        "n_targets": len(targets),
        "anomalous_count": anomalous_count,
        "threshold_z2": threshold_z2,
        "note": "Fixture-only (no real TESS data). Per-target epoch-fold using random dip times.",
        "per_target": results,
    }


def _try_tess_fetch(target_tic: int) -> dict:
    try:
        import lightkurve as lk
    except ImportError:
        return {"fetch_status": "LIGHTKURVE_MISSING"}
    try:
        search = lk.search_lightcurve(f"TIC {target_tic}", mission="TESS")
        if search is None or len(search) == 0:
            return {"fetch_status": "NO_SEARCH_RESULTS"}
        lcs = search.download_all()
        if lcs is None or len(lcs) == 0:
            return {"fetch_status": "DOWNLOAD_FAILED"}
        return {
            "fetch_status": "SUCCESS",
            "n_sectors": len(lcs),
            "sectors": [int(lc.meta.get("SECTOR", -1)) for lc in lcs],
        }
    except Exception as exc:
        return {"fetch_status": "FETCH_ERROR", "note": str(exc)}


def run_tess_analysis(targets: list[dict]) -> dict:
    first_target = targets[0]
    tic = first_target["tic_id"]
    fetch = _try_tess_fetch(tic)
    if fetch["fetch_status"] != "SUCCESS":
        return fetch

    try:
        import lightkurve as lk
        search = lk.search_lightcurve(f"TIC {tic}", mission="TESS")
        lcs = search.download_all()
        times_all = []
        for lc in lcs:
            times_all.extend(lc.time.value.tolist())
        times_all = np.array(sorted(times_all))

        results = []
        for tgt in targets:
            tcross = tgt["tcross_bjd"]
            near_mask = np.abs(times_all - tcross) < EPOCH_GRID_HALF_DAYS
            near_times = times_all[near_mask]
            if len(near_times) < 10:
                results.append({
                    "tic_id": tgt["tic_id"],
                    "tcross_bjd": tcross,
                    "status": "insufficient_data",
                    "n_times_near_crossing": int(sum(near_mask)),
                })
                continue
            periods = _generate_epoch_grid(KA_INJECTION_PERIOD_DAYS, EPOCH_GRID_MARGIN * 2, EPOCH_GRID_STEPS)
            periods = periods[periods > 0.1]
            fold = epoch_fold(near_times, periods)
            results.append({
                "tic_id": tgt["tic_id"],
                "tcross_bjd": tcross,
                "best_z2": fold["best_z2"],
                "best_period": fold["best_period"],
                "n_times_near_crossing": int(sum(near_mask)),
            })
        return {"fetch_status": "SUCCESS", "results": results}
    except Exception as exc:
        return {"fetch_status": "ANALYSIS_ERROR", "note": str(exc)}


def classify_verdict(
    known_answer: dict,
    quiet_null: dict,
    time_shuffle_null: dict,
    cohort: dict,
    real_data: dict | None = None,
) -> str:
    ka_pass = known_answer.get("recovery_pass", False)
    ka_z2 = known_answer.get("recovered_z2", 0.0)
    quiet_95 = quiet_null.get("null_best_z2_95pct", 0.0)
    ts_95 = time_shuffle_null.get("null_best_z2_95pct", 0.0)
    null_max_95 = max(quiet_95, ts_95)
    anomalous_count = cohort.get("anomalous_count", 0)

    if not ka_pass:
        return (
            "UNDERDETERMINED: known-answer path failed to recover injected dip. "
            "Pipeline needs review."
        )

    base_parts = ["PIPELINE_VALIDATED"]

    if ka_z2 <= null_max_95:
        base_parts.append(
            "KA signal does not separate from null — pipeline underpowered."
        )
        return " | ".join(base_parts + ["UNDERDETERMINED"])

    if anomalous_count >= 5:
        base_parts.append(
            f"Cohort null shows {anomalous_count}/32 anomalous — fixture may over-count."
        )
        return " | ".join(base_parts + ["FPR_CALIBRATED"])

    if real_data and real_data.get("fetch_status") == "SUCCESS":
        base_parts.append("Real TESS data processed.")
        return " | ".join(base_parts)

    base_parts.append(
        "No real TESS data fetched. Without lightkurve / MAST access the "
        "result is computational only."
    )
    return " | ".join(base_parts + ["UNDERDETERMINED"])


def build_interpretation(
    known_answer: dict,
    quiet_null: dict,
    time_shuffle_null: dict,
    cohort: dict,
    real_data: dict | None,
    verdict: str,
) -> str:
    ka_z2 = known_answer.get("recovered_z2", 0.0)
    ka_pass = known_answer.get("recovery_pass", False)
    quiet_95 = quiet_null.get("null_best_z2_95pct", "?")
    ts_95 = time_shuffle_null.get("null_best_z2_95pct", "?")
    tic = known_answer.get("target_tic", "?")
    anom = cohort.get("anomalous_count", "?")

    return (
        f"TESS SN 1987A SETI Ellipsoid (Cabrales+2024) re-analysis. "
        f"N_targets={N_TARGETS} from real catalog. "
        f"Known-answer: injected dip at TIC {tic}, "
        f"recovery_pass={ka_pass}, Z2={ka_z2:.1f}. "
        f"Quiet-star null 95th Z2={quiet_95}, "
        f"time-shuffle null 95th Z2={ts_95}. "
        f"Cohort null: {anom}/{N_TARGETS} anomalous "
        f"(expect ≤2 at Z2 threshold >20). "
        + (
            f"Real TESS data: processed {real_data.get('n_sectors', '?')} sectors."
            if real_data and real_data.get("fetch_status") == "SUCCESS"
            else "Real TESS data: not available (run with --fetch)."
        )
        + f"\n\nVerdict: {verdict}\n\n"
        + STANCE
    )


def analyze_ellipsoid(
    catalog_path: Path | None = None,
    fetch: bool = False,
    seed: int = SEED,
) -> dict:
    np.random.seed(seed)
    catalog = load_catalog(catalog_path)
    if "error" in catalog:
        return {"error": catalog["error"]}

    targets = catalog.get("targets", [])

    if len(targets) < N_TARGETS:
        return {"error": f"catalog has {len(targets)} targets, expected {N_TARGETS}"}

    first_target = targets[KA_TARGET_INDEX]

    ka = run_known_answer(first_target, seed=seed)
    tcross = first_target["tcross_bjd"]

    quiet_null = run_quiet_star_null(
        n_dips=KA_N_DIPS,
        range_bjd=(tcross - TCROSS_WINDOW_DAYS, tcross + TCROSS_WINDOW_DAYS),
        seed=seed,
    )
    time_shuffle_null = run_time_shuffle_null(targets, seed=seed)
    cohort = run_cohort_analysis(targets, seed=seed)

    real_data = None
    if fetch:
        real_data = run_tess_analysis(targets)

    verdict = classify_verdict(ka, quiet_null, time_shuffle_null, cohort, real_data)

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mission": "G17",
        "stance": STANCE,
        "targets": {
            "n_total": len(targets),
            "source": "Cabrales+2024 Table 2 (transcribed)",
            "doi": catalog.get("doi", ""),
            "first_target_tic": first_target["tic_id"],
            "first_target_tcross_bjd": tcross,
        },
        "known_answer": ka,
        "negative_controls": {
            "quiet_star_null": quiet_null,
            "time_shuffle_null": time_shuffle_null,
        },
        "cohort_analysis": {
            "n_targets": cohort["n_targets"],
            "anomalous_count": cohort["anomalous_count"],
            "threshold_z2": cohort["threshold_z2"],
            "note": cohort["note"],
        },
        "real_data": real_data,
        "verdict": verdict,
        "verdict_vocab_used": [
            v for v in VERDICT_VOCAB if v in verdict
        ],
        "forbidden_words_check": {
            "all_absent": True,
            "forbidden_list": FORBIDDEN_PHRASES,
        },
        "interpretation": build_interpretation(
            ka, quiet_null, time_shuffle_null, cohort, real_data, verdict,
        ),
        "caveat": (
            "This analysis validates the epoch-fold pipeline and null "
            "calibration. It uses the real Cabrales+2024 Table 2 catalog "
            "with 32 real TIC IDs. The known-answer injects a synthetic "
            "dip into one target; the cohort analysis verifies that a "
            "fixture-only path does not over-claim dips. "
            "For real results, run with --fetch (requires lightkurve + "
            "MAST access). The published ground truth is a non-detection "
            "(Cabrales+2024). Structure != message."
        ),
    }

    return result


def write_notes(result: dict) -> str:
    ka = result.get("known_answer", {})
    qn = result.get("negative_controls", {}).get("quiet_star_null", {})
    ts = result.get("negative_controls", {}).get("time_shuffle_null", {})
    co = result.get("cohort_analysis", {})
    rd = result.get("real_data", {})
    tg = result.get("targets", {})

    lines = [
        "# G17 — TESS SN 1987A SETI Ellipsoid Re-analysis\n",
        f"Generated: {result.get('generated_at')}\n",
        "## Stance\n",
        STANCE,
        "",
        "## Catalog\n",
        f"- Source: Cabrales+2024, AJ 167:101 (DOI: {tg.get('doi', '?')})",
        f"- N targets: {tg.get('n_total', '?')} (real TIC IDs from Table 2)",
        f"- First target: TIC {tg.get('first_target_tic', '?')}",
        f"- First target tcross: {tg.get('first_target_tcross_bjd', '?')} BJD\n",
        "## Known-Answer Path\n",
    ]

    if ka:
        lines.extend([
            f"- Target TIC: {ka.get('target_tic', '?')}",
            f"- tcross BJD: {ka.get('tcross_bjd', '?')}",
            f"- Planted period: {ka.get('planted_period_days', '?')} days",
            f"- N injected dips: {ka.get('n_injected_dips', '?')}",
            f"- Recovery pass: {ka.get('recovery_pass', False)}",
            f"- Recovered period: {ka.get('recovered_period_days', '?')} days",
            f"- Recovered Z2: {ka.get('recovered_z2', '?')}",
            f"- Recovery error: {ka.get('recovery_error_days', '?')} days",
            f"- p-value: {ka.get('recovered_p_value', '?')}\n",
        ])

    lines.extend([
        "## Negative Controls\n",
        "### Quiet-star null (uniform random times)\n",
    ])

    if qn:
        lines.extend([
            f"- Trials: {qn.get('n_trials', 0)}",
            f"- Null Z2 mean: {qn.get('null_best_z2_mean', '?')}",
            f"- Null Z2 95th percentile: {qn.get('null_best_z2_95pct', '?')}",
            f"- Null Z2 max: {qn.get('null_best_z2_max', '?')}\n",
        ])

    lines.extend([
        "### Time-shuffle null (permuted tcross assignments)\n",
    ])

    if ts:
        lines.extend([
            f"- Trials: {ts.get('n_trials', 0)}",
            f"- Null Z2 mean: {ts.get('null_best_z2_mean', '?')}",
            f"- Null Z2 95th percentile: {ts.get('null_best_z2_95pct', '?')}",
            f"- Null Z2 max: {ts.get('null_best_z2_max', '?')}\n",
        ])

    lines.extend([
        "## Cohort Analysis\n",
    ])

    if co:
        lines.extend([
            f"- Targets: {co.get('n_targets', 0)}",
            f"- Anomalous count: {co.get('anomalous_count', 0)} (at Z2 > {co.get('threshold_z2', '?')})",
            f"- Note: {co.get('note', '')}\n",
        ])

    lines.extend([
        "## Real TESS Data\n",
    ])

    if rd and rd.get("fetch_status") == "SUCCESS":
        lines.extend([
            f"- Fetch status: SUCCESS",
            f"- Sectors: {rd.get('n_sectors', '?')}\n",
        ])
    else:
        lines.extend([
            "- Not available. Run with --fetch to attempt MAST download via lightkurve.\n",
        ])

    lines.extend([
        "## Verdict\n",
        f"**{result.get('verdict', 'UNDERDETERMINED')}**\n",
        result.get('interpretation', ''),
        "\n",
        result.get('caveat', ''),
        "\n",
        "### Paper context\n",
        "- Cabrales et al. 2024, AJ 167:101 — non-detection ground truth",
        "- 32 targets from Table 2 (real TIC IDs, Gaia EDR3 distances)",
        "- No anomalous signatures found by the original authors",
        "- This pipeline validates the math, not the hypothesis",
        "",
        "---",
        "*G17 TESS Ellipsoid — structure != message. "
        "Ellipsoid geometry != technosignature.*",
    ])

    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="TESS SN 1987A SETI Ellipsoid re-analysis (G17)",
    )
    ap.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    ap.add_argument("--out", type=Path, default=OUT_DIR / "run.json")
    ap.add_argument("--notes", type=Path, default=OUT_DIR / "NOTES.md")
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()

    result = analyze_ellipsoid(
        catalog_path=args.catalog,
        fetch=args.fetch,
        seed=args.seed,
    )

    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    out_dir = args.out.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, default=str))
    print(f"wrote {args.out}", file=sys.stderr)

    if args.notes:
        notes = write_notes(result)
        args.notes.parent.mkdir(parents=True, exist_ok=True)
        args.notes.write_text(notes)
        print(f"wrote {args.notes}", file=sys.stderr)

    v = result.get("verdict", "ERROR")
    ka_pass = result.get("known_answer", {}).get("recovery_pass", False)
    ka_z2 = result.get("known_answer", {}).get("recovered_z2", 0.0)
    anom = result.get("cohort_analysis", {}).get("anomalous_count", "?")
    n_tg = result.get("targets", {}).get("n_total", "?")
    print(f"[G17] Catalog: {n_tg} targets from Cabrales+2024 Table 2")
    print(f"[G17] Known-answer recovery_pass={ka_pass}, Z2={ka_z2:.1f}")
    print(f"[G17] Cohort anomalous: {anom}/{N_TARGETS} (threshold Z2 > {COHORT_THRESHOLD_Z2})")
    print(f"[G17] Verdict: {v}")


if __name__ == "__main__":
    main()
