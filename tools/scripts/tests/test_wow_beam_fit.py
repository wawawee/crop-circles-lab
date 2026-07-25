"""test_wow_beam_fit.py — G3 known-answer + underdetermined caveat tests.

Standalone:
    python tools/scripts/tests/test_wow_beam_fit.py

Stance: structure != message. Tests pin the scaffold math, NOT a claim
about the real Wow! signal.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np

import tools.scripts.wow_beam_fit as WF


# --- fit invariant tests ---------------------------------------------------

def test_gaussian_r2_exceeds_constant():
    """Gaussian fit must trivially beat the constant baseline (r² ~ 0.986 vs 0)."""
    report = WF.run_beam_fit(seed=0)
    fit = report["fit"]
    assert fit["r2_gaussian"] >= fit["r2_constant"] + 0.5, (
        f"gaussian r²={fit['r2_gaussian']} should clearly exceed "
        f"constant r²={fit['r2_constant']}"
    )


def test_sinc_fit_returns_valid_params():
    """Sinc fit must produce non-None mu, sigma, amplitude."""
    report = WF.run_beam_fit(seed=0)
    rs = report["fit"]["recovered_sinc"]
    assert rs["mu_idx"] is not None
    assert rs["sigma_idx"] is not None
    assert rs["amplitude"] is not None
    assert 0.0 <= rs["mu_idx"] <= 5.0


def test_n_dof_gaussian_is_3():
    """Gaussian on N=6, K=3 -> d.o.f. = N-K = 3."""
    report = WF.run_beam_fit(seed=0)
    assert report["fit"]["n_dof_gaussian"] == 3
    assert report["fit"]["n_dof_sinc"] == 3
    assert report["fit"]["n_dof_constant"] == 5


def test_underdetermined_flag_true():
    """For N=6 the underdetermined flag MUST be True."""
    report = WF.run_beam_fit(seed=0)
    assert report["fit"]["underdetermined"] is True, (
        "N=6 fit must be flagged underdetermined"
    )


def test_degeneracy_pair_sums_to_6():
    """mu + (6-mu) symmetry: degeneracy_pair must sum to 6.0 ± 0.5."""
    report = WF.run_beam_fit(seed=0)
    d0, d1 = report["fit"]["degeneracy_pair"]
    assert abs((d0 + d1) - 6.0) < 0.5, (
        f"degeneracy_pair {report['fit']['degeneracy_pair']} must sum to ~6"
    )


def test_scramble_null_distribution_valid():
    """Scramble null must produce valid median, p5 <= median <= p95."""
    report = WF.run_beam_fit(seed=0)
    sn = report["scramble_null"]
    assert sn["n_permutations"] >= 24
    assert sn["r2_median"] is not None
    assert sn["r2_p5"] <= sn["r2_median"] + 1e-6, (
        f"p5({sn['r2_p5']}) > median({sn['r2_median']})"
    )
    assert sn["r2_median"] <= sn["r2_p95"] + 1e-6, (
        f"median({sn['r2_median']}) > p95({sn['r2_p95']})"
    )
    assert sn["mu_distribution_median"] is not None


# --- known-answer / cross-check --------------------------------------------

def test_structure_above_scramble_median():
    """Real intensities should show structure above scramble null."""
    report = WF.run_beam_fit(seed=0)
    cc = report["cross_check_scramble"]
    assert cc is not None
    assert cc["structure_above_scramble_median"] is True
    assert cc["delta_real_vs_scramble_median"] > 0.5


def test_verdict_is_underdetermined():
    """Top-level verdict must be UNDERDETERMINED (NOT NO_SIGNAL, NOT ET)."""
    report = WF.run_beam_fit(seed=0)
    assert report["verdict"] == "UNDERDETERMINED", (
        f"verdict must be UNDERDETERMINED, got {report['verdict']}"
    )
    assert "UNDERDETERMINED" in report["stance"]
    assert "structure \u2260 ET" in report["stance"] or "structure != ET" in report["stance"]


def test_underdetermined_note_cites_phl():
    """The underdetermined note must cite arXiv:2408.08513."""
    report = WF.run_beam_fit(seed=0)
    note = report["fit"]["underdetermined_note"]
    assert "arXiv:2408.08513" in note or "PHL@UPR" in note


def test_fit_quality_caveat_present():
    """fit_quality_caveat string must be present and non-empty."""
    report = WF.run_beam_fit(seed=0)
    caveat = report["fit"]["fit_quality_caveat"]
    assert isinstance(caveat, str) and len(caveat) > 20


def test_stance_contains_lab_motto():
    """Stance must contain 'structure != message' and 'necessary, NOT sufficient'."""
    stance = report["stance"].lower() if "stance" in (report := WF.run_beam_fit(seed=0)) else ""
    if not stance:
        report = WF.run_beam_fit(seed=0)
        stance = report["stance"].lower()
    assert "structure" in stance and "message" in stance
    assert "necessary" in stance and "sufficient" in stance


# --- input validation ------------------------------------------------------

def test_empty_samples_returns_empty_fit():
    """An empty samples array must produce predictable zero-shaped output."""
    fit = WF.fit_beam_transit(np.asarray([]))
    assert fit["n_samples"] == 0
    assert fit["recovered_gaussian"] is None
    assert fit["recovered_sinc"] is None
    assert fit["underdetermined"] is True


def test_scramble_null_empty():
    """Scramble null on empty array must not crash and return zeros."""
    sn = WF.scramble_null(np.asarray([]))
    assert sn["n_samples"] == 0
    assert sn["r2_median"] == 0.0


# --- standalone runner -----------------------------------------------------

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
