"""
test_linear_elamite_probe.py — known-answer + stance tests for G12 Linear Elamite probe.

Run:
    python tools/scripts/tests/test_linear_elamite_probe.py

Mirrors the G2/G2++ test style: synth invariants, shuffled negative control,
monumental inverse control (the new G12 caveat from the thinker review),
Desset 2024 claim block verdict logic, LE↔PE↔Uruk structure comparator,
forbidden-phrase guard, fetch-status test hooks, and main() end-to-end.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

import tools.scripts.linear_elamite_probe as LE  # noqa: E402
import tools.scripts.proto_elamite_probe as PE  # noqa: E402


# -----------------------------------------------------------------------------
# Forbidden-phrase guard
# -----------------------------------------------------------------------------

def test_forbidden_phrases_includes_le_specific_bans() -> None:
    """LE_FORBIDDEN_PHRASES must enumerate the G12-specific ban list
    AND retain the G2/G2++ baseline verbatim."""
    expected = (
        "translates to", "decodes as", "shares roots with",
        "is related to Sumerian",
        "Linear Elamite deciphered",
        "Linear Elamite = ",
        "viral blog",
        "youtube decipherment",
        "99% deciphered",
        "100% deciphered",
        "alien",
    )
    for needle in expected:
        assert needle in LE.LE_FORBIDDEN_PHRASES, f"missing forbidden phrase: {needle!r}"


def test_assert_no_forbidden_phrases_clean_text_passes() -> None:
    LE.assert_no_forbidden_phrases(
        "These metrics confirm sign-sequence structure, no decipherment.",
        where="clean text",
    )


def test_assert_no_forbidden_phrases_raises_on_every_banned_phrase() -> None:
    """For each phrase in LE_FORBIDDEN_PHRASES, embedding it in body text
    must raise ValueError. Skip-lines starting with `- ` (the explicit
    enumeration log) so we don't self-trigger."""
    for phrase in LE.LE_FORBIDDEN_PHRASES:
        if not phrase.strip():
            continue
        body = f"The Linear Elamite runs {phrase} here, that's the claim."
        try:
            LE.assert_no_forbidden_phrases(body, where="bad text")
        except ValueError:
            continue
        raise AssertionError(f"forbidden phrase {phrase!r} did NOT trigger ValueError")


def test_assert_no_forbidden_phrases_allows_log_section_lines() -> None:
    """The forbidden-phrases log section begins every line with ``- ` `` so
    `assert_no_forbidden_phrases` must ignore those lines. Otherwise the
    Markdown writer would self-trigger while rendering its own safety log."""
    body = "\n".join(
        f"- `{p}`" for p in LE.LE_FORBIDDEN_PHRASES
    )
    LE.assert_no_forbidden_phrases(body, where="log section")


# -----------------------------------------------------------------------------
# Number regex / numeral classification
# -----------------------------------------------------------------------------

def test_is_numeral_sign_matches_bare_digits_and_tagged_forms() -> None:
    """LE numerals accept bare Latin digits AND `N`-tagged forms (parity with
    CDLI ATF) — same convention the G2 NUMERAL_RE supports."""
    for tok in ("1", "2", "1(N01)", "2(N04)", "5(N19)", "8(N46)", "10(N14A)"):
        assert LE.is_numeral_sign(tok), f"expected numeral: {tok!r}"
    for tok in ("LE_017", "LE_044", "LE_088", "GI", "M388"):
        assert not LE.is_numeral_sign(tok), f"unexpected numeral class: {tok!r}"
    assert not LE.is_numeral_sign("")
    assert not LE.is_numeral_sign("?LE_017")  # after clean_token → "LE_017"


def test_clean_token_strips_atf_determiners() -> None:
    """ATF determiners (?, !, brackets, parens, <> ,) are stripped."""
    assert LE.clean_token("1(N01)") == "1N01"
    assert LE.clean_token("LE_017") == "LE_017"
    assert LE.clean_token("?LE_017") == "LE_017"
    assert LE.clean_token("...LE_017...") == "LE_017"
    assert LE.clean_token("") == ""
    assert LE.clean_token("...") == ""


# -----------------------------------------------------------------------------
# ATF parser
# -----------------------------------------------------------------------------

def test_parse_lei_atf_strips_comments_and_at_headers() -> None:
    atf = (
        "#atf: lang en\n"
        "@tablet\n"
        "@obverse\n"
        "&X001 = Anshan\n"
        "1. LE_017 LE_044 1 2 3 LE_088\n"
        "# trailing comment line\n"
        "2. LE_002 5 8\n"
    )
    toks = LE.parse_lei_atf(atf)
    assert toks == ["LE_017", "LE_044", "1", "2", "3", "LE_088",
                     "LE_002", "5", "8"], f"got {toks}"


def test_parse_lei_atf_drops_line_number_marker() -> None:
    """Without the line-number strip, '1. LE_017' would tokenise to '1' (a numeral)
    followed by 'LE_017' — making the first tokenise position a phantom numeral."""
    atf = "1. LE_017 LE_044 LE_088 1 1 1\n"
    toks = LE.parse_lei_atf(atf)
    # First token must be a LE catalogue ID, not a phantom '1' numeral.
    assert toks[0] == "LE_017", f"line marker leaked: {toks}"
    assert "1" in toks
    assert toks[-1] == "1", f"trailing numerals preserved: {toks}"


# -----------------------------------------------------------------------------
# Shuffle controls
# -----------------------------------------------------------------------------

def test_unigram_preserving_shuffle_keeps_counter() -> None:
    toks = ["LE_017", "LE_017", "LE_044", "1", "1", "1", "1"]
    shuf = LE.unigram_preserving_shuffle(toks, seed=0)
    assert Counter(shuf) == Counter(toks)
    assert shuf == LE.unigram_preserving_shuffle(toks, seed=0)


# -----------------------------------------------------------------------------
# Header/line split + numeral block extraction + 4 invariants
# -----------------------------------------------------------------------------

def test_split_header_blocks_basic() -> None:
    toks = ["LE_017", "LE_044", "LE_088", "1", "LE_002", "1", "2"]
    hdr, ln = LE.split_header_blocks(tokens=toks)
    assert hdr == ["LE_017", "LE_044", "LE_088"], f"hdr={hdr}"
    assert ln == ["1", "LE_002", "1", "2"], f"ln={ln}"


def test_extract_numeral_blocks_basic() -> None:
    toks = ["LE_017", "1", "1", "LE_088", "2", "3", "LE_002", "8"]
    blocks = LE.extract_numeral_blocks(toks)
    assert blocks == [["1", "1"], ["2", "3"], ["8"]], f"got {blocks}"


def test_synthetic_ledger_invariants_pass() -> None:
    """Synthetic known-answer: all 4 invariants MUST hold."""
    rep = LE.run_synthetic(seed=0, n_shuffles=500)
    inv = rep["invariants"]["invariants"]
    assert inv["header_numeral_void"], "synthetic header should have zero numerals"
    assert inv["header_fraction_bounded"], "header fraction must be bounded"
    assert inv["numeral_block_predictable"], "numeral blocks should collapse H(next|n)"
    assert inv["z_lock_vs_shuffle"], "line cond-H should beat shuffle"
    assert rep["invariants"]["all_pass"] is True


def test_shuffled_synthetic_invariants_fail_z_lock() -> None:
    """Random unigram-preserving-shuffled synth: z_lock MUST fail. The
    negative-control discriminator validates the test, not the pipeline."""
    import random as rnd
    rng = rnd.Random(7)
    base = LE.synth_lei_ledger(seed=0)
    rng.shuffle(base)
    rep = LE.run_ledger_probe(base, label="shuffled_negative_control",
                               n_shuffles=300, seed=0)
    inv = rep["invariants"]["invariants"]
    assert inv["z_lock_vs_shuffle"] is False


def test_monumental_inverse_control_fails_invariants_by_construction() -> None:
    """Concrete outcome of the G12 thinker-flagged caveat: when LE is
    monumental/narrative (no numerals, no accounting-block shape), the 4
    invariants MUST fail. This is the *intended* FAIL — it shows that
    failing the invariants means 'this is not an accounting tablet',
    not 'this script lacks structure'."""
    rep = LE.run_monumental_synthetic(seed=17, n_shuffles=300)
    assert rep["inverse_control"] is True
    assert rep["invariants"]["all_pass"] is False
    # header_numeral_void † colossal": monumental has NO numerals anywhere.
    inv = rep["invariants"]["invariants"]
    # monumental bundle has zero numerals ++ class is header (entire bundle
    # has no first-numeral). header_n_numerals = 0 → inv1 PASSES by accident,
    # but inv4 z_lock (cond-H on the whole bundle vs shuffle) FAILS.
    assert inv["z_lock_vs_shuffle"] is False, (
        "Monumental bundle must NOT z-lock vs shuffle (uniform text)"
    )
    # header_fraction_bounded †• fails because the entire bundle is the
    # 'header' (no numerals anywhere ⇒ header_frac == 1.0).
    assert inv["header_fraction_bounded"] is False, (
        "Monumental bundle = 100% header_frac > 0.80 (correct)"
    )


# -----------------------------------------------------------------------------
# Fetch-status test hooks
# -----------------------------------------------------------------------------

def test_default_fetch_is_never_attempted() -> None:
    """Default (no force, no --fetch-online) MUST NOT touch the network."""
    fr = LE.try_fetch_open_dumps("z4960710")
    assert fr.fetch_status == "NEVER_ATTEMPTED"
    assert fr.atf_text == ""
    assert fr.attempts == []


def test_force_status_unreachable_listed_attempts() -> None:
    fr = LE.try_fetch_open_dumps("z4960710", force_status_for_tests="UNREACHABLE")
    assert fr.fetch_status == "UNREACHABLE"
    assert fr.atf_text == ""
    assert len(fr.attempts) >= 4, "expected per-URL network attempts logged"
    for att in fr.attempts:
        assert att["verdict"] == "NETWORK_ERROR"


def test_force_status_parking_page_marked() -> None:
    fr = LE.try_fetch_open_dumps("z4960710", force_status_for_tests="PARKING_PAGE")
    assert fr.fetch_status == "PARKING_PAGE"
    assert all(att["verdict"] == "PARKING_PAGE" for att in fr.attempts)


def test_bundled_corpus_path_runs_ledger_probe() -> None:
    """USER_OVERRIDE bundled JSON parses + invariants run + per_tablet breakdown
    + script_genres counter populates from bundled metadata."""
    corpus_path = LE.DATA_DIR / "synth_corpus.json"
    rep = LE.run_bundled(corpus_path, n_shuffles=300, seed=0)
    assert rep["n_input_tokens"] > 0
    assert "per_tablet" in rep
    # Formulaic-ledger + monumental-narrative sub-bundles parsed separately.
    assert any(p["cdli_id"].startswith("SYNTH-LEI-L") for p in rep["per_tablet"]), \
        f"per_tablet did not list ledger bundles: {rep['per_tablet']}"
    assert any(p["cdli_id"].startswith("SYNTH-LEI-M") for p in rep["per_tablet"]), \
        f"per_tablet did not list monumental bundles: {rep['per_tablet']}"
    assert rep["script_genres"].get("formulaic_accounting_tablet", 0) >= 1


def test_live_open_dumps_honest_empty_yellow_banner() -> None:
    """Live open-dump path with NEVER_ATTEMPTED: must return honest-empty
    result WITHOUT passing invariants AND without fabricating tokens."""
    rep = LE.run_live_open_dumps("z4960710", n_shuffles=300, seed=0,
                                  force_status_for_tests="NEVER_ATTEMPTED")
    assert rep["fetch_status"] == "NEVER_ATTEMPTED"
    assert rep["n_input_tokens"] == 0
    assert rep["invariants"]["all_pass"] is False


# -----------------------------------------------------------------------------
# Desset 2024 claim block
# -----------------------------------------------------------------------------

def test_desset_claim_block_returns_required_fields() -> None:
    """The CUT block must surface: n_tokens, ic, top_unigrams, top_bigrams,
    shuffle_null with observed/mean/sd/z, claim_verdict_recommendation."""
    synth = LE.synth_lei_ledger(seed=0)
    blk = LE.desset_2024_claim_block(synth, n_shuffles=300, seed=0)
    for key in ("n_tokens", "n_distinct", "index_of_coincidence",
                "top_unigrams", "top_bigrams", "shuffled_null",
                "claim_verdict_recommendation", "caveat"):
        assert key in blk, f"missing key: {key}"
    assert blk["press_claim_summary"], "press claim summary must be present"
    # Shuffle-null structural invariants:
    assert "observed" in blk["shuffled_null"]
    assert "z" in blk["shuffled_null"]


def test_desset_claim_block_recommendation_pipeline_synthetic() -> None:
    """For the synthetic-ledger known-answer, signals beat shuffles (z<-3)
    → recommendation CANNOT be CLAIM_FAILS_NULL. CAUTION: 'beats shuffle'
    is NOT endorsement; the verdict vocabulary is CLAIM_UNDERDETERMINED."""
    synth = LE.synth_lei_ledger(seed=0)
    blk = LE.desset_2024_claim_block(synth, n_shuffles=500, seed=0)
    rec = blk["claim_verdict_recommendation"]
    assert rec == "CLAIM_UNDERDETERMINED", (
        f"expected CLAIM_UNDERDETERMINED for synth beating shuffle; got {rec!r}. "
        f"shuffled_null: z={blk['shuffled_null']['z']}"
    )
    # Caveat must be loud: "beats shuffle ≠ translates".
    assert "endors" in blk["caveat"].lower(), \
        "caveat must declare that beats-shuffle is not endorsement"


def test_desset_claim_block_recommendation_random_fails_null() -> None:
    """For a uniformly-random token sequence (synthetic known-answer NEGATED),
    signals should NOT beat the shuffle → recommendation should be
    CLAIM_FAILS_NULL."""
    import random as rnd
    rng = rnd.Random(13)
    toks = rng.choices(["A", "B", "C", "D", "E"], k=400)
    blk = LE.desset_2024_claim_block(toks, n_shuffles=300, seed=0)
    assert blk["claim_verdict_recommendation"] == "CLAIM_FAILS_NULL", blk


# -----------------------------------------------------------------------------
# Comparator: LE vs PE vs Uruk
# -----------------------------------------------------------------------------

def test_compare_le_vs_pe_uruk_no_language_claim() -> None:
    """Three DIFFERENT sign pools must pass the SAME 4 invariants AND
    language_family_claim_made MUST be False."""
    rep = LE.run_compare_le_vs_pe_uruk(seed=0, n_shuffles=300)
    shared = rep["shared_ledger_structure"]
    assert shared["pe_all_pass"] is True
    assert shared["uruk_all_pass"] is True
    assert shared["le_all_pass"] is True
    assert shared["all_three_pass"] is True
    assert shared["all_invariants_match_across_scripts"] is True
    assert rep["language_family_claim_made"] is False, (
        "Comparator MUST set language_family_claim_made=False (Captain brief)"
    )
    # No banned phrase in rendered Markdown body.
    synth = LE.run_synthetic(seed=0, n_shuffles=300)
    partial = {
        "mission": "G12",
        "generated_at": "test",
        "stance": LE.LE_STANCE,
        "stance_monumental_caveat": LE.LE_STANCE_MONUMENTAL_CAVEAT,
        "compare_le_vs_pe_uruk": rep,
        "forbidden_phrases": list(LE.LE_FORBIDDEN_PHRASES),
        "synthetic_run": synth,
    }
    md = LE.write_comparator_notes_md(partial)
    body = "\n".join(ln for ln in md.splitlines() if not ln.startswith("- `"))
    for phrase in LE.LE_FORBIDDEN_PHRASES:
        assert phrase not in body, f"forbidden phrase {phrase!r} leaked into comparator NOTES"


# -----------------------------------------------------------------------------
# Verdict tree
# -----------------------------------------------------------------------------

def test_verdict_tree_synthetic_structured_claim_undertermined() -> None:
    """Synthetic LE ledger: SEQUENCE_STRUCTURE | CLAIM_UNDERDETERMINED + COMP."""
    synth = LE.run_synthetic(seed=0, n_shuffles=300)
    blk = LE.desset_2024_claim_block(LE.synth_lei_ledger(seed=0), n_shuffles=300, seed=0)
    cmp = LE.run_compare_le_vs_pe_uruk(seed=0, n_shuffles=300)
    v = LE.compute_verdict(synth, blk, cmp)
    assert "SEQUENCE_STRUCTURE" in v["verdict"], v["verdict"]
    assert "CLAIM_UNDERDETERMINED" in v["verdict"], v["verdict"]
    assert "ACCOUNTING_FORMAT_STRUCTURED" in v["verdict"], v["verdict"]


def test_verdict_tree_empty_fetch_is_undertermined() -> None:
    """If the live fetch was NEVER_ATTEMPTED/UNREACHABLE/PARKING_PAGE, structure
    axis must be UNDERDETERMINED regardless of the bundled run being OK."""
    synth = LE.run_synthetic(seed=0, n_shuffles=300)
    live = LE.run_live_open_dumps("z4960710", n_shuffles=300, seed=0,
                                   force_status_for_tests="NEVER_ATTEMPTED")
    blk = LE.desset_2024_claim_block(LE.synth_lei_ledger(seed=0),
                                      n_shuffles=300, seed=0)
    v = LE.compute_verdict(live, blk, None)
    assert v["structure_axis"] == "UNDERDETERMINED", v
    # Feed values: claim is computed from synth tokens (real structure).
    assert "CLAIM_" in v["claim_axis"], v


def test_verdict_tree_random_pipeline_returns_undertermined() -> None:
    """If a pipeline produces NO structure (random shuffle), verdict must
    be NO_SIGNAL on axis 1. Mark the test: we use shuffled LE tokens."""
    import random as rnd
    rng = rnd.Random(13)
    toks = rng.choices(list("ABCDE"), k=200)
    rep = LE.run_ledger_probe(toks, label="shuffled_invariant_fail",
                               n_shuffles=300, seed=0)
    blk = LE.desset_2024_claim_block(toks, n_shuffles=300, seed=0)
    v = LE.compute_verdict(rep, blk, None)
    assert v["structure_axis"] == "NO_SIGNAL", v


def test_verdict_tree_monumental_inverse_ok() -> None:
    """Monumental inverse control: structure axis = INVERSE_CONTROL_OK
    (intentional FAIL on a narrative bundle)."""
    inv = LE.run_monumental_synthetic(seed=17, n_shuffles=300)
    blk = LE.desset_2024_claim_block(LE.synth_lei_ledger(seed=0),
                                      n_shuffles=300, seed=0)
    v = LE.compute_verdict(inv, blk, None)
    assert v["structure_axis"] == "INVERSE_CONTROL_OK", v


def test_verdict_string_never_combines_to_forbidden_phrase() -> None:
    """Verdict string must NEVER contain a forbidden phrase — even after
    merging structure + claim + comparator axes. The guard is in
    `compute_verdict` itself; this test normally passes silently but
    fires loudly if a future refactor regresses the guard."""
    synth = LE.run_synthetic(seed=0, n_shuffles=300)
    blk = LE.desset_2024_claim_block(LE.synth_lei_ledger(seed=0), n_shuffles=300, seed=0)
    cmp = LE.run_compare_le_vs_pe_uruk(seed=0, n_shuffles=300)
    v = LE.compute_verdict(synth, blk, cmp)
    LE.assert_no_forbidden_phrases(v["verdict"], where="verdict string")


# -----------------------------------------------------------------------------
# End-to-end main() smoke
# -----------------------------------------------------------------------------

def test_main_synthetic_writes_outputs_and_passes_guard() -> None:
    """End-to-end: --synthetic writes run.json + NOTES.md into a tempdir,
    bodies are guard-clean, and the file is parser-readable JSON."""
    td = Path(tempfile.mkdtemp(prefix="lei_main_"))
    try:
        out_json = td / "run.json"
        out_md = td / "NOTES.md"
        res = subprocess.run([
            sys.executable, str(ROOT / "tools" / "scripts" / "linear_elamite_probe.py"),
            "--synthetic",
            "--n-shuffles", "100",
            "--out-json", str(out_json),
            "--out-md", str(out_md),
        ], capture_output=True, text=True, timeout=120)
        assert res.returncode == 0, (
            f"linear_elamite_probe.py --synthetic failed:\nSTDOUT:\n{res.stdout[:800]}\n"
            f"STDERR:\n{res.stderr[:800]}"
        )
        assert out_json.exists(), "run.json not written"
        assert out_md.exists(), "NOTES.md not written"
        d = json.loads(out_json.read_text())
        assert "verdict_block" in d
        assert "desset_2024_claim_block" in d
        md_text = out_md.read_text()
        assert "G12" in md_text
        assert "Linear Elamite" in md_text
        assert "Verdict" in md_text
        # Drift guard: NOTES.md body MUST NOT contain a banned phrase.
        body = "\n".join(ln for ln in md_text.splitlines() if not ln.startswith("- `"))
        for phrase in LE.LE_FORBIDDEN_PHRASES:
            assert phrase.lower() not in body.lower(), \
                f"forbidden phrase {phrase!r} leaked into NOTES.md body"
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_main_comparator_writes_outputs_and_passes_guard() -> None:
    """End-to-end comparator: --compare-le-vs-pe-uruk into tempdir."""
    td = Path(tempfile.mkdtemp(prefix="lei_cmp_"))
    try:
        out_json = td / "compare.json"
        out_md = td / "compare.md"
        res = subprocess.run([
            sys.executable, str(ROOT / "tools" / "scripts" / "linear_elamite_probe.py"),
            "--compare-le-vs-pe-uruk",
            "--n-shuffles", "100",
            "--out-json", str(out_json),
            "--out-md", str(out_md),
        ], capture_output=True, text=True, timeout=180)
        assert res.returncode == 0, (
            f"linear_elamite_probe.py --compare-le-vs-pe-uruk failed:\n"
            f"STDOUT:\n{res.stdout[:800]}\nSTDERR:\n{res.stderr[:800]}"
        )
        assert out_json.exists()
        assert out_md.exists()
        d = json.loads(out_json.read_text())
        assert d.get("compare_le_vs_pe_uruk", {}).get("language_family_claim_made") is False
        # Comparator must show LE passing (math is calibrated against LE synth).
        shared = d.get("compare_le_vs_pe_uruk", {}).get("shared_ledger_structure", {})
        assert shared.get("le_all_pass") is True
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_main_inverse_control_writes_outputs() -> None:
    """End-to-end inverse control: --monumental-inverse into tempdir;
    invariants MUST fail by construction."""
    td = Path(tempfile.mkdtemp(prefix="lei_inv_"))
    try:
        out_json = td / "inverse.json"
        out_md = td / "inverse.md"
        res = subprocess.run([
            sys.executable, str(ROOT / "tools" / "scripts" / "linear_elamite_probe.py"),
            "--monumental-inverse",
            "--n-shuffles", "100",
            "--out-json", str(out_json),
            "--out-md", str(out_md),
        ], capture_output=True, text=True, timeout=120)
        assert res.returncode == 0, (
            f"linear_elamite_probe.py --monumental-inverse failed:\n"
            f"STDOUT:\n{res.stdout[:800]}\nSTDERR:\n{res.stderr[:800]}"
        )
        assert out_json.exists()
        d = json.loads(out_json.read_text())
        # Inverse control intentionally fails 4 invariants.
        assert d["inverse_control"] is True
        assert d["invariants"]["all_pass"] is False
    finally:
        shutil.rmtree(td, ignore_errors=True)


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
