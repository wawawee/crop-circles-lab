"""Tests for tools/radio/lde_probe.py (G19 — Long Delayed Echoes).

Stance: structure != message. Every test pins an invariant of the
LDE delay-value analysis, NOT a claim about ET / Lunan / moon-relay.

Standalone-runnable: python3 tools/radio/tests/test_lde_probe.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
TOOLS_RADIO = HERE.parent
ROOT = TOOLS_RADIO.parent.parent
sys.path.insert(0, str(TOOLS_RADIO))

import lde_probe as LP  # noqa: E402


# ---------------------------------------------------------------------------
# 1. Data loading
# ---------------------------------------------------------------------------

def test_load_master_returns_100_rows():
    """Master JSON has 100 delay observations."""
    rows = LP.load_master()
    assert len(rows) == 100, f"expected 100 rows, got {len(rows)}"


def test_load_master_has_required_keys():
    """Every row has 'delay_s' and 'source'."""
    rows = LP.load_master()
    for r in rows:
        assert "delay_s" in r, f"missing delay_s in {r}"
        assert "source" in r, f"missing source in {r}"
        assert isinstance(r["delay_s"], (int, float))


def test_load_master_from_csv():
    """CSV loader also works."""
    csv_path = ROOT / "data" / "radio" / "lde" / "lde_master.csv"
    rows = LP.load_master(csv_path)
    assert len(rows) == 100


# ---------------------------------------------------------------------------
# 2. Descriptive statistics
# ---------------------------------------------------------------------------

def test_descriptive_mode_is_8s():
    """8 s is the historical mode; master should confirm."""
    rows = LP.load_master()
    desc = LP.descriptive_stats(rows)
    assert desc["mode_delay_s"] == 8.0
    assert desc["mode_count"] >= 10


def test_descriptive_fraction_integer_high():
    """1920s observers rounded to seconds; >90% should be integer."""
    rows = LP.load_master()
    desc = LP.descriptive_stats(rows)
    assert desc["fraction_integer"] > 0.9, (
        f"expected >90% integer delays, got {desc['fraction_integer']}"
    )


def test_descriptive_per_source_has_six_sources():
    """Master has 6 distinct source groups."""
    rows = LP.load_master()
    desc = LP.descriptive_stats(rows)
    assert len(desc["per_source"]) == 6


# ---------------------------------------------------------------------------
# 3. Shuffle null does not invent SIGNAL
# ---------------------------------------------------------------------------

def test_integer_multiplicity_p_value_is_one():
    """Shuffle of a multiset preserves value counts exactly; p=1.0."""
    rows = LP.load_master()
    delays = np.array([float(r["delay_s"]) for r in rows])
    result = LP.integer_multiplicity_test(delays, n_shuffle=20, seed=0)
    assert result["p_value"] == 1.0, (
        f"multiset shuffle should give p=1.0 (degenerate), got {result['p_value']}"
    )
    assert result["exceeds_null"] is False


def test_mode_concentration_p_value_is_one():
    """Shuffle preserves 8s count exactly; p=1.0."""
    rows = LP.load_master()
    delays = np.array([float(r["delay_s"]) for r in rows])
    result = LP.mode_concentration_test(delays, n_shuffle=20, seed=0)
    assert result["p_value"] == 1.0
    assert result["exceeds_null"] is False


def test_entropy_vs_uniform_low_p():
    """Distribution IS more concentrated than uniform (rounding artifact)."""
    rows = LP.load_master()
    delays = np.array([float(r["delay_s"]) for r in rows])
    result = LP.entropy_test(delays, n_shuffle=20, seed=0)
    # Low entropy = concentrated. This is expected from integer rounding.
    assert result["observed_entropy_bits"] < result["uniform_null_mean_entropy"]


# ---------------------------------------------------------------------------
# 4. Forbidden phrases
# ---------------------------------------------------------------------------

def test_no_forbidden_phrases_in_report():
    """Report must never contain ET / alien probe / confirma Lunan."""
    report = LP.run_all(seed=0, n_shuffle_syn=10, n_shuffle_lunan=20)
    text = json.dumps(report).lower()
    forbidden = [
        "et signal", "alien probe", "confirms lunan",
        "moon relay proven", "extraterrestrial confirmed",
        "lunan verified", "probe confirmed",
    ]
    for phrase in forbidden:
        assert phrase not in text, f"forbidden phrase found: {phrase!r}"


# ---------------------------------------------------------------------------
# 5. Stormer subset claim path
# ---------------------------------------------------------------------------

def test_lunan_claim_returns_valid_verdict():
    """Lunan claim must return CLAIM_FAILS_NULL or UNDERDETERMINED."""
    result = LP.lunan_claim_test(n_shuffle=20, seed=0)
    assert result["verdict"] in ("CLAIM_FAILS_NULL", "UNDERDETERMINED"), (
        f"verdict must be CLAIM_FAILS_NULL or UNDERDETERMINED, got {result['verdict']}"
    )


def test_lunan_claim_never_confirms():
    """Lunan claim NEVER returns a positive/confirming verdict."""
    result = LP.lunan_claim_test(n_shuffle=20, seed=0)
    # The only acceptable verdicts
    assert result["verdict"] in ("CLAIM_FAILS_NULL", "UNDERDETERMINED")
    # Must NOT beat both nulls
    assert not (result["beats_shuffle_null"] and result["beats_prosaic_null"]), (
        "Lunan claim must never beat both nulls simultaneously"
    )


def test_lunan_claim_subset_is_stormer_oct11():
    """The subset tested is Stormer 1928 Oct 11, n=14."""
    result = LP.lunan_claim_test(n_shuffle=10, seed=0)
    assert result["subset"] == "Stormer 1928 Oct 11 (n=14)"
    assert len(result["delays"]) == 14
    assert result["delays"] == LP.STORMER_1928_OCT11_DELAYS_S


def test_lunan_claim_includes_accuracy_caveat():
    """Lunan result must surface timing accuracy caveat."""
    result = LP.lunan_claim_test(n_shuffle=10, seed=0)
    assert "accuracy" in result["accuracy_caveat"].lower()
    assert "stopwatch" in result["accuracy_caveat"].lower()


# ---------------------------------------------------------------------------
# 6. Overall verdict
# ---------------------------------------------------------------------------

def test_overall_verdict_is_valid():
    """Overall verdict must be one of the three allowed values."""
    report = LP.run_all(seed=0, n_shuffle_syn=10, n_shuffle_lunan=20)
    assert report["overall_verdict"] in (
        "NO_SIGNAL", "UNDERDETERMINED", "CLAIM_FAILS_NULL"
    )


def test_overall_verdict_claim_fails_null_when_lunan_fails():
    """If Lunan claim fails, overall verdict is CLAIM_FAILS_NULL."""
    report = LP.run_all(seed=0, n_shuffle_syn=10, n_shuffle_lunan=20)
    if report["lunan_claim"]["verdict"] == "CLAIM_FAILS_NULL":
        assert report["overall_verdict"] == "CLAIM_FAILS_NULL"


# ---------------------------------------------------------------------------
# 7. Epoch fold
# ---------------------------------------------------------------------------

def test_epoch_fold_returns_best_period():
    """Epoch fold on delay values returns a best period."""
    result = LP.delay_epoch_fold(
        np.array(LP.STORMER_1928_OCT11_DELAYS_S), seed=0
    )
    assert "best_period_s" in result
    assert result["best_period_s"] > 0


# ---------------------------------------------------------------------------
# 8. CLI
# ---------------------------------------------------------------------------

def test_cli_all_runs_without_error():
    """CLI --all produces valid JSON output."""
    td = Path(tempfile.mkdtemp(prefix="lde_cli_"))
    out_json = td / "run.json"
    res = subprocess.run([
        sys.executable, str(TOOLS_RADIO / "lde_probe.py"),
        "--all",
        "--n-shuffle-syn", "10",
        "--n-shuffle-lunan", "20",
        "--seed", "0",
        "--out-json", str(out_json),
    ], capture_output=True, text=True, timeout=120)
    assert res.returncode == 0, (
        f"CLI failed:\nSTDOUT: {res.stdout[:600]}\nSTDERR: {res.stderr[:600]}"
    )
    assert out_json.exists()
    d = json.load(open(out_json))
    assert d["label"] == "lde_probe"
    assert d["overall_verdict"] in ("NO_SIGNAL", "UNDERDETERMINED", "CLAIM_FAILS_NULL")


def test_cli_lunan_claim_runs_without_error():
    """CLI --lunan-claim produces valid JSON."""
    td = Path(tempfile.mkdtemp(prefix="lde_lunan_"))
    out_json = td / "lunan.json"
    res = subprocess.run([
        sys.executable, str(TOOLS_RADIO / "lde_probe.py"),
        "--lunan-claim",
        "--n-shuffle-lunan", "20",
        "--seed", "0",
        "--out-json", str(out_json),
    ], capture_output=True, text=True, timeout=120)
    assert res.returncode == 0, (
        f"CLI --lunan-claim failed:\n{res.stderr[:600]}"
    )
    d = json.load(open(out_json))
    assert d["lunan_claim"]["verdict"] in ("CLAIM_FAILS_NULL", "UNDERDETERMINED")


def test_cli_all_writes_notes_md():
    """CLI --all with --out-md produces a valid markdown file."""
    td = Path(tempfile.mkdtemp(prefix="lde_notes_"))
    out_json = td / "run.json"
    out_md = td / "NOTES.md"
    res = subprocess.run([
        sys.executable, str(TOOLS_RADIO / "lde_probe.py"),
        "--all",
        "--n-shuffle-syn", "10",
        "--n-shuffle-lunan", "20",
        "--seed", "0",
        "--out-json", str(out_json),
        "--out-md", str(out_md),
    ], capture_output=True, text=True, timeout=120)
    assert res.returncode == 0
    assert out_md.exists()
    md = out_md.read_text()
    assert "structure" in md.lower()
    assert "message" in md.lower()
    assert "Lunan" in md
    assert "CLAIM_FAILS_NULL" in md or "UNDERDETERMINED" in md


# ---------------------------------------------------------------------------
# 9. Honesty framing
# ---------------------------------------------------------------------------

def test_report_has_stance_field():
    """Report includes the lab-motto stance."""
    report = LP.run_all(seed=0, n_shuffle_syn=10, n_shuffle_lunan=20)
    assert "structure != message" in report["stance"].lower()


def test_report_has_accuracy_caveat():
    """Report surfaces the 1920s timing accuracy caveat."""
    report = LP.run_all(seed=0, n_shuffle_syn=10, n_shuffle_lunan=20)
    caveat = report["accuracy_caveat"].lower()
    assert "stopwatch" in caveat or "±1" in caveat


def test_report_has_forbidden_list():
    """Report includes the forbidden-actions list."""
    report = LP.run_all(seed=0, n_shuffle_syn=10, n_shuffle_lunan=20)
    assert isinstance(report["forbidden"], list)
    assert len(report["forbidden"]) >= 3


# ---------------------------------------------------------------------------
# 10. Edge cases
# ---------------------------------------------------------------------------

def test_load_master_file_not_found():
    """Missing file raises FileNotFoundError."""
    try:
        LP.load_master(Path("/nonexistent/path.json"))
        assert False, "should have raised"
    except FileNotFoundError:
        pass


def test_descriptive_single_value():
    """Descriptive stats on a single-value array."""
    rows = [{"delay_s": 8.0, "source": "test"}]
    desc = LP.descriptive_stats(rows)
    assert desc["n_total"] == 1
    assert desc["n_unique"] == 1
    assert desc["mode_delay_s"] == 8.0


def test_lunan_claim_custom_delays():
    """Lunan claim works with custom delay list."""
    custom = [8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8]
    result = LP.lunan_claim_test(stormer_delays=custom, n_shuffle=20, seed=0)
    assert result["verdict"] in ("CLAIM_FAILS_NULL", "UNDERDETERMINED")
    assert len(result["delays"]) == 14


# ---------------------------------------------------------------------------
# 11. Write notes md
# ---------------------------------------------------------------------------

def test_write_notes_md_produces_string():
    """write_notes_md returns a non-empty string."""
    report = LP.run_all(seed=0, n_shuffle_syn=10, n_shuffle_lunan=20)
    md = LP.write_notes_md(report)
    assert isinstance(md, str)
    assert len(md) > 500
    assert "LDE" in md or "lde" in md.lower()
