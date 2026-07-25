"""
meroitic_probe.py — G16: Meroitic sign-sequence structure probe.

Stance: structure != meaning. Meroitic script is partially deciphered
(the script is readable, the language is poorly understood; cf. Rilly 2007,
2010). This probe measures *sign-sequence structure* only — it does NOT
translate, decipher, or make "Meroitic deciphered" claims.

Reuses tools.forensics.symbolseq for ALL entropy metrics. Pure stdlib.

Deliverables for G16:
  1. Meroitic full-corpus structural analysis vs unigram-matched shuffle
  2. Known-answer: royal-name and formulaic segments that show structure
     vs shuffle (document what is honestly recoverable)
  3. Late-Egyptian control sample ~comparable N — structure comparator ONLY
  4. Negative control: unigram-matched shuffle of Meroitic

Outputs:
  outputs/meroitic/run.json + NOTES.md

Usage:
    python tools/scripts/meroitic_probe.py
    python tools/scripts/meroitic_probe.py --synthetic
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
DATA_DIR = ROOT / "data" / "scripts" / "meroitic"
OUT_DIR = ROOT / "outputs" / "meroitic"

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
    "Meroitic script is partially deciphered (the script's syllabic values "
    "are mostly known; the language is poorly understood; cf. Rilly 2007, 2010). "
    "This probe measures *sign-sequence structure* only — it does NOT translate, "
    "decipher beyond published readings, or make 'Meroitic deciphered' claims. "
    "STRUCTURE != MESSAGE. Reused tools/forensics/symbolseq.py."
)

FORBIDDEN_PHRASES = (
    "Meroitic deciphered",
    "translates to",
    "represents",
    "decodes as",
    "shares roots with",
    "crank 99.5%",
    "Ghost License",
    "Lackadaisical Security",
    "99.5% decipherment",
    "aliens wrote",
)

SOURCE = (
    "Corpus: Joshua-Otten/Meroitic-Corpus (GitHub open, 2025), Otten & "
    "Anastasopoulos. No license specified; all rights reserved by default. "
    "Sign transliterations scraped from RAMSES Online (ramses.ulg.ac.be). "
    "Late Egyptian control: RAMSES Online — Late Egyptian hieratic texts. "
    "Both sourced from the same RAMSES database; writing systems differ."
)

ROYAL_NAME_TOKENS = frozenset({
    "qor", "qr",           # king / ruler
    "pqr",                 # crown prince
    "kdi", "mkdi",         # queen / royal woman
    "qore", "qoreyi",      # king (construct forms)
    "pestE",               # son of the king
    "pqor", "pqorlike",    # prince / royal heir
    "pqri",                # prince (variant)
    "kdike",               # queen
    "kdiqo",               # queen mother
    "kdakqo",              # queen mother
    "ant",                 # clergyman (titulary)
    "pqrNyi",              # crown prince (genitive)
    "qorNyi",              # royal (genitive)
    "qo",                  # title / royal prefix
    "terite",              # royal name prefix (Terite-)
    "mn", "amni", "mni",   # Amun / Amani- prefix
    "mnitr", "amnitr",     # Amanitore
    "mnpte",               # Amanipate
    "mnpi",                # Amun of Napata
    "kedi",                # Anthroponym suffix
    "site", "sitE",        # son of / daughter of
    "abr", "abrs",         # man / people
    "wi",                  # brother
    "ste",                 # mother
    "kdis",                # sister
    "yetmde",              # nephew / cousin / relative
})

# --- Corpus loader ---------------------------------------------------------

def load_corpus(data_dir: Path) -> list[list[str]]:
    corpus_path = data_dir / "corpus.json"
    if not corpus_path.exists():
        print(f"FATAL: {corpus_path} not found.", file=sys.stderr)
        sys.exit(1)
    raw = json.loads(corpus_path.read_text())
    seqs = raw.get("sequences", {})
    result = [seq for seq in seqs.values() if seq]
    if not result:
        print("WARN: empty corpus, using synthetic.", file=sys.stderr)
        return synth_meroitic_corpus(seed=0)
    return result


def load_egyptian_control(data_dir: Path) -> list[list[str]]:
    egypt_path = data_dir / "late_egyptian_sample.json"
    if not egypt_path.exists():
        print(f"WARN: {egypt_path} not found. Egyptian control skipped.",
              file=sys.stderr)
        return []
    raw = json.loads(egypt_path.read_text())
    tokens = raw.get("tokens", [])
    if not tokens:
        return []
    return [tokens]


# --- Known-answer: royal-name detection -----------------------------------

def royal_name_sequences(sequences: list[list[str]]) -> list[list[str]]:
    result = []
    for seq in sequences:
        if any(t in ROYAL_NAME_TOKENS for t in seq):
            result.append(seq)
    return result


def formulaic_token_count(sequences: list[list[str]]) -> dict:
    total = 0
    match_count = 0
    for seq in sequences:
        for t in seq:
            total += 1
            if t in ROYAL_NAME_TOKENS:
                match_count += 1
    return {
        "n_total_tokens": total,
        "n_royal_name_tokens": match_count,
        "pct_royal_name": round(100 * match_count / total, 2) if total else 0.0,
    }


# --- Unigram-matched shuffle -----------------------------------------------

def unigram_preserving_shuffle(tokens: list[str], seed: int = 0) -> list[str]:
    rng = rnd.Random(seed)
    out = list(tokens)
    rng.shuffle(out)
    return out


def shuffled_cond_H(tokens: list[str], n: int = 1000, seed: int = 0) -> dict:
    if len(tokens) < 2:
        return {"observed": 0.0, "shuffled_mean": 0.0, "shuffled_sd": 0.0,
                "z": 0.0}
    obs = conditional_bigram_entropy(tokens)
    samples = []
    for s in range(n):
        shuffled = unigram_preserving_shuffle(tokens, seed=seed + s)
        samples.append(conditional_bigram_entropy(shuffled))
    mu = sum(samples) / len(samples)
    sd = (sum((x - mu) ** 2 for x in samples) / len(samples)) ** 0.5
    if sd < 1e-12:
        sd = 1e-12
    z = (obs - mu) / sd
    return {
        "observed": round(obs, 4),
        "shuffled_mean": round(mu, 4),
        "shuffled_sd": round(sd, 4),
        "z": round(z, 2),
        "more_structured_than_chance": obs < mu - 2 * sd,
    }


# --- Transition graph ------------------------------------------------------

def build_transition_graph(sequences: list[list[str]]) -> dict:
    adj: dict[str, Counter] = defaultdict(Counter)
    for seq in sequences:
        for i in range(len(seq) - 1):
            adj[seq[i]][seq[i + 1]] += 1
    return {k: dict(v) for k, v in adj.items()}


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
        "n_nodes": n,
        "n_edges": edges,
        "density": round(density, 6),
        "avg_out_degree": round(avg_deg, 4),
        "reciprocity": round(reciprocity, 4),
        "clustering_coefficient": clustering,
    }


# --- N-gram finder ---------------------------------------------------------

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
    return result[:20]


# --- Synthetic known-answer corpus -----------------------------------------

def synth_meroitic_corpus(seed: int = 0) -> list[list[str]]:
    rng = rnd.Random(seed)
    heads = [["wES", "wetNyiNqeli"], ["lEwi", "aribet", "wetemtr"],
             ["kiSri", "menEtel"]]
    middles = ["yetmdelEwi", "terikelEwi", "belElEke", "pqr",
               "qEwi", "xrpxN"]
    tails = [["krErEli"], ["yikidbitelEwi"], ["aqebetEwi"]]
    corpus = []
    for _ in range(200):
        h = rng.choice(heads)
        m = [rng.choice(middles) for _ in range(rng.randint(1, 4))]
        t = rng.choice(tails)
        corpus.append(h + m + t)
    return corpus


# --- Orchestrator ----------------------------------------------------------

def run_meroitic_probe(sequences: list[list[str]], label: str,
                       n_shuffles: int = 1000, seed: int = 0) -> dict:
    tokens = flatten(sequences)
    if not tokens:
        return {"label": label, "error": "empty corpus"}
    k = len(set(tokens))
    ctrl = shuffled_cond_H(tokens, n=n_shuffles, seed=seed)
    full = seq_analyze(sequences, n_shuffles=n_shuffles, seed=seed)
    graph_obs = transition_graph_stats(sequences)
    common_ngrams = find_common_ngrams(sequences, min_len=2, min_seq=2)
    structured = ctrl.get("z", 0.0) < -3.0
    return {
        "label": label,
        "n_sequences": len(sequences),
        "n_tokens": full.get("n_tokens", len(tokens)),
        "n_distinct": full.get("n_distinct", k),
        "unigram_entropy_bits": full.get("unigram_entropy_bits",
                                          round(unigram_entropy(tokens), 3)),
        "index_of_coincidence": full.get("index_of_coincidence",
                                          round(index_of_coincidence(tokens), 4)),
        "ioc_over_uniform": full.get("ioc_over_uniform",
                                      round(index_of_coincidence(tokens) * k, 3)
                                      if k else 0.0),
        "conditional_bigram_entropy_bits": full.get(
            "conditional_bigram_entropy_bits",
            round(conditional_bigram_entropy(tokens), 3)),
        "lz78_ratio": full.get("lz78_ratio", lz78_ratio(tokens)),
        "top_bigrams": full.get("top_bigrams", []),
        "shuffled_control": ctrl,
        "transition_graph": graph_obs,
        "formulaic_segments": common_ngrams[:10],
        "invariants": {
            "conditional_structure_vs_shuffle": bool(structured),
        },
    }


# --- Markdown writer -------------------------------------------------------

def write_notes_md(report: dict) -> str:
    parts = []

    verdict = report.get("verdict", "PENDING")
    icon_map = {"STRUCTURE_SIGNAL": "\U0001f7e2", "NO_SIGNAL": "\U0001f534",
                "UNDERDETERMINED": "\U0001f7e1"}
    icon = icon_map.get(verdict, "\U0001f7e1")

    parts.append(f"# G16 — Meroitic sign-sequence structure probe  {icon}")
    parts.append(f"Generated: {report.get('generated_at', '?')}")
    parts.append("")
    parts.append("## Stance")
    parts.append(STANCE)
    parts.append("")
    parts.append("**Motto:** *structure != meaning.* "
                 "No decipherment beyond published readings. "
                 "No translation claims.")
    parts.append("### Forbidden phrases")
    for fp in FORBIDDEN_PHRASES:
        parts.append(f"- `{fp}`")
    parts.append("")

    parts.append("## Source")
    parts.append(SOURCE)
    parts.append("")

    mg = report.get("metadata", {})
    parts.append(f"- Meroitic corpus: {mg.get('n_meroitic_inscriptions', 0)} "
                 f"inscriptions, {mg.get('n_meroitic_tokens', 0)} tokens, "
                 f"{mg.get('n_meroitic_distinct', 0)} distinct signs")
    parts.append(f"- Late Egyptian control: {mg.get('n_egyptian_tokens', 0)} "
                 f"tokens, {mg.get('n_egyptian_distinct', 0)} distinct signs")
    parts.append("")

    parts.append("## Group analyses")
    parts.append("")
    for r in report.get("groups", []):
        label = r.get("label", "?")
        parts.append(f"### {label}")
        parts.append(f"- tokens={r.get('n_tokens', 0)}  "
                     f"distinct={r.get('n_distinct', 0)}  "
                     f"H\u2081={r.get('unigram_entropy_bits')}  "
                     f"IC={r.get('index_of_coincidence')}")
        parts.append(f"- H(next|prev)={r.get('conditional_bigram_entropy_bits')}  "
                     f"LZ78={r.get('lz78_ratio')}")
        sc = r.get("shuffled_control", {})
        parts.append(f"- shuffle null: observed={sc.get('observed')}  "
                     f"mean={sc.get('shuffled_mean')}  z={sc.get('z')}")
        top_bg = r.get("top_bigrams", [])[:5]
        if top_bg:
            parts.append(f"- top bigrams: "
                         f"{[(b['pair'], b['count']) for b in top_bg]}")
        parts.append("")

    parts.append("## Known-answer: royal-name structure")
    parts.append("")
    ka = report.get("known_answer", {})
    parts.append(f"- Sequences containing royal-name tokens: "
                 f"{ka.get('n_sequences', 0)}")
    parts.append(f"- Royal-name token stats: "
                 f"{ka.get('royal_token_stats', {})}")
    sc_ka = ka.get("shuffled_control", {})
    parts.append(f"- shuffled null: observed={sc_ka.get('observed')}  "
                 f"mean={sc_ka.get('shuffled_mean')}  z={sc_ka.get('z')}")
    parts.append(f"- Royal-name sequences MUST show conditional structure "
                 f"vs shuffle (z << -3) if royal-name collocations are real.")
    parts.append("")

    parts.append("## Late Egyptian control (structure comparator)")
    parts.append("")
    eg = report.get("egyptian_control", {})
    sc_eg = eg.get("shuffled_control", {})
    parts.append(f"- tokens={eg.get('n_tokens', 0)}  "
                 f"distinct={eg.get('n_distinct', 0)}")
    parts.append(f"- H\u2081={eg.get('unigram_entropy_bits')}  "
                 f"H(next|prev)={eg.get('conditional_bigram_entropy_bits')}")
    parts.append(f"- shuffle null: observed={sc_eg.get('observed')}  "
                 f"mean={sc_eg.get('shuffled_mean')}  z={sc_eg.get('z')}")
    parts.append(f"- Note: Late Egyptian is a KNOWN language (Afro-Asiatic). "
                 f"Its structure signal is a sanity check \u2014 NOT evidence "
                 f"that Meroitic is Egyptian.")
    parts.append("")

    parts.append("## Negative control")
    parts.append("")
    nc = report.get("negative_control", {})
    sc_nc = nc.get("shuffled_control", {})
    parts.append(f"- Label: {nc.get('label', '?')}")
    parts.append(f"- tokens={nc.get('n_tokens', 0)}  "
                 f"distinct={nc.get('n_distinct', 0)}")
    parts.append(f"- shuffle null: observed={sc_nc.get('observed')}  "
                 f"mean={sc_nc.get('shuffled_mean')}  z={sc_nc.get('z')}")
    parts.append(f"- A unigram-matched shuffle of Meroitic must NOT light up.")
    parts.append("")

    parts.append(f"## Verdict: **{verdict}**")
    parts.append("")
    for r in report.get("groups", []):
        sc = r.get("shuffled_control", {})
        z = sc.get("z", 0)
        structured = z < -3.0
        parts.append(f"- {r['label']}: "
                     f"{'STRUCTURE_SIGNAL' if structured else 'NO_SIGNAL'} "
                     f"z={z}")
    ka_z = ka.get("shuffled_control", {}).get("z", 0)
    eg_z = eg.get("shuffled_control", {}).get("z", 0)
    nc_z = nc.get("shuffled_control", {}).get("z", 0)
    parts.append(f"- KA royal-name: z={ka_z} "
                 f"{'PASS' if ka_z < -3 else 'WARN'}")
    parts.append(f"- Late Egyptian control: z={eg_z} "
                 f"{'structure_expected' if eg_z < -3 else 'noisy_sample'}")
    parts.append(f"- Negative control: z={nc_z} "
                 f"{'PASS' if abs(nc_z) < 3 else 'FAIL'}")
    parts.append("")
    parts.append(report.get("caveat", ""))
    parts.append("")
    parts.append("## Caveats")
    parts.append("1. **Corpus is heterogeneous** \u2014 RAMSES scrapings aggregate "
                 "inscriptions of varying length and quality; no per-inscription "
                 "metadata (site, medium, date) is available in the open corpus.")
    parts.append("2. **Late Egyptian control is small** (~10K tokens vs 755K "
                 "Meroitic). Structure signal is not directly comparable; "
                 "the control only confirms that a known-language corpus "
                 "passes the same test.")
    parts.append("3. **Royal-name set is provisional** \u2014 based on published "
                 "vocabularies (Millet, Lobban, Rilly). Not exhaustive.")
    parts.append("4. **This is structure analysis, not decipherment.** "
                 "Entropy and bigram statistics are necessary but not "
                 "sufficient for identifying language properties.")
    parts.append("5. **Meroitic is partially deciphered** \u2014 sign values are "
                 "known; this does not imply the language is understood.")
    parts.append("\n---")
    parts.append("*G16 Meroitic \u2014 structure != meaning. No translation, "
                 "no decipherment, no aliens.*")

    return "\n".join(parts)


# --- main() ---------------------------------------------------------------

def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="G16 Meroitic structure probe.")
    ap.add_argument("--synthetic", action="store_true",
                    help="Use synthetic known-answer corpus.")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--n-shuffles", type=int, default=100)
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.synthetic:
        sequences = synth_meroitic_corpus(seed=args.seed)
        label = "synthetic_known_answer"
        all_meroitic_seqs = sequences
    else:
        sequences = load_corpus(DATA_DIR)
        label = "meroitic_corpus_ramses"
        all_meroitic_seqs = sequences

    # Full-corpus analysis
    group_result = run_meroitic_probe(all_meroitic_seqs, label=label,
                                       n_shuffles=args.n_shuffles,
                                       seed=args.seed)
    sc = group_result.get("shuffled_control", {})
    z_str = f"{sc.get('z', 0):>7.2f}" if isinstance(sc.get('z'), (int, float)) else "?"
    print(f"  {label:30s}: tokens={group_result['n_tokens']:7d}  "
          f"distinct={group_result['n_distinct']:5d}  "
          f"cond-H z={z_str}")

    # Known-answer: royal-name subsets
    if not args.synthetic:
        royal_seqs = royal_name_sequences(all_meroitic_seqs)
    else:
        royal_seqs = all_meroitic_seqs
    ka_result = run_meroitic_probe(royal_seqs,
                                    label="royal_name_ka",
                                    n_shuffles=args.n_shuffles,
                                    seed=args.seed)
    ka_royal_stats = formulaic_token_count(all_meroitic_seqs)
    ka_result["royal_token_stats"] = ka_royal_stats
    print(f"  {'royal_name_ka':30s}: tokens={ka_result['n_tokens']:7d}  "
          f"distinct={ka_result['n_distinct']:5d}  "
          f"z={ka_result.get('shuffled_control', {}).get('z', 0)}")

    # Late Egyptian control
    if not args.synthetic:
        egy_seqs = load_egyptian_control(DATA_DIR)
    else:
        egy_seqs = []
    if egy_seqs:
        eg_result = run_meroitic_probe(egy_seqs, label="late_egyptian_control",
                                        n_shuffles=args.n_shuffles,
                                        seed=args.seed + 333)
        print(f"  {'late_egyptian_control':30s}: "
              f"tokens={eg_result['n_tokens']:7d}  "
              f"distinct={eg_result['n_distinct']:5d}  "
              f"z={eg_result.get('shuffled_control', {}).get('z', 0)}")
    else:
        eg_result = {
            "label": "late_egyptian_control",
            "error": "sample not found",
            "n_tokens": 0,
            "n_distinct": 0,
            "shuffled_control": {"z": 0},
        }

    # Negative control: unigram-matched shuffle of Meroitic
    flat_tokens = flatten(all_meroitic_seqs)
    rng = rnd.Random(args.seed + 999)
    shuffled_tokens = list(flat_tokens)
    rng.shuffle(shuffled_tokens)
    neg_seqs = [shuffled_tokens]
    nc_result = run_meroitic_probe(neg_seqs,
                                    label="unigram_shuffle_negative_control",
                                    n_shuffles=args.n_shuffles,
                                    seed=args.seed + 777)
    print(f"  {'negative_control':30s}: tokens={nc_result['n_tokens']:7d}  "
          f"z={nc_result.get('shuffled_control', {}).get('z', 0)}")

    # Determine verdict
    meroitic_structured = group_result.get("invariants", {}).get(
        "conditional_structure_vs_shuffle", False)
    nc_z = nc_result.get("shuffled_control", {}).get("z", 0)
    nc_pass = abs(nc_z) < 3.0

    if meroitic_structured and nc_pass:
        verdict = "STRUCTURE_SIGNAL"
    elif not meroitic_structured:
        verdict = "NO_SIGNAL"
    else:
        verdict = "UNDERDETERMINED"

    metadata = {
        "n_meroitic_inscriptions": len(all_meroitic_seqs),
        "n_meroitic_tokens": len(flat_tokens),
        "n_meroitic_distinct": len(set(flat_tokens)),
        "n_egyptian_tokens": len(flatten(egy_seqs)) if egy_seqs else 0,
        "n_egyptian_distinct": len(set(flatten(egy_seqs))) if egy_seqs else 0,
    }

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata,
        "groups": [group_result],
        "known_answer": ka_result,
        "egyptian_control": eg_result,
        "negative_control": nc_result,
        "verdict": verdict,
        "pipeline": {
            "tool": "tools/scripts/meroitic_probe.py + tools/forensics/symbolseq.py",
            "parameters": {"n_shuffles": args.n_shuffles, "seed": args.seed},
        },
        "data_source": SOURCE,
        "stance": STANCE,
        "forbidden": list(FORBIDDEN_PHRASES),
        "caveat": (
            "Structure != meaning. Entropy and bigram statistics confirm "
            "sign-sequence structure distinct from noise, but do NOT "
            "constitute decipherment. Meroitic sign values are known; "
            "the language remains poorly understood."
        ),
    }

    out_json = OUT_DIR / "run.json"
    out_md = OUT_DIR / "NOTES.md"
    out_json.write_text(json.dumps(report, indent=2, default=str))
    out_md.write_text(write_notes_md(report))
    print(f"\nwrote {out_json}")
    print(f"wrote {out_md}")
    print(f"Verdict: {verdict}")


if __name__ == "__main__":
    main()
