#!/usr/bin/env python3
"""
rongorongo_refrain.py — STUB (Hecklefish Kimi #3).

G4 already landed parallel passages in tools/scripts/rongorongo_probe.py
(cross-tablet formulae, z≈+40.9). This stub is the *calendar / refrain*
follow-up: correlate repeated ≥4-glyph runs with Easter Island calendrical
markers if/when a dated tablet chronology is available.

Not a decipherment tool. STRUCTURE != MESSAGE.

Usage:
    python tools/scripts/rongorongo_refrain.py --help
    python tools/scripts/rongorongo_refrain.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / "outputs" / "rongorongo_refrain"

STANCE = (
    "Rongorongo refrain calendar correlation is SCAFFOLD ONLY. "
    "Reuse G4 parallel passages; do not claim ritual calendars without dates."
)


def main() -> None:
    ap = argparse.ArgumentParser(description="Rongorongo refrain×calendar stub.")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--delegate-g4", action="store_true",
                    help="Print pointer to existing G4 probe and exit 0.")
    a = ap.parse_args()

    plan = {
        "status": "scaffold",
        "stance": STANCE,
        "reuse": "tools/scripts/rongorongo_probe.py (G4 parallel passages)",
        "todos": [
            "Load G4 outputs/rongorongo/run.json parallel_passages.top_cross_tablet",
            "Filter runs with length ≥ 4 glyphs recurring on ≥ 2 tablets",
            "If dated tablet metadata appears, test calendar clustering vs shuffle dates",
            "Negative control: random assignment of the same runs to tablets",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if a.delegate_g4:
        print("Delegate to: python tools/scripts/rongorongo_probe.py")
        print(json.dumps(plan, indent=2))
        return
    if a.dry_run:
        print(json.dumps(plan, indent=2))
        return
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "STUB.json").write_text(json.dumps(plan, indent=2))
    print(f"wrote {OUT / 'STUB.json'} (scaffold only)")


if __name__ == "__main__":
    main()
