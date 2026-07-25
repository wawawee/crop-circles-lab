"""
symbolseq.py — general symbol-sequence structure analysis ("beyond wheat").

The crop-circle ASCII work is a special case of "is this sequence of discrete
symbols structured, and how?". This module generalises it to ANY token stream —
the Phaistos Disc sign sequence, Linear B, an unknown script, a bitstream chunked
into symbols — with the same measure-first discipline and a shuffled-baseline
negative control baked in.

Metrics: unigram (Shannon) entropy, index of coincidence, conditional bigram
entropy H(next|prev), top bigrams, word-length stats, and an LZ78-dictionary
compressibility proxy. `structured_vs_shuffled` compares the real conditional
entropy against many frequency-matched random shuffles (the honest control).

Pure standard library. Validated in tools/forensics/tests/test_symbolseq.py.

CAVEAT (applies to every result): "natural-language-like" statistics are
NECESSARY, NOT SUFFICIENT for "a real / decodable language". At small corpus
sizes many non-linguistic generators (ritual formulae, templates) look the same.
"""
from __future__ import annotations

import math
import random
from collections import Counter


def flatten(words):
    """words: list of lists of tokens (word groups) OR a flat list. Drops None."""
    out = []
    for w in words:
        if isinstance(w, (list, tuple)):
            out.extend(t for t in w if t is not None)
        elif w is not None:
            out.append(w)
    return out


def unigram_entropy(tokens):
    n = len(tokens)
    if n == 0:
        return 0.0
    c = Counter(tokens)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


def index_of_coincidence(tokens):
    n = len(tokens)
    if n < 2:
        return 0.0
    c = Counter(tokens)
    return sum(v * (v - 1) for v in c.values()) / (n * (n - 1))


def conditional_bigram_entropy(tokens):
    """H(next | prev) in bits over consecutive tokens."""
    if len(tokens) < 2:
        return 0.0
    bg = Counter(zip(tokens[:-1], tokens[1:]))
    first = Counter(tokens[:-1])
    nb = sum(bg.values())
    h = 0.0
    for (x, y), cxy in bg.items():
        pxy = cxy / nb
        pygx = cxy / first[x]
        h -= pxy * math.log2(pygx)
    return h


def top_bigrams(tokens, k=8):
    bg = Counter(zip(tokens[:-1], tokens[1:]))
    return bg.most_common(k)


def word_length_stats(words):
    lens = [len([t for t in w if t is not None]) for w in words
            if isinstance(w, (list, tuple))]
    if not lens:
        return {}
    return {"n_words": len(lens), "min": min(lens), "max": max(lens),
            "mean": round(sum(lens) / len(lens), 2),
            "hist": dict(sorted(Counter(lens).items()))}


def lz78_ratio(tokens):
    """LZ78 dictionary size / length — lower => more repetition/compressible."""
    if not tokens:
        return 1.0
    seq = [str(t) for t in tokens]
    d, w, phrases = set(), "", 0
    for s in seq:
        ws = w + ("|" if w else "") + s
        if ws in d:
            w = ws
        else:
            d.add(ws); phrases += 1; w = ""
    return round(phrases / len(seq), 4)


def structured_vs_shuffled(tokens, n=1000, seed=0):
    """Compare real H(next|prev) against frequency-matched shuffles (control).
    Negative z => the real sequence is MORE predictable (more structured) than chance."""
    obs = conditional_bigram_entropy(tokens)
    rng = random.Random(seed)
    t = list(tokens)
    samples = []
    for _ in range(n):
        rng.shuffle(t)
        samples.append(conditional_bigram_entropy(t))
    mu = sum(samples) / len(samples)
    var = sum((s - mu) ** 2 for s in samples) / len(samples)
    sd = math.sqrt(var)
    z = (obs - mu) / sd if sd > 1e-12 else 0.0
    return {"observed": round(obs, 4), "shuffled_mean": round(mu, 4),
            "shuffled_sd": round(sd, 4), "z": round(z, 2),
            "more_structured_than_chance": obs < mu - 2 * sd}


def repeat_structure(words, min_count=2, min_len=2):
    """Find repeated word-groups and characterise their LAYOUT.

    Answers "is a refrain spaced regularly (verse/metre) or clustered (headers)?"
    by reporting each repeated group's positions, the gaps between successive
    occurrences, and the coefficient of variation of those gaps (low CV => regular).
    """
    import statistics
    groups = [tuple(t for t in w if t is not None) for w in words
              if isinstance(w, (list, tuple))]
    pos = {}
    for i, g in enumerate(groups):
        if len(g) >= min_len:
            pos.setdefault(g, []).append(i)
    out = []
    for g, ps in pos.items():
        if len(ps) >= min_count:
            gaps = [ps[i + 1] - ps[i] for i in range(len(ps) - 1)]
            mean = sum(gaps) / len(gaps) if gaps else 0.0
            cv = (statistics.pstdev(gaps) / mean) if (len(gaps) > 1 and mean) else 0.0
            layout = ("regular/metrical" if (len(gaps) >= 2 and cv < 0.15)
                      else "single-gap" if len(gaps) == 1 else "irregular/clustered")
            out.append({"group": list(g), "count": len(ps), "positions": ps,
                        "gaps": gaps, "gap_mean": round(mean, 2), "gap_cv": round(cv, 3),
                        "layout": layout})
    out.sort(key=lambda d: (-d["count"], -len(d["group"])))
    return out


def analyze(words, n_shuffles=1000, seed=0):
    tokens = flatten(words)
    k = len(set(tokens))
    return {
        "n_tokens": len(tokens),
        "n_distinct": k,
        "max_entropy_bits": round(math.log2(k), 3) if k else 0.0,
        "unigram_entropy_bits": round(unigram_entropy(tokens), 3),
        "index_of_coincidence": round(index_of_coincidence(tokens), 4),
        "ioc_over_uniform": round(index_of_coincidence(tokens) * k, 3) if k else 0.0,
        "conditional_bigram_entropy_bits": round(conditional_bigram_entropy(tokens), 3),
        "lz78_ratio": lz78_ratio(tokens),
        "top_bigrams": [{"pair": list(p), "count": c} for p, c in top_bigrams(tokens)],
        "word_lengths": word_length_stats(words),
        "shuffled_control": structured_vs_shuffled(tokens, n=n_shuffles, seed=seed),
        "caveat": ("Necessary-not-sufficient: these statistics distinguish "
                   "'not random noise' from noise, but NOT 'undeciphered language' "
                   "from 'structured non-linguistic template' at small corpus sizes."),
    }


if __name__ == "__main__":
    import json
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(here, "..", ".."))
    seq_path = os.path.join(root, "data", "beyond", "phaistos_sequence.json")
    if os.path.exists(seq_path):
        data = json.load(open(seq_path))
        words = data["sides"]["A"] + data["sides"]["B"]
        rep = analyze(words)
        out = os.path.join(root, "outputs", "phaistos_analysis.json")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        json.dump(rep, open(out, "w"), indent=2)
        print("PHAISTOS DISC —", json.dumps({k: rep[k] for k in (
            "n_tokens", "n_distinct", "unigram_entropy_bits", "index_of_coincidence",
            "conditional_bigram_entropy_bits", "lz78_ratio")}, indent=2))
        print("shuffled control:", rep["shuffled_control"])
        print("top bigram:", rep["top_bigrams"][0])
        print("wrote", out)
        # refrain / repeat structure (Kimi's question: regular metre vs clustered headers?)
        refr = {"side_A": repeat_structure(data["sides"]["A"]),
                "side_B": repeat_structure(data["sides"]["B"]),
                "combined": repeat_structure(words)}
        rout = os.path.join(root, "outputs", "phaistos_refrain.json")
        json.dump(refr, open(rout, "w"), indent=2)
        print("\nrepeated word-groups, SIDE A:")
        for r in refr["side_A"]:
            print("  %s x%d  positions=%s gaps=%s -> %s"
                  % (r["group"], r["count"], r["positions"], r["gaps"], r["layout"]))
        print("wrote", rout)
    else:
        # tiny self-demo
        print(analyze([["A", "B"], ["A", "B"], ["A", "C"]], n_shuffles=200))
