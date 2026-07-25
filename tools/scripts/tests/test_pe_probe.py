"""
test_pe_probe.py — known-answer tests for tools/scripts/proto_elamite_probe.py.

Run:
    python tools/scripts/tests/test_pe_probe.py
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

import tools.scripts.proto_elamite_probe as PE  # noqa: E402


# --- Syntactic & digit-handling primitives --------------------------------

def test_clean_token_strips_atf_determiners() -> None:
    """ATF determiners (?, !, [], ( ), < >, ,) are stripped; bare text remains."""
    assert PE.clean_token("1(N01)") == "1N01"
    assert PE.clean_token("1(N01)") == "1N01"  # parens stripped
    assert PE.clean_token("?GI") == "GI"
    assert PE.clean_token("[M388]") == "M388"
    assert PE.clean_token("M122!") == "M122"
    assert PE.clean_token("...") == ""
    assert PE.clean_token("") == ""


def test_is_numeral_sign_matches_cdli_spec() -> None:
    """Numerals match 1(N01)/1/2(N04)/5(N19)/7(N39)/8(N46); non-numerals do not."""
    for tok in ("1", "2", "1(N01)", "2(N04)", "5(N19)", "7(N39)", "8(N46)", "1(N58)",
                "10(N01)", "1(N14A)"):
        assert PE.is_numeral_sign(tok), f"expected numeral: {tok!r}"
    for tok in ("GI", "M388", "M122", "SAG", "URUDU", "BU", "PAP"):
        assert not PE.is_numeral_sign(tok), f"unexpected numeral class: {tok!r}"
    # Empty / cleaned-out
    assert not PE.is_numeral_sign("")
    assert not PE.is_numeral_sign("?GI")  # after clean_token → "GI" → not numeral


def test_parse_pe_atf_strips_comments_and_at_headers() -> None:
    """ATF #, @, $, &, >, = lines are dropped; tokens are space-delim + cleaned."""
    atf = (
        "#atf: lang en\n"
        "@tablet\n"
        "@obverse\n"
        "&P000001 = Susa\n"
        "1. M388 1(N01) ?GI 2(N04)\n"
        "# trailing comment line\n"
        "2. SAG 3(N19)\n"
    )
    toks = PE.parse_pe_atf(atf)
    assert toks == ["M388", "1N01", "GI", "2N04", "SAG", "3N19"], f"got {toks}"


def test_unigram_preserving_shuffle_keeps_counter() -> None:
    """Multiset identity preserved exactly under deterministic seed."""
    toks = ["A", "A", "B", "B", "B", "C", "1(N01)", "1(N01)"]
    shuf = PE.unigram_preserving_shuffle(toks, seed=0)
    from collections import Counter
    assert Counter(shuf) == Counter(toks)
    assert len(shuf) == len(toks)
    # Deterministic: same seed → same shuffle.
    assert shuf == PE.unigram_preserving_shuffle(toks, seed=0)


# --- Header/line split + numeral block extraction -------------------------

def test_split_header_blocks_basic() -> None:
    """First contiguous no-numerals → header; rest → lines."""
    toks = ["M388", "GI", "M122", "1N01", "M058", "1N01", "2N04"]
    hdr, ln = PE.split_header_blocks(toks)
    assert hdr == ["M388", "GI", "M122"], f"hdr={hdr}"
    assert ln == ["1N01", "M058", "1N01", "2N04"], f"ln={ln}"


def test_split_header_blocks_all_header_no_first_numeral() -> None:
    """No numerals anywhere → all-header tokenisation."""
    toks = ["M388", "GI", "M122"]
    hdr, ln = PE.split_header_blocks(toks)
    assert hdr == toks and ln == []


def test_extract_numeral_blocks_basic() -> None:
    tokens = ["M388", "1N01", "2N04", "SAG", "3N19", "5N39", "M122", "8N46"]
    blocks = PE.extract_numeral_blocks(tokens)
    assert blocks == [["1N01", "2N04"], ["3N19", "5N39"], ["8N46"]], f"got {blocks}"


# --- Synthetic known-answer + invariants ----------------------------------

def test_synthetic_ledger_invariants_pass() -> None:
    """Synthetic known-answer: all 4 invariants MUST hold."""
    rep = PE.run_synthetic(seed=0, n_shuffles=500)
    inv = rep["invariants"]["invariants"]
    assert inv["header_numeral_void"], "synthetic header should have zero numerals"
    assert inv["header_fraction_bounded"], "header fraction must be bounded"
    assert inv["numeral_block_predictable"], "numeral blocks should collapse H(next|n)"
    assert inv["z_lock_vs_shuffle"], "line cond-H should be < shuffle baseline"
    assert rep["invariants"]["all_pass"] is True


def test_random_shuffled_corpus_invariants_fail() -> None:
    """Random shuffled tokens of equal mass: invariants must NOT pass.
    This is the negative control — confirms the test discriminates structure
    from pure noise.
    """
    import random as rnd
    rng = rnd.Random(7)
    base = PE.synth_pe_ledger(seed=0)
    rng.shuffle(base)
    rep = PE.run_ledger_probe(base, label="shuffled_negative_control",
                               n_shuffles=300, seed=0)
    # At minimum the z-lock must fail (shuffled data is by design at chance),
    # and the numeral-block-predictable invariant should fail because the
    # numeral blocks are now scattered through the sequence.
    inv = rep["invariants"]["invariants"]
    assert inv["z_lock_vs_shuffle"] is False, "shuffle should not z-lock"


# --- Live CDLI + bundled-override + honest-empty --------------------------

def test_default_fetch_is_never_attempted() -> None:
    """Default (no force, no --fetch-online) MUST NOT touch the network."""
    fr = PE.try_fetch_cdli_atf("P000001")
    assert fr.fetch_status == "NEVER_ATTEMPTED"
    assert fr.atf_text == ""
    assert fr.attempts == []


def test_force_status_unreachable_has_attempts_and_no_text() -> None:
    """Test hook UNREACHABLE: must list per-URL attempts with NETWORK_ERROR
    and never return ATF text."""
    fr = PE.try_fetch_cdli_atf("P000001", force_status_for_tests="UNREACHABLE")
    assert fr.fetch_status == "UNREACHABLE"
    assert fr.atf_text == ""
    assert len(fr.attempts) >= 5, "5 known CDLI URL patterns attempted"
    for att in fr.attempts:
        assert att["verdict"] == "NETWORK_ERROR"
        assert "UNREACHABLE" in att["error"]


def test_parking_page_force_status() -> None:
    """Test hook PARKING_PAGE: empty ATF + per-URL attempts flagged as such."""
    fr = PE.try_fetch_cdli_atf("P000001", force_status_for_tests="PARKING_PAGE")
    assert fr.fetch_status == "PARKING_PAGE"
    assert fr.atf_text == ""
    assert all(att["verdict"] == "PARKING_PAGE" for att in fr.attempts)


def test_bundled_corpus_path_parses_atf_and_passes_inv() -> None:
    """USER_OVERRIDE bundled JSON with ATF text: parse + invariants run."""
    td = Path(tempfile.mkdtemp(prefix="pe_bundled_"))
    try:
        corpus = td / "pe_corpus.json"
        corpus.write_text(json.dumps([
            {"cdli_id": "P000001",
             "atf": PE.synth_pe_ledger_atf()},
        ]))
        rep = PE.run_bundled(corpus, n_shuffles=300, seed=0)
        assert rep["n_input_tokens"] > 0
        assert rep["invariants"]["all_pass"] is True, \
            f"bundled synthetic should pass: {rep['invariants']}"
        assert rep["per_tablet"] == [{"cdli_id": "P000001",
                                       "n_tokens": rep["n_input_tokens"]}]
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_live_cdli_honest_empty_yellow_banner() -> None:
    """Live CDLI path with NEVER_ATTEMPTED: must return honest-empty result
    WITHOUT passing invariants AND WITHOUT fabricating tokens."""
    rep = PE.run_live_cdli("P000001", n_shuffles=300, seed=0,
                           force_status_for_tests="NEVER_ATTEMPTED")
    assert rep["fetch_status"] == "NEVER_ATTEMPTED"
    assert rep["n_input_tokens"] == 0
    assert rep["invariants"]["all_pass"] is False
    inv = rep["invariants"]["invariants"]
    for k, v in inv.items():
        assert v is False, f"honest-empty pass on {k} is fabrication"


# --- Stance honesty: forbidden phrases ------------------------------------

def test_forbidden_phrases_listed() -> None:
    """The forbidden-phrases surface MUST enumerate the 9 banned terms."""
    expected_substrings = (
        "translates to", "represents", "decodes as",
        "is related to Sumerian", "is related to Elamite",
    )
    for needle in expected_substrings:
        assert needle in PE.FORBIDDEN_PHRASES, f"missing forbidden phrase: {needle}"


# ============================================================================
# G2++ — Uruk III SFU comparator tests
# ============================================================================

def test_uruk_synthetic_invariants_pass() -> None:
    """G2++ Uruk synth uses DIFFERENT sign pool from PE; same 4 invariants
    should still pass — confirming the invariants describe a SHARED
    accounting-tablet FORMAT, not a script-specific artefact."""
    rep = PE.run_uruk_synthetic(seed=0, n_shuffles=500)
    assert rep["mission"] == "G2++"
    inv = rep["invariants"]["invariants"]
    assert inv["header_numeral_void"], "Uruk header should have zero numerals"
    assert inv["header_fraction_bounded"], "Uruk header fraction must be bounded"
    assert inv["numeral_block_predictable"], "Uruk numeral blocks should collapse H(next|n)"
    assert inv["z_lock_vs_shuffle"], "Uruk line cond-H should beat shuffle"
    assert rep["invariants"]["all_pass"] is True


def test_uruk_atf_tokenizer_handles_cuneiform_numerals() -> None:
    """Uruk III proto-cuneiform numerals share the N-tag system with PE —
    the G2 NUMERAL_RE must accept them, and parse_pe_atf must drop
    Sumerian transliteration determiners (e.g. trailing subscript digits)."""
    # Same parenthesised / clean-form coverage as G2.
    for tok in ("1(N01)", "2(N04)", "5(N19)", "7(N39)", "8(N46)",
                "1N01", "2N04", "5N19"):
        assert PE.is_numeral_sign(tok), f"Uruk cuneiform numeral not recognised: {tok!r}"
    # Sumerian transliteration: a header line + entries.
    atf = (
        "#atf: lang en\n"
        "@tablet\n"
        "@obverse\n"
        "&W 14306,a = Uruk III\n"
        "1. d lu2 ki sag engar 1(N01) 1(N01) mana 2(N04) gurus 3(N19)\n"
        "2. urudu tug2 5(N39) se 8(N46)\n"
    )
    toks = PE.parse_pe_atf(atf)
    # Expect ~6 header text signs then numerals + commodities.
    assert "d" in toks and "lu2" in toks and "ki" in toks, f"Uruk header missing: {toks}"
    assert "1N01" in toks and "2N04" in toks and "mana" in toks, \
        f"Uruk line tokens missing: {toks}"


def test_uruk_bundled_corpus_user_override() -> None:
    """USER_OVERRIDE bundled Uruk JSON with ATF text parses + invariants run."""
    td = Path(tempfile.mkdtemp(prefix="uruk_bundled_"))
    try:
        corpus = td / "uruk_corpus.json"
        corpus.write_text(json.dumps([
            {"cdli_id": "W 14306,a",
             "atf": PE.synth_uruk_ledger_atf("W 14306,a")},
        ]))
        rep = PE.run_uruk_bundled(corpus, n_shuffles=300, seed=0)
        assert rep["n_input_tokens"] > 0
        assert rep["mission"] == "G2++"
        assert rep["invariants"]["all_pass"] is True, \
            f"bundled Uruk synth should pass: {rep['invariants']}"
        assert rep["per_tablet"] == [{"cdli_id": "W 14306,a",
                                       "n_tokens": rep["n_input_tokens"]}]
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_uruk_compare_pe_vs_uruk_no_language_claim() -> None:
    """Comparison dict MUST exist with both/all_pass, numerical diffs, AND a
    `language_family_claim_made: False` gate. No banned phrase in the
    comparison dict (we verify by scanning the rendered Markdown)."""
    rep = PE.run_compare_pe_vs_uruk_main(seed=0, n_shuffles=300)
    assert rep["mission"] == "G2++"
    cmp = rep["compare_pe_vs_uruk"]
    sh = cmp["shared_ledger_structure"]
    assert sh["pe_all_pass"] is True
    assert sh["uruk_all_pass"] is True
    assert sh["both_pass"] is True
    assert sh["all_invariants_match"] is True
    assert cmp["language_family_claim_made"] is False
    diffs = cmp["numerical_diffs_no_language_claim"]
    for key in ("header_h1_diff_bits", "line_cond_h_diff_bits",
                "lz78_ratio_diff", "shuffled_z_diff"):
        assert key in diffs, f"missing diff field: {key}"
    # Rendered Markdown must NOT contain any banned phrase.
    md = PE.write_uruk_notes_md(rep)
    lines = md.splitlines()
    # Filter out the explicit forbidden-phrases log section (lines starting
    # with "- `" — that's where the Markdown writer enumerates the phrases
    # BY DESIGN for code-reviewer drift-detection). We check the body text.
    body_lines = [ln for ln in lines if not ln.startswith("- `")]
    body_text = "\n".join(body_lines)
    for phrase in PE.FORBIDDEN_PHRASES:
        assert phrase not in body_text, \
            f"forbidden phrase {phrase!r} leaked into G2++ NOTES.md body"


def test_uruk_sfu_subset_sum_skipped() -> None:
    """SFU/subset-sum probe MUST surface SKIPPED_PER_BRIEF_NON_TRIVIAL
    status (Captain brief: 'Optional SFU/subset-sum only if trivial; else SKIP')."""
    out = PE.sfu_subset_sum_probe([])
    assert out["status"] == "SKIPPED_PER_BRIEF_NON_TRIVIAL"
    assert "Captain brief" in out["note"], "SKIP note must cite the Captain brief"
    assert "tokens_analyzed" in out


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
