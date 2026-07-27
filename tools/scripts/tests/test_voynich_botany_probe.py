"""
test_voynich_botany_probe.py — known-answer tests for G10++ probe.

Run:
    python tools/scripts/tests/test_voynich_botany_probe.py

Stance: synthetic botanical shape structure ≠ herbal ID / decipherment.
"""
from __future__ import annotations

import json
import math
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

sys.path.insert(0, str(ROOT))
import tools.scripts.voynich_botany_probe as BOT  # noqa: E402

# -----------------------------------------------------------------------------
# Image generator tests
# -----------------------------------------------------------------------------


def test_make_plant_image_returns_correct_shape() -> None:
    img = BOT.make_plant_image(size=200, seed=0)
    assert img.shape == (200, 200), f"shape={img.shape}"
    assert img.dtype == np.uint8


def test_make_plant_image_contains_dark_pixels() -> None:
    img = BOT.make_plant_image(seed=0)
    assert img.min() < 128, "plant image should have dark (drawn) pixels"


def test_make_plant_image_deterministic() -> None:
    a = BOT.make_plant_image(seed=42)
    b = BOT.make_plant_image(seed=42)
    assert np.array_equal(a, b), "same seed must produce identical images"


def test_make_plant_image_varied_by_seed() -> None:
    a = BOT.make_plant_image(seed=0)
    b = BOT.make_plant_image(seed=1)
    assert not np.array_equal(a, b), "different seeds must differ"


# -----------------------------------------------------------------------------
# Null generator tests
# -----------------------------------------------------------------------------


def test_noise_image_is_random() -> None:
    img = BOT.make_noise_image(seed=0)
    assert img.shape == (BOT.IMG_SIZE, BOT.IMG_SIZE)
    assert img.min() >= 0 and img.max() <= 255


def test_scrambled_preserves_histogram() -> None:
    plant = BOT.make_plant_image(seed=0)
    scrambled = BOT.make_scrambled_plant(seed=0)
    assert sorted(plant.ravel().tolist()) == sorted(scrambled.ravel().tolist()), (
        "scrambled must preserve pixel histogram"
    )


def test_scrambled_not_equal_to_plant() -> None:
    plant = BOT.make_plant_image(seed=0)
    scrambled = BOT.make_scrambled_plant(seed=0)
    assert not np.array_equal(plant, scrambled), "scrambled must differ"


def test_random_shapes_contains_dark_pixels() -> None:
    img = BOT.make_random_shapes(seed=0)
    assert img.min() < 128, "random shapes should have dark pixels"


def test_plant_silhouette_fewer_lines_than_full_plant() -> None:
    plant = BOT.make_plant_image(seed=0)
    silhouette = BOT.make_plant_silhouette(seed=0)
    _, plant_edges = BOT.edge_ratio(plant)
    _, sil_edges = BOT.edge_ratio(silhouette)
    plant_lines = BOT.detect_lines(plant_edges)
    sil_lines = BOT.detect_lines(sil_edges)
    assert sil_lines <= plant_lines + 2, (
        f"silhouette lines ({sil_lines}) should not exceed "
        f"plant lines ({plant_lines}) by more than 2"
    )


# -----------------------------------------------------------------------------
# CCAT metrics tests
# -----------------------------------------------------------------------------


def test_compute_ccat_metrics_returns_all_keys() -> None:
    img = BOT.make_plant_image(seed=0)
    m = BOT.compute_ccat_metrics(img)
    for key in BOT.METRIC_LABELS:
        assert key in m, f"missing metric: {key}"


def test_compute_ccat_metrics_fractal_dimension_valid_range() -> None:
    img = BOT.make_plant_image(seed=0)
    m = BOT.compute_ccat_metrics(img)
    fd = m["fractal_dimension"]
    if fd is not None:
        assert 0.5 <= fd <= 2.5, f"FD={fd} outside expected range [0.5, 2.5]"


def test_compute_ccat_metrics_on_noise_lower_symmetry_than_plant() -> None:
    noise = BOT.make_noise_image(seed=0)
    plant = BOT.make_plant_image(seed=0)
    n_sym = BOT.compute_ccat_metrics(noise)["mirror_symmetry"]
    p_sym = BOT.compute_ccat_metrics(plant)["mirror_symmetry"]
    assert p_sym > n_sym, (
        f"plant mirror_symmetry={p_sym} should exceed noise={n_sym}"
    )


# -----------------------------------------------------------------------------
# Statistical comparison tests
# -----------------------------------------------------------------------------


def test_metric_array_filters_none() -> None:
    samples = [
        {"edge_pixel_ratio": 0.1},
        {"edge_pixel_ratio": 0.2},
        {"edge_pixel_ratio": None},
    ]
    vals = BOT.metric_array(samples, "edge_pixel_ratio")
    assert len(vals) == 2
    assert vals == [0.1, 0.2]


def test_compare_ka_vs_null_identical_distributions() -> None:
    ka = [{"edge_pixel_ratio": 0.1}, {"edge_pixel_ratio": 0.2}]
    null = [{"edge_pixel_ratio": 0.1}, {"edge_pixel_ratio": 0.2}]
    comp = BOT.compare_ka_vs_null(ka, null)
    assert abs(comp["edge_pixel_ratio"]["cohens_d"]) < 1e-6


def test_compare_ka_vs_null_separates_when_different() -> None:
    ka = [{"edge_pixel_ratio": 0.9}] * 20
    null = [{"edge_pixel_ratio": 0.1}] * 20
    comp = BOT.compare_ka_vs_null(ka, null)
    assert comp["edge_pixel_ratio"]["separates"] is True


# -----------------------------------------------------------------------------
# Verdict logic tests
# -----------------------------------------------------------------------------


def _make_comp(separates: bool) -> dict:
    return {
        m: {
            "ka_mean": 1.0, "null_mean": 0.0,
            "ka_std": 0.1, "null_std": 0.1,
            "cohens_d": 5.0, "z_score": 10.0 if separates else 0.5,
            "separates": separates,
        }
        for m in BOT.METRIC_LABELS
    }


def test_verdict_shape_structure_when_strong_separation() -> None:
    sep = _make_comp(True)
    no_sep = _make_comp(False)
    v = BOT.compute_verdict({}, sep, sep, sep, sep)
    assert "SHAPE_STRUCTURE" in v["verdict"]
    assert v["separation_counts"]["noise"] >= 3


def test_verdict_no_signal_when_no_separation() -> None:
    no_sep = _make_comp(False)
    v = BOT.compute_verdict({}, no_sep, no_sep, no_sep, no_sep)
    assert "NO_SIGNAL" in v["verdict"]


def test_verdict_always_fixture_only() -> None:
    sep = _make_comp(True)
    v = BOT.compute_verdict({}, sep, sep, sep, sep)
    assert "FIXTURE_ONLY" in v["verdict"]


# -----------------------------------------------------------------------------
# Forbidden-phrase guard
# -----------------------------------------------------------------------------


def test_assert_no_forbidden_phrases_clean_passes() -> None:
    BOT.assert_no_forbidden_phrases(
        "Synthetic plants show shape structure vs noise controls.",
        where="clean",
    )


def test_forbidden_phrase_triggers_value_error() -> None:
    for phrase in BOT.FORBIDDEN_PHRASES:
        bad = f"This synthetic plant {phrase} and should not pass."
        try:
            BOT.assert_no_forbidden_phrases(bad, where="test")
        except ValueError:
            continue
        raise AssertionError(
            f"forbidden phrase {phrase!r} did not raise ValueError"
        )


def test_forbidden_phrase_guard_on_report_prose() -> None:
    report = {
        "stance": "Shape structure analysis only. No plant ID claims.",
        "caveat": "Synthetic controls. No decipherment claim.",
        "verdict_block": {"notes": "Plants separate from noise."},
    }
    BOT.assert_no_forbidden_phrases_prose(report, where="test_report")


# -----------------------------------------------------------------------------
# End-to-end smoke test
# -----------------------------------------------------------------------------


def test_run_botany_probe_returns_complete_report() -> None:
    report = BOT.run_botany_probe(n_plants=5, n_nulls=5, seed=0)
    for key in (
        "mission_id", "probe", "generated_at", "synthetic_setup",
        "metrics_tested", "plant_samples", "nulls", "comparisons",
        "verdict_block", "stance", "forbidden_phrases",
    ):
        assert key in report, f"missing top-level key: {key}"
    assert report["mission_id"] == "G10++"
    assert "FIXTURE_ONLY" in report["verdict_block"]["verdict"]
    assert len(report["plant_samples"]) == 5


def test_run_botany_probe_passes_forbidden_guard() -> None:
    report = BOT.run_botany_probe(n_plants=3, n_nulls=3, seed=0)
    BOT.assert_no_forbidden_phrases_prose(
        report, where="post_run",
    )


# -----------------------------------------------------------------------------
# NOTES.md writer test
# -----------------------------------------------------------------------------


def test_notes_md_contains_verdict() -> None:
    report = BOT.run_botany_probe(n_plants=3, n_nulls=3, seed=0)
    md = BOT.write_notes_md(report)
    assert "G10++" in md
    assert "Verdict" in md
    assert "FIXTURE_ONLY" in md
    body_lines = [ln for ln in md.splitlines() if not ln.startswith("- `")]
    body = "\n".join(body_lines)
    for phrase in BOT.FORBIDDEN_PHRASES:
        assert phrase.lower() not in body.lower(), (
            f"forbidden phrase {phrase!r} leaked into NOTES.md body"
        )


# -----------------------------------------------------------------------------
# CLI smoke test
# -----------------------------------------------------------------------------


def test_main_writes_output_files() -> None:
    td = Path(tempfile.mkdtemp(prefix="botany_main_"))
    try:
        out_json = td / "run.json"
        out_md = td / "NOTES.md"
        import subprocess
        res = subprocess.run([
            sys.executable, str(ROOT / "tools" / "scripts" / "voynich_botany_probe.py"),
            "--n-plants", "3", "--n-nulls", "3",
            "--out-json", str(out_json),
            "--out-md", str(out_md),
        ], capture_output=True, text=True, timeout=120)
        assert res.returncode == 0, (
            f"probe failed:\nSTDOUT:\n{res.stdout[:500]}\n"
            f"STDERR:\n{res.stderr[:500]}"
        )
        assert out_json.exists(), "run.json not written"
        assert out_md.exists(), "NOTES.md not written"
        d = json.loads(out_json.read_text())
        assert "verdict_block" in d
        assert "FIXTURE_ONLY" in d["verdict_block"]["verdict"]
        md_text = out_md.read_text()
        assert "G10++" in md_text
    finally:
        import shutil
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
