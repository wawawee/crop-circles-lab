"""test_goebekli_taurid.py — ≥10 tests for Hecklefish #5.

Run:
    python tools/astro/tests/test_goebekli_taurid.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from tools.astro.goebekli_taurid import (
    CANONICAL_AZIMUTHS, EPOCH_YEAR, FORBIDDEN_PHRASES,
    HIT_THRESHOLD_DEG, MONTE_CARLO_TRIALS, OUT, STANCE,
    TAURID_DEC_DEG, TAURID_RA_H, VERDICT_VOCAB,
    _angular_delta_deg, _circular_std, _mean_angle,
    _rayleigh_z, classify_verdict, compute_taurid_azimuth,
    load_pillar_azimuths, precess_taurid, run_probe,
    run_random_azimuth_null, run_scrambled_date_null,
    score_alignments,
)


# =========================================================================
# 1. Stance / vocabulary
# =========================================================================

def test_stance_present() -> None:
    assert len(STANCE) > 30
    assert "null" in STANCE.lower()
    assert "apophenia" in STANCE.lower()


def test_verdict_vocab() -> None:
    for v in ("ORIENTATION_STRUCTURE", "NO_SIGNAL", "UNDERDETERMINED"):
        assert v in VERDICT_VOCAB


def test_forbidden_phrases_guard() -> None:
    expected = [
        "comet cult proven",
        "comet cult confirmed",
        "aliens built",
        "extraterrestrial construction",
        "ancient astronaut",
        "annunaki",
    ]
    for needle in expected:
        assert needle in FORBIDDEN_PHRASES, f"missing forbidden: {needle}"


def test_forbidden_not_in_output() -> None:
    path = OUT / "run.json"
    if not path.exists():
        return
    report = json.loads(path.read_text())
    text = json.dumps({k: v for k, v in report.items()
                       if k not in ("stance", "forbidden_words_check")}).lower()
    for fp in FORBIDDEN_PHRASES:
        assert fp.lower() not in text, f"output contains forbidden: {fp}"


def test_forbidden_not_in_notes() -> None:
    path = OUT / "NOTES.md"
    if not path.exists():
        return
    with open(path) as f:
        text = f.read()
    sections = text.split("## ")
    relevant = [s for s in sections if not s.startswith("Stance")]
    combined = " ".join(relevant).lower()
    for fp in FORBIDDEN_PHRASES:
        assert fp.lower() not in combined, f"NOTES.md contains forbidden: {fp}"


# =========================================================================
# 2. Angular helpers
# =========================================================================

def test_angular_delta_identical() -> None:
    assert _angular_delta_deg(121.17, 121.17) == 0.0


def test_angular_delta_opposite() -> None:
    assert _angular_delta_deg(0.0, 180.0) == 180.0


def test_angular_delta_wrap() -> None:
    assert _angular_delta_deg(355.0, 5.0) == 10.0


def test_angular_delta_180_symmetry() -> None:
    """θ and θ+180 give same min delta."""
    d0 = min(_angular_delta_deg(325, 121.17), _angular_delta_deg(325, 301.17))
    d180 = min(_angular_delta_deg(145, 121.17), _angular_delta_deg(145, 301.17))
    assert abs(d0 - d180) < 1e-10


def test_mean_angle_simple() -> None:
    m = _mean_angle([0, 90])
    assert abs(m - 45) < 1.0


def test_mean_angle_circular() -> None:
    m = _mean_angle([350, 10])
    assert abs(m - 0) < 1.0 or abs(m - 360) < 1.0


def test_circular_std_uniform() -> None:
    s = _circular_std([0, 90, 180, 270])
    assert s > 1.0  # large spread


def test_rayleigh_z_uniform() -> None:
    z, p = _rayleigh_z([0, 90, 180, 270])
    assert z < 0.2  # near uniform


def test_rayleigh_z_aligned() -> None:
    z, p = _rayleigh_z([45, 46, 44, 47])
    assert z > 2.0  # non-uniform


# =========================================================================
# 3. Pillar data
# =========================================================================

def test_canonical_azimuths_count() -> None:
    assert len(CANONICAL_AZIMUTHS) == 14


def test_canonical_azimuths_p43() -> None:
    assert CANONICAL_AZIMUTHS["P43"] == 325


def test_load_pillar_azimuths() -> None:
    az = load_pillar_azimuths()
    assert len(az) >= 14
    assert az["P43"] == 325


# =========================================================================
# 4. Precession
# =========================================================================

def test_precess_taurid_returns_triplet() -> None:
    ra, dec, backend = precess_taurid(-9600)
    assert isinstance(ra, float)
    assert isinstance(dec, float)
    assert backend in ("skyfield", "analytic")
    assert 0 <= ra < 24
    assert -90 <= dec <= 90


def test_precess_taurid_modern() -> None:
    """At J2000, precess should return approx J2000 coords."""
    ra, dec, backend = precess_taurid(2000)
    assert abs(ra - TAURID_RA_H) < 1.0  # allowance for proper motion / epoch difference
    assert abs(dec - TAURID_DEC_DEG) < 5.0


# =========================================================================
# 5. Taurid azimuth
# =========================================================================

def test_compute_taurid_azimuth_structure() -> None:
    result = compute_taurid_azimuth(3.5, 15.0, 37.2231, 38.9223, -9600)
    assert "rise_azimuth_deg" in result
    assert "culmination_azimuth_deg" in result
    assert "rise_possible" in result


def test_compute_taurid_azimuth_circumpolar_high_dec() -> None:
    """A high declination at -9600 BCE latitude should be circumpolar."""
    result = compute_taurid_azimuth(5.0, 85.0, 37.2231, 38.9223, -9600)
    assert result["rise_possible"] is False
    assert result["rise_azimuth_deg"] is None


# =========================================================================
# 6. Alignment scoring
# =========================================================================

def test_score_alignments_no_target() -> None:
    sc = score_alignments({"P43": 325, "P18": 215}, None)
    assert sc["n_hits"] == 0
    assert sc["mean_delta_deg"] is None


def test_score_alignments_exact_hit() -> None:
    sc = score_alignments({"P43": 121.17}, 121.17, threshold_deg=10)
    assert sc["n_hits"] == 1
    assert sc["min_delta_deg"] == 0.0


def test_score_alignments_180_symmetry() -> None:
    """A pillar facing 325 should also align with target 121.17 via 180° flip (121.17+180=301.17)."""
    sc = score_alignments({"P43": 325}, 121.17, threshold_deg=30)
    assert sc["n_hits"] == 1
    assert sc["min_delta_deg"] <= 30


def test_score_alignments_all_miss() -> None:
    pillar_az = {"P43": 0, "P18": 90, "P27": 180}
    sc = score_alignments(pillar_az, 45, threshold_deg=5)
    assert sc["n_hits"] == 0


# =========================================================================
# 7. Negative controls
# =========================================================================

def test_random_azimuth_null_structure() -> None:
    pillar_az = {"a": 0, "b": 90, "c": 180, "d": 270}
    null = run_random_azimuth_null(pillar_az, 45, n_trials=500, seed=42)
    assert null["n_trials"] == 500
    assert null["observed_hits"] is not None
    assert null["null_mean_hits"] >= 0
    assert null["null_sd_hits"] >= 0


def test_random_azimuth_null_no_target() -> None:
    pillar_az = {"a": 0, "b": 90}
    null = run_random_azimuth_null(pillar_az, None, n_trials=100, seed=42)
    assert null["observed_hits"] == 0
    assert null["null_mean_hits"] >= 0


def test_scrambled_date_null_structure() -> None:
    pillar_az = {"a": 0, "b": 90, "c": 180, "d": 270}
    null = run_scrambled_date_null(
        pillar_az, 3.5, 15.0, 37.2231, 38.9223, -9600,
        n_trials=200, seed=42,
    )
    assert null["n_trials"] == 200
    assert null["observed_hits"] is not None
    assert null["epoch_range"] == "[-11000, -7000]"


# =========================================================================
# 8. Verdict classification
# =========================================================================

def test_classify_no_signal() -> None:
    rand_null = {"p_empirical": 0.5, "z": 0.5}
    scram_null = {"p_empirical": 0.3, "z": 1.0}
    v, _ = classify_verdict(rand_null, scram_null, 14)
    assert v == "NO_SIGNAL"


def test_classify_underdetermined_small_n() -> None:
    rand_null = {"p_empirical": 0.5, "z": 0.5}
    scram_null = {"p_empirical": 0.3, "z": 1.0}
    v, _ = classify_verdict(rand_null, scram_null, 4)
    assert v == "UNDERDETERMINED"


def test_classify_structurally_requires_both_controls() -> None:
    rand_null = {"p_empirical": 0.005, "z": 3.0}
    scram_null = {"p_empirical": 0.5, "z": 0.5}
    v, _ = classify_verdict(rand_null, scram_null, 14)
    assert v == "NO_SIGNAL"  # scrambled didn't beat


# =========================================================================
# 9. run_probe integration
# =========================================================================

def test_run_probe_structure() -> None:
    report = run_probe(seed=42, n_trials=100)
    assert report["verdict"] in VERDICT_VOCAB
    assert report["site"]["epoch_year"] == -9600
    assert report["pillars"]["n_loaded"] >= 14
    assert report["forbidden_words_check"]["all_absent"] is True
    assert "taurid_radiant" in report
    assert "negative_controls" in report
    assert "random_azimuth_null" in report["negative_controls"]
    assert "scrambled_date_null" in report["negative_controls"]


# =========================================================================
# 10. Output files exist
# =========================================================================

def test_outputs_run_json_exists() -> None:
    path = OUT / "run.json"
    assert path.exists(), "outputs/goebekli/run.json missing — run probe first"


def test_outputs_run_json_verdict_valid() -> None:
    path = OUT / "run.json"
    assert path.exists()
    report = json.loads(path.read_text())
    assert report["verdict"] in VERDICT_VOCAB
    assert report["forbidden_words_check"]["all_absent"] is True


def test_outputs_notes_md_contains_verdict() -> None:
    path = OUT / "NOTES.md"
    assert path.exists()
    with open(path) as f:
        text = f.read()
    has_verdict = any(v in text for v in VERDICT_VOCAB)
    assert has_verdict, "NOTES.md missing verdict"
    assert "Hecklefish" in text
    assert "Taurid" in text


# =========================================================================
# 11. Known-answer test: injection of artificial alignment
# =========================================================================

def test_known_answer_injected_alignment() -> None:
    """If we set a pillar to exactly match the target, hits should be ≥1."""
    ra_epoch, dec_epoch, _ = precess_taurid(EPOCH_YEAR)
    taz = compute_taurid_azimuth(ra_epoch, dec_epoch, 37.2231, 38.9223, EPOCH_YEAR)
    target = taz.get("rise_azimuth_deg")
    if target is None:
        return  # skip if circumpolar
    planted = {"injected": target}
    sc = score_alignments(planted, target, threshold_deg=10)
    assert sc["n_hits"] == 1
    assert sc["min_delta_deg"] == 0.0


# =========================================================================
# runner
# =========================================================================

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
