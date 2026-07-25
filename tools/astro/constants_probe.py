"""constants_probe — dimensionless constants vs diatonic / random controls (N3).

Uses forensics/ratios nearest_diatonic on log-ratios between constants.
Negative control: random values with similar log10 magnitudes.

CLI:
  python tools/astro/constants_probe.py --out outputs/constants/run.json
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "forensics"))
import ratios as R  # noqa: E402

# Representative dimensionless / nearly-dimensionless numbers (CODATA-ish / cosmology-ish).
# Values are for pattern hunting + controls — not a claim of deep law.
CONSTANTS = {
    "alpha_fine_structure": 1 / 137.035999084,
    "mu_proton_electron_mass": 1836.15267343,
    "proton_electron_charge_abs": 1.0,  # trivial dimensionless by construction
    "approx_dirac_large_1e40": 1e40,  # placeholder scale Dirac discussed
    "approx_edington_1e39": 1e39,
    "omega_matter_planck18": 0.315,
    "omega_lambda_planck18": 0.685,
    "n_e_fine_inv": 137.035999084,
}


def pairwise_log_ratios(const: dict[str, float]) -> list[dict]:
    names = list(const.keys())
    rows = []
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            va, vb = const[a], const[b]
            if va <= 0 or vb <= 0:
                continue
            ratio = va / vb
            log10 = math.log10(ratio)
            # map |log10| fractional part style into a positive ratio near music range
            # Use max/min so ratio >= 1 for diatonic nearest
            hi, lo = max(va, vb), min(va, vb)
            r = hi / lo
            # compress huge ratios into octave-folded number in [1,2) for diatonic compare
            while r >= 2:
                r /= 2
            while r < 1:
                r *= 2
            note = R.nearest_diatonic(r)
            rows.append(
                {
                    "a": a,
                    "b": b,
                    "raw_ratio": ratio,
                    "log10_ratio": round(log10, 4),
                    "octave_folded": round(r, 6),
                    "nearest_diatonic": note.note if hasattr(note, "note") else str(note),
                    "diatonic_detail": str(note),
                }
            )
    return rows


def random_control(seed: int = 0) -> dict[str, float]:
    rng = random.Random(seed)
    # same count, log-uniform over similar decades
    out = {}
    for i, name in enumerate(CONSTANTS):
        # magnitudes from 1e-3 to 1e40
        exp = rng.uniform(-3, 40)
        out[f"rand_{i}_{name[:6]}"] = 10 ** exp
    return out


def analyze() -> dict:
    real = pairwise_log_ratios(CONSTANTS)
    ctrl_c = random_control(7)
    ctrl = pairwise_log_ratios(ctrl_c)

    def note_hist(rows):
        from collections import Counter
        return dict(Counter(r["nearest_diatonic"] for r in rows))

    return {
        "constants": CONSTANTS,
        "pairwise_real": real,
        "pairwise_random_control": ctrl,
        "diatonic_hist_real": note_hist(real),
        "diatonic_hist_control": note_hist(ctrl),
        "interpretation": (
            "If real hist ≈ control hist, Dirac-style 'musical' coupling is not evidenced "
            "beyond numerology. Report histograms; do not claim physics."
        ),
        "stance": "N3 scaffold — Hermes may extend constant set + proper CODATA citations.",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("outputs/constants/run.json"))
    args = ap.parse_args()
    result = analyze()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2))
    print(json.dumps({k: result[k] for k in ("diatonic_hist_real", "diatonic_hist_control", "interpretation")}, indent=2))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
