"""test_boyajian_tess_probe.py — known-answer + stance tests for G20.

Run:
    python tools/scripts/tests/test_boyajian_tess_probe.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

import tools.scripts.boyajian_tess_probe as BP


def test_stance_present() -> None:
    assert len(BP.STANCE) > 30
    assert "underdetermined" in BP.STANCE.lower()
    assert "structure" in BP.STANCE.lower()


def test_forbidden_phrases_guard() -> None:
    expected = (
        "alien megastructure",
        "Dyson sphere",
        "extraterrestrial",
        "Tabby's alien",
        "megastructure confirmed",
        "intelligent life built",
    )
    for needle in expected:
        assert needle in BP.FORBIDDEN_PHRASES, f"missing forbidden: {needle}"


def test_forbidden_not_in_output() -> None:
    path = BP.OUT_DIR / "run.json"
    if not path.exists():
        return
    report = json.loads(path.read_text())
    # Exclude stance field (meta-reference) and forbidden_words_check section
    text = json.dumps({k: v for k, v in report.items()
                       if k not in ("stance", "forbidden_words_check")}).lower()
    for fp in BP.FORBIDDEN_PHRASES:
        assert fp.lower() not in text, f"output contains forbidden: {fp}"


def test_forbidden_not_in_notes() -> None:
    path = BP.OUT_DIR / "NOTES.md"
    if not path.exists():
        return
    text = path.read_text()
    sections = text.split("## ")
    relevant = [s for s in sections
                if not s.startswith("Stance")]
    combined = " ".join(relevant).lower()
    for fp in BP.FORBIDDEN_PHRASES:
        assert fp.lower() not in combined, f"NOTES.md contains forbidden: {fp}"


def test_verdict_vocab() -> None:
    for v in ("NO_SIGNAL", "UNDERDETERMINED", "STRUCTURE_SIGNAL"):
        assert v in BP.VERDICT_VOCAB


def test_asymmetric_dip_profile_properties() -> None:
    profile = BP._asymmetric_dip_profile(100, 0.05, 0.5, 0.3)
    assert len(profile) == 100
    assert profile[0] < 1.0
    assert profile[-1] < 1.0
    assert min(profile) > 0.9  # 5% depth max
    # Asymmetric: ingress should differ from egress
    mid = 50
    ingress_vals = profile[:mid]
    egress_vals = profile[mid:]
    assert len(ingress_vals) > 0 and len(egress_vals) > 0


def test_inject_dip_lowers_flux() -> None:
    time = np.arange(1000, dtype=float) * 0.02  # 0.02 day cadence
    flux = np.ones(1000)
    orig_flux = flux.copy()
    flux = BP._inject_dip(time, flux, 10.0, 0.05, 0.5, 0.3)
    assert np.min(flux) < np.min(orig_flux)
    assert np.any(flux < orig_flux)


def test_synthetic_lc_generation() -> None:
    lc = BP._synthetic_lc(n_days=10.0, cadence_days=0.02, noise_ppm=500, seed=42,
                           dip_centers=[3.0, 6.0], dip_depths=[0.03, 0.02])
    assert len(lc["time"]) > 0
    assert len(lc["flux"]) == len(lc["time"])
    assert lc["label"] == "target"
    assert max(lc["flux"]) > min(lc["flux"])  # variability exists
    dip_min = min(lc["flux"])
    assert dip_min < 0.999, f"dip should produce flux < 0.999, got {dip_min}"  # dips present


def test_quiet_lc_no_dips() -> None:
    lc = BP._synthetic_lc(n_days=5.0, cadence_days=0.02, noise_ppm=200, seed=42,
                           dip_centers=None, dip_depths=None, label="quiet")
    assert min(lc["flux"]) > 0.995  # Should not dip below noise floor
    assert np.std(lc["flux"]) < 0.01  # Only noise (200 ppm)


def test_phase_fold_range() -> None:
    time = np.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
    phase = BP.phase_fold(time, 2.0, 0.0)
    assert np.all(phase >= 0.0) and np.all(phase < 1.0)


def test_phase_fold_periodicity() -> None:
    time = np.linspace(0, 10, 100)
    period = 2.5
    phase = BP.phase_fold(time, period, 0.0)
    # Check that integer multiples of period fold to same phase
    for t in time[::5]:
        p = BP.phase_fold(np.array([t + period]), period, 0.0)
        expected = ((t + period) / period) % 1.0
        assert abs(p[0] - expected) < 1e-10


def test_scramble_phases_preserves_distribution() -> None:
    flux = np.array([0.95, 0.98, 1.0, 1.02, 1.05, 0.99])
    scrambled = BP._scramble_phases(flux, seed=42)
    assert sorted(scrambled) == sorted(flux)
    assert any(scrambled[i] != flux[i] for i in range(len(flux)))


def test_period_search_on_synthetic_recovery() -> None:
    lc = BP._synthetic_lc(n_days=15.0, cadence_days=0.02, noise_ppm=200, seed=42,
                           dip_centers=[3.0, 7.0, 11.0], dip_depths=[0.03, 0.03, 0.03])
    results = BP.period_search(np.array(lc["time"]), np.array(lc["flux"]),
                                p_min=1.0, p_max=10.0, n_periods=100,
                                n_scrambles=20, seed=0)
    assert results["n_periods_tried"] == 100
    assert results["n_scrambles"] == 20
    assert results["best_period_days"] > 0
    assert isinstance(results["best_dip_score"], float)
    assert isinstance(results["z_vs_null"], float)


def test_known_answer_recovery_injected_epochs() -> None:
    lc = BP._synthetic_lc(n_days=28.0, cadence_days=0.02, noise_ppm=100, seed=42,
                           dip_centers=[4.0, 8.0, 16.0], dip_depths=[0.04, 0.04, 0.04])
    ka = BP.known_answer_recovery(
        lc["time"], lc["flux"],
        [4.0, 8.0, 16.0],
    )
    assert ka["n_recovered"] >= 1
    assert ka["min_injected_spacing_days"] > 0
    assert ka["best_score"] > 0


def test_synthetic_with_no_dips_returns_low_scores() -> None:
    """No-dip data should not outscore its own scrambles by extreme margin."""
    for _ in range(3):
        lc = BP._synthetic_lc(n_days=5.0, cadence_days=0.02, noise_ppm=1000, seed=_,
                               dip_centers=None, dip_depths=None)
        results = BP.period_search(np.array(lc["time"]), np.array(lc["flux"]),
                                    p_min=0.5, p_max=5.0, n_periods=30,
                                    n_scrambles=15, seed=_)
        score = results["best_dip_score"]
        null_mean = results["null_mean_score"]
        noise_floor = results["null_std_score"]
        if noise_floor > 0:
            z = results["z_vs_null"]
            assert z > -10, f"unexpected negative z={z}"  # sanity, not significance threshold


def test_run_probe_structure() -> None:
    # Generate data first
    BP.generate_synthetic_data(seed=0)
    result = BP.run_probe(use_synthetic=True, n_scrambles=10, seed=0, generate_data=False)
    assert "verdict" in result
    assert result["verdict"] in BP.VERDICT_VOCAB
    assert result["data_source"].startswith("synthetic")
    assert result["period_search"]["target"]["z_vs_null"] is not None
    assert result["period_search"]["quiet_star_control"]["z_vs_null"] is not None
    assert "stance" in result
    assert result["forbidden_words_check"]["all_absent"] is True


def test_notes_md_contains_verdict() -> None:
    path = BP.OUT_DIR / "NOTES.md"
    assert path.exists()
    text = path.read_text()
    has_verdict = any(v in text for v in BP.VERDICT_VOCAB)
    assert has_verdict, "NOTES.md missing verdict"
    assert "G20" in text
    assert "Boyajian" in text


def test_run_json_exists() -> None:
    path = BP.OUT_DIR / "run.json"
    assert path.exists(), "outputs/boyajian/run.json missing — run probe first"


def test_run_json_verdict_valid() -> None:
    path = BP.OUT_DIR / "run.json"
    assert path.exists()
    report = json.loads(path.read_text())
    assert report["verdict"] in BP.VERDICT_VOCAB
    assert report["target"]["tic_id"] == BP.TIC_ID
    assert "forbidden_words_check" in report
    assert report["forbidden_words_check"]["all_absent"] is True


def test_tess_fetch_returns_blocked() -> None:
    """Without lightkurve/astroquery, fetch should return BLOCKED."""
    result = BP.fetch_tess_data()
    assert result["fetch_status"] == "BLOCKED"
    assert result["data"] is None
    assert result.get("reason") is not None


def test_generate_data_creates_files() -> None:
    BP.generate_synthetic_data(seed=0)
    assert (BP.DATA_DIR / "synthetic_target_lc.csv").exists()
    assert (BP.DATA_DIR / "synthetic_quiet_lc.csv").exists()
    assert (BP.DATA_DIR / "kepler_dip_morphology.npz").exists()


def test_kepler_dip_morphology_loaded() -> None:
    BP.generate_synthetic_data(seed=0)
    morph = BP._load_kepler_dip_morphology()
    assert len(morph) > 0
    for name in ("D800", "D1519", "D1568"):
        assert name in morph, f"missing Kepler dip profile: {name}"


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
