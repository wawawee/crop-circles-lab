#!/usr/bin/env python3
"""
Offline tests for nazca_line_detect.

Run:  python3 tools/geo/tests/test_nazca_line_detect.py
No network. Synthetic tiles only.
"""
import json
import os
import sys
import tempfile

import numpy as np

from tools.geo import nazca_line_detect as p


# ---------------------------------------------------------------------------
# tile generation
# ---------------------------------------------------------------------------


def test_planted_tile_has_high_contrast():
    """Planted tiles should have long lines (mean brightness varies)."""
    rng = np.random.default_rng(0)
    tile = p.make_tile("planted", size=128, line_density=0.04, rng=rng)
    assert tile.shape == (128, 128), f"shape={tile.shape}"
    assert tile.dtype == np.uint8
    assert tile.min() < 180 and tile.max() > 60  # wide dynamic range


def test_csr_density_matches_target():
    rng = np.random.default_rng(1)
    tile = p.make_tile("csr", size=128, line_density=0.04, rng=rng)
    assert tile.shape == (128, 128)
    actual = (tile > 0).mean()
    assert 0.02 < actual < 0.07, f"actual density={actual}"


def test_desert_noise_below_planted():
    """Desert noise tiles should score lower than planted tiles."""
    rng = np.random.default_rng(2)
    desert = p.make_tile("desert_noise", size=128, line_density=0.04, rng=rng)
    planted = p.make_tile("planted", size=128, line_density=0.04, rng=rng)
    assert p.line_score(desert) < p.line_score(planted), "desert >= planted"


def test_ridge_clutter_masks_some_area():
    rng = np.random.default_rng(3)
    tile = p.make_tile("ridge_clutter", size=128, line_density=0.04, rng=rng)
    assert tile.shape == (128, 128)
    assert tile.dtype == np.uint8


def test_scramble_preserves_density():
    rng = np.random.default_rng(4)
    planted = p.make_tile("planted", size=64, line_density=0.04, rng=rng)
    scramble = p.make_tile("scramble", size=64, line_density=0.04, rng=rng, reference=planted)
    assert abs(float(scramble.mean()) - float(planted.mean())) < 0.5


def test_scramble_lower_score_than_planted():
    rng = np.random.default_rng(5)
    planted = p.make_tile("planted", size=128, line_density=0.04, rng=rng)
    planted_score = p.line_score(planted)
    scramble = p.make_tile("scramble", size=128, line_density=0.04,
                           rng=rng, reference=planted)
    scramble_score = p.line_score(scramble)
    assert planted_score > 0, f"planted_score={planted_score}"
    assert planted_score > scramble_score, (
        f"planted={planted_score} <= scramble={scramble_score}"
    )


# ---------------------------------------------------------------------------
# line detection
# ---------------------------------------------------------------------------


def test_line_score_nonzero_on_planted():
    rng = np.random.default_rng(6)
    tile = p.make_tile("planted", size=128, line_density=0.04, rng=rng)
    score = p.line_score(tile)
    assert score > 0, f"planted line_score={score}"


def test_line_score_zero_on_uniform():
    tile = np.full((64, 64), 128, dtype=np.uint8)
    assert p.line_score(tile) == 0.0


def test_line_score_non_negative():
    rng = np.random.default_rng(7)
    for kind in ["planted", "csr", "ridge_clutter", "desert_noise"]:
        tile = p.make_tile(kind, size=64, line_density=0.04, rng=rng)
        score = p.line_score(tile)
        assert score >= 0.0, f"{kind} score={score}"


# ---------------------------------------------------------------------------
# calibration
# ---------------------------------------------------------------------------


def test_calibration_returns_allowed_verdict():
    res = p.run_calibration(n_tiles=8, size=64, line_density=0.04, seed=8)
    allowed = {"FPR_CALIBRATED", "NO_SIGNAL", "UNDERDETERMINED"}
    assert res["verdict"] in allowed, f"verdict={res['verdict']}"
    assert res["real_data_verdict"] == "FIXTURE_ONLY"


def test_calibration_scores_have_stats():
    res = p.run_calibration(n_tiles=8, size=64, line_density=0.04, seed=9)
    for kind in ["planted", "csr", "ridge_clutter", "desert_noise", "scramble"]:
        assert "mean" in res["scores"][kind], f"missing mean for {kind}"
        assert "std" in res["scores"][kind], f"missing std for {kind}"
        assert "values" in res["scores"][kind], f"missing values for {kind}"
        assert len(res["scores"][kind]["values"]) == 8


def test_calibration_underdetermined_for_small_tiles():
    """Very small tiles produce ambiguous calibration."""
    res = p.run_calibration(n_tiles=5, size=32, line_density=0.04, seed=10)
    assert res["verdict"] in {"NO_SIGNAL", "UNDERDETERMINED"}, f"verdict={res['verdict']}"


# ---------------------------------------------------------------------------
# CLI / IO
# ---------------------------------------------------------------------------


def test_main_cli_writes_expected_files():
    with tempfile.TemporaryDirectory() as tmp:
        out_dir = os.path.join(tmp, "out")
        data_dir = os.path.join(tmp, "data")
        old_argv = sys.argv
        try:
            sys.argv = [
                "nazca_line_detect.py",
                "--out-dir", out_dir,
                "--data-dir", data_dir,
                "--n-tiles", "5",
                "--size", "64",
            ]
            p.main()
        finally:
            sys.argv = old_argv
        run_path = os.path.join(out_dir, "run.json")
        notes_path = os.path.join(out_dir, "NOTES.md")
        tiles_path = os.path.join(data_dir, "tiles.json")
        assert os.path.exists(run_path), f"missing {run_path}"
        assert os.path.exists(notes_path), f"missing {notes_path}"
        assert os.path.exists(tiles_path), f"missing {tiles_path}"
        with open(run_path) as fh:
            loaded = json.load(fh)
        assert "verdict" in loaded
        assert "fpr" in loaded
        assert "power_planted" in loaded


def test_sample_tiles_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        paths = p.write_sample_tiles(tmp, n_per_kind=2, size=32,
                                     line_density=0.04, bg_noise=0.02, seed=11)
        assert len(paths) == 1
        with open(paths[0]) as fh:
            archive = json.load(fh)
        assert len(archive) == 10  # 5 kinds * 2
        for rec in archive:
            assert "kind" in rec
            assert "tile_b64" in rec


# ---------------------------------------------------------------------------
# forbidden phrases
# ---------------------------------------------------------------------------


def test_forbidden_phrases_absent_in_notes():
    res = p.run_calibration(n_tiles=5, size=64, line_density=0.04, seed=12)
    with tempfile.TemporaryDirectory() as tmp:
        notes_path = os.path.join(tmp, "NOTES.md")
        p.write_notes(res, notes_path)
        with open(notes_path) as fh:
            text = fh.read().lower()
    for phrase in p.FORBIDDEN_PHRASES:
        assert phrase.lower() not in text, f"forbidden phrase: {phrase}"


# ---------------------------------------------------------------------------
# run all
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    fails = 0
    tests = [
        test_planted_tile_has_high_contrast,
        test_csr_density_matches_target,
        test_desert_noise_below_planted,
        test_ridge_clutter_masks_some_area,
        test_scramble_preserves_density,
        test_scramble_lower_score_than_planted,
        test_line_score_nonzero_on_planted,
        test_line_score_zero_on_uniform,
        test_line_score_non_negative,
        test_calibration_returns_allowed_verdict,
        test_calibration_scores_have_stats,
        test_calibration_underdetermined_for_small_tiles,
        test_main_cli_writes_expected_files,
        test_sample_tiles_roundtrip,
        test_forbidden_phrases_absent_in_notes,
    ]
    print(f"Running {len(tests)} tests...\n")
    for fn in tests:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except AssertionError as e:
            fails += 1
            print(f"  FAIL  {fn.__name__}: {str(e)[:200]}")
        except Exception as e:
            fails += 1
            print(f"  FAIL  {fn.__name__}: {type(e).__name__}: {str(e)[:200]}")
    print(f"\n{'ALL TESTS PASS' if fails == 0 else f'{fails} TEST(S) FAILED'}")
    sys.exit(1 if fails else 0)
