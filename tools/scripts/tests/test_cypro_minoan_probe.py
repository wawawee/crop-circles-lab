"""
test_cypro_minoan_probe.py — known-answer + stance tests for G11.

Run:
    python tools/scripts/tests/test_cypro_minoan_probe.py
"""
from __future__ import annotations

import json
import random as rnd
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

import tools.scripts.cypro_minoan_probe as CM  # noqa: E402
from tools.forensics.symbolseq import (  # noqa: E402
    conditional_bigram_entropy,
    flatten,
)


def test_normalize_tokens_strips_variants() -> None:
    assert CM.normalize_tokens(["046_", "012bis", "boh", "023", "SPACE"]) == [
        "046", "012", "023",
    ]


def test_is_tablet_inscription() -> None:
    assert CM.is_tablet_inscription("CM_ENKO.tab01")
    assert CM.is_tablet_inscription("foo/TAB/bar")
    assert not CM.is_tablet_inscription("CM_ENKO.cyl01")


def test_jaccard_identity_and_disjoint() -> None:
    assert CM.jaccard_similarity(["001", "023"], ["001", "023"]) == 1.0
    assert CM.jaccard_similarity(["001"], ["023"]) == 0.0


def test_shuffled_cond_H_structured_beats_null() -> None:
    toks = (["001", "023", "087"] * 40)
    ctrl = CM.shuffled_cond_H(toks, n=300, seed=1)
    assert ctrl["observed"] < ctrl["shuffled_mean"]
    assert ctrl["z"] < -2.0


def test_shuffled_cond_H_empty_and_single() -> None:
    assert CM.shuffled_cond_H([], n=50)["z"] == 0.0
    assert CM.shuffled_cond_H(["001"], n=50)["z"] == 0.0


def test_synthetic_scribal_variants_ka_pass() -> None:
    """Known-answer: planted scribal-variant corpus must show structure."""
    seqs = CM.synthetic_scribal_variant_corpus(seed=0)
    rep = CM.run_group_analysis(seqs, label="ka", n_shuffles=300, seed=0)
    z = rep["shuffled_control"]["z"]
    assert z < -3.0, f"KA must pass with z < -3, got {z}"


def test_negative_control_shuffle_no_signal() -> None:
    """Unigram-matched shuffle of KA corpus must NOT light up."""
    seqs = CM.synthetic_scribal_variant_corpus(seed=0)
    flat = flatten(seqs)
    rng = rnd.Random(999)
    shuffled = list(flat)
    rng.shuffle(shuffled)
    rep = CM.run_group_analysis(
        [shuffled], label="neg", n_shuffles=300, seed=777
    )
    z = rep["shuffled_control"]["z"]
    assert abs(z) < 3.0, f"negative control should be nullish, got z={z}"


def test_load_corpus_expected_scale() -> None:
    corpus = CM.load_corpus(CM.DATA_DIR)
    meta = corpus["metadata"]
    assert meta["n_inscriptions_with_clean_data"] >= 100
    assert meta["n_total_signs_cleaned"] >= 2000
    groups = CM.group_by_site_and_medium(corpus)
    assert len(groups["full_corpus"]) >= 100
    assert len(groups["tablet"]) >= 50
    assert len(groups["other_media"]) >= 50


def test_real_corpus_structure_signal() -> None:
    """Full CM corpus should show strong conditional structure (z < -3)."""
    corpus = CM.load_corpus(CM.DATA_DIR)
    groups = CM.group_by_site_and_medium(corpus)
    rep = CM.run_group_analysis(
        groups["full_corpus"], label="full", n_shuffles=300, seed=0
    )
    z = rep["shuffled_control"]["z"]
    assert z < -3.0, f"expected STRUCTURE_SIGNAL, got z={z}"
    assert rep["n_tokens"] >= 2000
    assert rep["n_distinct"] >= 80


def test_tablet_vs_other_jaccard_supports_allography() -> None:
    """Tablet vs other-media overlap should be substantial (not distinct scripts)."""
    corpus = CM.load_corpus(CM.DATA_DIR)
    groups = CM.group_by_site_and_medium(corpus)
    tab = [t for seq in groups["tablet"] for t in seq]
    oth = [t for seq in groups["other_media"] for t in seq]
    j = CM.jaccard_similarity(tab, oth)
    assert j >= 0.4, f"expected media/allography-level overlap, got J={j}"


def test_forbidden_phrases_listed() -> None:
    expected = (
        "translates to", "represents", "decodes as",
        "shares roots with", "is related to",
        "CM is Linear A", "aliens wrote",
    )
    for needle in expected:
        assert needle in CM.FORBIDDEN_PHRASES, f"missing: {needle}"


def test_notes_badge_media_allography() -> None:
    report = {
        "generated_at": "test",
        "metadata": {},
        "groups": [{
            "label": "full_corpus",
            "n_tokens": 10,
            "n_distinct": 3,
            "unigram_entropy_bits": 1.0,
            "index_of_coincidence": 0.1,
            "conditional_bigram_entropy_bits": 1.0,
            "lz78_ratio": 0.5,
            "top_bigrams": [],
            "shuffled_control": {
                "observed": 1.0, "shuffled_mean": 2.0, "z": -10.0,
            },
        }],
        "cross_group": {
            "pairs": [],
            "summary": {"tablet_vs_other_jaccard": 0.53, "mean_jaccard": 0.1},
            "shared_signs_across_groups": {
                "shared_across_all": ["001"],
                "unique_to_tablet": [],
                "unique_to_other": [],
            },
        },
        "known_answer": {
            "label": "ka",
            "n_tokens": 10,
            "n_distinct": 3,
            "unigram_entropy_bits": 1.0,
            "conditional_bigram_entropy_bits": 1.0,
            "shuffled_control": {"observed": 1.0, "shuffled_mean": 2.0, "z": -12.0},
        },
        "negative_control": {
            "label": "nc",
            "n_tokens": 10,
            "n_distinct": 3,
            "shuffled_control": {"observed": 2.0, "shuffled_mean": 2.0, "z": 0.1},
        },
    }
    md = CM.write_notes_md(report)
    assert "MEDIA_DRIVEN_ALLOGRAPHY" in md
    assert "No decipherment, language ID, or script classification.**" in md


def test_committed_run_json_matches_claims() -> None:
    """Gate check: committed outputs must match PR headline numbers."""
    path = CM.OUT_DIR / "run.json"
    assert path.exists(), "outputs/cypro_minoan/run.json missing"
    report = json.loads(path.read_text())
    by_label = {g["label"]: g for g in report["groups"]}
    assert by_label["full_corpus"]["shuffled_control"]["z"] < -20
    assert by_label["tablet"]["shuffled_control"]["z"] < -20
    ka_z = report["known_answer"]["shuffled_control"]["z"]
    nc_z = report["negative_control"]["shuffled_control"]["z"]
    assert ka_z < -3.0, f"committed KA fail: z={ka_z}"
    assert abs(nc_z) < 3.0, f"committed NC fail: z={nc_z}"
    j = report["cross_group"]["summary"]["tablet_vs_other_jaccard"]
    assert j >= 0.4, f"committed tablet↔other J too low: {j}"


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
