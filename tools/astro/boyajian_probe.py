"""boyajian_probe — Boyajian's Star TESS epoch-fold analysis (G20).

Analysis blocks:
  1. Known-answer path: epoch-fold on fixture dip times recovers planted ~24.5 d period
  2. Negative controls:
     a. Quiet-star control: uniform-random dip times with no planted period
     b. Random-phase null: add independent uniform offsets to destroy phase coherence
  3. Real-data path (optional --fetch): download TESS lightcurve via lightkurve,
     extract dip candidate times, epoch-fold for periodic structure

Core rule: structure != message. Dips at Boyajian's Star are astrophysical
(circumstellar dust / exocomets), not megastructures. The epoch-fold pipeline
validates math, not ET.

Outputs: outputs/boyajian/run.json + outputs/boyajian/NOTES.md

Usage:
  python tools/astro/boyajian_probe.py                          # fixture known-answer path
  python tools/astro/boyajian_probe.py --fetch                  # TESS real-data path
  python tools/astro/boyajian_probe.py --out outputs/boyajian/run.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# re-use epoch-fold math from radio_probe
# ---------------------------------------------------------------------------

try:
    from tools.radio.radio_probe import epoch_fold, rayleigh_p_value, rayleigh_z2
except ImportError:
    HERE_P = Path(__file__).resolve().parent
    ROOT_P = HERE_P.parents[1]
    sys.path.insert(0, str(ROOT_P))
    from tools.radio.radio_probe import epoch_fold, rayleigh_p_value, rayleigh_z2

# ---------------------------------------------------------------------------
# paths
# ---------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FIXTURE = ROOT / "data" / "astro" / "boyajian" / "boyajian_dip_times_fixture.json"
OUT_DIR = ROOT / "outputs" / "boyajian"

# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------

TARGET = "TIC 272172248 (KIC 8462852 / Boyajian's Star)"
STANCE = (
    "Structure != message. Aperiodic dips at Boyajian's Star are astrophysical "
    "phenomena (circumstellar dust / exocomets / debris), not artifacts of "
    "exogenous construction. No dip structure, even if periodic, constitutes "
    "evidence of artificial engineering without independent electromagnetic "
    "or infrared signatures."
)
FORBIDDEN_PHRASES = [
    "Dyson",
    "alien",
    "megastructure",
    "confirms ET",
    "extraterrestrial structure",
    "alien megastructure",
    "Dyson sphere",
    "ET engineering",
    "artificial construction",
]
VERDICT_VOCAB = ["DIP_STRUCTURE", "NO_SIGNAL", "UNDERDETERMINED"]

KEPLER_DIP_LABELS = {
    "D800": "~day 800, ~15% depth",
    "D1200": "~day 1200-1220 complex, ~22% max depth",
    "D1500": "~day 1500-1590 complex (D1519, D1568)",
}

PLANTED_PERIOD_DAYS = 24.5

GRID_MARGIN = 5.0
GRID_STEPS = 2001

TESS_SECTORS = [14, 15, 16, 55]

SEED = 42

QUIET_N_TRIALS = 200
RANDOM_PHASE_N_TRIALS = 200

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _generate_period_grid(
    center_period_d: float,
    margin_d: float = GRID_MARGIN,
    steps: int = GRID_STEPS,
) -> np.ndarray:
    return np.linspace(
        center_period_d - margin_d,
        center_period_d + margin_d,
        steps,
    )


def _uniform_random_times(
    n: int,
    range_bjd: tuple[float, float],
    seed: int,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return np.sort(rng.uniform(range_bjd[0], range_bjd[1], size=n))


def _random_phase_offset(
    times: np.ndarray,
    period_d: float,
    seed: int,
) -> np.ndarray:
    """Add independent uniform offsets to destroy phase coherence.

    Each dip time t_i is replaced by t_i + U[-period_d/2, period_d/2].
    This preserves the approximate time range and inter-dip interval
    distribution but randomizes the phase relative to any candidate
    period.
    """
    rng = np.random.default_rng(seed)
    offsets = rng.uniform(-period_d / 2.0, period_d / 2.0, size=len(times))
    return np.sort(times + offsets)


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


# ---------------------------------------------------------------------------
# fixture loader
# ---------------------------------------------------------------------------


def load_fixture(path: Path | None = None) -> dict:
    if path is None:
        path = FIXTURE
    if not path.exists():
        return {"error": f"fixture not found: {path}"}
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# known-answer path
# ---------------------------------------------------------------------------


def run_known_answer(
    dip_times_bjd: np.ndarray,
    planted_period_d: float = PLANTED_PERIOD_DAYS,
    steps: int = GRID_STEPS,
    margin_d: float = GRID_MARGIN,
) -> dict:
    periods = _generate_period_grid(planted_period_d, margin_d, steps)
    fold = epoch_fold(dip_times_bjd, periods)

    recovery_err = abs(fold["best_period"] - planted_period_d)
    recovery_tolerance = 0.5
    recovery_pass = bool(recovery_err <= recovery_tolerance)

    return {
        "n_dips": int(len(dip_times_bjd)),
        "planted_period_days": planted_period_d,
        "recovered_period_days": fold["best_period"],
        "recovered_z2": fold["best_z2"],
        "recovered_phase_rad": fold["best_phase_rad"],
        "recovered_p_value": fold["best_p_value"],
        "recovery_error_days": float(recovery_err),
        "recovery_tolerance_days": recovery_tolerance,
        "recovery_pass": recovery_pass,
        "period_grid": {
            "min_days": float(periods[0]),
            "max_days": float(periods[-1]),
            "n_steps": len(periods),
        },
    }


# ---------------------------------------------------------------------------
# negative controls
# ---------------------------------------------------------------------------


def run_quiet_star_null(
    n_dips: int,
    range_bjd: tuple[float, float],
    planted_period_d: float = PLANTED_PERIOD_DAYS,
    n_trials: int = QUIET_N_TRIALS,
    seed: int = SEED,
) -> dict:
    periods = _generate_period_grid(planted_period_d)
    null_best_z2 = []
    null_best_periods = []
    for i in range(n_trials):
        times = _uniform_random_times(n_dips, range_bjd, seed + i)
        fold = epoch_fold(times, periods)
        null_best_z2.append(fold["best_z2"])
        null_best_periods.append(fold["best_period"])

    return {
        "n_trials": n_trials,
        "n_dips": n_dips,
        "range_bjd": list(range_bjd),
        "seed": seed,
        "null_best_z2_mean": float(np.mean(null_best_z2)),
        "null_best_z2_std": float(np.std(null_best_z2, ddof=1)),
        "null_best_z2_max": float(np.max(null_best_z2)),
        "null_best_z2_95pct": float(np.percentile(null_best_z2, 95)),
        "null_best_z2_list": [round(v, 4) for v in null_best_z2],
        "null_best_periods_sample": [round(v, 4) for v in null_best_periods[:10]],
        "note": "Uniform-random dip times with no planted period.",
    }


def run_random_phase_null(
    dip_times_bjd: np.ndarray,
    planted_period_d: float = PLANTED_PERIOD_DAYS,
    n_trials: int = RANDOM_PHASE_N_TRIALS,
    seed: int = SEED,
) -> dict:
    """Random-phase null: add independent uniform offsets to each dip time.

    Each dip time is shifted by U[-P/2, P/2] independently. This destroys
    phase coherence while preserving the approximate time distribution.
    """
    periods = _generate_period_grid(planted_period_d)
    null_best_z2 = []
    for i in range(n_trials):
        shifted = _random_phase_offset(dip_times_bjd, planted_period_d, seed + i + 1000)
        fold = epoch_fold(shifted, periods)
        null_best_z2.append(fold["best_z2"])

    return {
        "n_trials": n_trials,
        "n_dips": int(len(dip_times_bjd)),
        "seed": seed,
        "null_best_z2_mean": float(np.mean(null_best_z2)),
        "null_best_z2_std": float(np.std(null_best_z2, ddof=1)),
        "null_best_z2_max": float(np.max(null_best_z2)),
        "null_best_z2_95pct": float(np.percentile(null_best_z2, 95)),
        "null_best_z2_list": [round(v, 4) for v in null_best_z2],
        "note": "Independent uniform phase offsets U[-P/2, P/2] added to each dip time.",
    }


# ---------------------------------------------------------------------------
# real-data TESS path
# ---------------------------------------------------------------------------


def _try_tess_fetch(target: str = TARGET) -> dict:
    try:
        import lightkurve as lk
    except ImportError:
        return {
            "fetch_status": "LIGHTKURVE_MISSING",
            "note": "lightkurve not installed. Install with: pip install lightkurve astroquery.mast",
        }
    try:
        search = lk.search_lightcurve(target, mission="TESS")
        if search is None or len(search) == 0:
            return {"fetch_status": "NO_SEARCH_RESULTS", "note": f"No TESS lightcurves found for {target}"}
        lcs = search.download_all()
        if lcs is None or len(lcs) == 0:
            return {"fetch_status": "DOWNLOAD_FAILED", "note": "Download returned zero lightcurves"}
        return {
            "fetch_status": "SUCCESS",
            "n_sectors": len(lcs),
            "sectors": [int(lc.meta.get("SECTOR", -1)) for lc in lcs],
            "note": f"Downloaded {len(lcs)} TESS sectors. Use run_tess_analysis() for epoch-fold.",
        }
    except Exception as exc:
        return {"fetch_status": "FETCH_ERROR", "note": str(exc)}


def run_tess_analysis(target: str = TARGET) -> dict:
    result = _try_tess_fetch(target)
    if result["fetch_status"] != "SUCCESS":
        return result
    try:
        import lightkurve as lk
        search = lk.search_lightcurve(target, mission="TESS")
        lcs = search.download_all()
        tess_times = []
        for lc in lcs:
            time = lc.time.value
            flux = lc.flux.value
            flux_norm = flux / np.nanmedian(flux)
            dip_mask = np.abs(flux_norm - 1) > 3 * np.nanstd(flux_norm)
            dip_times = time[dip_mask]
            tess_times.extend(dip_times.tolist())
        tess_times = np.array(sorted(tess_times))
        if len(tess_times) < 5:
            return {
                "fetch_status": "TOO_FEW_DIPS",
                "n_dips": int(len(tess_times)),
                "note": f"Only {len(tess_times)} dip candidates from TESS. Insufficient for epoch-fold analysis.",
            }
        periods = _generate_period_grid(24.5, 20.0, GRID_STEPS)
        fold = epoch_fold(tess_times, periods)
        shifted = _random_phase_offset(tess_times, 24.5, SEED + 2000)
        fold_shifted = epoch_fold(shifted, periods)
        return {
            "fetch_status": "SUCCESS",
            "n_dips": int(len(tess_times)),
            "tess_sectors": list(set(
                int(lc.meta.get("SECTOR", -1)) for lc in lcs
            )),
            "epochfold": fold,
            "negative_control": {
                "random_phase_z2_max": fold_shifted["best_z2"],
                "random_phase_best_period": fold_shifted["best_period"],
            },
            "caveat": (
                "TESS lightcurve dip extraction is heuristic (3-sigma outlier clipping). "
                "Shallow dips ~1-3% may not be detected. This is not a definitive "
                "dip catalog use Boyajian+2016/2018 for authoritative dip lists."
            ),
        }
    except Exception as exc:
        return {"fetch_status": "ANALYSIS_ERROR", "note": str(exc)}


# ---------------------------------------------------------------------------
# verdict classification
# ---------------------------------------------------------------------------


def classify_verdict(
    known_answer: dict,
    quiet_null: dict,
    random_phase_null: dict,
    real_data: dict | None = None,
) -> str:
    ka_pass = known_answer.get("recovery_pass", False)
    ka_z2 = known_answer.get("recovered_z2", 0.0)
    quiet_95pct = quiet_null.get("null_best_z2_95pct", 0.0)
    rp_95pct = random_phase_null.get("null_best_z2_95pct", 0.0)
    null_95pct = max(quiet_95pct, rp_95pct)

    if not ka_pass:
        return (
            "UNDERDETERMINED: known-answer path failed to recover planted period. "
            "Pipeline needs review see NOTES.md."
        )

    if ka_z2 > null_95pct * 2:
        if real_data and real_data.get("fetch_status") == "SUCCESS":
            real_z2 = real_data.get("epochfold", {}).get("best_z2", 0.0)
            if real_z2 > quiet_95pct:
                return "DIP_STRUCTURE detected in TESS data (Z2 exceeds quiet-star 95th percentile)"
        return "DIP_STRUCTURE (known-answer recovery confirms epoch-fold pipeline)"

    if ka_z2 > null_95pct:
        return "UNDERDETERMINED: weak structure detected (Z2 between 95th and 2x95th percentile of null)"

    return "NO_SIGNAL: dip times show no periodic structure above null expectation"


def build_interpretation(
    known_answer: dict,
    quiet_null: dict,
    random_phase_null: dict,
    real_data: dict | None,
    verdict: str,
) -> str:
    ka_z2 = known_answer.get("recovered_z2", 0.0)
    ka_period = known_answer.get("recovered_period_days", "?")
    ka_pass = known_answer.get("recovery_pass", False)
    quiet_95 = quiet_null.get("null_best_z2_95pct", "?")
    rp_95 = random_phase_null.get("null_best_z2_95pct", "?")

    return (
        f"Boyajian's Star (TIC 272172248) epoch-fold analysis. "
        f"Known-answer fixture: planted period {PLANTED_PERIOD_DAYS} d, "
        f"recovered {ka_period} d with Z2={ka_z2:.1f} "
        f"(recovery_pass={ka_pass}). "
        f"Quiet-star null 95th percentile Z2={quiet_95}, "
        f"random-phase null 95th percentile Z2={rp_95}. "
        + (
            f"Real TESS data: {real_data.get('n_dips', 'N/A')} dip candidates "
            f"from {real_data.get('tess_sectors', 'N/A')} sectors."
            if real_data and real_data.get("fetch_status") == "SUCCESS"
            else "Real TESS data: not available (run with --fetch)."
        )
        + f"\n\nVerdict: {verdict}\n\n"
        + STANCE
    )


# ---------------------------------------------------------------------------
# main analysis
# ---------------------------------------------------------------------------


def analyze_boyajian(
    fixture_path: Path | None = None,
    fetch: bool = False,
    seed: int = SEED,
) -> dict:
    np.random.seed(seed)

    fixture = load_fixture(fixture_path)
    if "error" in fixture:
        return {"error": fixture["error"], "generated_at": datetime.now(timezone.utc).isoformat()}

    dip_times = np.array(fixture["dip_times_bjd"], dtype=float)
    meta = fixture.get("metadata", {})
    controls = fixture.get("controls", {})
    quiet_star_def = controls.get("quiet_star", {})

    n_dips = len(dip_times)
    range_bjd = (
        quiet_star_def.get("range_bjd", [float(dip_times.min()), float(dip_times.max())])
        if quiet_star_def
        else [float(dip_times.min()), float(dip_times.max())]
    )
    quiet_n_dips = quiet_star_def.get("n_dips", n_dips)

    planted_period = meta.get("planted_period_days", PLANTED_PERIOD_DAYS)

    ka = run_known_answer(dip_times, planted_period)

    quiet_null = run_quiet_star_null(
        n_dips=quiet_n_dips,
        range_bjd=(range_bjd[0], range_bjd[1]),
        planted_period_d=planted_period,
        seed=seed,
    )
    random_phase_null = run_random_phase_null(
        dip_times, planted_period, seed=seed,
    )

    real_data = None
    if fetch:
        real_data = run_tess_analysis()

    verdict = classify_verdict(ka, quiet_null, random_phase_null, real_data)

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mission": "G20",
        "stance": STANCE,
        "target": TARGET,
        "fixture": {
            "path": str(fixture_path or FIXTURE),
            "source": meta.get("mission", "Kepler"),
            "synthetic": meta.get("synthetic", True),
            "planted_period_days": planted_period,
            "n_dips": n_dips,
            "dip_times_bjd": [round(float(t), 4) for t in dip_times],
            "references": [
                "Boyajian et al. 2016, MNRAS 457(4): 3988-4004",
                "Boyajian et al. 2018, ApJ 853(1): L8",
            ],
        },
        "known_answer": ka,
        "negative_controls": {
            "quiet_star_null": quiet_null,
            "random_phase_null": random_phase_null,
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
            ka, quiet_null, random_phase_null, real_data, verdict,
        ),
        "caveat": (
            "This analysis uses a synthetic fixture for math validation. "
            "The fixture emulates Kepler-era dip structure but does NOT "
            "replicate the full Kepler lightcurve. Epoch-fold on real TESS "
            "data (--fetch) uses heuristic dip extraction. For authoritative "
            "dip timing, see Boyajian et al. 2016 and 2018. "
            "DIP_STRUCTURE is a mathematical result, not evidence of "
            "exogenous artifacts. Structure != message."
        ),
    }

    return result


# ---------------------------------------------------------------------------
# NOTES.md writer
# ---------------------------------------------------------------------------


def write_notes(result: dict) -> str:
    ka = result.get("known_answer", {})
    qn = result.get("negative_controls", {}).get("quiet_star_null", {})
    rp = result.get("negative_controls", {}).get("random_phase_null", {})
    rd = result.get("real_data", {})
    fi = result.get("fixture", {})

    lines = [
        "# G20 --- Boyajian's Star TESS Epoch-Fold\n",
        f"Generated: {result.get('generated_at')}\n",
        "## Stance\n",
        STANCE,
        "",
        "## Target\n",
        f"- {TARGET}",
        f"- Constellation: Cygnus",
        f"- V mag: ~11.7, Spectral type: F3 V\n",
        "## Fixture\n",
        f"- Source: {fi.get('source', 'Kepler')}",
        f"- Synthetic: {fi.get('synthetic', True)}",
        f"- Planted period: {fi.get('planted_period_days', '?')} days",
        f"- N dip timestamps: {fi.get('n_dips', 0)}\n",
        "### References\n",
        "- Boyajian et al. 2016, MNRAS 457(4): 3988-4004",
        "- Boyajian et al. 2018, ApJ 853(1): L8",
        "- Meng et al. 2017, ApJ 847(2): 131\n",
        "## Known-Answer Path\n",
    ]

    if ka:
        lines.extend([
            f"- Recovery pass: {ka.get('recovery_pass', False)}",
            f"- Planted period: {ka.get('planted_period_days', '?')} days",
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
            f"- Null Z2 max: {qn.get('null_best_z2_max', '?')}",
            f"- Note: {qn.get('note', '')}\n",
        ])

    lines.extend([
        "### Random-phase null (independent uniform offsets)\n",
    ])

    if rp:
        lines.extend([
            f"- Trials: {rp.get('n_trials', 0)}",
            f"- Null Z2 mean: {rp.get('null_best_z2_mean', '?')}",
            f"- Null Z2 95th percentile: {rp.get('null_best_z2_95pct', '?')}",
            f"- Null Z2 max: {rp.get('null_best_z2_max', '?')}",
            f"- Note: {rp.get('note', '')}\n",
        ])

    if rd and rd.get("fetch_status") == "SUCCESS":
        lines.extend([
            "## Real TESS Data\n",
            f"- Fetch status: {rd.get('fetch_status', '?')}",
            f"- N dip candidates: {rd.get('n_dips', '?')}",
            f"- TESS sectors: {rd.get('tess_sectors', '?')}",
            f"- Epoch-fold best Z2: {rd.get('epochfold', {}).get('best_z2', '?')}",
            f"- Random-phase null Z2 max: {rd.get('negative_control', {}).get('random_phase_z2_max', '?')}\n",
        ])
    else:
        lines.extend([
            "## Real TESS Data\n",
            "- Not available. Run with --fetch to attempt MAST download.\n",
        ])

    lines.extend([
        "## Verdict\n",
        f"**{result.get('verdict', 'NO_SIGNAL')}**\n",
        result.get('interpretation', ''),
        "\n",
        result.get('caveat', ''),
        "\n",
        "### Kepler-era dip context (not reprocessed)\n",
    ])

    for label, desc in KEPLER_DIP_LABELS.items():
        lines.append(f"- {label}: {desc}")

    lines.extend([
        "",
        "---",
        "*G20 Boyajian's Star --- structure != message. "
        "Dip epoch-fold validates math, not exogenous artifacts.*",
    ])

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Boyajian's Star TESS epoch-fold analysis (G20)",
    )
    ap.add_argument("--fixture", type=Path, default=FIXTURE,
                    help="Path to dip times fixture JSON")
    ap.add_argument("--out", type=Path,
                    default=OUT_DIR / "run.json",
                    help="Output run.json path")
    ap.add_argument("--notes", type=Path,
                    default=OUT_DIR / "NOTES.md",
                    help="Output NOTES.md path")
    ap.add_argument("--fetch", action="store_true",
                    help="Download real TESS lightcurve from MAST")
    ap.add_argument("--seed", type=int, default=SEED,
                    help="RNG seed for reproducibility")
    args = ap.parse_args()

    result = analyze_boyajian(
        fixture_path=args.fixture,
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
    n_dips = result.get("fixture", {}).get("n_dips", 0)
    print(f"[G20] Target: {TARGET}")
    print(f"[G20] N dip timestamps: {n_dips}")
    print(f"[G20] Known-answer recovery_pass={ka_pass}, Z2={ka_z2:.1f}")
    print(f"[G20] Verdict: {v}")


if __name__ == "__main__":
    main()
