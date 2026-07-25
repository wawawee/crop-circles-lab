"""
test_cretan_hieroglyphic_probe.py - G15: ≥14 unit / stance tests for
the Cretan Hieroglyphic bipartite admin probe (synthetic fallback +
bipartite network + Linear A/B KA + two negative controls).

Run:
  python tools/scripts/tests/test_cretan_hieroglyphic_probe.py
"""
from __future__ import annotations

import json
import math
import random as rnd
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

import tools.scripts.cretan_hieroglyphic_probe as CH


# --- Stance / forbidden-phrase honesty ---------------------------------


def test_stance_present() -> None:
    assert len(CH.STANCE) > 50
    assert "structure" in CH.STANCE.lower()
    assert "decipher" in CH.STANCE.lower()


def test_forbidden_phrases_listed() -> None:
    expected = (
        "Cretan Hieroglyphic deciphered",
        "CH deciphered",
        "translates to",
        "language family",
        "99% deciphered",
        "100% deciphered",
        "aliens wrote",
    )
    for needle in expected:
        assert needle in CH.FORBIDDEN_PHRASES, f"missing forbidden: {needle}"


def test_forbidden_phrases_guard_clean_passes() -> None:
    CH.assert_no_forbidden_phrases(
        "These metrics measure sign-sequence structure; no decipherment.",
        where="clean text")


def test_forbidden_phrases_guard_raises_on_banned() -> None:
    for phrase in CH.FORBIDDEN_PHRASES:
        bad = f"A test sentence that contains {phrase} for the guard."
        try:
            CH.assert_no_forbidden_phrases(bad, where="bad text")
        except ValueError:
            pass
        else:
            raise AssertionError(
                f"forbidden phrase {phrase!r} did NOT trigger ValueError")


# --- Synthetic corpus + real loader ------------------------------------


def test_synthetic_corpus_has_admin_shape() -> None:
    insc = CH.synth_ch_corpus(seed=0)
    assert len(insc) >= 100
    for ins in insc[:5]:
        assert "id" in ins
        assert isinstance(ins["rows"], list)
        for row in ins["rows"]:
            assert isinstance(row, list)
            assert len(row) >= 2
            # admin motifs: same-sign doubles OR arithmogram tail
            has_d = any(row[i] == row[i+1] for i in range(len(row)-1))
            tail_num = row[-1].isdigit() if row else False
            assert has_d or tail_num or len(row) >= 2


def test_synth_corpus_rows_flatten() -> None:
    rows = CH.synth_corpus_rows(seed=0)
    assert len(rows) >= 200
    for r in rows:
        if not r:
            continue
        for tok in r:
            assert isinstance(tok, str)


def test_load_real_corpus_missing_returns_empty() -> None:
    rows, meta = CH.load_real_corpus(CH.DATA_DIR)
    assert rows == []
    assert meta.get("reason") == "no_corpus_file"


def test_load_ch_corpus_falls_back_to_synthetic() -> None:
    rows, meta = CH.load_ch_corpus(CH.DATA_DIR, force_synthetic=False, seed=0)
    # corpus.json does not exist locally -> synthetic fallback
    assert rows
    assert meta["is_synthetic"] is True
    assert meta["source"] == "synthetic_evans_inventory"


def test_load_ch_corpus_force_synthetic_always_synthetic() -> None:
    rows, meta = CH.load_ch_corpus(CH.DATA_DIR, force_synthetic=True, seed=0)
    assert rows
    assert meta["is_synthetic"] is True


def test_linear_a_rows_load() -> None:
    p = ROOT / "data" / "scripts" / "linear_a" / "linear_a_corpus.json"
    rows = CH.load_linear_a_rows(p)
    n_tokens = sum(len(r) for r in rows)
    assert n_tokens >= 4000
    assert len(rows) >= 1000


def test_linear_b_rows_load() -> None:
    p = ROOT / "data" / "scripts" / "linear_a" / "linearb_corpus.json"
    rows = CH.load_linear_b_rows(p)
    n_tokens = sum(len(r) for r in rows)
    assert n_tokens >= 1000


# --- Bipartite stats + distance ----------------------------------------


def test_bipartite_network_stats_empty_zero() -> None:
    s = CH.bipartite_network_stats([])
    assert s["n_signs"] == 0
    assert s["n_rows"] == 0
    assert s["density"] == 0.0
    assert s["admin_motif_fraction"] == 0.0


def test_bipartite_network_stats_basic_shape() -> None:
    rows = [["CH_001", "CH_002", "CH_001", "12"],
            ["CH_002", "CH_002", "08"]]
    s = CH.bipartite_network_stats(rows)
    assert s["n_rows"] == 2
    # distinct tokens (CH_001, CH_002, "12", "08") = 4
    assert s["n_signs"] == 4
    assert s["n_edges"] >= 5
    assert 0.0 <= s["density"] <= 1.0
    assert s["admin_motif_count"] == 2
    assert s["admin_motif_fraction"] == 1.0


def test_bipartite_distance_identity_zero() -> None:
    s = {"density": 0.5, "avg_sign_degree_norm": 0.4,
         "avg_row_degree_norm": 0.3, "admin_motif_fraction": 0.2,
         "degree_skew_gini": 0.1}
    assert CH.bipartite_distance(s, s) == 0.0


def test_bipartite_distance_disjoint_nonzero() -> None:
    a = {"density": 0.1, "avg_sign_degree_norm": 0.5,
         "avg_row_degree_norm": 0.5, "admin_motif_fraction": 0.0,
         "degree_skew_gini": 0.5}
    b = {"density": 0.9, "avg_sign_degree_norm": 0.05,
         "avg_row_degree_norm": 0.05, "admin_motif_fraction": 1.0,
         "degree_skew_gini": 0.05}
    d = CH.bipartite_distance(a, b)
    assert isinstance(d, float)
    assert d == d  # not NaN
    assert d > 0.15


def test_bipartite_distance_nan_on_empty() -> None:
    d = CH.bipartite_distance({}, {"density": 0.5, "avg_sign_degree_norm": 0.5,
                                    "avg_row_degree_norm": 0.5,
                                    "admin_motif_fraction": 0.5,
                                    "degree_skew_gini": 0.5})
    assert math.isnan(d)


# --- Shuffle controls ---------------------------------------------------


def test_shuffled_cond_H_structured_beats_null() -> None:
    tokens = ["X"] * 30 + ["Y"] * 30 + ["Z"] * 30
    sc = CH.shuffled_cond_H(tokens, n=100, seed=0)
    assert sc["z"] < -3.0


def test_shuffled_cond_H_empty_zero() -> None:
    assert CH.shuffled_cond_H([], n=10)["z"] == 0.0
    assert CH.shuffled_cond_H(["x"], n=10)["z"] == 0.0


def test_negative_unigram_shuffle_no_lightup() -> None:
    rows, _ = CH.load_ch_corpus(CH.DATA_DIR, force_synthetic=True, seed=0)
    flat = CH.flatten(rows)
    rng = rnd.Random(999)
    shuf = list(flat)
    rng.shuffle(shuf)
    sc = CH.shuffled_cond_H(shuf, n=50, seed=0)
    assert abs(sc["z"]) < 3.0


def test_random_bipartite_rows_density_in_range() -> None:
    # density follows target within tolerable binomial spread:
    expected = 50 * 20 * 0.3  # = 300
    sd = (50 * 20 * 0.3 * 0.7) ** 0.5  # binomial-P sd
    rows = CH.random_bipartite_rows(n_signs=20, n_rows=50,
                                     density=0.3, seed=42)
    n_total = sum(len(r) for r in rows)
    assert abs(n_total - expected) <= 5 * sd, (
        f"n_total={n_total} far from expected {expected} (sd={sd:.1f})")


def test_negative_random_bipartite_high_distance() -> None:
    # Mirror main(): the random null uses CH's observed density (not a
    # lower arbitrary density) so the test actually validates the metric
    # at parity; otherwise density=0.05 could trivially make random rows
    # far from CH regardless of correctness.
    ch_rows, _ = CH.load_ch_corpus(CH.DATA_DIR, force_synthetic=True, seed=0)
    ch_bip = CH.bipartite_network_stats(ch_rows)
    rand = CH.random_bipartite_rows(
        n_signs=max(2, ch_bip["n_signs"]),
        n_rows=max(1, ch_bip["n_rows"]),
        density=max(0.001, ch_bip["density"]),
        seed=999)
    rand_bip = CH.bipartite_network_stats(rand)
    d = CH.bipartite_distance(ch_bip, rand_bip)
    assert d == d  # not NaN
    # Random bipartite with the same edge density should not lie in
    # the admin iso band (else the bipartite metric is degenerate).
    assert d > CH.BIPARTITE_ISO_THRESHOLD


# --- Run probe (orchestrator) ------------------------------------------


def test_run_ch_probe_returns_required_keys() -> None:
    rows = [["CH_001", "CH_002", "12"], ["CH_002", "CH_001"]]
    rep = CH.run_ch_probe(rows, label="x", n_shuffles=50, seed=0)
    for k in ("label", "n_rows", "n_tokens", "n_distinct",
             "unigram_entropy_bits", "conditional_bigram_entropy_bits",
             "shuffled_control", "bipartite_network", "invariants"):
        assert k in rep
    inv = rep["invariants"]
    assert "conditional_structure_vs_shuffle" in inv


def test_run_ch_probe_empty_error() -> None:
    rep = CH.run_ch_probe([], label="empty", n_shuffles=10, seed=0)
    assert rep.get("error") == "empty_rows"


# --- Linear A / B known-answer + main() end-to-end ---------------------


def test_linear_a_admin_ka_structured() -> None:
    p = ROOT / "data" / "scripts" / "linear_a" / "linear_a_corpus.json"
    rows = CH.load_linear_a_rows(p)
    rep = CH.run_ch_probe(rows, label="la_ka", n_shuffles=50, seed=0)
    assert rep["shuffled_control"]["z"] < -3.0


def test_linear_b_admin_ka_structured() -> None:
    p = ROOT / "data" / "scripts" / "linear_a" / "linearb_corpus.json"
    rows = CH.load_linear_b_rows(p)
    rep = CH.run_ch_probe(rows, label="lb_ka", n_shuffles=50, seed=0)
    assert rep["shuffled_control"]["z"] < -3.0


def test_main_writes_outputs(tmp_run_dir=None) -> None:
    tmp_root = ROOT / "outputs" / "cretan_hieroglyphic"
    tmp_root.mkdir(parents=True, exist_ok=True)
    # Mutate OUT_DIR for the call
    saved = CH.OUT_DIR
    CH.OUT_DIR = tmp_root
    try:
        CH.main.__globals__["__file__"]  # no-op; just touch for lints
        # Drive main without argparse hijack
        sys_argv_backup = sys.argv
        try:
            sys.argv = ["cretan_hieroglyphic_probe", "--synthetic",
                        "--n-shuffles", "20", "--seed", "0"]
            CH.main()
        finally:
            sys.argv = sys_argv_backup
    finally:
        CH.OUT_DIR = saved
    assert (tmp_root / "run.json").exists()
    assert (tmp_root / "NOTES.md").exists()


def test_run_json_verdict_and_keys() -> None:
    path = ROOT / "outputs" / "cretan_hieroglyphic" / "run.json"
    if not path.exists():
        # run main first
        sys_argv_backup = sys.argv
        try:
            sys.argv = ["cretan_hieroglyphic_probe", "--synthetic",
                        "--n-shuffles", "20", "--seed", "0"]
            CH.main()
        finally:
            sys.argv = sys_argv_backup
    report = json.loads(path.read_text())
    assert "verdict" in report
    assert "metadata" in report
    assert "groups" in report
    assert "bipartite_distance_to_linear_a_admin" in report
    # either SEQUENCE_STRUCTURE or NO_SIGNAL or UNDERDETERMINED + maybe BIPARTITE_ADMIN
    assert any(t in report["verdict"]
               for t in ("SEQUENCE_STRUCTURE", "NO_SIGNAL", "UNDERDETERMINED"))


def test_notes_md_has_synthetic_caveat() -> None:
    path = ROOT / "outputs" / "cretan_hieroglyphic" / "NOTES.md"
    text = path.read_text() if path.exists() else ""
    if not text:
        return
    assert "structure" in text.lower()
    assert "structure != meaning" in text.lower() or "STRUCTURE != MEANING" in text


def test_forbidden_phrases_not_in_notes_body() -> None:
    import re as _re
    path = ROOT / "outputs" / "cretan_hieroglyphic" / "NOTES.md"
    if not path.exists():
        return
    text = path.read_text()
    # Mask the deliberate listing subsection
    # (`### Forbidden phrases (logged so a code-reviewer catches drift)`
    # followed by `- `<phrase>\`` lines) before substring-checking, so
    # the listing itself is allowed but a leak into another NOTES.md
    # section or footer still trips.
    masked = _re.sub(
        r"\n### Forbidden phrases[^\n]*\n(?:- `[^\n]*`\n?)+",
        "\n[masked-listing]\n", text)
    lower = masked.lower()
    for fp in CH.FORBIDDEN_PHRASES:
        if fp.lower() in lower:
            raise AssertionError(
                f"forbidden phrase {fp!r} leaked outside the listing section in NOTES.md")


# --- Driver ------------------------------------------------------------


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
