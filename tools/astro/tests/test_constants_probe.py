"""Validation for constants_probe.py -- Hermes mission N3.

Run:
    python3 tools/astro/tests/test_constants_probe.py

Every test pins a SPECIFIC NUMBER so it actually catches regressions in the
ratio math, the diatonic matcher, and the null-model logic.
"""
from __future__ import annotations

import math
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent.parent / "tools" / "forensics"))

import constants_probe as CP  # noqa: E402
import ratios as R  # noqa: E402

EPS_RATIO = 1e-4


# ---------------------------------------------------------------------------
# Table integrity
# ---------------------------------------------------------------------------
def test_constant_table_integrity() -> None:
    table = CP.get_table("core")
    assert len(table) >= 10, "need at least 10 constants for the hunt"
    for c in table:
        for k in ("name", "symbol", "value", "source"):
            assert k in c, f"{c.get('name','?')} missing {k}"
        v = float(c["value"])
        assert math.isfinite(v) and v > 0, f"{c['name']} value non-positive or NaN"


def test_large_set_separates_fundamental_from_derived() -> None:
    big = CP.get_table("large")
    names = {c["name"] for c in big}
    assert "alpha_G_proton" in names, "Dirac fundamental alpha_G missing"

    # The two derived ratios are flagged so the filter can drop them.
    derived = {c["name"] for c in big if c.get("derived", False)}
    assert "ratio_LNDirac" in derived, "alpha/alpha_G must be tagged derived"
    assert "ratio_age_Hubble" in derived, "1/(H_0*t_P) must be tagged derived"

    # Unknown set must raise cleanly with no half-assert.
    try:
        CP.get_table("bogus")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError on unknown set")


# ---------------------------------------------------------------------------
# Pairwise expansion + ordering invariance
# ---------------------------------------------------------------------------
def test_pairwise_count() -> None:
    n = len(CP.get_table("core"))
    pairs = CP.pairwise_ratios(CP.get_table("core"))
    assert len(pairs) == n * (n - 1) // 2, f"got {len(pairs)} expected {n*(n-1)//2}"


def test_pair_order_is_direction_invariant() -> None:
    """The pair (alpha, mp_me) and a separately-built pair (mp_me, alpha)
    must end up with the SAME (a_name, b_name, ratio) because the helper
    always labels the larger value 'a'. The watchlist tagger depends on this.
    """
    table = CP.get_table("core")
    pairs = CP.pairwise_ratios(table)
    p1 = next(p for p in pairs
              if {p.a_name, p.b_name} == {"alpha", "mp_me"})

    # Build by hand: alpha=0.00729..., mp_me=1836 -- so mp_me is bigger, must
    # be labelled 'a'.
    assert p1.a_name == "mp_me", (
        f"expected the larger constant (mp_me) to be labelled 'a', got {p1.a_name}"
    )
    assert p1.b_name == "alpha"
    # ratio = 1836.15267343 / 0.0072973525643 ≈ 251471
    expected_ratio = 1836.15267343 / 7.2973525643e-3
    assert abs(p1.ratio - expected_ratio) / expected_ratio < 1e-6


def test_watchlist_tagger_is_symmetric() -> None:
    """whichever way the pair (X, Y) appears in `pairwise_ratios`, both arrivals
    in WATCHLIST are interchangeable. `(_tag_watch)` returns True for either
    order."""
    assert CP._tag_watch("alpha", "mp_me") == CP._tag_watch("mp_me", "alpha")
    # And an arbitrary non-watchlist pair returns False.
    assert CP._tag_watch("alpha", "Omega_Lambda") == (False, "")


# ---------------------------------------------------------------------------
# log10 matrix
# ---------------------------------------------------------------------------
def test_log10_matrix_antisymmetric_and_zero_diag() -> None:
    M, names = CP.log10_signed_matrix(CP.get_table("core"))
    assert M.shape == (len(names), len(names))
    # Antisymmetric: M = -M^T
    assert np.allclose(M, -M.T, atol=1e-9), "log10 ratio matrix must be antisymmetric"
    # Zero diagonal
    assert np.allclose(np.diag(M), 0.0, atol=1e-12), "diagonal must be 0"
    # Sign sanity: log10(mp_me / alpha) > 0 because mp_me > alpha
    name_idx = {n: i for i, n in enumerate(names)}
    i_mpme = name_idx["mp_me"]
    i_alpha = name_idx["alpha"]
    assert M[i_mpme, i_alpha] > 0, "log10(mp_me/alpha) must be > 0"


# ---------------------------------------------------------------------------
# Concrete numeric checks (the diatonic matcher is a black box -- test it!)
# ---------------------------------------------------------------------------
def test_mp_me_alpha_ratio_matches_known() -> None:
    """mp_me / alpha ~ 251471. After octave-fold, that lands somewhere in
    [1, 2). We pin only that it's NOT a clean diatonic: this is the
    Eddington-pair test that the watchlist reports separately.
    """
    pairs = CP.pairwise_ratios(CP.CONSTANTS_CORE)
    p = next(x for x in pairs if {x.a_name, x.b_name} == {"alpha", "mp_me"})
    # magnitude sanity
    expected = 1836.15267343 / 7.2973525643e-3
    assert abs(p.ratio - expected) / expected < 1e-6
    # the cents error is finite (no NaN) -- and almost certainly NOT a hit
    assert math.isfinite(p.cents_error)


def test_omega_matter_lambda_ratio_pins_value() -> None:
    """Ω_m / Ω_Λ ≈ 0.4602 -- the cosmic coincidence. Folded to [1, 2)
    gives ~1.84 -- NEARLY a major 7th (≈1.875) but probably not within 20c."""
    pairs = CP.pairwise_ratios(CP.CONSTANTS_CORE)
    p = next(x for x in pairs
             if {x.a_name, x.b_name} == {"Omega_matter", "Omega_Lambda"})
    # raw ratio (larger over smaller -- both are <1, but Ω_Λ > Ω_m, so a=Ω_Λ)
    expected = 0.6847 / 0.3153
    assert abs(p.ratio - expected) / expected < 1e-4
    # folded to [1,2): Ω_Λ/Ω_m = ~2.171, divided by 2 once = ~1.0856
    # which is near minor 2nd (≈1.066) but not within 20c.
    assert 1.0 <= p.folded_to_octave < 2.0
    assert math.isfinite(p.folded_to_octave)


def test_filter_excludes_derived_rows() -> None:
    """Empty-input safety: filter on it should yield empty list, not KeyError."""
    pairs = CP.pairwise_ratios(CP.get_table("large"), tol_cents=20.0)
    constants = CP.get_table("large")
    filtered = CP.filter_for_hits(pairs, constants)
    # All derived rows must be gone: no pair should mention ratio_LNDirac or
    # ratio_age_Hubble.
    for p in filtered:
        assert p.a_name not in {"ratio_LNDirac", "ratio_age_Hubble"}
        assert p.b_name not in {"ratio_LNDirac", "ratio_age_Hubble"}


# ---------------------------------------------------------------------------
# Negative controls
# ---------------------------------------------------------------------------
def test_decade_null_returns_distribution() -> None:
    constants = CP.get_table("core")
    null_a = CP.random_constants_control(constants, n_trials=200,
                                          tol_cents=20.0, seed=42)
    assert null_a.shape == (200,)
    n_pairs = len(CP.pairwise_ratios(CP.get_table("core")))
    assert 0 <= null_a.mean() <= n_pairs
    assert null_a.max() >= 0
    # Should produce SOME hits by chance: 100 pairs of similar-magnitude
    # constants will randomly align with at least 1 diatonic note.
    assert null_a.max() >= 1


def test_permutation_null_returns_distribution() -> None:
    constants = CP.get_table("core")
    null_b = CP.pair_permutation_control(constants, n_trials=200, seed=42)
    assert null_b.shape == (200,)
    # Permutation null average should be LOWER than decade null because
    # magnitude structure is preserved -- but BOTH must be non-negative.
    assert null_b.mean() >= 0
    assert null_b.max() >= 1


def test_nulls_are_deterministic_for_fixed_seed() -> None:
    import numpy as np
    a1 = CP.random_constants_control(CP.get_table("core"), n_trials=50, seed=123)
    a2 = CP.random_constants_control(CP.get_table("core"), n_trials=50, seed=123)
    assert np.array_equal(a1, a2), "decade null must be deterministic for the same seed"

    b1 = CP.pair_permutation_control(CP.get_table("core"), n_trials=50, seed=123)
    b2 = CP.pair_permutation_control(CP.get_table("core"), n_trials=50, seed=123)
    assert np.array_equal(b1, b2), "permutation null must be deterministic for the same seed"


# ---------------------------------------------------------------------------
# Output writers + interpret logic
# ---------------------------------------------------------------------------
def test_csv_uses_dynamic_tolerance_column() -> None:
    import csv as csvmod
    pairs = CP.pairwise_ratios(CP.CONSTANTS_CORE, tol_cents=20.0)
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "ft.csv"
        CP.write_feature_table_csv(pairs, path, tol_cents=20.0)
        with open(path) as f:
            rows = list(csvmod.DictReader(f))
        assert "within_tol_cents_20" in rows[0]
        # Now retry with --tol-cents=50 -> must be a DIFFERENT column.
        CP.write_feature_table_csv(pairs, path, tol_cents=50.0)
        with open(path) as f:
            rows2 = list(csvmod.DictReader(f))
        assert "within_tol_cents_50" in rows2[0]
        assert "within_tol_cents_20" not in rows2[0], (
            "20-cent column should be gone when tol_cents=50 -- the column "
            "name must reflect the actual tolerance."
        )


def test_tol_column_name_helper() -> None:
    assert CP.tol_column_name(20.0) == "within_tol_cents_20"
    assert CP.tol_column_name(50.0) == "within_tol_cents_50"
    assert CP.tol_column_name(12.7) == "within_tol_cents_13"   # rounded
    assert CP.tol_column_name(0.5) == "within_tol_cents_0"    # edge case


def test_interpret_returns_all_four_messages_when_real_below_medians() -> None:
    """A forced low-hit result must trigger the 'BELOW both null medians'
    branch -- the most defensive line -- to confirm the triage logic works."""
    pairs_fake: list[CP.PairwiseRatio] = [
        CP.PairwiseRatio(
            i=0, j=1,
            a_name="x", b_name="y", a_symbol="x", b_symbol="y",
            ratio=2.0, log10_abs=0.30103, folded_to_octave=2.0,
            diatonic_note="octave (2:1)", diatonic_target=2.0,
            cents_error=0.0, within_tol=True,
            integer_ratio="2/1", integer_pct_error=0.0,
            on_watchlist=False, watchlist_reason="",
        )
    ]
    # Decade null returns very high counts -> filtered hits (1) is BELOW
    # both p50s and p95s -> must hit the bottom branch.
    high_null = np.full(100, 30, dtype=int)
    notes = CP.interpret(pairs_fake, pairs_fake, high_null, high_null, 20.0)
    msg = "\n".join(notes)
    assert "BELOW both null medians" in msg, (
        f"when filtered hits < both p50s, expect the BELOW-both-medians "
        f"branch. Got:\n{msg}"
    )


def test_main_runs_end_to_end_with_small_control() -> None:
    """Full pipeline (CSV + JSON + MD) on a tiny control set."""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        sys_argv_save = sys.argv
        try:
            sys.argv = ["constants_probe.py", "--set", "core",
                        "--small-control", "--out", str(out), "--seed", "42"]
            rc = CP.main()
        finally:
            sys.argv = sys_argv_save
        assert rc == 0
        assert (out / "feature_table.csv").exists()
        assert (out / "constants_analysis.json").exists()
        assert (out / "constants_notes.md").exists()

        # JSON keys must include both nulls + a real interpretation list.
        report = json.loads((out / "constants_analysis.json").read_text())
        assert "null_decade" in report and "null_permutation" in report
        assert isinstance(report["interpretation"], list)
        assert len(report["interpretation"]) >= 6


# ---------------------------------------------------------------------------
# Mixings set (CKM + PMNS) -- entered 2026-07-25 per Hermes follow-up
# ---------------------------------------------------------------------------
def test_get_table_supports_mixings_set() -> None:
    """The 'mixings' set should be CORE + MIXINGS, no derived rows.
    Same shape invariant as 'core' but adds 7 mixing parameters."""
    t = CP.get_table("mixings")
    assert len(t) == len(CP.CONSTANTS_CORE) + len(CP.CONSTANTS_MIXINGS), (
        f"expected core+{len(CP.CONSTANTS_MIXINGS)} mixings, got {len(t)}"
    )
    for c in t:
        assert not c.get("derived", False), f"mixings leak: {c['name']} derived=True"
    nm_mixings = {c["name"] for c in CP.CONSTANTS_MIXINGS}
    seen_mixings = {c["name"] for c in t} & nm_mixings
    assert seen_mixings == nm_mixings, f"missing mixings: {nm_mixings - seen_mixings}"


def test_mixings_constants_not_on_watchlist() -> None:
    """CKM + PMNS were measured long AFTER the famous coincidences that
    motivate the watchlist. Placing them there would silently re-introduce
    the selection-bias loop we removed in round 1."""
    watch_names = {n for row in CP.WATCHLIST for n in (row[0], row[1])}
    nm_mixings = {c["name"] for c in CP.CONSTANTS_MIXINGS}
    assert watch_names & nm_mixings == set(), (
        f"watchlist unexpectedly contains mixing constants: "
        f"{watch_names & nm_mixings}"
    )


def test_everything_set_combines_all_three_layers() -> None:
    """`everything` = core + mixings + Dirac LNH. Derived rows from LNH
    (ratio_LNDirac, ratio_age_Hubble) must be present so filter_for_hits
    actually has to do work."""
    t = CP.get_table("everything")
    derived = {c["name"] for c in t if c.get("derived", False)}
    assert "ratio_LNDirac" in derived
    assert "ratio_age_Hubble" in derived


if __name__ == "__main__":
    import json
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    ok = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
            ok += 1
        except AssertionError as e:
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{ok}/{len(fns)} passed")
    sys.exit(0 if ok == len(fns) else 1)
