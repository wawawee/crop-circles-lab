#!/usr/bin/env python3
"""
Offline tests for lidar_negative_probe.

Run:  python3 tools/geo/tests/test_lidar_negative_probe.py
No network, no scipy. Synthetic tiles only.
"""
import os
import sys
import tempfile

import numpy as np

from tools.geo import lidar_negative_probe as p


def test_csr_density_matches_target():
    rng = np.random.default_rng(0)
    tile = p.make_tile("csr", shape=(128, 128), density=0.08, rng=rng)
    assert tile.shape == (128, 128)
    assert 0.05 < tile.mean() < 0.11


def test_forest_texture_is_smoothed():
    """Forest tiles should have more neighbour agreement than CSR."""
    rng = np.random.default_rng(1)
    forest = p.make_tile("forest", shape=(64, 64), density=0.08, rng=rng)
    csr = p.make_tile("csr", shape=(64, 64), density=0.08, rng=rng)
    def agree(m):
        h = (m[:, 1:] == m[:, :-1]).sum()
        v = (m[1:, :] == m[:-1, :]).sum()
        n = m.shape[0] * (m.shape[1] - 1) + (m.shape[0] - 1) * m.shape[1]
        return (h + v) / n
    assert agree(forest) > agree(csr)


def test_scramble_preserves_density():
    rng = np.random.default_rng(2)
    planted = p.make_tile("planted", shape=(64, 64), density=0.08, rng=rng)
    scramble = p.make_tile("scramble", shape=(64, 64), density=0.08, rng=rng, reference=planted)
    assert abs(scramble.mean() - planted.mean()) < 1e-9


def test_planted_score_exceeds_csr():
    rng = np.random.default_rng(3)
    planted = p.make_tile("planted", shape=(64, 64), density=0.08, rng=rng)
    csr = p.make_tile("csr", shape=(64, 64), density=0.08, rng=rng)
    assert p.geoglyph_score(planted) > p.geoglyph_score(csr)


def test_stripes_score_high():
    stripes = p.make_tile("stripes", shape=(64, 64), density=0.08)
    csr = p.make_tile("csr", shape=(64, 64), density=0.08)
    assert p.geoglyph_score(stripes) > p.geoglyph_score(csr)


def test_geoglyph_score_is_non_negative():
    rng = np.random.default_rng(4)
    for kind in ["csr", "forest", "planted", "scramble"]:
        tile = p.make_tile(kind, shape=(32, 32), density=0.08, rng=rng)
        assert p.geoglyph_score(tile) >= 0.0


def test_calibration_returns_allowed_verdict():
    res = p.run_calibration(n_tiles=10, shape=(32, 32), density=0.08, seed=5)
    assert res["verdict"] in {"NO_SIGNAL", "FPR_CALIBRATED", "UNDERDETERMINED"}
    assert res["real_data_verdict"] == "UNDERDETERMINED"


def test_calibration_separates_planted_from_nulls():
    # Use 128x128 tiles to match the calibrated default and keep the
    # tail of the forest texture distribution below the threshold.
    res = p.run_calibration(n_tiles=20, shape=(128, 128), density=0.08, seed=6)
    assert res["power_planted"] >= 0.8, f"power={res['power_planted']}"
    assert res["fpr"]["csr"] <= 0.10, f"csr_fpr={res['fpr']['csr']}"
    assert res["fpr"]["scramble"] <= 0.10, f"scramble_fpr={res['fpr']['scramble']}"
    assert res["fpr"]["forest"] <= 0.10, f"forest_fpr={res['fpr']['forest']}"


def test_calibration_produces_score_stats():
    res = p.run_calibration(n_tiles=10, shape=(32, 32), density=0.08, seed=7)
    for kind in ["csr", "forest", "scramble", "planted"]:
        assert "mean" in res["scores"][kind]
        assert "std" in res["scores"][kind]


def test_main_cli_writes_expected_files():
    """Exercise the real CLI main() in a temporary directory."""
    import json
    with tempfile.TemporaryDirectory() as tmp:
        out_dir = os.path.join(tmp, "out")
        data_dir = os.path.join(tmp, "data")
        old_argv = sys.argv
        try:
            sys.argv = [
                "lidar_negative_probe.py",
                "--out-dir", out_dir,
                "--data-dir", data_dir,
                "--n-tiles", "5",
                "--shape", "32", "32",
            ]
            p.main()
        finally:
            sys.argv = old_argv
        run_path = os.path.join(out_dir, "run.json")
        notes_path = os.path.join(out_dir, "NOTES.md")
        tiles_path = os.path.join(data_dir, "tiles.json")
        assert os.path.exists(run_path)
        assert os.path.exists(notes_path)
        assert os.path.exists(tiles_path)
        with open(run_path) as fh:
            loaded = json.load(fh)
        assert "verdict" in loaded
        assert "fpr" in loaded
        assert "power_planted" in loaded


def test_forbidden_phrases_absent_in_notes():
    res = p.run_calibration(n_tiles=5, shape=(32, 32), density=0.08, seed=9)
    with tempfile.TemporaryDirectory() as tmp:
        notes_path = os.path.join(tmp, "NOTES.md")
        p.write_notes(res, notes_path)
        with open(notes_path) as fh:
            text = fh.read().lower()
    for phrase in p.FORBIDDEN_PHRASES:
        assert phrase.lower() not in text, f"forbidden phrase: {phrase}"


def test_sample_tiles_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        paths = p.write_sample_tiles(tmp, n_per_kind=2, shape=(32, 32), density=0.08, seed=10)
        assert len(paths) == 1
        import json
        with open(paths[0]) as fh:
            archive = json.load(fh)
        assert len(archive) == 8  # 4 kinds * 2
        for rec in archive:
            loaded = p._tile_from_json(rec)
            assert loaded.shape == tuple(rec["shape"])


def test_small_tile_returns_zero_score():
    tile = np.zeros((5, 5), dtype=bool)
    assert p.geoglyph_score(tile) == 0.0


if __name__ == "__main__":
    fails = 0
    tests = [
        test_csr_density_matches_target,
        test_forest_texture_is_smoothed,
        test_scramble_preserves_density,
        test_planted_score_exceeds_csr,
        test_stripes_score_high,
        test_geoglyph_score_is_non_negative,
        test_calibration_returns_allowed_verdict,
        test_calibration_separates_planted_from_nulls,
        test_calibration_produces_score_stats,
        test_main_cli_writes_expected_files,
        test_forbidden_phrases_absent_in_notes,
        test_sample_tiles_roundtrip,
        test_small_tile_returns_zero_score,
    ]
    for fn in tests:
        try:
            fn()
            print("PASS", fn.__name__)
        except AssertionError as e:
            fails += 1
            print("FAIL", fn.__name__, "->", str(e)[:400])
    print("\n" + ("ALL TESTS PASS" if fails == 0 else f"{fails} TEST(S) FAILED"))
    sys.exit(1 if fails else 0)
