#!/usr/bin/env python3
"""
alpha_variation_probe.py — WEEKEND BACKLOG stub (Hecklefish Kimi #7).

Fine-structure constant α directional variation (quasar absorption).
Do NOT implement deeply until astro/feature_table weekend slot.

Usage:
    python tools/scripts/stubs/alpha_variation_probe.py --help
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "outputs" / "alpha_variation"

STANCE = "Weekend backlog. Instrument systematics null before any dipole claim."


def main() -> None:
    ap = argparse.ArgumentParser(description="α variation — weekend backlog stub.")
    ap.add_argument("--dry-run", action="store_true", default=True)
    a = ap.parse_args()
    plan = {
        "status": "weekend_backlog",
        "stance": STANCE,
        "reuse": ["tools/ccat/feature_table.py", "tools/ccat/spatial_report.py"],
        "todos": [
            "Curate published Δα/α measurements 1999–2024 with sky coords",
            "Fit dipole vs instrument/time systematics",
            "Negative: scramble directions; scramble epochs",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    print(json.dumps(plan, indent=2))


if __name__ == "__main__":
    main()
