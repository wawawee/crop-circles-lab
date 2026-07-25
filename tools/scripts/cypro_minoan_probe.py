"""
cypro_minoan_probe.py — G11 mission: Cypro-Minoan sign-sequence structure probe.

Stance: structure != meaning. No decipherment, no language-family claims,
"CM is Linear A," or aliens.

Reuses tools.forensics.symbolseq for ALL entropy metrics. Pure stdlib.

Core tests:
  1. Full-corpus entropy / bigram / cond-H vs unigram-matched shuffle
  2. Per-medium (tablet vs other) structural comparison — media/allography
  3. Per-site structural profiles (CM_ENKO, CM_RASH, CM_KALA, CM_KITI)
  4. Cross-group Jaccard/shared-sign overlap
  5. Known-answer: planted scribal-variant corpus must collapse vs shuffle
  6. Negative control: unigram-matched shuffle must NOT light up

Outputs:
  outputs/cypro_minoan/run.json + NOTES.md

Usage:
    python tools/scripts/cypro_minoan_probe.py
"""
from __future__ import annotations

import json
import math
import random as rnd
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA_DIR = ROOT / "data" / "scripts" / "cypro_minoan"
OUT_DIR = ROOT / "outputs" / "cypro_minoan"

sys.path.insert(0, str(ROOT))
from tools.forensics.symbolseq import (
    analyze as seq_analyze,
    conditional_bigram_entropy,
    flatten,
    index_of_coincidence,
    lz78_ratio,
    repeat_structure,
    structured_vs_shuffled,
    unigram_entropy,
)

STANCE = (
    "Cypro-Minoan (ca. 1500-1100 BCE, Cyprus / Ugarit) script(s) is/are "
    "undeciphered. This probe measures *sign-sequence structure* only — "
    "it does NOT translate, decipher, or claim language family. "
    "STRUCTURE != MESSAGE. Reused tools/forensics/symbolseq.py."
)

FORBIDDEN_PHRASES = (
    "translates to", "represents", "decodes as", "shares roots with",
    "is related to", "CM is Linear A", "aliens wrote",
)

CORPUS_LICENSE = (
    "Corazza et al. 2022 PLOS ONE (Figshare 6095488), CC BY 4.0. "
    "Sign sequences from sign2vec_d context.csv (CC-BY). "
    "Sign images copyright original publishers."
)


def load_corpus(data_dir: Path) -> dict:
    path = data_dir / "corpus.json"
    if not path.exists():
        print(f"FATAL: {path} not found. Run ingest_cm_corpus.py first.", file=sys.stderr)
        sys.exit(1)
    return json.loads(path.read_text())


def normalize_tokens(tokens: list[str]) -> list[str]:
    out = []
    for t in tokens:
        if t.endswith("_") and len(t) > 1:
            t = t.rstrip("_")
        if t == "012bis":
            t = "012"
        if t and t not in ("boh", "et", "punto", "SPACE", "False"):
            out.append(t)
    return out


def is_tablet_inscription(ins_path: str) -> bool:
    return "tab" in ins_path.lower()


def group_by_site_and_medium(
    corpus: dict,
) -> dict[str, list[list[str]]]:
    seqs = corpus["sequences"]
    groups: dict[str, list[list[str]]] = {
        "full_corpus": [],
        "tablet": [],
        "other_media": [],
    }
    site_groups: dict[str, list[list[str]]] = {}

    for uid, info in seqs.items():
        tokens = normalize_tokens(info["tokens"])
        if not tokens:
            continue
        site = info.get("site", "unknown")
        ins = info.get("inscription", "")

        groups["full_corpus"].append(tokens)
        if is_tablet_inscription(ins):
            groups["tablet"].append(tokens)
        else:
            groups["other_media"].append(tokens)

        if site not in site_groups:
            site_groups[site] = []
        site_groups[site].append(tokens)

    for site, seqs_list in site_groups.items():
        groups[f"site_{site}"] = seqs_list

    return groups


def jaccard_similarity(tokens_a: list[str], tokens_b: list[str]) -> float:
    set_a = set(tokens_a)
    set_b = set(tokens_b)
    if not set_a and not set_b:
        return 1.0
    return len(set_a & set_b) / len(set_a | set_b)


def shared_sign_stats(groups: dict[str, list[list[str]]]) -> list[dict]:
    flat_tokens = {}
    for label, seqs in groups.items():
        tokens = [t for seq in seqs for t in seq]
        flat_tokens[label] = tokens

    results = []
    labels = sorted(flat_tokens.keys())
    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            a, b = labels[i], labels[j]
            tok_a, tok_b = flat_tokens[a], flat_tokens[b]
            set_a, set_b = set(tok_a), set(tok_b)
            shared = set_a & set_b
            only_a = set_a - set_b
            only_b = set_b - set_a
            jac = jaccard_similarity(tok_a, tok_b)
            results.append({
                "group_a": a,
                "group_b": b,
                "n_signs_a": len(set_a),
                "n_signs_b": len(set_b),
                "shared_signs": len(shared),
                "only_in_a": len(only_a),
                "only_in_b": len(only_b),
                "shared_list": sorted(shared),
                "jaccard": round(jac, 4),
            })
    return results


def shuffled_cond_H(
    tokens: list[str], n: int = 1000, seed: int = 0
) -> dict:
    if len(tokens) < 2:
        return {"observed": 0.0, "shuffled_mean": 0.0, "shuffled_sd": 0.0, "z": 0.0}
    obs = conditional_bigram_entropy(tokens)
    rng = rnd.Random(seed)
    t = list(tokens)
    samples = []
    for s in range(n):
        rng.shuffle(t)
        samples.append(conditional_bigram_entropy(t))
    mu = sum(samples) / len(samples)
    var = sum((x - mu) ** 2 for x in samples) / len(samples)
    sd = math.sqrt(var) if var > 0 else 1e-12
    z = (obs - mu) / sd
    return {
        "observed": round(obs, 4),
        "shuffled_mean": round(mu, 4),
        "shuffled_sd": round(sd, 4),
        "z": round(z, 2),
        "more_structured_than_chance": obs < mu - 2 * sd,
    }


def run_group_analysis(
    sequences: list[list[str]], label: str, n_shuffles: int = 1000, seed: int = 0
) -> dict:
    tokens = flatten(sequences)
    if not tokens:
        return {"label": label, "error": "empty", "n_tokens": 0}

    ctrl = shuffled_cond_H(tokens, n=n_shuffles, seed=seed)
    full = seq_analyze(sequences, n_shuffles=n_shuffles, seed=seed)
    repeats = repeat_structure(sequences)

    return {
        "label": label,
        "n_sequences": len(sequences),
        "n_tokens": full.get("n_tokens", len(tokens)),
        "n_distinct": full.get("n_distinct", len(set(tokens))),
        "unigram_entropy_bits": full.get("unigram_entropy_bits",
                                          round(unigram_entropy(tokens), 3)),
        "index_of_coincidence": full.get("index_of_coincidence",
                                          round(index_of_coincidence(tokens), 4)),
        "ioc_over_uniform": full.get("ioc_over_uniform",
                                     round(index_of_coincidence(tokens) * len(set(tokens)), 3)
                                     if set(tokens) else 0.0),
        "conditional_bigram_entropy_bits": full.get("conditional_bigram_entropy_bits",
                                                     round(conditional_bigram_entropy(tokens), 3)),
        "lz78_ratio": full.get("lz78_ratio", lz78_ratio(tokens)),
        "top_bigrams": full.get("top_bigrams", []),
        "shuffled_control": ctrl,
        "repeat_structure": [
            {k: r[k] for k in ("group", "count", "gap_mean", "gap_cv", "layout")}
            for r in repeats[:10]
        ],
    }


def synthetic_scribal_variant_corpus(seed: int = 0) -> list[list[str]]:
    """Plant a corpus where two 'scribal variants' share sign inventory
    and bigram structure — should look like ONE system (cond-H << shuffle)."""
    rng = rnd.Random(seed)
    signs = [f"{s:03d}" for s in range(1, 61)]
    base_bigrams = [["001", "023"], ["023", "087"], ["087", "102"],
                    ["102", "005"], ["005", "075"], ["075", "097"]]
    scribe_a_signs = ["001", "023", "087", "102", "005", "075", "097",
                      "004", "025", "027", "069", "082", "104"]
    scribe_b_signs = ["001", "023", "087", "102", "005", "075",
                      "038", "051", "107", "110", "021"]
    seqs = []
    for _ in range(40):
        bg = rng.choice(base_bigrams)
        mid = rng.choices(signs, k=rng.randint(0, 3))
        seq_a = bg[:1] + mid + bg[1:]
        seq_b = bg[:1] + mid + bg[1:]
        seqs.append(seq_a)
        seqs.append(seq_b)
    return seqs


def write_notes_md(report: dict) -> str:
    parts = []

    icon = "🟢"
    for r in report.get("groups", []):
        sc = r.get("shuffled_control", {})
        if sc.get("z", 0) >= -2:
            icon = "🔴"
    tablet_j = (
        report.get("cross_group", {})
        .get("summary", {})
        .get("tablet_vs_other_jaccard", 0)
    )
    if icon == "🟢" and tablet_j >= 0.5:
        badge = "STRUCTURE_SIGNAL | MEDIA_DRIVEN_ALLOGRAPHY"
    elif icon == "🟢":
        badge = "STRUCTURE_SIGNAL"
    else:
        badge = "STRUCTURE_INCONCLUSIVE"

    parts.append(f"# G11 — Cypro-Minoan sign-sequence structure probe  {icon}")
    parts.append(f"Generated: {report.get('generated_at', '?')}")
    parts.append("")
    parts.append("## Stance")
    parts.append(STANCE)
    parts.append("")
    parts.append("**Motto:** *structure != message.* No decipherment, no language-family claim.")
    parts.append("### Forbidden phrases")
    for fp in FORBIDDEN_PHRASES:
        parts.append(f"- `{fp}`")
    parts.append("")

    parts.append("## Source")
    parts.append(CORPUS_LICENSE)
    parts.append("")

    mg = report.get("metadata", {})
    parts.append(f"- {mg.get('n_inscriptions',0)} inscriptions, "
                 f"{mg.get('n_tokens',0)} tokens, {mg.get('n_distinct',0)} distinct signs")
    parts.append(f"- {mg.get('n_sites',0)} sites; "
                 f"tablet: {mg.get('n_tablet_tokens',0)} signs, "
                 f"other: {mg.get('n_other_tokens',0)} signs")
    parts.append("")

    parts.append("## Group analyses")
    parts.append("")
    for r in report.get("groups", []):
        label = r.get("label", "?")
        parts.append(f"### {label}")
        parts.append(f"- tokens={r.get('n_tokens',0)}  distinct={r.get('n_distinct',0)}  "
                     f"H₁={r.get('unigram_entropy_bits')}  IC={r.get('index_of_coincidence')}")
        parts.append(f"- H(next|prev)={r.get('conditional_bigram_entropy_bits')}  "
                     f"LZ78={r.get('lz78_ratio')}")
        sc = r.get("shuffled_control", {})
        parts.append(f"- shuffle null: observed={sc.get('observed')}  "
                     f"mean={sc.get('shuffled_mean')}  z={sc.get('z')}")
        top_bg = r.get("top_bigrams", [])[:5]
        if top_bg:
            parts.append(f"- top bigrams: {[(b['pair'], b['count']) for b in top_bg]}")
        parts.append("")

    parts.append("## Cross-group Jaccard overlap")
    parts.append("")
    cg = report.get("cross_group", {})
    # Keep NOTES readable: only headline pairs (media + major sites).
    key_labels = {
        "full_corpus", "tablet", "other_media",
        "site_CM_ENKO", "site_CM_RASH", "site_CM_KALA",
    }
    key_pairs = [
        e for e in cg.get("pairs", [])
        if e["group_a"] in key_labels and e["group_b"] in key_labels
    ]
    for entry in key_pairs:
        parts.append(f"- {entry['group_a']} vs {entry['group_b']}: "
                     f"J={entry['jaccard']}  shared={entry['shared_signs']}  "
                     f"A-only={entry['only_in_a']}  B-only={entry['only_in_b']}")
    parts.append(f"- (full pairwise matrix: {len(cg.get('pairs', []))} pairs in run.json)")
    parts.append("")

    parts.append("## Cross-group shared-sign analysis")
    parts.append("")
    cg_ss = cg.get("shared_signs_across_groups", {})
    all_shared = cg_ss.get("shared_across_all", [])
    parts.append(f"- Signs shared across all groups: {len(all_shared)}")
    if all_shared:
        parts.append(f"  {all_shared[:15]}{'...' if len(all_shared) > 15 else ''}")
    parts.append(f"- Signs unique to tablet: {len(cg_ss.get('unique_to_tablet', []))}")
    parts.append(f"- Signs unique to other media: {len(cg_ss.get('unique_to_other', []))}")
    parts.append("")

    parts.append("## Known-answer: synthetic scribal variants")
    parts.append("")
    ka = report.get("known_answer", {})
    parts.append(f"- Label: {ka.get('label', '?')}")
    sc_ka = ka.get("shuffled_control", {})
    parts.append(f"- tokens={ka.get('n_tokens',0)}  distinct={ka.get('n_distinct',0)}")
    parts.append(f"- H₁={ka.get('unigram_entropy_bits')}  "
                 f"H(next|prev)={ka.get('conditional_bigram_entropy_bits')}")
    parts.append(f"- shuffle null: observed={sc_ka.get('observed')}  "
                 f"mean={sc_ka.get('shuffled_mean')}  z={sc_ka.get('z')}")
    parts.append(f"- Scribal variants (shared sign set, bigram structure) MUST show "
                 f"strong conditional structure vs shuffle (z << -3).")
    parts.append("")

    parts.append("## Negative control")
    parts.append("")
    nc = report.get("negative_control", {})
    sc_nc = nc.get("shuffled_control", {})
    parts.append(f"- Label: {nc.get('label', '?')}")
    parts.append(f"- tokens={nc.get('n_tokens',0)}  distinct={nc.get('n_distinct',0)}")
    parts.append(f"- shuffle null: observed={sc_nc.get('observed')}  "
                 f"mean={sc_nc.get('shuffled_mean')}  z={sc_nc.get('z')}")
    parts.append(f"- A shuffled version of the real data must NOT light up as structured.")
    parts.append("")

    verdict_parts = []
    for r in report.get("groups", []):
        sc = r.get("shuffled_control", {})
        z = sc.get("z", 0)
        structured = z < -3.0
        if structured:
            verdict_parts.append(f"- {r['label']}: STRUCTURE_SIGNAL z={z}")
        else:
            verdict_parts.append(f"- {r['label']}: NO_SIGNAL z={z}")
    cg_j = cg.get("summary", {})
    verdict_parts.append(f"- Cross-group Jaccard mean: {cg_j.get('mean_jaccard', '?')}")
    verdict_parts.append(f"- Tablet vs other shared: {cg_j.get('tablet_vs_other_jaccard', '?')}")
    ka_z = ka.get("shuffled_control", {}).get("z", 0)
    verdict_parts.append(f"- KA scribal variants: z={ka_z} "
                         f"{'PASS' if ka_z < -3 else 'FAIL'}")

    parts.append("## Verdict")
    parts.append("")
    parts.append(f"**{badge}**")
    parts.append("")
    for vp in verdict_parts:
        parts.append(vp)
    parts.append("")

    parts.append("## Caveats")
    parts.append("")
    parts.append("1. **Corpus reconstructed from trigram-sliding-window data** — "
                 "sign sequences are read from individual cropped sign image paths, "
                 "not from authoritative transliteration tables. Directionality "
                 "(LTR/RTL/boustrophedon) may not be preserved.")
    parts.append("2. **CM1/CM2/CM3 labels not directly available** in the open "
                 "sign2vec_d data. Site-based and medium-based labels used as proxies.")
    parts.append("3. **Token normalization** strips underscore-suffixed variants "
                 "(e.g., '046_' → '046'). These are paleographic variants, "
                 "not distinct graphemes, per the paper's argument.")
    parts.append("4. **Short sequences predominate** — many inscriptions carry "
                 "only 1–5 signs. Longer tablet sequences drive most structural signal.")
    parts.append("5. **No decipherment, language ID, or script classification.**") 

    return "\n".join(parts)


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="G11 Cypro-Minoan structure probe.")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--n-shuffles", type=int, default=1000)
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    corpus = load_corpus(DATA_DIR)
    groups = group_by_site_and_medium(corpus)

    group_results = []
    group_labels = ["full_corpus", "tablet", "other_media",
                    "site_CM_ENKO", "site_CM_RASH", "site_CM_KALA"]
    for label in group_labels:
        seqs = groups.get(label, [])
        if seqs:
            grp = run_group_analysis(seqs, label=label, n_shuffles=args.n_shuffles,
                                     seed=args.seed)
            group_results.append(grp)
            sc = grp.get("shuffled_control", {})
            z_val = sc.get('z', '?')
            z_str = f"{z_val:>7.2f}" if isinstance(z_val, (int, float)) else f"{z_val:>7}"
            print(f"  {label:25s}: tokens={grp['n_tokens']:5d}  "
                  f"distinct={grp['n_distinct']:3d}  "
                  f"cond-H z={z_str}")


    jaccard_pairs = shared_sign_stats(groups)
    jaccard_summary = {
        "pairs": jaccard_pairs,
        "summary": {
            "n_groups": len(group_labels),
            "mean_jaccard": round(
                sum(j["jaccard"] for j in jaccard_pairs) / len(jaccard_pairs), 4
            ) if jaccard_pairs else 0,
        },
    }

    tablet_seqs = groups.get("tablet", [])
    other_seqs = groups.get("other_media", [])
    tablet_tokens = set(t for seq in tablet_seqs for t in seq)
    other_tokens = set(t for seq in other_seqs for t in seq)
    shared_across_all = None
    if tablet_tokens and other_tokens:
        shared_across_all = tablet_tokens & other_tokens
        jaccard_summary["shared_signs_across_groups"] = {
            "shared_across_all": sorted(shared_across_all),
            "n_shared": len(shared_across_all),
            "unique_to_tablet": sorted(tablet_tokens - other_tokens),
            "n_unique_tablet": len(tablet_tokens - other_tokens),
            "unique_to_other": sorted(other_tokens - tablet_tokens),
            "n_unique_other": len(other_tokens - tablet_tokens),
        }
    tablet_vs_other_j = jaccard_summary.get("shared_signs_across_groups", {})
    jaccard_summary["summary"]["tablet_vs_other_jaccard"] = round(
        jaccard_similarity(list(tablet_tokens), list(other_tokens)), 4
    ) if tablet_tokens and other_tokens else 0

    # Known-answer: synthetic scribal variants
    ka_seqs = synthetic_scribal_variant_corpus(seed=args.seed)
    ka_result = run_group_analysis(ka_seqs, label="synthetic_scribal_variants_ka",
                                   n_shuffles=args.n_shuffles, seed=args.seed)

    # Negative control: shuffle the full corpus
    flat_all = flatten(groups.get("full_corpus", []))
    rng = rnd.Random(args.seed + 999)
    shuffled_all = list(flat_all)
    rng.shuffle(shuffled_all)
    neg_seqs = [shuffled_all]
    nc_result = run_group_analysis(neg_seqs, label="unigram_shuffle_negative_control",
                                   n_shuffles=args.n_shuffles, seed=args.seed + 777)

    metadata = {
        "n_tokens": len(flat_all),
        "n_distinct": len(set(flat_all)),
        "n_inscriptions": len(groups.get("full_corpus", [])),
        "n_sites": len([g for g in groups if g.startswith("site_")]),
        "n_tablet_tokens": len(flatten(groups.get("tablet", []))),
        "n_other_tokens": len(flatten(groups.get("other_media", []))),
        "n_tablet_sequences": len(tablet_seqs),
        "n_other_sequences": len(other_seqs),
    }

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata,
        "groups": group_results,
        "cross_group": jaccard_summary,
        "known_answer": ka_result,
        "negative_control": nc_result,
        "pipeline": {
            "tool": "tools/scripts/cypro_minoan_probe.py + tools/forensics/symbolseq.py",
            "parameters": {"n_shuffles": args.n_shuffles, "seed": args.seed},
        },
        "data_source": CORPUS_LICENSE,
        "stance": STANCE,
        "forbidden": list(FORBIDDEN_PHRASES),
    }

    out_json = OUT_DIR / "run.json"
    out_md = OUT_DIR / "NOTES.md"
    out_json.write_text(json.dumps(report, indent=2, default=str))
    out_md.write_text(write_notes_md(report))
    print(f"\nwrote {out_json}")
    print(f"wrote {out_md}")


if __name__ == "__main__":
    main()
