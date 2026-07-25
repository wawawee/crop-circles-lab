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
        {"id": "G3", "owner": "Minimax→Ozma", "title": "Wow! 1977 sidereal beam-fit", "status": "done", "href": "outputs/radio/"},
        {"id": "G7", "owner": "Opencode", "title": "Gorafe megaliths orientation", "status": "done", "href": "outputs/gorafe/run.json"},
        {"id": "G4", "owner": "Opencode", "title": "Rongorongo 2D parallel passages", "status": "done", "href": "outputs/rongorongo/run.json"},
        {"id": "G-Amazon", "owner": "Ulfberht", "title": "Amazon earthworks Mode A", "status": "done", "href": "outputs/amazon/run.json"},
        {"id": "G-BLC1", "owner": "Ozma", "title": "BLC1 RFI known-answer", "status": "in_progress", "href": "tools/radio/blc1_fetcher.py"},
        {"id": "R1++", "owner": "Ozma", "title": "CHIME Cat 2 periods (16.35 d)", "status": "in_progress", "href": "tools/radio/cat2_fetcher.py"},
    ]
    domains = {
        "crop_circles": {"covered": True, "notes": "B1–B11 + signal + wheat closeout"},
        "phaistos": {"covered": True, "notes": "z≈−14 + period-3 refrain; metre yes, meaning no"},
        "linear_a": {"covered": True, "notes": "z≈−73 formulaic STRUCTURE; null validates; not decipherment"},
        "rongorongo": {"covered": True, "notes": "cond-entropy z≈−42.9 vs per-tablet shuffle; 33 cross-tablet parallels z≈+40.9; SEQUENCE_STRUCTURE, no decipherment"},
        "dna_epigenetics": {"covered": True, "notes": "bio_probe SARS + chr22 slice; biology ≠ message"},
        "uap_video": {"covered": True, "notes": "metadata poverty → g underdetermined"},
        "constants": {"covered": True, "notes": "first probe landed; verdict: structure, not signal"},
        "archaeoastronomy": {"covered": True, "notes": "lunar-phase probe vs uniform null — NO SIGNAL; Gorafe orientation STRUCTURE, astro UNDERDETERMINED"},
        "amazon": {"covered": True, "notes": "Mode A spatial point-process (PR #1 merged): STRUCTURE_ONLY clustering vs CSR, NN R=0.175 z=−46.7, Ripley L>CSR all radii; Mode B BLOCKED; not lost-civilisation"},
        "nazca": {"covered": False, "notes": "scout brief only"},
        "wow_frb": {"covered": True, "notes": "radio scaffold + honest CHIME/Vela fetchers (park when unreachable); G3 Wow beam-fit UNDERDETERMINED"},
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
