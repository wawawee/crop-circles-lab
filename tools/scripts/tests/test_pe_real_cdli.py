"""
test_pe_real_cdli.py — G2-REAL tests for real CDLI fetch paths.

Tests the multi-fetch orchestrator, verdict composition, numeral-vs-numeral
split analysis, synth-vs-real comparison, and forbidden-phrase guards.

Run:
    python tools/scripts/tests/test_pe_real_cdli.py
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

import tools.scripts.proto_elamite_probe as PE


# --- Multi-fetch orchestration --------------------------------------------

def test_multi_fetch_all_fetched_passes_invariants() -> None:
    """When all tablets are FETCHED via test-force, the combined corpus
    must pass the 4 invariants (since each tablet is the synth fixture)."""
    rep = PE.run_multi_fetch_cdli(
        ["P008001", "P008002"], n_shuffles=100, seed=0,
        force_status_for_tests="FETCHED")
    assert rep["mission"] == "G2-REAL"
    assert rep["n_requested_ids"] == 2
    assert rep["n_tablets_fetched"] == 2
    assert rep["n_tablets_blocked"] == 0
    assert "STRUCTURE_SIGNAL" in rep["verdict"], f"got {rep['verdict']}"
    assert rep["probe"]["invariants"]["all_pass"] is True


def test_multi_fetch_all_blocked_returns_fetch_blocked() -> None:
    """When all tablets are UNREACHABLE, verdict must be FETCH_BLOCKED."""
    rep = PE.run_multi_fetch_cdli(
        ["P008001"], n_shuffles=100, seed=0,
        force_status_for_tests="UNREACHABLE")
    assert rep["mission"] == "G2-REAL"
    assert "FETCH_BLOCKED" in rep["verdict"], f"got {rep['verdict']}"
    assert rep["n_tablets_fetched"] == 0
    assert rep["n_tablets_blocked"] == 1


def test_multi_fetch_never_attempted() -> None:
    """NEVER_ATTEMPTED force must produce NEVER_ATTEMPTED verdict."""
    rep = PE.run_multi_fetch_cdli(
        ["P008001"], n_shuffles=100, seed=0,
        force_status_for_tests="NEVER_ATTEMPTED")
    assert rep["mission"] == "G2-REAL"
    assert "NEVER_ATTEMPTED" in rep["verdict"], f"got {rep['verdict']}"
    assert rep["n_tablets_fetched"] == 0


# --- Verdict composition --------------------------------------------------

def test_verdict_never_attempted() -> None:
    v = PE._compose_real_verdict({
        "per_tablet_fetch_statuses": ["NEVER_ATTEMPTED"],
        "probe": {"n_input_tokens": 0, "invariants": {"all_pass": False,
                  "invariants": {}}}
    })
    assert v == "NEVER_ATTEMPTED", f"got {v}"


def test_verdict_fetch_blocked() -> None:
    v = PE._compose_real_verdict({
        "per_tablet_fetch_statuses": ["UNREACHABLE", "PARKING_PAGE"],
        "probe": {"n_input_tokens": 0, "invariants": {"all_pass": False,
                  "invariants": {}}}
    })
    assert "FETCH_BLOCKED" in v, f"got {v}"


def test_verdict_structure_signal() -> None:
    v = PE._compose_real_verdict({
        "per_tablet_fetch_statuses": ["FETCHED", "FETCHED"],
        "probe": {"n_input_tokens": 50, "invariants": {"all_pass": True,
                  "invariants": {"h": True, "f": True, "n": True, "z": True}}}
    })
    assert "STRUCTURE_SIGNAL" in v, f"got {v}"


def test_verdict_no_signal() -> None:
    v = PE._compose_real_verdict({
        "per_tablet_fetch_statuses": ["FETCHED"],
        "probe": {"n_input_tokens": 50, "invariants": {"all_pass": False,
                  "invariants": {"h": False, "f": True, "n": True, "z": False}}}
    })
    assert "NO_SIGNAL" in v, f"got {v}"


def test_verdict_underdetermined() -> None:
    v = PE._compose_real_verdict({
        "per_tablet_fetch_statuses": ["FETCHED"],
        "probe": {"n_input_tokens": 3, "invariants": {"all_pass": False,
                  "invariants": {}}}
    })
    assert "UNDERDETERMINED" in v, f"got {v}"


# --- Numeral vs non-numeral split analysis --------------------------------

def test_numeric_split_analysis_with_mixed_tokens() -> None:
    tokens = ["M388", "GI", "1N01", "2N04", "M122", "3N19"]
    split = PE._numeric_split_analysis(tokens, n_shuffles=100, seed=0)
    assert split["n_total_tokens"] == 6
    assert split["n_numeral_tokens"] == 3
    assert split["n_non_numeral_tokens"] == 3
    assert split["numeral_fraction"] == 0.5
    assert split["numeral_non_numeral_ratio"] == 1.0
    assert "numeral_analysis" in split
    assert "non_numeral_analysis" in split
    assert "z_diff_numeral_minus_non" in split


def test_numeric_split_analysis_empty() -> None:
    split = PE._numeric_split_analysis([], n_shuffles=100, seed=0)
    assert split["n_tokens"] == 0
    assert "note" in split


def test_numeric_split_analysis_all_numerals() -> None:
    tokens = ["1N01", "2N04", "3N19", "1N01"]
    split = PE._numeric_split_analysis(tokens, n_shuffles=100, seed=0)
    assert split["n_total_tokens"] == 4
    assert split["n_numeral_tokens"] == 4
    assert split["n_non_numeral_tokens"] == 0
    assert split["numeral_fraction"] == 1.0


# --- Synth vs real comparison ---------------------------------------------

def test_compare_synth_vs_real_both_pass() -> None:
    synth = PE.run_synthetic(seed=0, n_shuffles=100)
    real = PE.run_synthetic(seed=0, n_shuffles=100)  # same synth as "real" for test
    cmp = PE._compare_synth_vs_real(synth, real)
    assert cmp["synth_all_pass"] is True
    assert cmp["real_all_pass"] is True
    assert cmp["all_invariants_match"] is True
    assert cmp["both_pass"] is True
    diffs = cmp["numerical_diffs"]
    for key in ("cond_h_bits_diff_real_minus_synth", "z_diff_real_minus_synth",
                "lz78_ratio_diff", "header_h1_diff"):
        assert key in diffs, f"missing diff field: {key}"


def test_compare_synth_vs_real_synth_passes_real_not() -> None:
    """Synthetic passes but a shuffled corpus fails: comparison must show
    the mismatch."""
    synth = PE.run_synthetic(seed=0, n_shuffles=100)
    import random as rnd
    base = PE.synth_pe_ledger(seed=0)
    rnd.Random(7).shuffle(base)
    real = PE.run_ledger_probe(base, label="shuffled_real",
                                n_shuffles=100, seed=0)
    cmp = PE._compare_synth_vs_real(synth, real)
    assert cmp["synth_all_pass"] is True
    assert cmp["real_all_pass"] is False
    assert cmp["all_invariants_match"] is False
    assert cmp["both_pass"] is False


# --- Forbidden-phrase guard on new outputs --------------------------------

def test_real_notes_md_no_forbidden_phrases_in_body() -> None:
    """The rendered real_NOTES.md must not contain any forbidden phrases
    outside the explicit logging section."""
    rep = PE.run_multi_fetch_cdli(
        ["P008001"], n_shuffles=100, seed=0,
        force_status_for_tests="FETCHED")
    md = PE.write_real_notes_md(rep)
    lines = md.splitlines()
    # Exclude the forbidden-phrases log section (lines starting with "- `")
    body_lines = [ln for ln in lines if not ln.startswith("- `")]
    body_text = "\n".join(body_lines)
    for phrase in PE.FORBIDDEN_PHRASES:
        assert phrase not in body_text, \
            f"forbidden phrase {phrase!r} leaked into real_NOTES.md body"


def test_real_notes_md_renders_verdict() -> None:
    """The rendered NOTES must include the verdict string."""
    rep = PE.run_multi_fetch_cdli(
        ["P008001"], n_shuffles=100, seed=0,
        force_status_for_tests="FETCHED")
    md = PE.write_real_notes_md(rep)
    assert rep["verdict"] in md, "verdict should appear in rendered NOTES"
    assert "STRUCTURE_SIGNAL" in md


def test_real_notes_md_underdetermined_banner() -> None:
    """Rendered NOTES for blocked multi-fetch must highlight the blockage."""
    rep = PE.run_multi_fetch_cdli(
        ["P008001"], n_shuffles=100, seed=0,
        force_status_for_tests="UNREACHABLE")
    md = PE.write_real_notes_md(rep)
    assert "FETCH_BLOCKED" in md


# --- Per-tablet fetch detail ----------------------------------------------

def test_multi_fetch_per_tablet_records_attempts() -> None:
    """Per-tablet records must include fetch_status, n_tokens, and attempts."""
    rep = PE.run_multi_fetch_cdli(
        ["P008001", "P008002"], n_shuffles=100, seed=0,
        force_status_for_tests="FETCHED")
    for pt in rep["per_tablet"]:
        assert "cdli_id" in pt
        assert "fetch_status" in pt
        assert "n_tokens" in pt
        assert pt["fetch_status"] == "FETCHED"
        assert pt["n_tokens"] > 0


def test_multi_fetch_per_tablet_blocked_records() -> None:
    """Blocked tablets must have n_tokens=0 and empty attempts list."""
    rep = PE.run_multi_fetch_cdli(
        ["P008001", "P008002"], n_shuffles=100, seed=0,
        force_status_for_tests="UNREACHABLE")
    for pt in rep["per_tablet"]:
        assert pt["fetch_status"] == "UNREACHABLE"
        assert pt["n_tokens"] == 0
        assert len(pt["attempts"]) >= 5, \
            f"expected ≥5 CDLI URL attempts, got {len(pt['attempts'])}"


# --- List known CDLI IDs -------------------------------------------------

def test_known_pe_cdli_ids_are_strings() -> None:
    """All KNOWN_PE_CDLI_IDS must be non-empty strings starting with P."""
    for cid in PE.KNOWN_PE_CDLI_IDS:
        assert isinstance(cid, str)
        assert cid.startswith("P"), f"unexpected ID format: {cid!r}"
        assert len(cid) >= 7


# --- main() --------------------------------------------------------------

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
