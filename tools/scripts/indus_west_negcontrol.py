#!/usr/bin/env python3
"""
indus_west_negcontrol.py — Barbara West Indus “decipherment” negative control.

Stance: STRUCTURE != MESSAGE. Claim-under-test only. No language-family claim.
Compares symbolseq entropy profiles of:

  1. Indus seal streams (existing corpus.json / G9)
  2. West-style claimed plaintext (fixture until real digitization)
  3. Tamil + Telugu letter baselines (Dravidian *comparators*, not affiliation)

Hypothesis (Kimi): if West “plaintext” entropy ≈ Indus seals (and far from
natural-language baselines), the claim looks like symbol remapping, not
translation.

Reuses tools.forensics.symbolseq for ALL entropy metrics. Pure stdlib for
metrics; JSON I/O only.

Outputs:
  outputs/indus_west/run.json + NOTES.md

Usage:
    python tools/scripts/indus_west_negcontrol.py
    python tools/scripts/indus_west_negcontrol.py --west data/scripts/indus/west/west_plaintext_real.json
    python tools/scripts/indus_west_negcontrol.py --synthetic
    python tools/scripts/indus_west_negcontrol.py --n-shuffles 200

If west_plaintext_real.json exists, it is preferred over the synthetic fixture
unless --west is set explicitly. Drop real JSON in and re-run in one command.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
INDUS_DIR = ROOT / "data" / "scripts" / "indus"
WEST_DIR = INDUS_DIR / "west"
OUT_DIR = ROOT / "outputs" / "indus_west"
WEST_REAL = WEST_DIR / "west_plaintext_real.json"
WEST_FIXTURE = WEST_DIR / "west_plaintext_fixture.json"

sys.path.insert(0, str(ROOT))
from tools.forensics.symbolseq import (  # noqa: E402
    analyze as seq_analyze,
    flatten,
)

STANCE = (
    "Barbara West's Indus 'decipherment' is treated strictly as a claim-under-test. "
    "This probe compares entropy / IC / conditional-H profiles of Indus seals, "
    "West-style plaintext (fixture or real), and Tamil/Telugu baselines. "
    "It does NOT endorse West, identify Indus as Dravidian, or translate seals. "
    "STRUCTURE != MESSAGE. Reused tools/forensics/symbolseq.py."
)

FORBIDDEN_PHRASES = (
    "West deciphered",
    "Indus is Tamil",
    "Indus is Telugu",
    "Indus is Dravidian",
    "translates to",
    "decodes as",
    "aliens wrote",
)


def load_indus_tokens(data_dir: Path) -> list[str]:
    corpus_path = data_dir / "corpus.json"
    if not corpus_path.exists():
        # tiny fallback
        return (["P122", "P385", "P001"] * 40)
    raw = json.loads(corpus_path.read_text())
    seqs = raw.get("sequences", {})
    return flatten(list(seqs.values()))


def load_west_streams(path: Path) -> dict[str, list[str]]:
    raw = json.loads(path.read_text())
    streams = raw.get("streams", {})
    out: dict[str, list[str]] = {}
    for name, block in streams.items():
        if "sequences" in block:
            out[name] = flatten(list(block["sequences"].values()))
        elif "text" in block:
            out[name] = letters_from_text(block["text"])
    return out


def letters_from_text(text: str) -> list[str]:
    """Letterize Unicode text: keep letters; drop spaces/punct."""
    # Prefer letter characters; fall back to non-whitespace if script has no \w
    toks = [ch for ch in text if ch.isalpha()]
    if len(toks) < 20:
        toks = [ch for ch in text if not ch.isspace()]
    return toks


def load_baseline(path: Path) -> list[str]:
    raw = json.loads(path.read_text())
    return letters_from_text(raw.get("text", ""))


def profile(tokens: list[str], label: str, n_shuffles: int, seed: int) -> dict:
    if len(tokens) < 2:
        return {"label": label, "n_tokens": len(tokens), "error": "too_short"}
    full = seq_analyze([[t] for t in tokens], n_shuffles=n_shuffles, seed=seed)
    return {
        "label": label,
        "n_tokens": full["n_tokens"],
        "n_distinct": full["n_distinct"],
        "unigram_entropy_bits": full["unigram_entropy_bits"],
        "conditional_bigram_entropy_bits": full["conditional_bigram_entropy_bits"],
        "index_of_coincidence": full["index_of_coincidence"],
        "lz78_ratio": full["lz78_ratio"],
        "shuffled_control": full["shuffled_control"],
    }


def _norm_features(p: dict) -> dict | None:
    """Alphabet-size-normalized features for cross-stream comparison.

    Raw H₁ is dominated by alphabet size (Indus ~182 signs vs letter streams
    ~20–30), so Euclidean distance on raw bits falsely pulls any small-alphabet
    stream toward Tamil/Telugu. Use H₁/Hmax, H₂/H₁, IC·k, LZ78 instead.
    """
    import math

    if "error" in p or p.get("n_distinct", 0) < 2:
        return None
    k = float(p["n_distinct"])
    h1 = float(p["unigram_entropy_bits"])
    h2 = float(p["conditional_bigram_entropy_bits"])
    hmax = math.log2(k)
    return {
        "h1_over_max": h1 / hmax if hmax > 0 else 0.0,
        "h2_over_h1": h2 / h1 if h1 > 1e-9 else 0.0,
        "ioc_over_uniform": float(p["index_of_coincidence"]) * k,
        "lz78_ratio": float(p["lz78_ratio"]),
    }


def euclidean_metric_distance(a: dict, b: dict) -> float:
    fa, fb = _norm_features(a), _norm_features(b)
    if fa is None or fb is None:
        return float("nan")
    s = 0.0
    for k in fa:
        s += (fa[k] - fb[k]) ** 2
    return round((s / len(fa)) ** 0.5, 4)


def classify_claim(indus: dict, west: dict, baselines: list[dict]) -> dict:
    """Compare West profile distance to Indus vs mean distance to language baselines."""
    d_indus = euclidean_metric_distance(indus, west)
    d_lang = [euclidean_metric_distance(west, b) for b in baselines if "error" not in b]
    mean_lang = round(sum(d_lang) / len(d_lang), 4) if d_lang else None
    verdict = "UNDERDETERMINED"
    note = ""
    if mean_lang is None or mean_lang != mean_lang:  # NaN guard
        verdict = "UNDERDETERMINED"
        note = "Missing language baselines or non-finite distance."
    elif d_indus < mean_lang * 0.85:
        verdict = "CLAIM_LOOKS_LIKE_RECODE"
        note = (
            "West stream sits closer to Indus seal *normalized* entropy shape "
            "than to Tamil/Telugu letter baselines — consistent with remapping / "
            "formulaic glosses, NOT proof West is wrong about every seal, and "
            "NOT a language ID. Distances use H₁/Hmax, H₂/H₁, IC·k, LZ78."
        )
    elif mean_lang < d_indus * 0.85:
        verdict = "CLAIM_LOOKS_LANGUAGE_LIKE"
        note = (
            "West stream sits closer to Dravidian letter baselines than to Indus "
            "seals (normalized metrics) — escalate for human review of the real "
            "West tables. Still NOT an endorsement of the decipherment."
        )
    else:
        verdict = "NO_CLEAR_SEPARATION"
        note = "Distances comparable; need larger / authentic West plaintext."
    return {
        "distance_west_to_indus": d_indus,
        "distance_west_to_lang_mean": mean_lang,
        "distances_west_to_each_baseline": {
            b["label"]: euclidean_metric_distance(west, b) for b in baselines if "error" not in b
        },
        "feature_space": "h1_over_max, h2_over_h1, ioc_over_uniform, lz78_ratio",
        "west_features": _norm_features(west),
        "indus_features": _norm_features(indus),
        "verdict": verdict,
        "note": note,
    }


def write_notes(report: dict) -> str:
    parts = [
        "# Indus × Barbara West negative control\n",
        f"Generated: {report.get('generated_at', '?')}\n",
        "## Stance\n",
        report.get("stance", STANCE),
        "",
        "**Motto:** structure ≠ message. Claim-under-test ≠ endorsement.\n",
        "### Forbidden phrases\n",
    ]
    parts.extend(f"- `{p}`" for p in report.get("forbidden_phrases", FORBIDDEN_PHRASES))
    parts.append("\n## Profiles\n")
    for p in report.get("profiles", []):
        if "error" in p:
            parts.append(f"- `{p['label']}`: ERROR {p['error']}")
            continue
        sc = p.get("shuffled_control", {})
        parts.append(
            f"- **{p['label']}**: N={p['n_tokens']}  H₁={p['unigram_entropy_bits']}  "
            f"H₂={p['conditional_bigram_entropy_bits']}  IC={p['index_of_coincidence']}  "
            f"LZ78={p['lz78_ratio']}  z={sc.get('z')}"
        )
    cut = report.get("claim_under_test", {})
    parts.append(f"\n## Claim-under-test: **{cut.get('verdict', '?')}**\n")
    parts.append(cut.get("note", ""))
    parts.append(
        f"\n- d(West, Indus) = {cut.get('distance_west_to_indus')}  "
        f"d(West, lang mean) = {cut.get('distance_west_to_lang_mean')}"
    )
    parts.append("\n## Data\n")
    parts.append(report.get("data_note", ""))
    parts.append(
        "\n---\n*G9++ West negcontrol — Hecklefish quick win. "
        "Replace fixture with licensed West tables when available.*"
    )
    return "\n".join(parts)


def default_west_path() -> Path:
    """Prefer real claim JSON when present; else synthetic fixture."""
    if WEST_REAL.exists():
        return WEST_REAL
    return WEST_FIXTURE


def pick_west_stream(streams: dict[str, list[str]], requested: str | None) -> str:
    """Choose claim stream: explicit flag, else claim_plaintext → recode_like → first."""
    if requested and requested != "auto":
        if requested not in streams:
            raise SystemExit(
                f"West stream '{requested}' missing in file. "
                f"Available: {sorted(streams)}"
            )
        return requested
    for key in ("claim_plaintext", "recode_like"):
        if key in streams:
            return key
    if not streams:
        raise SystemExit("No streams found in West JSON")
    return sorted(streams)[0]


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Barbara West Indus claim — entropy negative control."
    )
    ap.add_argument("--synthetic", action="store_true",
                    help="Skip Indus corpus; use tiny synthetic seal stream.")
    ap.add_argument(
        "--west",
        type=Path,
        default=None,
        help=(
            "West plaintext JSON (streams.*.sequences|text). "
            f"Default: {WEST_REAL.name} if present else {WEST_FIXTURE.name}."
        ),
    )
    ap.add_argument("--tamil", type=Path, default=WEST_DIR / "tamil_baseline.json")
    ap.add_argument("--telugu", type=Path, default=WEST_DIR / "telugu_baseline.json")
    ap.add_argument(
        "--west-stream",
        default="auto",
        help=(
            "Stream key under streams{} to treat as the claim "
            "(claim_plaintext | recode_like | english_like | auto)."
        ),
    )
    ap.add_argument("--also-english-ka", action="store_true",
                    help="Also profile english_like as known-answer comparator.")
    ap.add_argument("--n-shuffles", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out-json", type=Path, default=None)
    ap.add_argument("--out-md", type=Path, default=None)
    a = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    west_path = a.west if a.west is not None else default_west_path()

    if a.synthetic:
        indus_toks = (["P122", "P385", "P001", "P147", "P316"] * 50)
        indus_label = "indus_synthetic"
    else:
        indus_toks = load_indus_tokens(INDUS_DIR)
        indus_label = "indus_corpus_mohenjodaro"

    west_streams = load_west_streams(west_path)
    west_stream = pick_west_stream(west_streams, a.west_stream)
    west_toks = west_streams[west_stream]
    tamil = load_baseline(a.tamil)
    telugu = load_baseline(a.telugu)

    profiles = [
        profile(indus_toks, indus_label, a.n_shuffles, a.seed),
        profile(west_toks, f"west_{west_stream}", a.n_shuffles, a.seed + 1),
        profile(tamil, "tamil_letters", a.n_shuffles, a.seed + 2),
        profile(telugu, "telugu_letters", a.n_shuffles, a.seed + 3),
    ]
    if a.also_english_ka and "english_like" in west_streams:
        profiles.append(
            profile(west_streams["english_like"], "west_english_like_KA",
                    a.n_shuffles, a.seed + 4)
        )

    by_label = {p["label"]: p for p in profiles}
    cut = classify_claim(
        by_label[indus_label],
        by_label[f"west_{west_stream}"],
        [by_label["tamil_letters"], by_label["telugu_letters"]],
    )

    # Known-answer sanity: english_like should prefer language baselines
    ka_block = None
    if "west_english_like_KA" in by_label:
        ka_block = classify_claim(
            by_label[indus_label],
            by_label["west_english_like_KA"],
            [by_label["tamil_letters"], by_label["telugu_letters"]],
        )
        # For English letters vs Tamil/Telugu, "language-like" may still be
        # far from Dravidian scripts; we only check it is NOT closer to Indus
        # than to letter baselines when baselines are Latin — skip hard assert.

    using_real = west_path.resolve() == WEST_REAL.resolve() and WEST_REAL.exists()
    report = {
        "stance": STANCE,
        "forbidden_phrases": list(FORBIDDEN_PHRASES),
        "profiles": profiles,
        "claim_under_test": cut,
        "english_known_answer": ka_block,
        "verdict": cut["verdict"],
        "west_path": str(west_path.relative_to(ROOT)) if ROOT in west_path.resolve().parents else str(west_path),
        "west_stream": west_stream,
        "using_real_claim_file": using_real,
        "data_note": (
            f"West source: {west_path} (stream={west_stream}). "
            + (
                "Best-effort public claim sample — see DATA_SOURCES.md "
                "(Barbara West 2004 tables blocked / unobtainable). "
                if using_real
                else "Synthetic fixture — drop west_plaintext_real.json and re-run. "
            )
            + "Indus: mayig CISI subset. Tamil/Telugu: short letter baselines."
        ),
        "tools_used": ["symbolseq", "indus_west_negcontrol"],
        "negative_controls": ["tamil_letters", "telugu_letters", "shuffled_control"],
        "todos": [
            "If authentic Barbara West 2004 tables surface: replace claim_plaintext in west_plaintext_real.json",
            "Optionally add longer Tamil/Telugu corpora (CLDR / Project Madurai)",
            "Compare West word-length distribution to English Zipf separately",
        ],
    }
    report["generated_at"] = datetime.now(timezone.utc).isoformat()

    out_json = a.out_json or OUT_DIR / "run.json"
    out_md = a.out_md or OUT_DIR / "NOTES.md"
    out_json.write_text(json.dumps(report, indent=2, default=str))
    out_md.write_text(write_notes(report))
    print(f"wrote {out_json}")
    print(f"wrote {out_md}")
    print(f"verdict={cut['verdict']} d_indus={cut['distance_west_to_indus']} "
          f"d_lang={cut['distance_west_to_lang_mean']}")


if __name__ == "__main__":
    main()
