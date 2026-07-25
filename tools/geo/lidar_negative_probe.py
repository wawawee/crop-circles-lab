#!/usr/bin/env python3
"""
lidar_negative_probe.py — STUB (Hecklefish Kimi #6).

Amazon Mode A already reports STRUCTURE_ONLY clustering on known geoglyph
points (G-Amazon). This stub plans a DEM / LiDAR “negative geoglyph” search:
places where canopy is flat but elevation shows human-planned berms.

Reuse: tools/geo/amazon_earthworks_probe.py + ccat adapted for DEM rasters.
Do not invent lost civilisations. STRUCTURE != MESSAGE.

Usage:
    python tools/geo/lidar_negative_probe.py --help
    python tools/geo/lidar_negative_probe.py --dry-run
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / "outputs" / "lidar_negative"

STANCE = (
    "LiDAR negative-geoglyph search is SCAFFOLD. Known Acre/Bolivia geoglyphs "
    "are training / known-answer only — not proof of thousands of hidden cities."
)


def main() -> None:
    ap = argparse.ArgumentParser(description="Amazon LiDAR negative-geoglyph stub.")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    plan = {
        "status": "scaffold",
        "stance": STANCE,
        "reuse": [
            "tools/geo/amazon_earthworks_probe.py",
            "tools/ccat/ccat.py (edge on DEM hillshade)",
            "data/amazon/",
        ],
        "todos": [
            "Acquire small open DEM tiles (Copernicus / OpenTopography) over known geoglyphs",
            "Hillshade → Canny/edge features; calibrate recovery of known berms",
            "CSR / scramble null on elevation residuals",
            "Only then scan adjacent tiles; report candidates with coordinates + null scores",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if a.dry_run:
        print(json.dumps(plan, indent=2))
        return
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "STUB.json").write_text(json.dumps(plan, indent=2))
    print(f"wrote {OUT / 'STUB.json'} (scaffold only)")


if __name__ == "__main__":
    main()
