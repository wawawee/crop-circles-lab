"""
test_meroitic_probe.py — known-answer + stance tests for G16.

Run:
    python tools/scripts/tests/test_meroitic_probe.py
"""
from __future__ import annotations

import json
import random as rnd
import sys

import tools.scripts.meroitic_probe as MP
from tools.forensics.symbolseq import (
    conditional_bigram_entropy,
    flatten,
)


def test_stance_present() -> None:
    assert len(MP.STANCE) > 50
    assert "structure" in MP.STANCE.lower()
    assert "decipher" in MP.STANCE.lower()


def test_forbidden_phrases_guard() -> None:
    expected = (
        "Meroitic deciphered",
        "translates to",
        "represents",
        "decodes as",
        "crank 99.5%",
        "Ghost License",
        "Lackadaisical Security",
        "aliens wrote",
    )
    for needle in expected:
        assert needle in MP.FORBIDDEN_PHRASES, f"missing forbidden: {needle}"


def test_source_present() -> None:
    assert "Joshua-Otten/Meroitic-Corpus" in MP.SOURCE
    assert "RAMSES" in MP.SOURCE


def test_royal_name_tokens_defensive() -> None:
    assert len(MP.ROYAL_NAME_TOKENS) > 20
    assert "qor" in MP.ROYAL_NAME_TOKENS
    assert "pqr" in MP.ROYAL_NAME_TOKENS
    assert "kdi" in MP.ROYAL_NAME_TOKENS


def test_shuffle_cond_H_structured_beats_null() -> None:
    toks = (["qor", "pqr", "kdi"] * 40)
    ctrl = MP.shuffled_cond_H(toks, n=200, seed=1)
    assert ctrl["observed"] < ctrl["shuffled_mean"]
    assert ctrl["z"] < -2.0


def test_shuffle_cond_H_empty_and_single() -> None:
    assert MP.shuffled_cond_H([], n=50)["z"] == 0.0
    assert MP.shuffled_cond_H(["qor"], n=50)["z"] == 0.0


def test_synthetic_known_answer_pass() -> None:
    seqs = MP.synth_meroitic_corpus(seed=0)
    rep = MP.run_meroitic_probe(seqs, label="ka", n_shuffles=100, seed=0)
    z = rep["shuffled_control"]["z"]
    assert z < -3.0, f"KA synthetic must pass with z < -3, got {z}"


def test_negative_control_shuffle_no_signal() -> None:
    seqs = MP.synth_meroitic_corpus(seed=0)
    flat = flatten(seqs)
    rng = rnd.Random(999)
    shuffled = list(flat)
    rng.shuffle(shuffled)
    rep = MP.run_meroitic_probe([shuffled], label="neg", n_shuffles=100, seed=777)
    z = rep["shuffled_control"]["z"]
    assert abs(z) < 3.0, f"negative control should be nullish, got z={z}"


def test_load_corpus_expected_scale() -> None:
    seqs = MP.load_corpus(MP.DATA_DIR)
    assert len(seqs) >= 1000
    tokens = flatten(seqs)
    assert len(tokens) >= 100000
    assert len(set(tokens)) >= 500


def test_royal_name_sequences_nonempty() -> None:
    seqs = MP.load_corpus(MP.DATA_DIR)
    royal_seqs = MP.royal_name_sequences(seqs)
    assert len(royal_seqs) > 0


def test_formulaic_token_count_sanity() -> None:
    seqs = MP.load_corpus(MP.DATA_DIR)
    stats = MP.formulaic_token_count(seqs)
    assert stats["n_total_tokens"] > 0
    assert stats["pct_royal_name"] > 0


def test_real_corpus_structure_signal() -> None:
    seqs = MP.load_corpus(MP.DATA_DIR)
    rep = MP.run_meroitic_probe(seqs, label="full", n_shuffles=50, seed=0)
    z = rep["shuffled_control"]["z"]
    assert z < -3.0, f"expected STRUCTURE_SIGNAL, got z={z}"
    assert rep["n_tokens"] >= 100000
    assert rep["n_distinct"] >= 500


def test_egyptian_control_loads() -> None:
    egy = MP.load_egyptian_control(MP.DATA_DIR)
    assert len(egy) > 0
    tokens = flatten(egy)
    assert len(tokens) >= 1000
    assert len(set(tokens)) >= 100


def test_egyptian_control_shows_structure() -> None:
    egy = MP.load_egyptian_control(MP.DATA_DIR)
    rep = MP.run_meroitic_probe(egy, label="egy", n_shuffles=50, seed=333)
    z = rep["shuffled_control"]["z"]
    # Egyptian (a known language) should show structure
    assert z < -3.0, f"Late Egyptian control should show structure, got z={z}"


def test_transition_graph_basic_properties() -> None:
    seqs = MP.synth_meroitic_corpus(seed=0)
    graph = MP.transition_graph_stats(seqs)
    assert graph["n_nodes"] > 0
    assert graph["n_edges"] > 0
    assert graph["density"] > 0


def test_find_common_ngrams_formulaic() -> None:
    seqs = MP.synth_meroitic_corpus(seed=0)
    ngrams = MP.find_common_ngrams(seqs, min_len=2, min_seq=2)
    assert len(ngrams) > 0
    for ng in ngrams:
        assert ng["total_occurrences"] >= ng["n_sequences"]


def test_committed_run_json_exists() -> None:
    path = MP.OUT_DIR / "run.json"
    assert path.exists(), "outputs/meroitic/run.json missing, run meroitic_probe.py first"


def test_committed_run_json_verdict() -> None:
    path = MP.OUT_DIR / "run.json"
    assert path.exists()
    report = json.loads(path.read_text())
    assert report["verdict"] == "STRUCTURE_SIGNAL"
    nc_z = report["negative_control"]["shuffled_control"]["z"]
    assert abs(nc_z) < 3.0, f"Negative control should be nullish, got z={nc_z}"
    assert "Joshua-Otten/Meroitic-Corpus" in report["data_source"]


def test_forbidden_not_in_notes() -> None:
    """Gate check: forbidden phrases must not appear outside the listing."""
    path = MP.OUT_DIR / "NOTES.md"
    if not path.exists():
        return
    text = path.read_text()
    # Split on "##" section headers; check sections AFTER the forbidden-phrase listing
    sections = text.split("## ")
    relevant = [s for s in sections
                if not s.startswith("Forbidden") and not s.startswith("Stance")]
    combined = " ".join(relevant).lower()
    for fp in MP.FORBIDDEN_PHRASES:
        assert fp.lower() not in combined, f"Analysis section contains forbidden: {fp}"


def test_notes_md_contains_verdict() -> None:
    path = MP.OUT_DIR / "NOTES.md"
    assert path.exists()
    text = path.read_text()
    assert "STRUCTURE_SIGNAL" in text or "NO_SIGNAL" in text
    assert "G16" in text
    assert "Meroitic" in text


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
