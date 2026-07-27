"""
test_indus_west_negcontrol.py — known-answer tests for
tools/scripts/indus_west_negcontrol.py (G9++).

Run:
    python tools/scripts/tests/test_indus_west_negcontrol.py
"""
from __future__ import annotations

import sys
from collections import Counter

sys.path.insert(0, ".")
import tools.scripts.indus_west_negcontrol as IW
from tools.forensics.symbolseq import (
    conditional_bigram_entropy,
    unigram_entropy,
    index_of_coincidence,
    lz78_ratio,
)


# --- Fixture loading -------------------------------------------------------

def test_load_west_indus_fixture() -> None:
    """West-style fixture must load with expected site structure."""
    seqs = IW.load_west_indus_fixture(IW.DATA_DIR)
    assert len(seqs) >= 100, f"expected >=100 sequences, got {len(seqs)}"
    all_signs = [s for seq in seqs for s in seq]
    assert len(all_signs) >= 500, f"expected >=500 tokens, got {len(all_signs)}"
    distinct = set(all_signs)
    assert len(distinct) >= 50, f"expected >=50 distinct signs, got {len(distinct)}"


def test_load_tamil_control() -> None:
    """Tamil control must load with expected structure."""
    seqs = IW.load_tamil_control(IW.DATA_DIR)
    assert len(seqs) >= 50, f"expected >=50 sequences, got {len(seqs)}"


def test_load_telugu_control() -> None:
    """Telugu control must load with expected structure."""
    seqs = IW.load_telugu_control(IW.DATA_DIR)
    assert len(seqs) >= 50, f"expected >=50 sequences, got {len(seqs)}"


# --- Shuffle primitives ----------------------------------------------------

def test_unigram_preserving_shuffle_keeps_counter() -> None:
    toks = ["P001", "P001", "P121", "P385", "P385", "P385", "P073"]
    shuf = IW.unigram_preserving_shuffle(toks, seed=0)
    assert Counter(shuf) == Counter(toks)
    assert len(shuf) == len(toks)


def test_unigram_preserving_shuffle_deterministic() -> None:
    toks = [f"P{i:03d}" for i in range(1, 30)]
    assert IW.unigram_preserving_shuffle(toks, 0) == \
        IW.unigram_preserving_shuffle(toks, 0)
    assert IW.unigram_preserving_shuffle(toks, 1) != \
        IW.unigram_preserving_shuffle(toks, 0)


# --- Entropy edge cases ----------------------------------------------------

def test_constant_sequence_zero_conditional_entropy() -> None:
    toks = ["P001"] * 20
    assert conditional_bigram_entropy(toks) < 1e-9


def test_periodic_sequence_low_conditional_entropy() -> None:
    toks = ["P001", "P121"] * 30
    assert conditional_bigram_entropy(toks) < 1e-9


def test_uniform_entropy_approx_log2() -> None:
    toks = [f"P{i:03d}" for i in range(1, 9)] * 30
    assert abs(unigram_entropy(toks) - 3.0) < 0.01


def test_index_of_coincidence_uniform() -> None:
    toks = [f"P{i:03d}" for i in range(1, 51)] * 2
    ic = index_of_coincidence(toks)
    assert 0.0 < ic < 0.03  # Uniform over 50 signs


def test_lz78_ratio_constant() -> None:
    toks = ["P001"] * 100
    assert lz78_ratio(toks) < 0.2  # Highly compressible


# --- Structured vs shuffled control ----------------------------------------

def test_structured_beats_shuffled() -> None:
    """Strongly periodic sequence must be more predictable than its shuffle."""
    toks = (["P001", "P121", "P385"] * 40)
    ctrl = IW.shuffled_cond_H(toks, n=300, seed=1)
    assert ctrl["observed"] < ctrl["shuffled_mean"]
    assert ctrl["z"] < -2.0


def test_shuffled_cond_H_empty() -> None:
    ctrl = IW.shuffled_cond_H([], n=100)
    assert ctrl["observed"] == 0.0
    assert ctrl["z"] == 0.0


def test_shuffled_cond_H_single() -> None:
    ctrl = IW.shuffled_cond_H(["P001"], n=100)
    assert ctrl["observed"] == 0.0
    assert ctrl["z"] == 0.0


# --- Transition graph ------------------------------------------------------

def test_transition_graph_empty() -> None:
    stats = IW.transition_graph_stats([])
    assert stats == {}


def test_transition_graph_single_sequence() -> None:
    stats = IW.transition_graph_stats([["P001", "P121", "P385"]])
    assert stats["n_nodes"] == 3
    assert stats["n_edges"] == 2


def test_transition_graph_reciprocity() -> None:
    stats = IW.transition_graph_stats([
        ["P001", "P121"], ["P121", "P001"],
    ])
    assert stats["reciprocity"] > 0


# --- Entropy profile & distance --------------------------------------------

def test_entropy_profile() -> None:
    seqs = [["P001", "P121", "P385"], ["P001", "P121"]]
    prof = IW.entropy_profile(seqs)
    assert "unigram_entropy" in prof
    assert "cond_bigram_entropy" in prof
    assert "ioc" in prof
    assert "lz78_ratio" in prof
    assert prof["unigram_entropy"] > 0


def test_profile_distance_zero() -> None:
    p = {"unigram_entropy": 3.0, "cond_bigram_entropy": 1.5,
         "ioc": 0.1, "lz78_ratio": 0.5}
    assert IW.profile_distance(p, p) == 0.0


def test_profile_distance_nonzero() -> None:
    p1 = {"unigram_entropy": 3.0, "cond_bigram_entropy": 1.5,
          "ioc": 0.1, "lz78_ratio": 0.5}
    p2 = {"unigram_entropy": 5.0, "cond_bigram_entropy": 3.0,
          "ioc": 0.05, "lz78_ratio": 0.3}
    d = IW.profile_distance(p1, p2)
    assert d > 0


# --- Bigram Jaccard --------------------------------------------------------

def test_bigram_jaccard_identical() -> None:
    seqs = [["P001", "P121", "P385"], ["P001", "P121", "P385"]]
    assert IW.bigram_jaccard(seqs, seqs) == 1.0


def test_bigram_jaccard_disjoint() -> None:
    a = [["P001", "P121"]]
    b = [["X001", "X121"]]
    assert IW.bigram_jaccard(a, b) < 0.1


# --- N-gram finder ---------------------------------------------------------

def test_find_common_ngrams_empty() -> None:
    assert IW.find_common_ngrams([], min_len=2) == []


def test_find_common_ngrams_finds_repeats() -> None:
    seqs = [["P001", "P121", "P385"]] * 3
    ngrams = IW.find_common_ngrams(seqs, min_len=2, min_seq=2)
    assert len(ngrams) >= 1
    any_p001_p121 = any(g["ngram"] == ["P001", "P121"] for g in ngrams)
    assert any_p001_p121


# --- Known-answer: West fixture structure ----------------------------------

def test_west_fixture_known_answer() -> None:
    """West-style fixture MUST show conditional structure vs shuffle."""
    seqs = IW.load_west_indus_fixture(IW.DATA_DIR)
    rep = IW.run_corpus_analysis(seqs, "test_ka", n_shuffles=300, seed=0)
    inv = rep["invariants"]
    assert inv["conditional_structure_vs_shuffle"], \
        "West-style fixture should have conditional structure"
    z = rep["shuffled_control"]["z"]
    assert z < -3.0, f"expected strong structure z < -3, got {z}"


def test_west_fixture_has_formulaic_ngrams() -> None:
    """West-style fixture should have repeated n-grams (e.g., P122+P385)."""
    seqs = IW.load_west_indus_fixture(IW.DATA_DIR)
    rep = IW.run_corpus_analysis(seqs, "test_formulaic", n_shuffles=100, seed=0)
    assert rep["has_formulaic_repeated_ngrams"]


def test_tamil_control_known_answer() -> None:
    """Tamil synthetic control should show structure vs shuffle."""
    seqs = IW.load_tamil_control(IW.DATA_DIR)
    rep = IW.run_corpus_analysis(seqs, "test_ka_tamil", n_shuffles=300, seed=0)
    assert rep["invariants"]["conditional_structure_vs_shuffle"]


def test_telugu_control_known_answer() -> None:
    """Telugu synthetic control should show structure vs shuffle."""
    seqs = IW.load_telugu_control(IW.DATA_DIR)
    rep = IW.run_corpus_analysis(seqs, "test_ka_telugu", n_shuffles=300, seed=0)
    assert rep["invariants"]["conditional_structure_vs_shuffle"]


# --- Full pipeline ---------------------------------------------------------

def test_full_pipeline_runs() -> None:
    """Full negative control pipeline must complete without error."""
    west = IW.load_west_indus_fixture(IW.DATA_DIR)
    tamil = IW.load_tamil_control(IW.DATA_DIR)
    telugu = IW.load_telugu_control(IW.DATA_DIR)
    rep = IW.run_negcontrol(west, tamil, telugu,
                            n_shuffles=100, seed=0, is_fixture_only=True)
    assert "verdict" in rep
    assert "west_indus_fixture" in rep
    assert "tamil_control" in rep
    assert "telugu_control" in rep
    assert "cross_comparison" in rep
    assert "known_answer" in rep
    assert "real_data_status" in rep
    assert rep["real_data_status"]["barbara_west_tables"] == "NEVER_ATTEMPTED"


def test_full_pipeline_verdict_format() -> None:
    """Verdict must start with FIXTURE_ONLY for synthetic data."""
    west = IW.load_west_indus_fixture(IW.DATA_DIR)
    tamil = IW.load_tamil_control(IW.DATA_DIR)
    telugu = IW.load_telugu_control(IW.DATA_DIR)
    rep = IW.run_negcontrol(west, tamil, telugu,
                            n_shuffles=100, seed=0, is_fixture_only=True)
    v = rep["verdict"]
    assert v.startswith("FIXTURE_ONLY"), f"expected FIXTURE_ONLY prefix, got {v}"


# --- Stance honesty: forbidden phrases -------------------------------------

def test_forbidden_phrases_listed() -> None:
    expected = ("translates to", "represents",
                "is related to Dravidian",
                "Indus is Dravidian",
                "aliens wrote")
    for needle in expected:
        assert needle in IW.FORBIDDEN_PHRASES, f"missing: {needle}"


def test_forbidden_phrases_no_family_claims() -> None:
    """Ensure no language-family claim phrases leak."""
    text = " ".join(IW.FORBIDDEN_PHRASES)
    for bad in ["language family confirmed", "decoded as Dravidian"]:
        assert bad in text, f"should contain: {bad}"


# --- Synthetic fallbacks ---------------------------------------------------

def test_synth_fixture_produces_sequences() -> None:
    seqs = IW.synth_fixture(seed=0)
    assert len(seqs) >= 50
    for s in seqs:
        assert len(s) >= 1


def test_synth_tamil_produces_sequences() -> None:
    seqs = IW.synth_tamil_corpus(seed=0)
    assert len(seqs) >= 50
    for s in seqs:
        assert all(t.startswith("TA_") for t in s)


def test_synth_telugu_produces_sequences() -> None:
    seqs = IW.synth_telugu_corpus(seed=0)
    assert len(seqs) >= 50
    for s in seqs:
        assert all(t.startswith("TE_") for t in s)


# --- Determinism -----------------------------------------------------------

def test_deterministic_output() -> None:
    """Same seed must produce identical results."""
    west = IW.synth_fixture(seed=0)
    tamil = IW.synth_tamil_corpus(seed=1)
    telugu = IW.synth_telugu_corpus(seed=2)
    rep1 = IW.run_negcontrol(west, tamil, telugu,
                             n_shuffles=100, seed=0, is_fixture_only=True)
    west2 = IW.synth_fixture(seed=0)
    tamil2 = IW.synth_tamil_corpus(seed=1)
    telugu2 = IW.synth_telugu_corpus(seed=2)
    rep2 = IW.run_negcontrol(west2, tamil2, telugu2,
                             n_shuffles=100, seed=0, is_fixture_only=True)
    assert rep1["verdict"] == rep2["verdict"]


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
