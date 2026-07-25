"""
linear_a_probe.py — thin loader for Linear A/B sign-sequence entropy analysis.

Reuses tools/forensics/symbolseq.py for all metrics. Does NOT fork a second
entropy stack. Produces outputs/linear_a/run.json.

Stance: structure != meaning. No decipherment claims.
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA = os.path.join(ROOT, "data", "scripts", "linear_a")
OUT = os.path.join(ROOT, "outputs", "linear_a")
sys.path.insert(0, os.path.join(ROOT, "tools", "forensics"))
import symbolseq as S  # noqa: E402


def load_corpus(name: str):
    path = os.path.join(DATA, f"{name}_corpus.json")
    with open(path) as f:
        return json.load(f)


def run_analysis(words, label: str, n_shuffles: int = 1000, seed: int = 0):
    tokens = S.flatten(words)
    base = S.analyze(words, n_shuffles=n_shuffles, seed=seed)
    repeats = S.repeat_structure(words)
    return {
        "label": label,
        "n_tokens": base["n_tokens"],
        "n_distinct": base["n_distinct"],
        "alphabet_size": base["max_entropy_bits"],
        "unigram_entropy_bits": base["unigram_entropy_bits"],
        "index_of_coincidence": base["index_of_coincidence"],
        "ioc_over_uniform": base["ioc_over_uniform"],
        "conditional_bigram_entropy_bits": base["conditional_bigram_entropy_bits"],
        "lz78_ratio": base["lz78_ratio"],
        "top_bigrams": base["top_bigrams"],
        "word_lengths": base["word_lengths"],
        "shuffled_control": base["shuffled_control"],
        "repeat_structure": [
            {k: r[k] for k in ("group", "count", "positions", "gaps", "gap_mean", "gap_cv", "layout")}
            for r in repeats
        ],
        "caveat": ("Structure != meaning. These metrics distinguish structured from random, "
                   "not 'language' from 'structured template' at small corpus sizes."),
    }


def main():
    os.makedirs(OUT, exist_ok=True)

    lin_a = load_corpus("linear_a")
    lin_b = load_corpus("linearb")

    results = {"corpus": [], "controls": [], "negative": [], "metadata": {}}

    # 1. Linear A — full corpus
    results["corpus"].append(
        run_analysis(lin_a["words"], "Linear A (full corpus)")
    )

    # 2. Linear B — known-answer
    results["corpus"].append(
        run_analysis(lin_b["words"], "Linear B (known-answer: deciphered syllabary)")
    )

    # 3. Negative control: unigram-matched shuffle of Linear A
    #    symbolseq.structured_vs_shuffled already does frequency-matched shuffle
    #    but here we want a separate run that's explicitly labeled as negative control
    import random as rnd
    rng = rnd.Random(42)
    flat_a = S.flatten(lin_a["words"])
    shuffled = list(flat_a)
    rng.shuffle(shuffled)
    # Re-chunk into pseudo-words of similar lengths for structure analysis
    word_lens = [len(w) for w in lin_a["words"]]
    idx = 0
    shuffled_words = []
    for wl in word_lens:
        shuffled_words.append(shuffled[idx:idx + wl])
        idx += wl
    results["negative"].append(
        run_analysis(shuffled_words, "Linear A — unigram-matched shuffle (negative control)")
    )

    # 4. Metadata
    results["metadata"] = {
        "pipeline": {
            "tool": "tools/scripts/linear_a_probe.py + tools/forensics/symbolseq.py",
            "analyze_params": {"n_shuffles": 1000, "seed": 0},
        },
        "data_sources": [
            "SigLA (sigla.phis.me) — Ester Salgarella & Simon Castellan, CC BY-NC-SA 4.0",
            "lineara.xyz / mwenge — GORILA compilations (Godart & Olivier + Douros)",
        ],
        "stance": "structure != meaning. No decipherment claims.",
        "forbidden": "decipherment, language-family claims, 'Minoan = X'",
    }

    path = os.path.join(OUT, "run.json")
    with open(path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"wrote {path}")

    # Print summary
    for group_key in ("corpus", "negative"):
        for r in results[group_key]:
            sc = r["shuffled_control"]
            print(f"\n{'='*60}")
            print(f"{r['label']}")
            print(f"{'='*60}")
            print(f"  tokens={r['n_tokens']}  distinct={r['n_distinct']}  "
                  f"H₁={r['unigram_entropy_bits']}  IC={r['index_of_coincidence']}")
            print(f"  H(next|prev)={r['conditional_bigram_entropy_bits']}  "
                  f"LZ78={r['lz78_ratio']}")
            print(f"  shuffle control: observed={sc['observed']}  mean={sc['shuffled_mean']}  "
                  f"z={sc['z']}  structured={sc['more_structured_than_chance']}")
            top = r['top_bigrams'][:3] if r['top_bigrams'] else []
            if top:
                print(f"  top bigrams: {[(t['pair'], t['count']) for t in top]}")
            rpt = [r2 for r2 in r.get('repeat_structure', []) if r2['count'] >= 3]
            if rpt:
                print(f"  repeated phrases (>=3x): {len(rpt)}")
                for rp in rpt[:3]:
                    print(f"    {rp['group']} x{rp['count']}  gaps={rp['gaps']}  {rp['layout']}")


if __name__ == "__main__":
    main()
