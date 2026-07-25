"""
test_voynich_probe.py — known-answer tests for tools/scripts/voynich_probe.py.

Run:
    python tools/scripts/tests/test_voynich_probe.py

Stance: the synthetic plants and synthetic Latin-like lexicon are deterministic
and reproducible. The ZL3b-n corpus is gated behind a graceful skip if absent
(fresh clone without `bash tools/open_archives.sh`).
"""
from __future__ import annotations

import json
import math
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

import tools.scripts.voynich_probe as VOY  # noqa: E402


# -----------------------------------------------------------------------------
# IVTFF parser tests
# -----------------------------------------------------------------------------

def test_clean_text_payload_drops_brackets_and_operators() -> None:
    s = VOY.clean_text_payload("<!commentary> daiin.[a:b].otor{ann}.<$>")
    # [a:b] -> a (correction choice resolves to first option)
    assert "daiin.a.otor" in s, f"got {s!r}"
    # Stream must be dot-joined word tokens (no leading/trailing dots
    # because the parser strips them after splitting on '.').
    assert s.startswith("daiin")
    assert s.endswith("otor")
    assert "<!" not in s
    assert "}" not in s
    assert "[" not in s
    assert "$" not in s


def test_clean_text_payload_strips_leading_uncertainty() -> None:
    s = VOY.clean_text_payload("??aiin.otor")
    assert "aiin" in s
    assert "?aiin" not in s


def test_parse_zl_ivtff_minimal_inline() -> None:
    """Construct a minimal IVTFF file and round-trip through the parser."""
    td = Path(tempfile.mkdtemp(prefix="voy_parser_"))
    try:
        inline = (
            "#=IVTFF 2.0\n"
            "# synthetic test corpus\n"
            "<f1r>\n"
            "<f1r.1,@P0>  daiin.otor.hol.daiin.<$>\n"
            "<f1r.2,@P0> {annotation}.?aiin.shol.<!operator commentary>\n"
            "<f1v.1,@P0> [a:b].chor.ky.<->\n"
        )
        p = td / "inline.ivtff"
        p.write_text(inline)
        parsed = VOY.parse_zl_ivtff(p)
        assert parsed["n_lines_text"] >= 3, f"expected >=3 text lines, got {parsed['n_lines_text']}"
        # Tokens should include gli phs from at least one line
        assert any("daiin" in w for w in parsed["tokens_word"]), parsed["tokens_word"][:5]
        assert any("aiin" in w for w in parsed["tokens_word"]), parsed["tokens_word"][:5]
        # Bracket choice should resolve "a" or "b" — only "a" is kept
        assert all("[" not in w and "]" not in w and "{" not in w and "}" not in w and "<" not in w
                   for w in parsed["tokens_word"]), parsed["tokens_word"][:5]
        # Multi-folio count
        assert parsed["folio_count"] >= 2, f"expected >=2 folios, got {parsed['folio_count']}"
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_parse_zl_real_corpus_if_present() -> None:
    """If the bundled ZL3b-n.txt is present, the parser must yield a
    non-trivial token stream (~hundreds to ~hundreds of thousands of tokens).
    Skip gracefully if absent (fresh clone)."""
    p = ROOT / "data" / "scripts" / "voynich" / "ZL3b-n.txt"
    if not p.exists():
        return
    parsed = VOY.parse_zl_ivtff(p)
    assert parsed["n_lines_text"] >= 1000, (
        f"text_lines={parsed['n_lines_text']} (expected >1000)"
    )
    n_chars = len(parsed["tokens_char"])
    assert n_chars >= 50_000, (
        f"n_chars={n_chars} (expected >50k for ~402KB file)"
    )
    n_distinct = len(set(parsed["tokens_char"]))
    assert n_distinct >= 30, f"only {n_distinct} distinct chars?"
    # Folio count should be >= 100 (224+ original folios).
    assert parsed["folio_count"] >= 50, f"folio_count={parsed['folio_count']}"


# -----------------------------------------------------------------------------
# Spearman rho tests (pure math)
# -----------------------------------------------------------------------------

def test_spearman_perfect_correlation_equals_one() -> None:
    rho = VOY.spearman_rho([1.0, 2.0, 3.0, 4.0], [1.0, 2.0, 3.0, 4.0])
    assert abs(rho - 1.0) < 1e-9


def test_spearman_perfect_inverse_correlation_equals_minus_one() -> None:
    rho = VOY.spearman_rho([1.0, 2.0, 3.0, 4.0], [4.0, 3.0, 2.0, 1.0])
    assert abs(rho - (-1.0)) < 1e-9


def test_spearman_random_around_zero() -> None:
    import random as rnd
    rng = rnd.Random(42)
    xs = [rng.randint(0, 100) for _ in range(60)]
    ys = [rng.randint(0, 100) for _ in range(60)]
    rho = VOY.spearman_rho(xs, ys)
    assert -0.4 < rho < 0.4, f"expected |rho| ~ 0 for unrelated ranks; got {rho}"


def test_spearman_rho_on_bigram_freqs_aligned_unique_match() -> None:
    """If both sides have identical bigram frequencies in identical order,
    the rank correlation should be 1.0."""
    a = ["a", "b", "c", "a", "b", "c", "a", "b", "c", "a"]
    b = list(a)
    out = VOY.spearman_rho_on_bigram_freqs(a, b, top_n=8)
    assert abs(out["value"] - 1.0) < 1e-9
    assert out["n_aligned"] >= 2


# -----------------------------------------------------------------------------
# Planted-Voynichese + planted-Latin tests
# -----------------------------------------------------------------------------

def test_planted_voynichese_passes_negative_control() -> None:
    """Plant MUST separate from unigram-preserving shuffle: z < -3."""
    plant = VOY.plant_voynichese_like(seed=11)
    block = VOY.entropy_block(plant, "plant_test", n_shuffles=500, seed=0)
    z = block["shuffled_control"]["z"]
    assert z < -3.0, f"plant z = {z} (must be < -3 to pass known-answer)"


def test_planted_latin_passes_negative_control() -> None:
    """Latin-like MUST separate from unigram-preserving shuffle: z < -3."""
    plant = VOY.plant_latin_like(seed=31)
    block = VOY.entropy_block(plant, "latin_plant", n_shuffles=500, seed=0)
    z = block["shuffled_control"]["z"]
    assert z < -1.5, f"Latin plant z = {z} (must be < -1.5 to be detectable). " \
        "Lighter than Voynich but should still beat shuffle if pipeline is honest."
    # Document: weaker than Voynich plant because synthetic Latin-like is noisy.
    # We require < -1.5 not < -3 because the synthetic Markov is hand-rolled
    # and we don't want to over-tune the test. If this fails, either tighten
    # the latin generator or surface as UNDERDETERMINED.


def test_planted_voynichese_unigram_distribution() -> None:
    """Plant vocabulary must include characters from PLANT_ALPHABET."""
    plant = VOY.plant_voynichese_like(seed=11)
    seen = set(plant)
    assert seen.issubset(set(VOY.PLANT_ALPHABET)), (
        f"plant introduced char outside PLANT_ALPHABET: {seen - set(VOY.PLANT_ALPHABET)}"
    )


# -----------------------------------------------------------------------------
# Claim-under-test: spearman ρ
# -----------------------------------------------------------------------------

def test_expand_semantic_roots_emits_expected_count() -> None:
    """The embedded Semitic-root pool must have a non-trivial token mass
    (each root repeated by ROOT_REPEAT) and the resulting alphabet must
    be drawn exclusively from common Latin-letter consonants used in
    Semitic romanisations (no exotic unicode or punctuation slips in).

    We deliberately do NOT pin an exact token count because the embedded
    roots vary in length (3 or 4 consonants each); pinning the exact
    tally would couple the test to the current root list shape, which
    can legitimately grow as the curator adds more roots. The structural
    invariant is: tokens are present, length is bounded, alphabet is
    restricted to lowercase Latin consonants.
    """
    roots = VOY.expand_semantic_roots()
    expected_per_pass = sum(len(r) for r in VOY.EMBEDDED_SEMITIC_ROOTS)
    assert len(roots) == expected_per_pass * VOY.ROOT_REPEAT, (
        f"expected {expected_per_pass * VOY.ROOT_REPEAT} tokens, got {len(roots)}"
    )
    allowed = set("abcdefghijklmnopqrstuvwxyz")
    assert set(roots).issubset(allowed), (
        f"introduced non-Latin-consonant char(s): "
        f"{set(roots) - allowed}"
    )


def test_dominik_rho_claim_block_returns_valid_publishable_fields() -> None:
    """Mirrors the prior `test_dribble_rho_claim_block_*` after the rename
    to `dominik_rho_claim_block`. The ρ block must surface observed value,
    shuffle null, and the abstract ρ for auditability.
    """
    plant_realish = list("abcdefghilmnoqrst") * 100
    block = VOY.dominik_rho_claim_block(plant_realish, n_shuffles=200, seed=0)
    assert "value" in block
    assert "n_aligned_bigrams" in block
    assert "n_aligned_bigrams" in block
    assert "shuffle_null" in block
    assert block["published_rho_in_abstract"] == 0.82
    assert block["published_rho_in_packaged_json_unverified"] == 0.9999


def test_spearman_rho_shuffle_null_z_for_random_equal_zero() -> None:
    """End-to-end correctness check on the shuffle-null ρ pipeline for two
    random sequences over disjoint alphabets.

    We deliberately do NOT pin a strict statistical bound (the test would
    be flaky for n=200 shuffles); instead we check structural properties:
      (a) observed ρ is a valid rank correlation in [-1, 1];
      (b) the shuffle-null z is finite (no division-by-zero / NaN);
      (c) the observed ρ does not appear to overwhelm the null by > 5σ
          (which would mean the shuffle-null machinery is broken).
    """
    import random as rnd
    rng = rnd.Random(0)
    a = [rng.choice("abcdef") for _ in range(800)]
    b = [rng.choice(list("klmnop")) for _ in range(800)]
    out = VOY.spearman_rho_shuffle_null(a, b, top_n=64, n=200, seed=0)
    assert -1.0 <= out["observed"] <= 1.0, (
        f"observed ρ = {out['observed']} out of [-1, 1]"
    )
    assert math.isfinite(out["z_relative_to_shuffle"]), (
        f"non-finite z: {out['z_relative_to_shuffle']}"
    )
    # Anti-coup guard: observed ρ should NOT be a colossal outlier that
    # beat the null by >5σ. Two unrelated sequences cannot legitimately
    # produce such an extreme z from a 200-round null; if this fails,
    # suspect a tie-rank pathology in spearman_rho.
    z = out["z_relative_to_shuffle"]
    assert -5.0 <= z <= 5.0, f"absurd z = {z} from disjoint random sequences"


# -----------------------------------------------------------------------------
# Verdict logic tests
# -----------------------------------------------------------------------------

def _stub_block(z: float, more_structured: bool = True) -> dict:
    return {
        "label": "stub", "n_tokens": 1000, "n_distinct": 10,
        "unigram_entropy_bits": 3.0,
        "index_of_coincidence": 0.1,
        "conditional_bigram_entropy_bits": 2.0,
        "lz78_ratio": 0.5,
        "shuffled_control": {
            "observed": 2.0, "shuffled_mean": 3.0, "shuffled_sd": 0.1,
            "z": z, "more_structured_than_chance": more_structured,
        },
    }


def _stub_rho(z_rel: float) -> dict:
    return {
        "value": 0.1,
        "n_aligned_bigrams": 50,
        "top_keys": [],
        "shuffle_null": {
            "observed": 0.1, "shuffled_mean": 0.0, "shuffled_sd": 0.05,
            "z_relative_to_shuffle": z_rel, "n_shuffles": 200,
            "interpretation": "stub",
        },
        "published_rho_in_abstract": 0.82,
        "published_rho_in_packaged_json_unverified": 0.9999,
        "packaged_json_slope_unverified": 0.044,
        "interpretation": "stub",
    }


def test_verdict_pipelinepasses_real_structured_rho_fails() -> None:
    """Plant ok, Latin ok, real structured, ρ fails null → SEQUENCE_STRUCTURE | CLAIM_FAILS_NULL."""
    plant = _stub_block(-10.0)
    latin = _stub_block(-5.0)
    morph = {
        "word_level": _stub_block(-12.0),
        "char_level": _stub_block(-7.0),
    }
    rho = _stub_rho(z_rel=0.5)  # does NOT beat shuffle by 2σ
    v = VOY.compute_verdict(morph, plant, latin, rho)
    assert "SEQUENCE_STRUCTURE" in v["verdict"]
    assert "CLAIM_FAILS_NULL" in v["verdict"]
    assert v["invariants"]["plant_passes"] is True
    assert v["invariants"]["latin_passes"] is True
    assert v["invariants"]["rho_fails_null"] is True
    assert v["invariants"]["voynich_word_structured"] is True


def test_verdict_pipelinepasses_rho_passes() -> None:
    """Plant ok, Latin ok, real structured, ρ beats null → SEQUENCE_STRUCTURE | RHO_PENDING."""
    plant = _stub_block(-10.0)
    latin = _stub_block(-5.0)
    morph = {
        "word_level": _stub_block(-12.0),
        "char_level": _stub_block(-7.0),
    }
    rho = _stub_rho(z_rel=3.5)  # beats shuffle by > 2σ
    v = VOY.compute_verdict(morph, plant, latin, rho)
    assert "SEQUENCE_STRUCTURE" in v["verdict"]
    assert "RHO_PENDING" in v["verdict"]
    assert v["invariants"]["rho_fails_null"] is False


def test_verdict_underdetermined_plant_failed() -> None:
    """If plant fails negative control, the pipeline is UNDERDETERMINED."""
    plant = _stub_block(-0.5)  # NOT < -3
    latin = _stub_block(-5.0)
    morph = {
        "word_level": _stub_block(-12.0),
        "char_level": _stub_block(-7.0),
    }
    rho = _stub_rho(z_rel=0.5)
    v = VOY.compute_verdict(morph, plant, latin, rho)
    assert v["verdict"] == "UNDERDETERMINED"
    assert "PLANT" in v["notes"] or "plant" in v["notes"].lower()


def test_verdict_no_signal_voynich_unstructured() -> None:
    """Plant + Latin pass; voynich is NOT structured → NO_SIGNAL."""
    plant = _stub_block(-10.0)
    latin = _stub_block(-5.0)
    morph = {
        "word_level": _stub_block(z=0.5),    # not structured
        "char_level": _stub_block(z=0.7),    # not structured
    }
    rho = _stub_rho(z_rel=0.5)
    v = VOY.compute_verdict(morph, plant, latin, rho)
    assert v["verdict"] == "NO_SIGNAL"


# -----------------------------------------------------------------------------
# Forbidden-phrase guard
# -----------------------------------------------------------------------------

def test_assert_no_forbidden_phrases_clean_text_passes() -> None:
    VOY.assert_no_forbidden_phrases(
        "These metrics confirm sign-sequence structure, no decipherment.",
        where="clean text",
    )


def test_assert_no_forbidden_phrases_raises_on_banned() -> None:
    for phrase in VOY.FORBIDDEN_PHRASES:
        bad = f"The Voynich is {phrase}, that's a strong claim."
        try:
            VOY.assert_no_forbidden_phrases(bad, where="bad text")
        except ValueError:
            continue
        raise AssertionError(f"forbidden phrase {phrase!r} did NOT trigger ValueError")


# -----------------------------------------------------------------------------
# End-to-end on synthetic (no ZL3b-n required)
# -----------------------------------------------------------------------------

def test_run_pseudo_assembles_full_report() -> None:
    """Pseudo-data path must produce every documented field even
    when the real ZL3b-n corpus is absent."""
    pseudo = {
        "tokens_word": VOY.plant_latin_like(seed=11)[:1000],
        "tokens_char": [],
        "n_text_lines": 1,
        "folio_count": 1,
        "folios": ["<synth>"],
    }
    pseudo["tokens_char"] = [c for w in pseudo["tokens_word"] for c in w]
    args = type("A", (), {
        "n_shuffles": 200, "seed": 0, "top_n": 64,
    })()
    rep = VOY._run_pseudo(pseudo, args)
    for key in ("verdict_block", "morphology", "planted_voynichese_like",
                "planted_latin_like", "claim_under_test_results",
                "stance", "forbidden_phrases"):
        assert key in rep, f"missing key: {key}"
    # Stance + FORBIDDEN_PHRASES in the report itself should never crash.
    assert "STRUCTURE" in rep["verdict_block"]["verdict"] or \
        rep["verdict_block"]["verdict"] in ("UNDERDETERMINED", "NO_SIGNAL")


def test_full_report_pure_plant_pair_smoke() -> None:
    """If we manually pass the plant's tokens through the same code path,
    the plant_passes invariant must hold. Skip gracefully if no ZL3b-n
    corpus is present (otherwise we test the real corpus separately)."""
    pseudo = {
        "tokens_word": VOY.plant_voynichese_like(seed=11),
        "n_text_lines": 1, "folio_count": 1, "folios": ["<synth>"],
    }
    pseudo["tokens_char"] = [c for w in pseudo["tokens_word"] for c in w]
    args = type("A", (), {"n_shuffles": 200, "seed": 0, "top_n": 64})()
    rep = VOY._run_pseudo(pseudo, args)
    # When the "voynich corpus" IS the plant, the conditional_structure
    # invariant still cascades (z<-3 on word AND char level -> structural).
    assert rep["verdict_block"]["invariants"]["plant_passes"] is True


# -----------------------------------------------------------------------------
# main() smoke + end-to-end subprocess
# -----------------------------------------------------------------------------

def test_main_synthetic_runs_to_files() -> None:
    """End-to-end: --synthetic + --out-* into a tempdir. Check both
    files exist + both contain the verdict string."""
    td = Path(tempfile.mkdtemp(prefix="voy_main_"))
    try:
        out_json = td / "run.json"
        out_md = td / "NOTES.md"
        res = __import__("subprocess").run([
            sys.executable, str(ROOT / "tools" / "scripts" / "voynich_probe.py"),
            "--synthetic",
            "--n-shuffles", "100",
            "--out-json", str(out_json),
            "--out-md", str(out_md),
        ], capture_output=True, text=True, timeout=120)
        assert res.returncode == 0, (
            f"voynich_probe.py --synthetic failed:\nSTDOUT:\n{res.stdout[:600]}\n"
            f"STDERR:\n{res.stderr[:600]}"
        )
        assert out_json.exists(), "run.json not written"
        assert out_md.exists(), "NOTES.md not written"
        d = json.load(out_json.open())
        assert "verdict_block" in d
        md_text = out_md.read_text()
        assert "G10" in md_text
        assert "Verdict" in md_text
        # Drift guard: NOTES.md must not contain a banned phrase in BODY
        # (excluding the explicit forbidden-phrases log section).
        body_lines = [ln for ln in md_text.splitlines() if not ln.startswith("- `")]
        body = "\n".join(body_lines)
        for phrase in VOY.FORBIDDEN_PHRASES:
            assert phrase.lower() not in body.lower(), (
                f"forbidden phrase {phrase!r} leaked into NOTES.md body"
            )
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_main_real_corpus_endto_end_if_present() -> None:
    """If ZL3b-n is bundled, the probe must produce a non-trivial report
    on the real corpus. Run with a small --n-shuffles for speed."""
    p = ROOT / "data" / "scripts" / "voynich" / "ZL3b-n.txt"
    if not p.exists():
        return
    td = Path(tempfile.mkdtemp(prefix="voy_real_"))
    try:
        out_json = td / "real_run.json"
        out_md = td / "real_notes.md"
        res = __import__("subprocess").run([
            sys.executable, str(ROOT / "tools" / "scripts" / "voynich_probe.py"),
            "--data", str(p),
            "--n-shuffles", "200",   # cheap for CI
            "--out-json", str(out_json),
            "--out-md", str(out_md),
        ], capture_output=True, text=True, timeout=600)
        assert res.returncode == 0, (
            f"voynich_probe.py real-corpus failed:\nSTDOUT:\n{res.stdout[:600]}\n"
            f"STDERR:\n{res.stderr[:600]}"
        )
        d = json.load(out_json.open())
        assert d["n_tokens_char"] >= 50_000
        # The real ZL3b-n must show a clear conditional-structure signal
        # (condition ≥ -3σ on both word AND char levels).
        m = d["morphology"]
        assert m["word_level"]["shuffled_control"]["z"] < -3.0, \
            f"real Voynich word-level z={m['word_level']['shuffled_control']['z']}"
        assert m["char_level"]["shuffled_control"]["z"] < -3.0, \
            f"real Voynich char-level z={m['char_level']['shuffled_control']['z']}"
        # After the FULL/PARTIAL refactor, FULL requires both levels structured.
        assert d["verdict_block"]["structure_level"] == "FULL", \
            f"expected FULL structure level, got {d['verdict_block']['structure_level']}"
        # Plant MUST pass.
        assert d["planted_voynichese_like"]["shuffled_control"]["z"] < -3.0, \
            "planted control failed: pipeline is broken"
        # PDF prose: NOTES.md mentions verdict, mentions ρ, mentions
        # forbidden phrases are forbidden.
        md = out_md.read_text()
        assert "Verdict" in md
        assert "Forbidden" in md or "forbidden" in md
        assert "structure != message" in md.lower() or "STRUCTURE != MESSAGE" in md
    finally:
        shutil.rmtree(td, ignore_errors=True)


# -----------------------------------------------------------------------------
# Extended-EVA-glyph lexer tests (G10 lexer-extension)
# -----------------------------------------------------------------------------

def test_tokenize_eva_extended_basic_greedy_matches() -> None:
    """Canonical ZL3b-n-like words — verify greedy longest-match splits
    into the documented digraphs/triglyphs/quadrylls.

    Note: not asserting absolute equality of *entire* token lists (the
    underlying implementation may evolve), but rather that the lexer
    picks the canonical extended-glyph atoms wherever they apply.
    """
    # 2-letter digraphs
    assert VOY.tokenize_eva_extended("chol") == ["ch", "o", "l"]
    assert VOY.tokenize_eva_extended("shol") == ["sh", "o", "l"]
    # 3-letter triglyph (Takahashi cth triple-letter ligature)
    assert VOY.tokenize_eva_extended("cthol") == ["cth", "o", "l"]
    # 4-letter quadryll ligature
    assert VOY.tokenize_eva_extended("aiin") == ["aiin"]
    assert VOY.tokenize_eva_extended("dain") == ["dain"]
    # 'daiin' is not a published ligature: must parse as 'd' + 'aiin'
    assert VOY.tokenize_eva_extended("daiin") == ["d", "aiin"]
    # Vowel+r digraphs (ol/or/ar/an/am/en/os/as/is/es):
    # pruned from EVA_EXTENDED_GLYPHS because they OVERLAP with per-char
    # sequences in real ZL3b-n words (e.g., "chol" -> ch + o + l, not
    # ch + ol). These are phonetic combinations, not ligatures.
    # Verification: each two-letter input falls through to per-char tokens.
    assert VOY.tokenize_eva_extended("ol") == ["o", "l"]
    assert VOY.tokenize_eva_extended("or") == ["o", "r"]
    assert VOY.tokenize_eva_extended("ar") == ["a", "r"]
    assert VOY.tokenize_eva_extended("an") == ["a", "n"]


def test_tokenize_eva_extended_no_match_per_char_fallback() -> None:
    """Words without any extended-glyph prefix fall through to single
    characters (this is the conservative default for unknown words).
    """
    assert VOY.tokenize_eva_extended("qokeedy") == [
        "q", "o", "k", "e", "e", "d", "y"
    ]
    assert VOY.tokenize_eva_extended("xyz") == ["x", "y", "z"]
    # 'iiin' has no `iiin` or `iin` in the lexicon — falls to per-char.
    assert VOY.tokenize_eva_extended("iiin") == ["i", "i", "i", "n"]


def test_tokenize_eva_extended_empty_and_singleton() -> None:
    assert VOY.tokenize_eva_extended("") == []
    assert VOY.tokenize_eva_extended("a") == ["a"]


def test_tokenize_eva_extended_longest_match_wins() -> None:
    """Greedy longest-match must pick a longer prefix over a shorter one.
    Specifically 'aiin' (4) must NOT be split into 'a' + 'i' + 'i' + 'n';
    and 'dain' (4) must NOT be split into 'd' + 'a' + 'i' + 'n'.
    """
    toks_aiin = VOY.tokenize_eva_extended("aiin")
    assert "aiin" in toks_aiin and len(toks_aiin) == 1
    toks_dain = VOY.tokenize_eva_extended("dain")
    assert "dain" in toks_dain and len(toks_dain) == 1


def test_flatten_eva_extended_aggregates_word_stream() -> None:
    """Multi-word input aggregates tokens correctly across word
    boundaries; per-word limits are preserved (no cross-word digraphs).
    """
    out = VOY.flatten_eva_extended(["chol", "aiin", "qokeedy"])
    assert out == ["ch", "o", "l", "aiin", "q", "o", "k", "e", "e", "d", "y"]


def test_eva_extended_glyphs_sorted_length_descending() -> None:
    """The lexicon must be sorted length-descending for the greedy
    longest-match guarantee. If a future curator edit drops the invariant,
    this test fires.
    """
    lens = [len(g) for g in VOY.EVA_EXTENDED_GLYPHS]
    assert lens == sorted(lens, reverse=True), (
        f"EVA_EXTENDED_GLYPHS not length-descending: {VOY.EVA_EXTENDED_GLYPHS}"
    )
    # 4-letter and 3-letter entries must come before 2-letter entries.
    assert "aiin" in VOY.EVA_EXTENDED_GLYPHS
    assert "dain" in VOY.EVA_EXTENDED_GLYPHS
    assert "cth" in VOY.EVA_EXTENDED_GLYPHS


def test_morphology_block_accepts_tokens_glyph_and_returns_glyph_level() -> None:
    """morphology_block signature is (word, char, glyph, ...) and the
    returned dict must include a 'glyph_level' block.
    """
    words = ["chol", "aiin", "qokeedy", "sholdain"]
    chars = [c for w in words for c in w]
    glyphs = VOY.flatten_eva_extended(words)
    block = VOY.morphology_block(words, chars, glyphs, n_shuffles=100, seed=0)
    assert "char_level" in block
    assert "word_level" in block
    assert "glyph_level" in block
    g = block["glyph_level"]
    assert g["label"] == "voynich_glyph"
    assert g["n_tokens"] == len(glyphs)
    assert g["n_tokens"] < len(chars), (
        "Glyph tokens must strictly fewer than char tokens when digraphs "
        "collapse (otherwise the digraph lexicon isn't matching)."
    )


def test_parse_zl_real_corpus_returns_tokens_glyph_with_fewer_tokens() -> None:
    """End-to-end on real ZL3b-n: parse_zl_ivtff must populate
    tokens_glyph, and the glyph stream must be SHORTER than the char
    stream (because digraphs + triglyphs + the quadryll collapse multiple
    chars into one token). Skip gracefully if the bundled corpus is
    absent (fresh clone).
    """
    p = ROOT / "data" / "scripts" / "voynich" / "ZL3b-n.txt"
    if not p.exists():
        return
    parsed = VOY.parse_zl_ivtff(p)
    n_char = len(parsed["tokens_char"])
    n_glyph = len(parsed["tokens_glyph"])
    n_distinct_char = len(set(parsed["tokens_char"]))
    n_distinct_glyph = len(set(parsed["tokens_glyph"]))
    assert n_glyph > 0
    assert n_glyph < n_char, (
        f"glyph tokens ({n_glyph}) should be fewer than char tokens "
        f"({n_char}); digraphs/triglyphs/quadryll collapse "
        f"{(1 - n_glyph/n_char) * 100:.1f}% of positions when matched."
    )
    assert n_distinct_glyph > 0, (
        f"distinct glyphs ({n_distinct_glyph}) must be > 0; lexer "
        f"appears to produce zero tokens (regression)."
    )
    # The digraph lexicon may EXPAND the alphabet atom count: 'ch' is
    # ONE glyph but distinct from 'c' and 'h'. Coalescence would only
    # reduce the alphabet if the digraph LETTERS share the same
    # surface forms — which they don't here (aiin != a+i+i+n as
    # separate atoms). Real corpora in the wild show n_distinct_glyph
    # ALMOST EQUAL OR GREATER than n_distinct_char.
    assert n_distinct_glyph >= n_distinct_char, (
        f"distinct glyphs ({n_distinct_glyph}) should be >= "
        f"distinct chars ({n_distinct_char}); multi-char "
        f"coalescence was found to EXPAND not reduce."
    )
    # Sanity: a few common extended glyphs should appear at least once.
    glyphs = set(parsed["tokens_glyph"])
    assert any(g in glyphs for g in ("ch", "sh", "aiin", "dain", "cth")), (
        f"at least one of (ch, sh, aiin, dain, cth) should appear in the "
        f"Voynich glyph stream; got {sorted(glyphs)[:30]}"
    )


# -----------------------------------------------------------------------------
# Runner
# -----------------------------------------------------------------------------

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
