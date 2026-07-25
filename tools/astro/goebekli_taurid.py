#!/usr/bin/env python3
"""
goebekli_taurid.py — STUB (Hecklefish Kimi #5).

Sweatman & Tsikritsis (2017) claim Pillar 43 (Vulture Stone) encodes a
~10 950 BCE Taurid / Younger Dryas comet event. This stub wires the plan
onto tools/astro/astro_probe.py + random-date negative controls.

STRUCTURE != MESSAGE. Apophenia is the null.

Usage:
    python tools/astro/goebekli_taurid.py --help
    python tools/astro/goebekli_taurid.py --dry-run
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / "outputs" / "goebekli"

STANCE = (
    "Göbekli Tepe × Taurid claim-under-test. Scaffold only. "
    "Match-on-random-dates must fail before any positive claim."
)


def main() -> None:
    ap = argparse.ArgumentParser(description="Göbekli Tepe × Taurid stub.")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    plan = {
        "status": "scaffold",
        "stance": STANCE,
        "claim_under_test": "Sweatman & Tsikritsis 2017 Pillar 43 → 10950 BCE Taurid",
        "reuse": ["tools/astro/astro_probe.py", "tools/astro/archaeo_probe.py"],
        "todos": [
            "Encode Pillar 43 animal→asterism mapping as an explicit JSON hypothesis",
            "skyfield / astro_probe: Taurid radiant + solstice geometry @ ~10950 BCE",
            "Negative: same mapping scored on N random BCE dates (uniform / seasonal)",
            "If random dates match equally → NO_SIGNAL (apophenia)",
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
