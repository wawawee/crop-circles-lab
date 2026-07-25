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
        {"id": "G1", "owner": "Opencode", "title": "Linear A symbolseq", "status": "done", "href": "outputs/linear_a/run.json"},
        {"id": "N1", "owner": "Minimax", "title": "DNA/RNA bio_probe", "status": "done", "href": "outputs/bio/sars_run.json"},
        {"id": "N2", "owner": "Opencode", "title": "UAP flight consistency", "status": "done", "href": "tools/uap/uap_flight_consistency.py"},
        {"id": "N3", "owner": "Hermes", "title": "Dimensionless constants", "status": "done", "href": "tools/astro/constants_probe.py"},
        {"id": "N4", "owner": "Opencode", "title": "Archaeoastronomy", "status": "done", "href": "tools/astro/archaeo_probe.py"},
        {"id": "N5", "owner": "Captain/Cursor", "title": "Mission dashboard", "status": "done", "href": "reports/mission_dashboard.html"},
        {"id": "R1", "owner": "Minimax", "title": "radio_probe + honest fetchers", "status": "done", "href": "outputs/radio/"},
        {"id": "W1", "owner": "Cursor", "title": "Wheat closeout scans", "status": "done", "href": "outputs/wheat_closeout/SUMMARY.md"},
    ]
    domains = {
        "crop_circles": {"covered": True, "notes": "B1–B11 + signal + wheat closeout"},
        "phaistos": {"covered": True, "notes": "z≈−14 + period-3 refrain; metre yes, meaning no"},
        "linear_a": {"covered": True, "notes": "z≈−73 formulaic STRUCTURE; null validates; not decipherment"},
        "dna_epigenetics": {"covered": True, "notes": "bio_probe SARS + chr22 slice; biology ≠ message"},
        "uap_video": {"covered": True, "notes": "metadata poverty → g underdetermined"},
        "constants": {"covered": True, "notes": "first probe landed; verdict: structure, not signal"},
        "archaeoastronomy": {"covered": True, "notes": "lunar-phase probe vs uniform null — NO SIGNAL"},
        "nazca": {"covered": False, "notes": "scout brief only"},
        "wow_frb": {"covered": True, "notes": "radio scaffold + honest CHIME/Vela fetchers (park when unreachable)"},
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
