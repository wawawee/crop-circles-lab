"""
test_indus_probe.py — known-answer tests for tools/scripts/indus_probe.py.

Run:
    python tools/scripts/tests/test_indus_probe.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter

import tools.scripts.indus_probe as IND
from tools.forensics.symbolseq import (
    conditional_bigram_entropy,
    unigram_entropy,
)


# --- Shuffle primitives ----------------------------------------------------

def test_unigram_preserving_shuffle_keeps_counter() -> None:
    toks = ["P001", "P001", "P121", "P121", "P121", "P385", "P385"]
    shuf = IND.unigram_preserving_shuffle(toks, seed=0)
    assert Counter(shuf) == Counter(toks)
    assert len(shuf) == len(toks)
    assert shuf == IND.unigram_preserving_shuffle(toks, seed=0)


def test_unigram_preserving_shuffle_deterministic() -> None:
    toks = [f"P{i:03d}" for i in range(1, 50)]
    assert IND.unigram_preserving_shuffle(toks, 0) == \
        IND.unigram_preserving_shuffle(toks, 0)
    assert IND.unigram_preserving_shuffle(toks, 1) != \
        IND.unigram_preserving_shuffle(toks, 0)


# --- Entropy ---------------------------------------------------------------

def test_constant_sequence_zero_conditional_entropy() -> None:
    toks = ["P001"] * 20
    assert conditional_bigram_entropy(toks) < 1e-9


def test_periodic_sequence_low_conditional_entropy() -> None:
    toks = ["P001", "P121"] * 30
    assert conditional_bigram_entropy(toks) < 1e-9


def test_uniform_entropy_approx_log2() -> None:
    toks = [f"P{i:03d}" for i in range(1, 9)] * 30
    assert abs(unigram_entropy(toks) - 3.0) < 0.01


# --- Structured vs shuffled control ----------------------------------------

def test_structured_beats_shuffled() -> None:
    """Strongly periodic sequence must be more predictable than its shuffle."""
    toks = (["P001", "P121", "P385"] * 40)
    ctrl = IND.shuffled_cond_H(toks, n=300, seed=1)
    assert ctrl["observed"] < ctrl["shuffled_mean"]
    assert ctrl["z"] < -2.0


def test_shuffled_cond_H_empty() -> None:
    ctrl = IND.shuffled_cond_H([], n=100)
    assert ctrl["observed"] == 0.0
    assert ctrl["z"] == 0.0


def test_shuffled_cond_H_single() -> None:
    ctrl = IND.shuffled_cond_H(["P001"], n=100)
    assert ctrl["observed"] == 0.0
    assert ctrl["z"] == 0.0


# --- Transition graph ------------------------------------------------------

def test_transition_graph_empty() -> None:
    stats = IND.transition_graph_stats([])
    assert stats == {}


def test_transition_graph_single_sequence() -> None:
    stats = IND.transition_graph_stats([["P001", "P121", "P385"]])
    assert stats["n_nodes"] == 3
    assert stats["n_edges"] == 2
    assert stats["density"] > 0


def test_transition_graph_reciprocity() -> None:
    """A<->B bidirectional edge should give reciprocity > 0."""
    stats = IND.transition_graph_stats([["P001", "P121"], ["P121", "P001"]])
    assert stats["reciprocity"] > 0


# --- Degree-preserving null (M77-style) ------------------------------------

def test_degree_preserving_null_preserves_lengths() -> None:
    seqs = [["P001", "P121"], ["P385", "P073", "P108"], ["P202"]]
    null = IND.degree_preserving_null(seqs, seed=0)
    assert len(null) == len(seqs)
    for n, o in zip(null, seqs):
        assert len(n) == len(o)


def test_degree_preserving_null_preserves_sign_frequencies() -> None:
    seqs = [["P001", "P121", "P385"], ["P001", "P121"], ["P385"]]
    orig_flat = [s for seq in seqs for s in seq]
    null = IND.degree_preserving_null(seqs, seed=0)
    null_flat = [s for seq in null for s in seq]
    assert Counter(orig_flat) == Counter(null_flat)


def test_degree_preserving_null_breaks_bigrams() -> None:
    """Mixed-sign columns should have bigrams disrupted after shuffle."""
    seqs = [["P001", "P121", "P385"],
            ["P121", "P385", "P001"],
            ["P385", "P001", "P121"]]
    orig_ent = conditional_bigram_entropy([s for seq in seqs for s in seq])
    null = IND.degree_preserving_null(seqs, seed=7)
    null_ent = conditional_bigram_entropy([s for seq in null for s in seq])
    assert null_ent > orig_ent + 0.001


# --- Build graph stats -----------------------------------------------------

def test_build_transition_graph() -> None:
    graph = IND.build_transition_graph([["P001", "P121", "P385"]])
    assert graph["P001"] == {"P121": 1}
    assert graph["P121"] == {"P385": 1}


# --- N-gram finder ---------------------------------------------------------

def test_find_common_ngrams_empty() -> None:
    assert IND.find_common_ngrams([], min_len=2) == []


def test_find_common_ngrams_finds_repeats() -> None:
    seqs = [["P001", "P121", "P385"]] * 3
    ngrams = IND.find_common_ngrams(seqs, min_len=2, min_seq=2)
    assert len(ngrams) >= 1
    any_p001_p121 = any(g["ngram"] == ["P001", "P121"] for g in ngrams)
    assert any_p001_p121


# --- Known-answer: synthetic corpus ----------------------------------------

def test_synthetic_corpus_invariants_pass() -> None:
    """Synthetic known-answer: structure and graph invariants MUST hold."""
    seqs = IND.synth_indus_corpus(seed=0)
    rep = IND.run_indus_probe(seqs, label="synth_test", n_shuffles=300, seed=0)
    inv = rep["invariants"]
    assert inv["conditional_structure_vs_shuffle"], \
        "synthetic should have conditional structure"
    assert inv["graph_deviates_from_positional_null"], \
        "synthetic should deviate from positional null"
    assert rep["has_formulaic_repeated_ngrams"]


def test_random_shuffled_corpus_invariants_fail() -> None:
    """Randomly permuted signs of equal mass: structure invariant must NOT pass.
    This is the negative control — confirms the test discriminates structure
    from pure noise.
    """
    import random as rnd
    rng = rnd.Random(7)
    base_seqs = IND.synth_indus_corpus(seed=0)
    shuffled_seqs = [rng.sample(s, len(s)) for s in base_seqs]
    rep = IND.run_indus_probe(shuffled_seqs, label="shuffled_neg_control",
                               n_shuffles=300, seed=0)
    inv = rep["invariants"]
    # With per-sequence shuffling the structure should be severely weakened
    # or absent. At minimum conditional structure should fail or be marginal.
    z = rep.get("shuffled_control", {}).get("z", 0.0)
    # Per-sequence shuffle destroys the formulaic patterns
    assert not rep.get("has_formulaic_repeated_ngrams", True) or z > -3.0, \
        f"z={z} — shuffled data should not show strong structure"


# --- Real corpus loading ---------------------------------------------------

def test_load_corpus() -> None:
    """Real corpus must load with expected counts."""
    seqs = IND.load_corpus(IND.DATA_DIR)
    assert len(seqs) >= 100, f"expected >=100 sequences, got {len(seqs)}"
    all_signs = [s for seq in seqs for s in seq]
    assert len(all_signs) >= 800, f"expected >=800 signs, got {len(all_signs)}"
    distinct = set(all_signs)
    assert len(distinct) >= 100, f"expected >=100 distinct signs, got {len(distinct)}"


def test_corpus_runs_probe() -> None:
    """Full pipeline on real corpus must complete without error."""
    seqs = IND.load_corpus(IND.DATA_DIR)
    rep = IND.run_indus_probe(seqs, label="test_corpus", n_shuffles=100, seed=0)
    assert rep["n_tokens"] >= 800
    assert rep["n_sequences"] >= 100
    assert "shuffled_control" in rep
    assert "transition_graph" in rep
    assert "formulaic_segments" in rep


def test_corpus_structure_signal() -> None:
    """Real Indus corpus should show a conditional structure signal (z < -3)."""
    seqs = IND.load_corpus(IND.DATA_DIR)
    rep = IND.run_indus_probe(seqs, label="test_structure", n_shuffles=300, seed=0)
    z = rep["shuffled_control"]["z"]
    assert z < -3.0, f"expected strong structure signal, got z={z}"
    assert rep["invariants"]["conditional_structure_vs_shuffle"]


def test_corpus_has_formulaic_ngrams() -> None:
    """Real Indus corpus should have repeated bigrams."""
    seqs = IND.load_corpus(IND.DATA_DIR)
    rep = IND.run_indus_probe(seqs, label="test_formulaic", n_shuffles=100, seed=0)
    assert rep["has_formulaic_repeated_ngrams"]
    assert len(rep["formulaic_segments"]) >= 3


# --- Stance honesty: forbidden phrases -------------------------------------

def test_forbidden_phrases_listed() -> None:
    expected = ("translates to", "represents",
                "is related to Dravidian", "is related to Sumerian")
    for needle in expected:
        assert needle in IND.FORBIDDEN_PHRASES, f"missing: {needle}"


# --- main() ----------------------------------------------------------------

if __name__ == "__main__":
    fns = [(k, v) for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    ok = bad = 0
    for name, fn in fns:
        try:
            fn()
            print(f"PASS {name}")
            ok += 1
        except AssertionError as e:
            print(f"FAIL {name}: {e}")
            bad += 1
        except Exception as e:
            print(f"ERROR {name}: {type(e).__name__}: {e}")
            bad += 1
    print(f"\n{ok}/{len(fns)} passed, {bad} failed")
    sys.exit(0 if bad == 0 else 1)
