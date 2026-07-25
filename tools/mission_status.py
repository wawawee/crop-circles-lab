#!/usr/bin/env python3
"""Regenerate data/catalog/mission_status.json for the Captain dashboard."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    outputs = []
    for p in sorted((root / "outputs").rglob("*.json")):
        if "local_prep" in p.parts:
            continue
        outputs.append(
            {
                "path": str(p.relative_to(root)).replace("\\", "/"),
                "name": p.name,
                "kb": round(p.stat().st_size / 1024, 1),
            }
        )

    missions = [
        {"id": "N0", "owner": "Hyper", "title": "Phaistos symbolseq", "status": "done", "href": "outputs/phaistos_analysis.json"},
        {"id": "N1", "owner": "Hyper", "title": "DNA/RNA bio_probe", "status": "scaffolded", "href": "tools/bio/bio_probe.py"},
        {"id": "N2", "owner": "Opencode", "title": "UAP flight consistency", "status": "scaffolded", "href": "tools/uap/uap_flight_consistency.py"},
        {"id": "N3", "owner": "Hermes", "title": "Dimensionless constants", "status": "scaffolded", "href": "tools/astro/constants_probe.py"},
        {"id": "N4", "owner": "Kimi", "title": "Archaeoastronomy", "status": "scaffolded", "href": "tools/astro/astro_probe.py"},
        {"id": "N5", "owner": "Captain/Cursor", "title": "Mission dashboard", "status": "done", "href": "reports/mission_dashboard.html"},
        {"id": "W1", "owner": "Cursor", "title": "Wheat closeout scans", "status": "done", "href": "outputs/wheat_closeout/SUMMARY.md"},
    ]
    domains = {
        "crop_circles": {"covered": True, "notes": "B1–B9 + signal + wheat closeout"},
        "phaistos": {"covered": True, "notes": "symbolseq structured vs shuffle"},
        "dna_epigenetics": {"covered": False, "notes": "scaffold only"},
        "uap_video": {"covered": False, "notes": "needs official media"},
        "constants": {"covered": False, "notes": "scaffold demo runnable"},
        "archaeoastronomy": {"covered": False, "notes": "scaffold + lunar on formations.csv"},
        "nazca": {"covered": False, "notes": "scout brief only"},
        "wow_frb": {"covered": False, "notes": "scout brief only"},
    }
    status = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "missions": missions,
        "domains": domains,
        "outputs": outputs,
        "n_outputs": len(outputs),
    }
    out = root / "data" / "catalog" / "mission_status.json"
    out.write_text(json.dumps(status, indent=2))
    # Embed for file:// dashboard
    embed = root / "reports" / "mission_status.embed.js"
    embed.write_text("window.MISSION_STATUS = " + json.dumps(status) + ";\n")
    print(f"wrote {out} and {embed} ({len(outputs)} outputs)")


if __name__ == "__main__":
    main()
