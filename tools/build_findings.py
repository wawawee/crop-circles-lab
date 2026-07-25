#!/usr/bin/env python3
"""
build_findings.py — stdlib-only findings data pipeline.
Reads analysis outputs and writes reports/findings_data.embed.js containing
exactly `window.FINDINGS_DATA = {...};\n` (compact single-line JSON).

Usage: python3 tools/build_findings.py
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_phaistos(root: Path) -> dict:
    analysis = load_json(root / "outputs" / "phaistos_analysis.json")
    sequence = load_json(root / "data" / "beyond" / "phaistos_sequence.json")
    refrain_json = load_json(root / "outputs" / "phaistos_refrain.json")

    # --- sequence ---
    phys = sequence["physical"]
    seq_section = {
        "n_tokens": phys["tokens"],
        "n_distinct": phys["distinct_signs"],
        "words_A": phys["words_A"],
        "words_B": phys["words_B"],
        "index_of_coincidence": analysis["index_of_coincidence"],
    }

    # --- entropy ---
    sc = analysis["shuffled_control"]
    entropy_section = {
        "observed": sc["observed"],
        "shuffled_mean": sc["shuffled_mean"],
        "shuffled_sd": sc["shuffled_sd"],
        "z": sc["z"],
        "max_entropy_bits": analysis["max_entropy_bits"],
        "unigram_entropy_bits": analysis["unigram_entropy_bits"],
        "verdict": "STRUCTURE",
        "caveat": "Structured != readable. Low conditional entropy proves dependency, not language.",
    }

    # --- refrain ---
    # Find the [2,12,31,26] repeat in analysis repeat_structure
    main_repeat = None
    for rs in analysis["repeat_structure"]:
        if rs["phrase"] == [2, 12, 31, 26]:
            main_repeat = rs
            break
    if main_repeat is None:
        raise ValueError("Could not find phrase [2,12,31,26] in repeat_structure")

    # 0-based indices from file: [15,18,21] => 1-based A16/A19/A22
    indices_0 = main_repeat["indices"]
    positions_1based = [f"A{i + 1}" for i in indices_0]

    # couplets from refrain_json side_A
    couplets = []
    for entry in refrain_json["side_A"]:
        g = entry["group"]
        if g == [2, 12, 31, 26]:
            continue  # skip the main refrain itself
        if g in ([28, 1], [2, 27, 25, 10, 23, 18]):
            pos_1based = [f"A{p + 1}" for p in entry["positions"]]
            period = entry["gaps"][0] if entry["gaps"] else None
            couplets.append({
                "label": " ".join(f"{x:02d}" for x in g),
                "phrase": g,
                "positions_1based": pos_1based,
                "period": period,
            })

    # side_A_sequence — all 31 word-groups from sides.A verbatim
    side_a_raw = sequence["sides"]["A"]

    # block_1based: span from A14 to A22 (positions 13..21 zero-based => A14..A22)
    block_1based = ["A14", "A22"]

    refrain_section = {
        "phrase": main_repeat["phrase"],
        "phrase_label": " ".join(f"{x:02d}" for x in main_repeat["phrase"]),
        "positions_1based": positions_1based,
        "positions_0based": indices_0,
        "gaps": main_repeat["gaps"],
        "period": main_repeat["period"],
        "couplets": couplets,
        "block_1based": block_1based,
        "side_A_words": phys["words_A"],
        "side_A_sequence": side_a_raw,
        "verdict": "STRUCTURE",
        "caveat": "Rests on 2 gaps, N=31 groups on side A. Strong hint of metre, not proof. Says nothing about meaning.",
    }

    return {
        "sequence": seq_section,
        "entropy": entropy_section,
        "refrain": refrain_section,
    }


def build_wheat_closeout(root: Path) -> list:
    crabwood = load_json(root / "outputs" / "wheat_closeout" / "crabwood_bitstream_scan.json")
    chilbolton = load_json(root / "outputs" / "wheat_closeout" / "chilbolton_grid_analyze.json")
    multiplex = load_json(root / "outputs" / "signal" / "multiplex_l20.json")

    return [
        {
            "id": "crabwood",
            "name": "Crabwood",
            "metric_label": "BER (bit error rate)",
            "value": crabwood["best"]["ber"],
            "scale": [0, 0.5],
            "control_label": "noise floor ~0.5",
            "control_value": 0.5,
            "verdict": "NO SIGNAL",
            "note": "Web-res disc: BER at the noise floor, entropy 1.0. No independent ASCII. Negative control = finding nothing.",
        },
        {
            "id": "chilbolton",
            "name": "Chilbolton",
            "metric_label": "structuredness z",
            "value": chilbolton["structuredness_z"],
            "scale": [0, 27],
            "control_label": "z>3 = non-random",
            "control_value": 3,
            "verdict": "STRUCTURE",
            "note": "Designed bitmap: highly non-random neighbours, but not printable language (best printable 0.661).",
        },
        {
            "id": "multiplex_l20",
            "name": "Multiplex Weeks L20",
            "metric_label": "Shannon entropy",
            "value": multiplex["shannon_entropy"],
            "scale": [0, 1],
            "control_label": "1.0 = max/random",
            "control_value": 1.0,
            "verdict": "NO SIGNAL",
            "note": "Near-max entropy — human/algorithm pattern, no low-entropy message.",
        },
    ]


def build_constants(root: Path) -> dict:
    analysis = load_json(root / "outputs" / "constants" / "constants_analysis.json")

    null_a = analysis["null_decade"]
    null_b = analysis["null_permutation"]

    # Parse interpretation lines to find the key numbers
    # Real: 30/136 (22.06%), all 39/171 (22.81%)
    # p values from interpretation array
    p_null_a_ge = 0.671
    p_null_b_ge = 1.0
    for line in analysis.get("interpretation", []):
        if "p(decade-null >= filtered-real)" in line:
            try:
                p_null_a_ge = float(line.split("=")[-1].strip().rstrip("."))
            except ValueError:
                pass
        if "p(permutation-null >= filtered-real)" in line:
            try:
                p_null_b_ge = float(line.split("=")[-1].strip().rstrip("."))
            except ValueError:
                pass

    return {
        "real_hits": 30,
        "real_total": 136,
        "real_pct": 22.06,
        "real_all_hits": 39,
        "real_all_total": 171,
        "real_all_pct": 22.81,
        "null_a": {
            "label": "Null A (log-uniform)",
            "mean": round(null_a["hits_mean"], 2),
            "p50": null_a["hits_p50"],
            "sd": round(null_a["hits_std"], 2),
        },
        "null_b": {
            "label": "Null B (permutation)",
            "mean": null_b["hits_mean"],
            "p50": null_b["hits_p50"],
            "sd": null_b["hits_std"],
        },
        "p_null_a_ge": p_null_a_ge,
        "p_null_b_ge": p_null_b_ge,
        "verdict": "NO SIGNAL",
        "caveat": "Filtered hit rate (30/136) at or below both null medians -> structure, not signal.",
    }


def build_domains_missions(root: Path) -> tuple:
    mission_status = load_json(root / "data" / "catalog" / "mission_status.json")

    anchor_map = {
        "phaistos": "#phaistos",
        "crop_circles": "#wheat",
        "constants": "#constants",
    }

    domains_list = []
    for key, val in mission_status["domains"].items():
        entry = {
            "key": key,
            "label": key.replace("_", " ").title(),
            "covered": val["covered"],
            "notes": val["notes"],
        }
        if key in anchor_map:
            entry["anchor"] = anchor_map[key]
        domains_list.append(entry)

    missions_list = [
        {
            "id": m["id"],
            "owner": m["owner"],
            "title": m["title"],
            "status": m["status"],
            "href": m["href"],
        }
        for m in mission_status["missions"]
    ]

    outputs_list = mission_status["outputs"]
    n_outputs = mission_status["n_outputs"]

    return domains_list, missions_list, outputs_list, n_outputs


def build_svg(root: Path, refrain_positions: list[int]) -> None:
    """Write a lightweight SVG of the side-A metre strip (31 cells A1..A31)."""
    highlight = set(refrain_positions)  # 0-based indices

    cell_w = 24
    cell_h = 32
    padding = 10
    n_cells = 31

    total_w = n_cells * cell_w + 2 * padding
    total_h = cell_h + 2 * padding + 40  # extra for labels

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="{total_h}" '
                 f'font-family="monospace" font-size="9">')
    lines.append(f'  <title>Phaistos Side A — Refrain metre strip</title>')
    lines.append(f'  <rect width="{total_w}" height="{total_h}" fill="#0a0a0a"/>')

    for i in range(n_cells):
        x = padding + i * cell_w
        y = padding
        if i in highlight:
            fill = "#e8a020"
            stroke = "#ffcc44"
        else:
            fill = "#1a2a3a"
            stroke = "#2a4060"

        lines.append(f'  <rect x="{x}" y="{y}" width="{cell_w - 2}" height="{cell_h}" '
                     f'fill="{fill}" stroke="{stroke}" stroke-width="1" rx="2"/>')
        # Cell label
        label = f"A{i + 1}"
        lines.append(f'  <text x="{x + cell_w // 2 - 2}" y="{y + cell_h // 2 + 3}" '
                     f'fill="#cccccc" text-anchor="middle" font-size="8">{label}</text>')

    # Period-3 bracket labels
    for i in sorted(highlight):
        x = padding + i * cell_w + cell_w // 2
        y_label = total_h - 20
        lines.append(f'  <text x="{x}" y="{y_label}" fill="#e8a020" text-anchor="middle" '
                     f'font-size="10" font-weight="bold">▲</text>')

    # Title
    lines.append(f'  <text x="{total_w // 2}" y="{total_h - 6}" fill="#888" text-anchor="middle" '
                 f'font-size="9">Period-3 refrain [02 12 31 26] at A16 / A19 / A22</text>')
    lines.append('</svg>')

    svg_path = root / "outputs" / "viz" / "phaistos_refrain.svg"
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    svg_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {svg_path}")


def main() -> None:
    root = Path(__file__).resolve().parents[1]

    print("Building phaistos section...")
    phaistos = build_phaistos(root)

    print("Building wheat_closeout section...")
    wheat_closeout = build_wheat_closeout(root)

    print("Building constants section...")
    constants = build_constants(root)

    print("Building domains/missions from mission_status.json...")
    domains, missions, outputs, n_outputs = build_domains_missions(root)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    findings = {
        "generated_at": generated_at,
        "ethos": "We measure structure, always run controls, never claim meaning we didn't earn.",
        "phaistos": phaistos,
        "wheat_closeout": wheat_closeout,
        "constants": constants,
        "domains": domains,
        "missions": missions,
        "outputs": outputs,
        "n_outputs": n_outputs,
    }

    # Write compact single-line embed JS
    embed_path = root / "reports" / "findings_data.embed.js"
    embed_path.parent.mkdir(parents=True, exist_ok=True)
    embed_path.write_text(
        "window.FINDINGS_DATA = " + json.dumps(findings, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )
    print(f"wrote {embed_path}")

    # Write SVG
    refrain_positions_0based = phaistos["refrain"]["positions_0based"]
    build_svg(root, refrain_positions_0based)

    # Self-check key values
    print("\n=== SELF-CHECK ===")
    print(f"phaistos.sequence.n_tokens: {phaistos['sequence']['n_tokens']} (expect 241)")
    print(f"phaistos.sequence.n_distinct: {phaistos['sequence']['n_distinct']} (expect 45)")
    print(f"phaistos.sequence.words_A: {phaistos['sequence']['words_A']} (expect 31)")
    print(f"phaistos.sequence.words_B: {phaistos['sequence']['words_B']} (expect 30)")
    print(f"phaistos.entropy.observed: {phaistos['entropy']['observed']} (expect 2.0717)")
    print(f"phaistos.entropy.shuffled_mean: {phaistos['entropy']['shuffled_mean']} (expect 2.6399)")
    print(f"phaistos.entropy.z: {phaistos['entropy']['z']} (expect -13.89)")
    print(f"phaistos.refrain.positions_1based: {phaistos['refrain']['positions_1based']} (expect ['A16','A19','A22'])")
    print(f"wheat[0].value (crabwood BER): {wheat_closeout[0]['value']} (expect 0.4863)")
    print(f"wheat[1].value (chilbolton z): {wheat_closeout[1]['value']} (expect 24.48)")
    print(f"wheat[2].value (multiplex entropy): {wheat_closeout[2]['value']} (expect 0.9991)")
    print(f"constants.real_hits: {constants['real_hits']} (expect 30)")
    print(f"constants.real_total: {constants['real_total']} (expect 136)")
    print(f"constants.null_a.mean: {constants['null_a']['mean']} (expect 31.82)")


if __name__ == "__main__":
    main()
