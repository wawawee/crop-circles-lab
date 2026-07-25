#!/usr/bin/env python3
"""
vasco_missing.py — WEEKEND BACKLOG stub (Hecklefish Kimi #8 / board G13).

VASCO vanishing / missing stars. Plate-artifact nulls mandatory.
Do NOT deep-implement now (Captain / Kimi: save for weekend).

Usage:
    python tools/scripts/stubs/vasco_missing.py --help
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

STANCE = (
    "G13 VASCO — weekend backlog. No-signal prior. Plate artifacts first."
)


def main() -> None:
    ap = argparse.ArgumentParser(description="VASCO missing stars — backlog stub.")
    ap.add_argument("--dry-run", action="store_true", default=True)
    a = ap.parse_args()
    plan = {
        "status": "weekend_backlog",
        "mission_id": "G13",
        "stance": STANCE,
        "data": "Zenodo 10.5281/zenodo.14563521 (CC-BY) — verify before ingest",
        "reuse": ["tools/astro/astro_probe.py", "tools/ccat/spatial_report.py"],
        "todos": [
            "Ingest VASCO candidate catalogue subset",
            "Cluster on sky + galactic latitude tests",
            "Plate-artifact / emulsion nulls mandatory",
            "No Dyson-sphere claims without surviving nulls",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    print(json.dumps(plan, indent=2))


if __name__ == "__main__":
    main()
