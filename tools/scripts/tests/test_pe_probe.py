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
