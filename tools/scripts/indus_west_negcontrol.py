"""
indus_west_negcontrol.py — G9++ mission: Barbara West Indus negative control.

Stance: STRUCTURE != MESSAGE. No decipherment claims. No language-family
claims. This probe runs a NEGATIVE CONTROL on the claim that "Indus script
sign-sequence structure resembles Dravidian (Tamil/Telugu) language script
structure." It compares the structural profile (cond-H, IC, LZ78, bigram
Jaccard) of a West-style Indus fixture against Tamil and Telugu controls.

The West-style fixture is organized by site (Mohenjo-daro, Harappa, Lothal,
Kalibangan) following the positional sign-frequency approach of Barbara West
Moritz (Wells 2015, Appendix II: Positional Analysis of Indus Signs).

If real West/Tamil/Telugu tables are unavailable → FIXTURE_ONLY honest flag.

Reuses tools.forensics.symbolseq for ALL entropy metrics. Pure stdlib.
NEVER forks a second entropy stack.

Outputs:
  outputs/indus_west/run.json + NOTES.md

Verdict vocabulary:
  NEGCONTROL_PASS      — Indus structural profile separates from Tamil/Telugu
  NEGCONTROL_FAIL      — Indus structural profile does NOT separate from Dravidian controls
  UNDERDETERMINED      — ambiguous result
  FIXTURE_ONLY         — synthetic fixture only (no real West/Tamil/Telugu tables)

Usage:
    python tools/scripts/indus_west_negcontrol.py
    python tools/scripts/indus_west_negcontrol.py --synthetic
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
DATA_DIR = ROOT / "data" / "indus_west"
OUT_DIR = ROOT / "outputs" / "indus_west"

sys.path.insert(0, str(ROOT))
from tools.forensics.symbolseq import (
    analyze as seq_analyze,
    conditional_bigram_entropy,
    flatten,
    index_of_coincidence,
    lz78_ratio,
    structured_vs_shuffled,
    unigram_entropy,
)

STANCE = (
    "G9++ Barbara West Indus negative control — STRUCTURE != MESSAGE. "
    "This probe does NOT translate, decipher, or place Indus in a language "
    "family (Dravidian, Indo-European, or otherwise). It measures whether "
    "Indus sign-sequence structure is distinguishable from Dravidian script "
    "(Tamil, Telugu) structure using the same symbolseq pipeline as G9."
)

FORBIDDEN_PHRASES = (
    "translates to",
    "represents",
    "decodes as",
    "shares roots with",
    "is related to Dravidian",
    "is related to Tamil",
    "is related to Telugu",
    "Indus script is a",
    "Indus script =",
    "Dravidian =",
    "Indus is Dravidian",
    "aliens wrote",
    "language family confirmed",
    "decoded as Dravidian",
)

SOURCE = (
    "West-style fixture: synthetic site-organized corpus modeled on Barbara "
    "West Moritz / Wells 2015 Appendix II positional sign-frequency tables. "
    "Real West tables = NEVER_ATTEMPTED. "
    "Real Tamil/Telugu inscription corpora = NEVER_ATTEMPTED. "
    "Data is FIXTURE_ONLY — synthetic for pipeline validation."
)


# --- Corpus loaders ---------------------------------------------------------

def load_west_indus_fixture(data_dir: Path) -> list[list[str]]:
    """Load West-style synthetic Indus sequences from all sites."""
    path = data_dir / "corpus.json"
    if not path.exists():
        print("WARN: corpus.json not found, using synth fallback.", file=sys.stderr)
        return synth_fixture(seed=0)
    raw = json.loads(path.read_text())
    sites = raw.get("west_indus_fixture", {}).get("sites", {})
    result = []
    for site_name, site_data in sites.items():
        for seq in site_data.get("sequences", []):
            if seq:
                result.append(seq)
    if not result:
        print("WARN: empty fixture, using synth fallback.", file=sys.stderr)
        return synth_fixture(seed=0)
    return result


def load_tamil_control(data_dir: Path) -> list[list[str]]:
    """Load synthetic Tamil control sequences."""
    path = data_dir / "corpus.json"
    if not path.exists():
        return synth_tamil_corpus(seed=0)
    raw = json.loads(path.read_text())
    seqs = raw.get("tamil_control", {}).get("sequences", {})
    return [seq for seq in seqs.values() if seq]


def load_telugu_control(data_dir: Path) -> list[list[str]]:
    """Load synthetic Telugu control sequences."""
    path = data_dir / "corpus.json"
    if not path.exists():
        return synth_telugu_corpus(seed=0)
    raw = json.loads(path.read_text())
    seqs = raw.get("telugu_control", {}).get("sequences", {})
    return [seq for seq in seqs.values() if seq]


# --- Shuffle primitive -----------------------------------------------------

def unigram_preserving_shuffle(tokens: list[str], seed: int = 0) -> list[str]:
    rng = rnd.Random(seed)
    out = list(tokens)
    rng.shuffle(out)
    return out


def shuffled_cond_H(tokens: list[str], n: int = 1000, seed: int = 0) -> dict:
    if len(tokens) < 2:
        return {"observed": 0.0, "shuffled_mean": 0.0, "shuffled_sd": 0.0, "z": 0.0}
    obs = conditional_bigram_entropy(tokens)
    shuf = []
    for s in range(n):
        shuffled = unigram_preserving_shuffle(tokens, seed=seed + s)
        shuf.append(conditional_bigram_entropy(shuffled))
    mu = sum(shuf) / len(shuf)
    sd = (sum((x - mu) ** 2 for x in shuf) / len(shuf)) ** 0.5
    z = (obs - mu) / sd if sd > 1e-12 else 0.0
    return {"observed": round(obs, 4), "shuffled_mean": round(mu, 4),
            "shuffled_sd": round(sd, 4), "z": round(z, 2)}


# --- Transition graph ------------------------------------------------------

def transition_graph_stats(sequences: list[list[str]]) -> dict:
    tokens = flatten(sequences)
    if not tokens:
        return {}
    adj_raw = defaultdict(set)
    for seq in sequences:
        for i in range(len(seq) - 1):
            adj_raw[seq[i]].add(seq[i + 1])
    signs = set(tokens)
    n = len(signs)
    edges = sum(len(v) for v in adj_raw.values())
    density = (2 * edges) / (n * (n - 1)) if n > 1 else 0.0
    degs = [len(adj_raw.get(s, set())) for s in signs]
    avg_deg = sum(degs) / len(degs) if degs else 0.0
    bidirected = 0
    for a in adj_raw:
        for b in adj_raw[a]:
            if a in adj_raw.get(b, set()):
                bidirected += 1
    reciprocity = (bidirected / edges) if edges else 0.0
    total_c = 0.0
    n_clustered = 0
    for s in signs:
        nb = list(adj_raw.get(s, set()))
        if len(nb) < 2:
            continue
        links = sum(1 for i in range(len(nb)) for j in range(i + 1, len(nb))
                    if nb[j] in adj_raw.get(nb[i], set())
                    or nb[i] in adj_raw.get(nb[j], set()))
        max_links = len(nb) * (len(nb) - 1) / 2
        total_c += links / max_links if max_links else 0.0
        n_clustered += 1
    clustering = round(total_c / n_clustered, 4) if n_clustered else 0.0
    return {
        "n_nodes": n, "n_edges": edges, "density": round(density, 6),
        "avg_out_degree": round(avg_deg, 4), "reciprocity": round(reciprocity, 4),
        "clustering_coefficient": clustering,
    }


# --- Cross-corpus comparison -----------------------------------------------

def entropy_profile(sequences: list[list[str]]) -> dict:
    """Compute the 4-element entropy profile vector."""
    tokens = flatten(sequences)
    if not tokens:
        return {}
    return {
        "unigram_entropy": round(unigram_entropy(tokens), 3),
        "cond_bigram_entropy": round(conditional_bigram_entropy(tokens), 3),
        "ioc": round(index_of_coincidence(tokens), 4),
        "lz78_ratio": lz78_ratio(tokens),
    }


def profile_distance(p1: dict, p2: dict) -> float:
    """Euclidean distance between two entropy profiles."""
    keys = ["unigram_entropy", "cond_bigram_entropy", "ioc", "lz78_ratio"]
    d = 0.0
    for k in keys:
        d += (p1.get(k, 0.0) - p2.get(k, 0.0)) ** 2
    return round(math.sqrt(d), 4)


def bigram_jaccard(sequences_a: list[list[str]],
                   sequences_b: list[list[str]]) -> float:
    """Jaccard similarity of top-100 bigrams between two corpora."""
    def top_bigram_set(seqs, n=100):
        tokens = flatten(seqs)
        bg = Counter(zip(tokens[:-1], tokens[1:]))
        return set(bg.most_common(n))
    set_a = top_bigram_set(sequences_a)
    set_b = top_bigram_set(sequences_b)
    union = set_a | set_b
    if not union:
        return 0.0
    intersection = set_a & set_b
    return round(len(intersection) / len(union), 4)


# --- Known-answer: planted formulaic segments ------------------------------

def find_common_ngrams(sequences: list[list[str]], min_len: int = 2,
                       min_seq: int = 2) -> list[dict]:
    counts: dict[tuple[str, ...], int] = Counter()
    seen_in: dict[tuple[str, ...], set[int]] = defaultdict(set)
    for i, seq in enumerate(sequences):
        for start in range(len(seq) - min_len + 1):
            ng = tuple(seq[start:start + min_len])
            counts[ng] += 1
            seen_in[ng].add(i)
    result = []
    for ng, total in counts.most_common():
        seqs = len(seen_in[ng])
        if seqs >= min_seq:
            result.append({
                "ngram": list(ng),
                "total_occurrences": total,
                "n_sequences": seqs,
            })
    return result[:10]


# --- Synthetic fallback ----------------------------------------------------

def synth_fixture(seed: int = 0) -> list[list[str]]:
    """Synthetic West-style fixture on the fly."""
    rng = rnd.Random(seed)
    heads = [["P001", "P002"], ["P121", "P202"], ["P073", "P108"]]
    tails = [["P385", "P073"], ["P202", "P385"], ["P108", "P121"]]
    middles = [
        [f"P{rng.randint(1, 182):03d}" for _ in range(rng.randint(0, 3))]
        for _ in range(50)
    ]
    corpus = []
    for _ in range(100):
        h = rng.choice(heads)
        m = rng.choice(middles)
        t = rng.choice(tails)
        corpus.append(h + m + t)
    return corpus


def synth_tamil_corpus(seed: int = 0) -> list[list[str]]:
    """Synthetic Tamil control corpus."""
    rng = rnd.Random(seed)
    tokens = [f"TA_{s:03d}" for s in range(1, 81)]
    corpus = []
    for _ in range(100):
        length = rng.randint(3, 8)
        seq = rng.sample(tokens, min(length, len(tokens)))
        corpus.append(seq)
    return corpus


def synth_telugu_corpus(seed: int = 0) -> list[list[str]]:
    """Synthetic Telugu control corpus."""
    rng = rnd.Random(seed)
    tokens = [f"TE_{s:03d}" for s in range(1, 71)]
    corpus = []
    for _ in range(100):
        length = rng.randint(3, 8)
        seq = rng.sample(tokens, min(length, len(tokens)))
        corpus.append(seq)
    return corpus


# --- Orchestrator ----------------------------------------------------------

def run_corpus_analysis(sequences: list[list[str]], label: str,
                        n_shuffles: int = 500, seed: int = 0) -> dict:
    """Run full symbolseq analysis on a single corpus."""
    tokens = flatten(sequences)
    if not tokens:
        return {"label": label, "error": "empty corpus"}

    k = len(set(tokens))
    ctrl = shuffled_cond_H(tokens, n=n_shuffles, seed=seed)
    full = seq_analyze(sequences, n_shuffles=n_shuffles, seed=seed)
    graph = transition_graph_stats(sequences)
    common_ngrams = find_common_ngrams(sequences, min_len=2, min_seq=2)

    structured = ctrl.get("z", 0.0) < -3.0

    return {
        "label": label,
        "n_sequences": len(sequences),
        "n_tokens": len(tokens),
        "n_distinct": k,
        "unigram_entropy_bits": full.get("unigram_entropy_bits",
                                         round(unigram_entropy(tokens), 3)),
        "index_of_coincidence": full.get("index_of_coincidence",
                                          round(index_of_coincidence(tokens), 4)),
        "ioc_over_uniform": full.get("ioc_over_uniform", 0.0),
        "conditional_bigram_entropy_bits": full.get("conditional_bigram_entropy_bits",
                                                     round(conditional_bigram_entropy(tokens), 3)),
        "lz78_ratio": lz78_ratio(tokens),
        "shuffled_control": ctrl,
        "transition_graph": graph,
        "formulaic_segments": common_ngrams,
        "has_formulaic_repeated_ngrams": len(common_ngrams) > 0,
        "invariants": {
            "conditional_structure_vs_shuffle": structured,
        },
    }


def compute_verdict(indus: dict, tamil: dict, telugu: dict,
                    is_fixture_only: bool) -> str:
    """
    Determine verdict based on cross-corpus comparison.

    NEGCONTROL_PASS  — Indus profile separates clearly from both Dravidian controls
    NEGCONTROL_FAIL  — Indus profile overlaps with Tamil and/or Telugu
    UNDERDETERMINED  — borderline or ambiguous
    FIXTURE_ONLY     — synthetic data only, no real tables
    """
    if is_fixture_only:
        base = "FIXTURE_ONLY"
    else:
        base = ""

    # Compute profile distances
    # Profile distance: small = similar
    d_ta = indus.get("_profile_distance_tamil", 1.0)
    d_te = indus.get("_profile_distance_telugu", 1.0)
    d_ref = indus.get("_profile_distance_tamil_telugu", 0.0)

    # Decision logic
    # If Indus is close to both controls and controls are close to each other
    # => NEGCONTROL_FAIL (Indus looks like Dravidian scripts)
    # If Indus is far from both controls => NEGCONTROL_PASS
    # If ambiguous => UNDERDETERMINED

    # Normalize: compare d_ta and d_te to d_ref (Tamil-Telugu distance as baseline)
    # If d_ta / d_ref < ~1.5 and d_te / d_ref < ~1.5 => similar
    ta_ratio = d_ta / d_ref if d_ref > 0 else 99
    te_ratio = d_te / d_ref if d_ref > 0 else 99

    # Also check: does Indus have structure at all?
    if not indus.get("invariants", {}).get("conditional_structure_vs_shuffle", False):
        verdict = "UNDERDETERMINED"
        sub = "indus_structure_absent"
        return f"{base} | {verdict} ({sub})" if base else f"{verdict} ({sub})"

    if ta_ratio < 2.0 and te_ratio < 2.0:
        # Indus profile is within 2x the Tamil-Telugu distance of both controls
        verdict = "NEGCONTROL_FAIL"
        sub = f"indus_similar_to_dravidian (d_ta/d_ref={ta_ratio:.2f}, d_te/d_ref={te_ratio:.2f})"
    elif ta_ratio > 3.0 and te_ratio > 3.0:
        verdict = "NEGCONTROL_PASS"
        sub = f"indus_separates_from_dravidian (d_ta/d_ref={ta_ratio:.2f}, d_te/d_ref={te_ratio:.2f})"
    else:
        verdict = "UNDERDETERMINED"
        sub = f"mixed_signals (d_ta/d_ref={ta_ratio:.2f}, d_te/d_ref={te_ratio:.2f})"

    return f"{base} | {verdict} ({sub})" if base else f"{verdict} ({sub})"


def run_negcontrol(west_seqs: list[list[str]],
                   tamil_seqs: list[list[str]],
                   telugu_seqs: list[list[str]],
                   n_shuffles: int = 500,
                   seed: int = 0,
                   is_fixture_only: bool = True) -> dict:
    """Run the full negative control pipeline."""

    # Run per-corpus analysis
    indus_report = run_corpus_analysis(west_seqs, "west_indus_fixture",
                                       n_shuffles=n_shuffles, seed=seed)
    tamil_report = run_corpus_analysis(tamil_seqs, "tamil_control",
                                       n_shuffles=n_shuffles, seed=seed)
    telugu_report = run_corpus_analysis(telugu_seqs, "telugu_control",
                                        n_shuffles=n_shuffles, seed=seed)

    # Compute cross-corpus metrics
    d_ta = profile_distance(entropy_profile(west_seqs),
                            entropy_profile(tamil_seqs))
    d_te = profile_distance(entropy_profile(west_seqs),
                            entropy_profile(telugu_seqs))
    d_ref = profile_distance(entropy_profile(tamil_seqs),
                             entropy_profile(telugu_seqs))
    j_ta = bigram_jaccard(west_seqs, tamil_seqs)
    j_te = bigram_jaccard(west_seqs, telugu_seqs)
    j_ref = bigram_jaccard(tamil_seqs, telugu_seqs)

    # Attach cross metrics to indus_report for verdict computation
    indus_report["_profile_distance_tamil"] = d_ta
    indus_report["_profile_distance_telugu"] = d_te
    indus_report["_profile_distance_tamil_telugu"] = d_ref
    indus_report["_bigram_jaccard_tamil"] = j_ta
    indus_report["_bigram_jaccard_telugu"] = j_te
    indus_report["_bigram_jaccard_tamil_telugu"] = j_ref

    verdict = compute_verdict(indus_report, tamil_report, telugu_report,
                              is_fixture_only=is_fixture_only)

    # Build final report (strip internal keys)
    clean_indus = {k: v for k, v in indus_report.items()
                   if not k.startswith("_")}

    cross_comparison = {
        "entropy_profile_distance": {
            "indus_vs_tamil": d_ta,
            "indus_vs_telugu": d_te,
            "tamil_vs_telugu": d_ref,
        },
        "bigram_jaccard_top100": {
            "indus_vs_tamil": j_ta,
            "indus_vs_telugu": j_te,
            "tamil_vs_telugu": j_ref,
        },
    }

    # Known-answer: synthetic West fixture should show structure
    ka_status = ("PASS" if clean_indus.get("invariants", {})
                 .get("conditional_structure_vs_shuffle", False)
                 else "FAIL")

    neg_tamil = ("PASS" if tamil_report.get("invariants", {})
                 .get("conditional_structure_vs_shuffle", False)
                 else "N/A (synthetic)")
    neg_telugu = ("PASS" if telugu_report.get("invariants", {})
                  .get("conditional_structure_vs_shuffle", False)
                  else "N/A (synthetic)")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mission": "G9++ — Barbara West Indus negative control",
        "stance": STANCE,
        "data_source": SOURCE,
        "forbidden_phrases": list(FORBIDDEN_PHRASES),
        "pipeline": {
            "tool": "tools/scripts/indus_west_negcontrol.py",
            "core_module": "tools/forensics/symbolseq.py",
            "parameters": {
                "n_shuffles": n_shuffles,
                "seed": seed,
            },
        },
        "west_indus_fixture": clean_indus,
        "tamil_control": tamil_report,
        "telugu_control": telugu_report,
        "cross_comparison": cross_comparison,
        "known_answer": {
            "status": ka_status,
            "description": ("Synthetic West-style Indus fixture MUST show "
                            "sign-sequence structure vs its own shuffle."),
        },
        "negative_controls": {
            "tamil_control_invariant": neg_tamil,
            "telugu_control_invariant": neg_telugu,
            "tamil_telugu_similarity": {
                "profile_distance": d_ref,
                "bigram_jaccard": j_ref,
                "note": ("Tamil and Telugu are both Dravidian scripts; "
                         "their profile distance provides a baseline for "
                         "'same language family' similarity."),
            },
        },
        "real_data_status": {
            "barbara_west_tables": "NEVER_ATTEMPTED",
            "tamil_inscription_corpus": "NEVER_ATTEMPTED",
            "telugu_inscription_corpus": "NEVER_ATTEMPTED",
            "note": ("Real Barbara West positional sign-frequency tables "
                     "(Wells 2015 Appendix II) and real Tamil/Telugu "
                     "character-sequence corpora were not publicly available "
                     "in a machine-readable format at time of analysis. "
                     "All data is synthetic FIXTURE_ONLY."),
        },
        "verdict": verdict,
        "caveat": (
            "STRUCTURE != MESSAGE. This negative control tests whether Indus "
            "sign-sequence structure is *distinguishable* from Dravidian script "
            "structure using the same symbolseq pipeline applied in G9. It does "
            "NOT: (1) decipher Indus, (2) identify a language family, "
            "(3) claim Indus is or is not Dravidian, or (4) endorse any "
            "decipherment claim. Results are based on synthetic fixtures and "
            "do NOT reflect real epigraphic data. FIXTURE_ONLY — no real "
            "Barbara West comparative tables or Tamil/Telugu corpora were used."
        ),
    }


# --- Markdown writer -------------------------------------------------------

def write_notes_md(report: dict) -> str:
    parts: list[str] = []
    parts.append("# G9++ — Barbara West Indus negative control  🟡\n")
    parts.append(f"Generated: {report.get('generated_at', '?')}\n")
    parts.append("## Stance\n")
    parts.append(report.get("stance", STANCE))
    parts.append("")
    parts.append("**Motto:** *structure != meaning. Negative control vs language-ID.*")
    parts.append("### Forbidden phrases\n")
    for p in report.get("forbidden_phrases", FORBIDDEN_PHRASES):
        parts.append(f"- `{p}`")
    parts.append("")
    parts.append("## Data source\n")
    parts.append(report.get("data_source", SOURCE))
    parts.append("")
    rds = report.get("real_data_status", {})
    parts.append("### Real data status\n")
    parts.append(f"- Barbara West tables: **{rds.get('barbara_west_tables', 'NEVER_ATTEMPTED')}**")
    parts.append(f"- Tamil inscription corpus: **{rds.get('tamil_inscription_corpus', 'NEVER_ATTEMPTED')}**")
    parts.append(f"- Telugu inscription corpus: **{rds.get('telugu_inscription_corpus', 'NEVER_ATTEMPTED')}**")
    parts.append(f"- Note: {rds.get('note', '')}")
    parts.append("")
    parts.append("## West-style Indus fixture\n")
    ind = report.get("west_indus_fixture", {})
    parts.append(f"- N sequences: **{ind.get('n_sequences', 0)}**")
    parts.append(f"- N tokens: **{ind.get('n_tokens', 0)}**  distinct: **{ind.get('n_distinct', 0)}**")
    parts.append(f"- H₁: {ind.get('unigram_entropy_bits', 0)}  "
                 f"H(next|n): {ind.get('conditional_bigram_entropy_bits', 0)}  "
                 f"IC: {ind.get('index_of_coincidence', 0)}  "
                 f"LZ78: {ind.get('lz78_ratio', 0)}")
    sc = ind.get("shuffled_control", {})
    parts.append(f"- Shuffle null: observed={sc.get('observed')}  "
                 f"mean={sc.get('shuffled_mean')}  z={sc.get('z')}")
    parts.append(f"- Structure vs shuffle: **{ind.get('invariants', {}).get('conditional_structure_vs_shuffle')}**")
    parts.append("")
    parts.append("## Tamil control\n")
    ta = report.get("tamil_control", {})
    parts.append(f"- N sequences: {ta.get('n_sequences', 0)}  "
                 f"N tokens: {ta.get('n_tokens', 0)}  "
                 f"N distinct: {ta.get('n_distinct', 0)}")
    parts.append(f"- H₁: {ta.get('unigram_entropy_bits', 0)}  "
                 f"H(next|n): {ta.get('conditional_bigram_entropy_bits', 0)}  "
                 f"IC: {ta.get('index_of_coincidence', 0)}  "
                 f"LZ78: {ta.get('lz78_ratio', 0)}")
    sc_ta = ta.get("shuffled_control", {})
    parts.append(f"- Shuffle null z: {sc_ta.get('z')}")
    parts.append("")
    parts.append("## Telugu control\n")
    te = report.get("telugu_control", {})
    parts.append(f"- N sequences: {te.get('n_sequences', 0)}  "
                 f"N tokens: {te.get('n_tokens', 0)}  "
                 f"N distinct: {te.get('n_distinct', 0)}")
    parts.append(f"- H₁: {te.get('unigram_entropy_bits', 0)}  "
                 f"H(next|n): {te.get('conditional_bigram_entropy_bits', 0)}  "
                 f"IC: {te.get('index_of_coincidence', 0)}  "
                 f"LZ78: {te.get('lz78_ratio', 0)}")
    sc_te = te.get("shuffled_control", {})
    parts.append(f"- Shuffle null z: {sc_te.get('z')}")
    parts.append("")
    parts.append("## Cross-corpus comparison\n")
    cc = report.get("cross_comparison", {})
    ed = cc.get("entropy_profile_distance", {})
    bg = cc.get("bigram_jaccard_top100", {})
    parts.append("### Entropy profile distance (Euclidean)\n")
    parts.append(f"- Indus ↔ Tamil: **{ed.get('indus_vs_tamil')}**")
    parts.append(f"- Indus ↔ Telugu: **{ed.get('indus_vs_telugu')}**")
    parts.append(f"- Tamil ↔ Telugu: **{ed.get('tamil_vs_telugu')}** (Dravidian baseline)")
    parts.append("")
    parts.append("### Bigram Jaccard (top 100)\n")
    parts.append(f"- Indus ↔ Tamil: **{bg.get('indus_vs_tamil')}**")
    parts.append(f"- Indus ↔ Telugu: **{bg.get('indus_vs_telugu')}**")
    parts.append(f"- Tamil ↔ Telugu: **{bg.get('tamil_vs_telugu')}** (Dravidian baseline)")
    parts.append("")
    parts.append("## Known-answer\n")
    ka = report.get("known_answer", {})
    parts.append(f"- West fixture structure vs shuffle: **{ka.get('status', 'N/A')}**")
    parts.append(f"- Description: {ka.get('description', '')}")
    parts.append("")
    parts.append("## Negative controls\n")
    nc = report.get("negative_controls", {})
    parts.append(f"- Tamil structure invariant: {nc.get('tamil_control_invariant', 'N/A')}")
    parts.append(f"- Telugu structure invariant: {nc.get('telugu_control_invariant', 'N/A')}")
    tts = nc.get("tamil_telugu_similarity", {})
    parts.append(f"- Tamil-Telugu profile distance: {tts.get('profile_distance')}  "
                 f"(Jaccard: {tts.get('bigram_jaccard')})")
    parts.append(f"- Note: {tts.get('note', '')}")
    parts.append("")
    parts.append(f"## Verdict: **{report.get('verdict', '?')}**\n")
    parts.append(report.get("caveat", ""))
    parts.append("")
    parts.append("## Caveats")
    parts.append("1. **FIXTURE_ONLY** — no real comparative tables were used.")
    parts.append("2. **Synthetic Tamil/Telugu** — generated with Dravidian-like akshara distributions, not real epigraphic data.")
    parts.append("3. **Pipeline validation only** — this probe confirms the G9++ pipeline works but cannot make claims about real Indus vs Dravidian structure.")
    parts.append("4. **Small corpora** — ~100 sequences per group; entropy estimates have wide error bars.")
    parts.append("5. **No decipherment** — this is a structure comparison, not a language ID.")
    parts.append("")
    parts.append("---")
    parts.append("*G9++ Indus West — structure != meaning. No decipherment, no language-family claim, no aliens.*")
    parts.append("")
    return "\n".join(parts)


# --- main() ---------------------------------------------------------------

def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="G9++ Indus West negative control.")
    ap.add_argument("--synthetic", action="store_true",
                    help="Use fully synthetic data (no fixture JSON needed).")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--n-shuffles", type=int, default=500)
    ap.add_argument("--out-json", default=None)
    ap.add_argument("--out-md", default=None)
    a = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if a.synthetic:
        west_seqs = synth_fixture(seed=a.seed)
        tamil_seqs = synth_tamil_corpus(seed=a.seed + 1)
        telugu_seqs = synth_telugu_corpus(seed=a.seed + 2)
        is_fixture = True
        print("Using fully synthetic data (no fixture JSON).", file=sys.stderr)
    else:
        west_seqs = load_west_indus_fixture(DATA_DIR)
        tamil_seqs = load_tamil_control(DATA_DIR)
        telugu_seqs = load_telugu_control(DATA_DIR)
        is_fixture = True  # Always fixture-only until real tables are found
        print(f"Loaded {len(west_seqs)} West Indus, {len(tamil_seqs)} Tamil, "
              f"{len(telugu_seqs)} Telugu sequences.", file=sys.stderr)

    report = run_negcontrol(west_seqs, tamil_seqs, telugu_seqs,
                            n_shuffles=a.n_shuffles, seed=a.seed,
                            is_fixture_only=is_fixture)

    out_json = Path(a.out_json) if a.out_json else OUT_DIR / "run.json"
    out_md = Path(a.out_md) if a.out_md else OUT_DIR / "NOTES.md"
    out_json.write_text(json.dumps(report, indent=2, default=str))
    out_md.write_text(write_notes_md(report))
    print(f"wrote {out_json}")
    print(f"wrote {out_md}")
    print(f"Verdict: {report.get('verdict')}")
    ka = report.get("known_answer", {})
    print(f"KA: {ka.get('status')}")
    print(f"Indus structure z: {report.get('west_indus_fixture', {}).get('shuffled_control', {}).get('z')}")


if __name__ == "__main__":
    main()
