"""Parse archived BLT lab-report text into structured metrics (B5)."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _snippets(text: str, pattern: str, n: int = 3) -> list[str]:
    out = []
    for m in re.finditer(rf".{{0,50}}{pattern}.{{0,90}}", text, re.I):
        out.append(_clean(m.group(0)))
        if len(out) >= n:
            break
    return out


def parse_logan(text: str) -> dict:
    rec: dict = {
        "id": "logan-utah-1996",
        "lab_report": 79,
        "lab_code": None,
        "location": "Logan, Utah, USA",
        "crop": "barley (Hordeum vulgare)",
        "source_file": "data/reports/blt_wayback/logan_lab.txt",
        "metrics": {},
        "notes": [],
        "snippets": {},
    }
    m = re.search(r"Lab\s*Code:\s*([A-Z0-9\-]+)", text, re.I)
    if m:
        rec["lab_code"] = m.group(1)
    # Node expansion 15-65%
    m = re.search(r"Node expansion levels were found\s+in the range of\s+(\d+)\s*[-–]\s*(\d+)\s*%", text, re.I)
    if m:
        rec["metrics"]["node_expansion_pct_range"] = [int(m.group(1)), int(m.group(2))]
    m = re.search(r"Two circles\s*\(([\d.]+)['′]?\s+and\s+([\d.]+)['′]?\s*diam", text, re.I)
    if not m:
        m = re.search(r"large circle\s+([\d.]+)\s*ft.*?smaller\s+circle\s+([\d.]+)\s*-?ft", text, re.I | re.S)
    if m:
        rec["metrics"]["circle_diameters_ft"] = [float(m.group(1)), float(m.group(2))]
    m = re.search(r"Overall\s+length\s+approximately\s+([\d.]+)\s*ft", text, re.I)
    if m:
        rec["metrics"]["overall_length_ft"] = float(m.group(1))
    if re.search(r"Expulsion\s+cavit", text, re.I):
        rec["metrics"]["expulsion_cavities_reported"] = True
    if re.search(r"more radial than spiral", text, re.I):
        rec["notes"].append("crop_lay_more_radial_than_spiral")
    if re.search(r"triangular holes", text, re.I):
        rec["notes"].append("triangular_holes_in_centers")
    if re.search(r"microwave", text, re.I):
        rec["notes"].append("microwave_mentioned_in_lab_context")
    if re.search(r"light balls|BOL", text, re.I):
        rec["notes"].append("addendum_BOL_witness_account")
    rec["snippets"] = {
        "node_expansion": _snippets(text, r"Node expansion"),
        "expulsion": _snippets(text, r"Expulsion"),
        "microwave": _snippets(text, r"microwave"),
    }
    # Sample dates
    for key, pat in [
        ("date_discovered", r"Date\s+Discovered:\s*([^\n]+)"),
        ("date_sampled", r"Date\s+Sampled:\s*([^\n]+)"),
        ("date_occurred", r"Date\s+Occurred:\s*([^\n]+)"),
    ]:
        m = re.search(pat, text, re.I)
        if m:
            rec["metrics"][key] = _clean(m.group(1))[:80]
    return rec


def parse_edmonton(text: str) -> dict:
    rec: dict = {
        "id": "edmonton-1999",
        "lab_report": 122,
        "lab_code": None,
        "location": "Edmonton, Alberta, Canada",
        "crop": "barley (Hordeum vulgare), thistle-infested field",
        "source_file": "data/reports/blt_wayback/edmonton_labreport.txt",
        "metrics": {},
        "notes": [],
        "snippets": {},
    }
    m = re.search(r"Lab\s*Code:\s*([A-Z0-9\-]+)", text, re.I)
    if m:
        rec["lab_code"] = m.group(1)
    m = re.search(r"overall length\s+(\d+)\s*feet", text, re.I)
    if m:
        rec["metrics"]["overall_length_ft"] = int(m.group(1))
    m = re.search(r"(\d+)\s*-circle formation", text, re.I)
    if m:
        rec["metrics"]["circle_count"] = int(m.group(1))
    m = re.search(
        r"large\s*\(([\d.]+)['′]?\s*diameter\)\s*center circle with six adjacent smaller\s*\(from\s*([\d.]+)['′]?\s*to\s*([\d.]+)['′]?\s*diameter\)",
        text,
        re.I,
    )
    if m:
        rec["metrics"]["center_diameter_ft"] = float(m.group(1))
        rec["metrics"]["satellite_diameter_ft_range"] = [float(m.group(2)), float(m.group(3))]
    m = re.search(r"bent nodes.*?(\d+)\s*[-–]\s*(\d+)\s*degrees", text, re.I | re.S)
    if m:
        rec["metrics"]["bent_node_degrees_range"] = [int(m.group(1)), int(m.group(2))]
    if re.search(r"expulsion cavities", text, re.I):
        rec["metrics"]["expulsion_cavities_reported"] = True
    if re.search(r"apical node elongation", text, re.I):
        rec["metrics"]["apical_node_elongation_reported"] = True
    if re.search(r"counter-clockwise", text, re.I):
        rec["notes"].append("ccw_perimeter_ring_under_radial_lay")
    if re.search(r"magnetic particles", text, re.I):
        rec["notes"].append("magnetic_particles_in_soils")
    if re.search(r"cell.?phone|battery failure", text, re.I):
        rec["notes"].append("cellphone_battery_failure_inside")
    if re.search(r"no possibility\s+that this crop event was manually created", text, re.I):
        rec["notes"].append("authors_conclude_not_manual")
    if re.search(r"microwaves", text, re.I):
        rec["notes"].append("heating_component_probably_microwaves")
    # XRD / clay
    if re.search(r"XRD|clay", text, re.I):
        rec["notes"].append("clay_mineral_or_XRD_discussed")
    for key, pat in [
        ("date_discovered", r"Date\s+Discovered:\s*([^\n]+)"),
        ("date_sampled", r"Date\s+Sampled:\s*([^\n]+)"),
        ("date_occurred", r"Date\s+Occurred:\s*([^\n]+)"),
        ("funded_note", r"(Rockefeller|financial support)[^\n.]{0,120}"),
    ]:
        m = re.search(pat, text, re.I)
        if m:
            rec["metrics"][key] = _clean(m.group(0) if key == "funded_note" else m.group(1))[:120]
    rec["snippets"] = {
        "expulsion": _snippets(text, r"expulsion"),
        "magnetic": _snippets(text, r"magnetic"),
        "microwave": _snippets(text, r"microwave"),
        "manual": _snippets(text, r"manually created"),
    }
    return rec


def parse_semi_molten(text: str) -> dict:
    """Cherhill 1993 iron-glaze writeup (published page, not lab #104 HTML)."""
    rec = {
        "id": "cherhill-1993",
        "lab_report": None,
        "publication": "Semi-Molten Meteoric Iron Associated with a Crop Formation (BLT published page)",
        "location": "Cherhill, Wiltshire, UK",
        "source_file": "data/reports/blt_wayback/semi_molten_iron_blt.txt",
        "metrics": {},
        "notes": [],
        "snippets": {},
    }
    if not text:
        rec["notes"].append("source_text_missing")
        return rec
    m = re.search(r"two,?\s*([\d.]+)\s*m\s+counterclockwise", text, re.I)
    if m:
        rec["metrics"]["circle_diameter_m"] = float(m.group(1))
    if re.search(r"hematite\s*\(Fe\s*2\s*O\s*3\)|hematite \(Fe2O3\)", text, re.I) or "hematite" in text.lower():
        rec["metrics"]["oxides_claimed"] = ["hematite_Fe2O3", "magnetite_Fe3O4"]
    if re.search(r"magnetite", text, re.I):
        rec["notes"].append("magnetite_mentioned")
    if re.search(r"Perseid", text, re.I):
        rec["notes"].append("associated_with_Perseid_shower_timing_claim")
    if re.search(r"meteoritic|meteoric", text, re.I):
        rec["notes"].append("meteoritic_origin_claimed")
    if re.search(r"semi-molten|semimolten|glaze", text, re.I):
        rec["notes"].append("semi_molten_iron_glaze_claimed")
    rec["snippets"] = {
        "iron_glaze": _snippets(text, r"glaze|hematite|magnetite|meteor"),
        "formation": _snippets(text, r"Cherhill|1993"),
    }
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wayback", type=Path, default=Path("data/reports/blt_wayback"))
    ap.add_argument("--out-json", type=Path, default=Path("data/catalog/blt_lab_metrics.json"))
    ap.add_argument("--out-md", type=Path, default=Path("outputs/blt_lab_summary.md"))
    args = ap.parse_args()

    logan = parse_logan((args.wayback / "logan_lab.txt").read_text(encoding="utf-8", errors="replace"))
    edmonton = parse_edmonton(
        (args.wayback / "edmonton_labreport.txt").read_text(encoding="utf-8", errors="replace")
    )
    sm_path = args.wayback / "semi_molten_iron_blt.txt"
    cherhill = parse_semi_molten(sm_path.read_text(encoding="utf-8", errors="replace") if sm_path.exists() else "")

    payload = {
        "schema": "blt_lab_metrics.v1",
        "caveat": (
            "Extracted from Wayback HTML→text; percentages/ranges are as stated by BLT, "
            "not independently remeasured. CICAP and others have criticized methodology — "
            "treat as claims with citations, not established physics."
        ),
        "cases": [logan, edmonton, cherhill],
    }
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# BLT lab metrics summary (B5)",
        "",
        payload["caveat"],
        "",
    ]
    for case in payload["cases"]:
        lines.append(f"## {case['id']}")
        if case.get("lab_report"):
            lines.append(f"- Lab report: **#{case['lab_report']}** (`{case.get('lab_code')}`)")
        if case.get("publication"):
            lines.append(f"- Publication page: {case['publication']}")
        lines.append(f"- Source: `{case['source_file']}`")
        lines.append(f"- Location / crop: {case.get('location')} — {case.get('crop', 'n/a')}")
        lines.append("- Metrics:")
        for k, v in case.get("metrics", {}).items():
            lines.append(f"  - `{k}`: {v}")
        if case.get("notes"):
            lines.append("- Notes: " + ", ".join(case["notes"]))
        # one exemplar snippet
        for sk, sv in case.get("snippets", {}).items():
            if sv:
                lines.append(f"- Snippet ({sk}): “{sv[0]}”")
                break
        lines.append("")
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {args.out_json}")
    print(f"Wrote {args.out_md}")


if __name__ == "__main__":
    main()
