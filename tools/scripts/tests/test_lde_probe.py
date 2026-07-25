"""
test_lde_probe.py — G19 tests for LDE historic series probe.

Runs:
    python tools/scripts/tests/test_lde_probe.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

import tools.scripts.lde_probe as LP  # noqa: E402
from tools.scripts.lde_probe import (  # noqa: E402
    DATA_DIR, FORBIDDEN_PHRASES, OUT_DIR, STANCE,
    analyze_dataset, assert_no_forbidden_phrases,
    autocorr_delays, build_verdict, delay_histogram,
    fft_power_spectrum, histogram_to_delays,
    load_appleton_histogram, load_crawford_histogram,
    load_stormer_series, mode_clustering,
    scramble_null, uniform_null,
)


# ---------------------------------------------------------------------------
# Stance / forbidden phrases
# ---------------------------------------------------------------------------

def test_stance_present() -> None:
    assert len(STANCE) > 50
    assert "structure" in STANCE.lower()
    assert "NO_SIGNAL" in STANCE


def test_forbidden_phrases_listed() -> None:
    expected = (
        "alien relay confirmed",
        "Lunan proved",
        "Epsilon Boötis probe",
        "extraterrestrial communication",
        "alien relay",
    )
    for needle in expected:
        assert needle in FORBIDDEN_PHRASES


def test_assert_no_forbidden_phrases_clean_passes() -> None:
    LP.assert_no_forbidden_phrases(
        "LDE delay distribution analysis: no structure above null. "
        "This is a propagation physics exercise, not an ET claim.",
        where="clean text",
    )


def test_assert_no_forbidden_phrases_raises_on_banned() -> None:
    for phrase in FORBIDDEN_PHRASES:
        bad = f"the text mentions {phrase} and must be caught."
        try:
            LP.assert_no_forbidden_phrases(bad, where="bad text")
        except ValueError:
            pass
        else:
            raise AssertionError(
                f"forbidden phrase {phrase!r} did NOT trigger ValueError"
            )


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def test_load_stormer_series_has_expected_n() -> None:
    raw = load_stormer_series()
    assert len(raw["all_delays_s"]) == 58
    assert raw["mission"] == "G19"
    assert "series" in raw
    assert len(raw["series"]) == 5


def test_load_appleton_histogram_has_expected_bins() -> None:
    raw = load_appleton_histogram()
    h = raw["histogram_bins"]
    assert len(h["delay_s"]) == 14
    assert len(h["counts"]) == 14
    assert sum(h["counts"]) == 77


def test_load_crawford_histogram_has_expected_bins() -> None:
    raw = load_crawford_histogram()
    h = raw["histogram_bins"]
    assert len(h["delay_s"]) == 40
    assert sum(h["counts"]) == 50


def test_histogram_to_delays_produces_correct_n() -> None:
    raw = load_appleton_histogram()
    delays = histogram_to_delays(raw)
    assert len(delays) == 77


# ---------------------------------------------------------------------------
# Analysis functions
# ---------------------------------------------------------------------------

def test_delay_histogram_counts() -> None:
    delays = [3.0, 5.0, 5.0, 8.0, 8.0, 8.0]
    h = delay_histogram(delays, range(3, 10))
    assert h["n"] == 6
    assert h["counts"][0] == 1
    assert h["counts"][2] == 2
    assert h["counts"][5] == 3


def test_mode_clustering_top_modes() -> None:
    delays = [3.0, 5.0, 5.0, 8.0, 8.0, 8.0]
    m = mode_clustering(delays)
    assert m["top_modes"][0] == (8, 3)
    assert m["top_modes"][1] == (5, 2)
    assert m["n_unique_delays"] == 3


def test_mode_clustering_empty() -> None:
    assert mode_clustering([]) == {}


def test_autocorr_peak_reasonable() -> None:
    delays = [3.0, 5.0, 5.0, 8.0, 8.0, 8.0, 3.0, 5.0, 5.0]
    ac = autocorr_delays(delays)
    assert "peak_lag" in ac
    assert ac["n"] == 9
    assert -1.0 <= ac["peak_value"] <= 1.0


def test_autocorr_too_few() -> None:
    ac = autocorr_delays([3.0])
    assert "note" in ac


def test_fft_power_spectrum_returns_expected_keys() -> None:
    delays = [3.0, 5.0, 8.0, 12.0, 3.0, 5.0, 8.0, 12.0]
    fft = fft_power_spectrum(delays)
    assert "peak_bin" in fft
    assert fft["n"] == 8
    assert fft["peak_power"] > 0


def test_fft_power_spectrum_too_few() -> None:
    fft = fft_power_spectrum([3.0, 5.0, 8.0])
    assert "note" in fft


# ---------------------------------------------------------------------------
# Null controls
# ---------------------------------------------------------------------------

def test_scramble_null_returns_expected_keys() -> None:
    delays = [3.0, 5.0, 8.0, 12.0, 3.0, 5.0, 8.0, 12.0]
    scrm = scramble_null(delays, n_sims=100, seed=0)
    assert "z" in scrm
    assert scrm["n_sims"] == 100


def test_scramble_null_too_few() -> None:
    scrm = scramble_null([3.0, 5.0])
    assert "note" in scrm


def test_uniform_null_returns_expected_keys() -> None:
    delays = [3.0, 5.0, 8.0, 12.0, 3.0, 5.0, 8.0, 12.0]
    uni = uniform_null(delays, n_sims=100, seed=0)
    assert "z" in uni
    assert uni["n_sims"] == 100


def test_uniform_null_too_few() -> None:
    uni = uniform_null([3.0])
    assert "note" in uni


# ---------------------------------------------------------------------------
# Verdict assembly
# ---------------------------------------------------------------------------

def test_verdict_all_null_underdetermined() -> None:
    v = build_verdict(None, None, None)
    assert "UNDERDETERMINED" in v


def test_verdict_all_noise_no_signal() -> None:
    v = build_verdict(-5.0, -4.0, -6.0)
    assert "NO_SIGNAL" in v


def test_verdict_mixed_underdetermined() -> None:
    v = build_verdict(-0.5, 14.0, -1.0)
    assert "UNDERDETERMINED" in v or "STRUCTURE_SIGNAL" in v


# ---------------------------------------------------------------------------
# Known-answer: synthetic periodic delays
# ---------------------------------------------------------------------------

def test_analyze_dataset_known_periodic() -> None:
    periodic = [3.0, 6.0, 9.0, 12.0, 3.0, 6.0, 9.0, 12.0,
                3.0, 6.0, 9.0, 12.0, 3.0, 6.0, 9.0, 12.0]
    res = analyze_dataset("known_periodic", periodic, seed=0)
    scrm = res.get("scramble_null", {})
    z = scrm.get("z", 0)
    assert z > 3.0, f"known periodic should exceed 3, got z={z}"


def test_analyze_dataset_known_noise() -> None:
    import random as rnd
    rng = rnd.Random(42)
    noise = [rng.uniform(3.0, 15.0) for _ in range(50)]
    res = analyze_dataset("known_noise", noise, seed=0)
    scrm = res.get("scramble_null", {})
    z = scrm.get("z", 0)
    assert abs(z) < 3.0, f"uniform noise should have |z|<3, got z={z}"


# ---------------------------------------------------------------------------
# End-to-end outputs
# ---------------------------------------------------------------------------

def test_run_outputs_exist() -> None:
    assert (OUT_DIR / "run.json").exists()
    assert (OUT_DIR / "NOTES.md").exists()


def test_run_json_has_expected_keys() -> None:
    path = OUT_DIR / "run.json"
    rep = json.loads(path.read_text())
    for k in ("mission", "generated_at", "verdict", "metadata",
              "datasets", "caveat", "data_source", "stance",
              "forbidden_phrases", "pipeline"):
        assert k in rep, f"missing key: {k}"
    assert rep["mission"] == "G19"
    assert "STRUCTURE_SIGNAL" in rep["verdict"] or "NO_SIGNAL" in rep["verdict"]


def test_notes_md_has_stance_and_caveats() -> None:
    path = OUT_DIR / "NOTES.md"
    assert path.exists()
    text = path.read_text()
    assert "structure != meaning" in text.lower()
    assert "## Stance" in text
    assert "## Caveats" in text
    assert "## Verdict" in text


def test_forbidden_phrases_absent_from_output_text() -> None:
    path = OUT_DIR / "NOTES.md"
    text = path.read_text()
    for phrase in FORBIDDEN_PHRASES:
        if phrase in text:
            # The phrase may appear in the "Forbidden phrases" listing section
            # Check it's only there
            listing_section = text[text.find("### Forbidden phrases"):text.find("## Source")]
            if phrase not in listing_section:
                raise AssertionError(
                    f"forbidden phrase {phrase!r} found outside listing in NOTES.md"
                )


# ---------------------------------------------------------------------------
# Data file integrity
# ---------------------------------------------------------------------------

def test_data_files_exist() -> None:
    assert (DATA_DIR / "stormer_1928_series.json").exists()
    assert (DATA_DIR / "appleton_1934_histogram.json").exists()
    assert (DATA_DIR / "crawford_1967_distribution.json").exists()
    assert (DATA_DIR / "README.md").exists()


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
