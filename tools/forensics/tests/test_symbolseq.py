"""Known-answer tests for tools/forensics/symbolseq.py.
Run: python tools/forensics/tests/test_symbolseq.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import symbolseq as S  # noqa: E402


def test_uniform_entropy():
    toks = list(range(8)) * 50
    assert abs(S.unigram_entropy(toks) - 3.0) < 0.01   # log2(8)=3


def test_constant_zero_entropy_and_ioc_one():
    toks = ["x"] * 40
    assert S.unigram_entropy(toks) == 0.0
    assert S.index_of_coincidence(toks) == 1.0


def test_periodic_conditional_entropy_zero():
    toks = ["A", "B"] * 60          # ABAB... -> next is deterministic given prev
    assert S.conditional_bigram_entropy(toks) < 1e-9


def test_structured_beats_shuffled():
    # a strongly periodic sequence must be MORE predictable than its shuffle
    toks = (["A", "B", "C"] * 40)
    ctrl = S.structured_vs_shuffled(toks, n=300, seed=1)
    assert ctrl["observed"] < ctrl["shuffled_mean"]
    assert ctrl["more_structured_than_chance"]


def test_flatten_drops_none():
    assert S.flatten([[1, 2, None], [3]]) == [1, 2, 3]


def test_repeat_structure_regular():
    words = [["R", "E", "F"] if i % 3 == 0 else [str(i), "z"] for i in range(9)]
    top = [r for r in S.repeat_structure(words) if r["group"] == ["R", "E", "F"]][0]
    assert top["count"] == 3 and top["gaps"] == [3, 3]
    assert top["layout"].startswith("regular")


def test_phaistos_loads_and_is_structured():
    import json
    p = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "beyond",
                     "phaistos_sequence.json")
    data = json.load(open(p))
    words = data["sides"]["A"] + data["sides"]["B"]
    rep = S.analyze(words, n_shuffles=300)
    assert 235 <= rep["n_tokens"] <= 242          # ~241 tokens
    assert rep["n_distinct"] <= 45
    assert 4.5 <= rep["unigram_entropy_bits"] <= 5.2   # ~4.99
    assert rep["shuffled_control"]["observed"] < rep["shuffled_control"]["shuffled_mean"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    ok = 0
    for fn in fns:
        try:
            fn(); print(f"PASS {fn.__name__}"); ok += 1
        except AssertionError as e:
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{ok}/{len(fns)} passed")
    sys.exit(0 if ok == len(fns) else 1)
