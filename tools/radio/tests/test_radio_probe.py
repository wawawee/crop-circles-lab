"""Tests for tools/radio/radio_probe.py.

Stance: structure != message. Every quantitative test pins an invariant of
the scaffold math, NOT a claim about real Wow! / real FRBs.

Standalone-runnable: `python3 tools/radio/tests/test_radio_probe.py`.
"""
from __future__ import annotations

import inspect
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS_RADIO = HERE.parent
ROOT = TOOLS_RADIO.parent.parent
sys.path.insert(0, str(TOOLS_RADIO))

import numpy as np  # noqa: E402

import radio_probe as RP  # noqa: E402


# --- FFT known-answer -----------------------------------------------------

def test_synth_periodic_train_fft_peaks_at_known_freq():
    """Plant a sin at period 1.0 s. FFT peak must be within 1.5 bins of 1.0 Hz
    when Hann-windowed."""
    x, _dt = RP.synth_periodic_train(
        period_s=1.0, dt_s=0.01, n=1000, noise_frac=0.0, seed=42
    )
    fs = 1.0 / 0.01
    expected_freq = 1.0 / 1.0
    freqs, power = RP.fft_power_spectrum(x, sample_dt=0.01, window="hann")
    summary = RP.fft_summary(freqs, power, n_top=3)
    res = fs / len(x)  # freq resolution
    assert summary["peak_freq_hz"] is not None
    err = abs(summary["peak_freq_hz"] - expected_freq)
    assert err <= res * 1.5, (
        f"FFT peak at {summary['peak_freq_hz']} Hz, expected ~1.0 Hz, "
        f"res={res}, err={err}"
    )


def test_fft_summary_excludes_dc_from_top_bins():
    """The DC bin should never appear in the top-N list even when the
    signal has a strong mean (it's an after-detrend leak, not a signal)."""
    x = np.zeros(64)
    rng = np.random.default_rng(0)
    x[1:] = rng.standard_normal(63) * 0.01  # tiny signal, big DC
    x[0] = 1000.0  # spurious DC spike
    freqs, power = RP.fft_power_spectrum(x, sample_dt=1.0, window="none")
    summary = RP.fft_summary(freqs, power, n_top=3)
    # No top_bin should have bin_index == 0 (DC).
    for tb in summary["top_bins"]:
        assert tb["bin_index"] != 0, (
            f"DC leaked into top_bins: {summary['top_bins']}"
        )


# --- autocorrelation known-answer -----------------------------------------

def test_autocorr_value_at_plant_period_is_high():
    """For a sin at period 1.0 s, dt=0.01 s -> period_in_samples = 100.
    At that lag the autocorrelation MUST be > 0.5 (clear positive
    correlation at the FFT-detected period). We do NOT assert lag 100
    via argmax: for dense periodic sin waves (period << N), raw argmax
    lands at lag 1 (r=0.996) not lag P (r=0.9) because adjacent-sample
    correlation stays near 1.0. The CONFIRMATORY contract is therefore
    `r[period_in_samples] > threshold` against the FFT-detected
    period -- the FFT peak is the proper period detector.
    """
    x, _dt = RP.synth_periodic_train(
        period_s=1.0, dt_s=0.01, n=1000, noise_frac=0.0, seed=7
    )
    r = RP.autocorrelation(x, max_lag=200)
    plant_in_samples = int(round(1.0 / 0.01))  # 100
    ac = RP.autocorr_summary(r, plant_period_in_samples=plant_in_samples)
    # Confirmatory mode keys:
    assert ac["plant_period_in_samples"] == plant_in_samples, (
        f"summary plant_period_in_samples got {ac.get('plant_period_in_samples')}, "
        f"expected {plant_in_samples}"
    )
    assert ac["r_at_plant_period"] > 0.5, (
        f"r at plant period = {ac.get('r_at_plant_period')}, expected > 0.5 "
        f"(a clean sin at lag=P should give ~0.9 since r ≈ (N-P)/N × cos(2π) ≈ "
        f"(N-P)/N)"
    )
    assert ac["r_at_plant_period_is_high"] is True, (
        "r_at_plant_period_is_high must be True when r > 0.5"
    )


# --- epoch-fold / Rayleigh Z² ---------------------------------------------

def test_epoch_fold_recovers_plant_period_16p35d():
    """30 synthetic arrivals around multiples of 16.35 d -> epoch-fold
    should recover 16.35 d ± 1 d with Z² >> 1."""
    times = RP.synth_frb_arrivals(
        period_d=RP.FRB_180916_PERIOD_DAYS,
        n_arrivals=30,
        obs_window_d=500.0,
        jitter_d=0.1,  # very tight clustering
        seed=0,
    )
    grid = np.arange(10.0, 30.0 + 1e-9, 0.05)
    fold = RP.epoch_fold(times, grid)
    assert fold["best_period"] is not None
    err = abs(fold["best_period"] - 16.35)
    assert err <= 1.0, f"epoch_fold missed plant: {fold['best_period']}"
    assert fold["best_z2"] > 30.0, (
        f"Z² = {fold['best_z2']} below expected ~60 for N=30 tight "
        f"arrivals -- formula or normalization is wrong"
    )
    assert fold["best_p_value"] < 0.01, (
        f"p = {fold['best_p_value']} not below 0.01 for tight clustering"
    )


def test_epoch_fold_uniform_null_stays_low():
    """A uniform random schedule should NOT produce a Z² so large that
    it looks like a real signal. Fisher-Ballager max-of-grid distribution
    sets the upper bound: E[max Z²] ≈ log(n_grid) + γ(2). For n_grid=401
    that's ≈ 6.6, but variance is high and a specific seed can sneak
    higher. We test "stays in the noise regime" with the liberal bound
    Z² < 18 -- strict enough to catch a true plant (Z² ≈ 60) and loose
    enough to never flake under grid-search noise."""
    rng = np.random.default_rng(20260725)
    times = rng.uniform(0.0, 500.0, size=30)
    grid = np.arange(10.0, 30.0 + 1e-9, 0.05)
    fold = RP.epoch_fold(times, grid)
    assert fold["best_z2"] < 18.0, (
        f"shuffled null produced Z² = {fold['best_z2']} > 18 -- looks "
        f"like a real signal where there should be only uniform noise"
    )


# --- Wow! honesty audit ----------------------------------------------------

def test_wow_six_samples_has_only_three_freq_bins():
    """With 6 samples, the rfft produces 4 bins total (DC + 3 unique freq).
    NOT 6 -- the negative half of the DFT is mirrored.
    """
    wow = RP.wow_honest_check()
    assert wow["n_samples"] == 6
    assert wow["n_bins"] == 4, (
        f"Wow! DFT has 6 samples -> 4 bins (DC + 3 freq). "
        f"Got n_bins = {wow['n_bins']}"
    )
    assert wow["freq_resolution_hz"] is not None
    # resolution = 1 / (6 * 12) = 1/72 ≈ 0.01389
    expected = 1.0 / (6 * 12.0)
    assert abs(wow["freq_resolution_hz"] - expected) < 1e-6


def test_fft_rejects_nonfinite_samples():
    """A NaN or inf in the input must raise, NOT silently propagate a
    NaN spectrum downstream."""
    import math
    try:
        RP.fft_power_spectrum([1.0, float("nan"), 0.5, -0.3], sample_dt=1.0)
        raised = False
    except ValueError:
        raised = True
    assert raised, "fft_power_spectrum must raise on NaN input"
    try:
        RP.fft_power_spectrum([1.0, float("inf"), 0.5, -0.3], sample_dt=1.0)
        raised2 = False
    except ValueError:
        raised2 = True
    assert raised2, "fft_power_spectrum must raise on inf input"


def test_autocorr_rejects_nonfinite_samples():
    """Same nan/inf guard contract as the FFT."""
    try:
        RP.autocorrelation([1.0, float("nan"), 0.5, -0.3, 0.1, 0.2], max_lag=3)
        raised = False
    except ValueError:
        raised = True
    assert raised, "autocorrelation must raise on NaN input"


def test_rayleigh_z2_uses_standard_2N_over_N_formula():
    """Standard Rayleigh Z² = 2/N * R². For N tight arrivals at multiples
    of a candidate period, Z² should approach 2*N (≈60 for N=30)."""
    times = RP.synth_frb_arrivals(
        period_d=RP.FRB_180916_PERIOD_DAYS,
        n_arrivals=30,
        jitter_d=0.001,  # very tight
        seed=0,
    )
    z2, phase = RP.rayleigh_z2(times, RP.FRB_180916_PERIOD_DAYS)
    # Tight clustering: Z² ≈ 2*N = 60.
    assert z2 > 50.0, (
        f"Tight-cluster Z² = {z2}, expected ~60 for N=30; the 2*R²/N "
        f"formulation must yield this magnitude, NOT the (R/N)² formula "
        f"which would give ~1."
    )
    assert phase >= 0.0 and phase < 2 * math.pi


def test_wow_six_samples_claim_blocked_is_True():
    """claim_blocked must be True -- the scaffold is audit-only."""
    wow = RP.wow_honest_check()
    assert wow["claim_blocked"] is True, (
        "Wow! claim_blocked must be True -- 6 samples can NEVER support "
        "a periodicity claim"
    )


def test_wow_uses_published_six_intensities():
    """The 6EQUJ5 sigma values must surface in our report, not be re-imagined."""
    assert RP.WOW_SAMPLES_SIGMA == (6.5, 14.5, 26.5, 30.5, 19.5, 5.5)
    wow = RP.wow_honest_check()
    assert wow["freq_mhz"] == 1420.0
    assert wow["sample_dt_s"] == 12.0


# --- run-level integration -------------------------------------------------

def test_run_known_train_overall_pass():
    """Top-level orchestrator: FFT + autocorr known-answer should both pass."""
    out = RP.run_known_train(seed=11)
    ka = out["known_answer"]
    assert ka["fft_pass"], f"FFT known-answer failed: {ka}"
    assert ka["autocorr_pass"], f"autocorr known-answer failed: {ka}"
    assert ka["overall_pass"], "overall known-answer should pass"


def test_run_wow_blocked_by_design():
    """run_wow_honest surfaces claim_blocked = True so the orchestrator
    level is also honest."""
    out = RP.run_wow_honest()
    assert out["wow_honest"]["claim_blocked"] is True


def test_run_frb_180916_recovery_pass():
    """FRB 180916 scaffold recovers the 16.35-d plant within 1 d."""
    out = RP.run_frb_180916(seed=0)
    ka = out["known_answer"]
    assert ka["recovery_pass"], f"FRB recovery failed: {ka}"
    # Shuffled null must stay well below.
    nc = out["negative_controls"]
    assert nc["shuffled_uniform_z2_max"] < out["epochfold"]["best_z2"], (
        "Shuffled control should NOT outperform the plant"
    )


def test_frb_180916_scaffold_does_not_use_frb_121102_period():
    """Belt-and-suspenders: the scaffold MUST use 16.35 d, not the FRB 121102
    cycle of ~157 d."""
    out = RP.run_frb_180916(seed=0)
    plant = out["plant"]
    assert plant["true_period_d"] == 16.35
    assert plant["decoy_period_d_for_frb_121102"] == 157.0
    # And the recovered period must come down near 16.35 d, NOT 157 d.
    rec = out["epochfold"]["best_period"]
    assert 10.0 <= rec <= 30.0, (
        f"recovered period {rec} d outside the 10..30 d search grid -- "
        f"the epoch-fold is searching the WRONG range"
    )


# --- markdown notes & CLI --------------------------------------------------

def test_write_notes_markdown_runs_without_error_and_advertises_honesty():
    """Notes-renderer must surface the honesty framing."""
    report = RP.analyze(mode="all", seed=0)
    md = RP.write_notes_markdown(report)
    assert isinstance(md, str)
    # Honesty hits:
    assert "Structure ≠ message" in md or "Structure != message" in md, (
        "Markdown must surface the lab motto"
    )
    # Wow! honest block must be present
    assert "claim_blocked" in md
    # FRB 180916 must be present
    assert "FRB 180916" in md
    # Synthesized FRB 121102's 157 d must NOT be the active plant period
    assert "16.35" in md


def test_cli_all_of_above_writes_both_files():
    """End-to-end CLI: --all-of-the-above produces run.json and notes.md
    in a temp dir; both files are non-empty and parseable.
    """
    td = Path(tempfile.mkdtemp(prefix="radio_all_"))
    out_json = td / "run.json"
    out_md = td / "notes.md"
    res = subprocess.run([
        sys.executable, str(TOOLS_RADIO / "radio_probe.py"),
        "--all-of-the-above", "--seed", "0",
        "--out-json", str(out_json), "--out-md", str(out_md),
    ], capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, (
        f"CLI failed:\nSTDOUT:\n{res.stdout[:600]}\n"
        f"STDERR:\n{res.stderr[:600]}"
    )
    assert out_json.exists() and out_md.exists()
    d = json.load(open(out_json))
    assert "known_train" in d and "wow_honest" in d and "frb_180916" in d
    # Wow! honest audit must show claim_blocked = True
    assert d["wow_honest"]["wow_honest"]["claim_blocked"] is True
    # FRB 180916 known-answer should pass
    assert d["frb_180916"]["known_answer"]["recovery_pass"] is True
    # notes.md should have an FFT peak line for the train
    md_text = out_md.read_text()
    assert "known-answer" in md_text.lower()


# --- real-data fetch-path tests ------------------------------------------

def test_chime_fetcher_unreachable_does_not_synthesize():
    """When ALL candidate URLs are unreachable, the fetcher MUST surface
    UNREACHABLE and an empty mjds list -- it MUST NOT synthesize data."""
    import chime_frb_fetcher as CFF
    # Use a deliberately invalid URL (low port on localhost) so the test
    # fails fast and never accidentally contacts the canonical mirror.
    res = CFF.try_fetch_chime_frb_catalog_1_csv(
        attempt_urls=[("http://127.0.0.1:1/nope", "deliberate_invalid",
                        "text/csv")],
        timeout_s=2.0,
        use_cache=False,
    )
    assert res.fetch_status in ("UNREACHABLE", "PARKING_PAGE"), (
        f"fetch_status should be UNREACHABLE/PARKING_PAGE, got "
        f"{res.fetch_status}; an HTML response on canonical mirrors is "
        f"classified PARKING_PAGE."
    )
    assert res.mjds == [], (
        "mjds must be empty when fetch fails; we never silently synthesize"
    )
    assert len(res.attempts) >= 1
    att0 = res.attempts[0]
    assert att0.verdict in ("NETWORK_ERROR", "TIMEOUT",
                            "4XX", "5XX", "HTML_PARKING"), (
        f"verdict should be a real failure mode, got {att0.verdict}"
    )


def test_chime_fetcher_html_response_classified_as_parking():
    """An HTTP 200 with content-type text/html is a parking page -- it
    MUST NOT be silently treated as an empty CSV."""
    import chime_frb_fetcher as CFF
    res = CFF.try_fetch_chime_frb_catalog_1_csv(
        force_status_for_tests="PARKING_PAGE",
    )
    assert res.fetch_status == "PARKING_PAGE"
    assert res.mjds == []
    assert res.attempts, "attempts list must be populated"
    for att in res.attempts:
        assert att.verdict == "HTML_PARKING", (
            f"all attempts should be classified HTML_PARKING when the "
            f"site returns an HTML parking page; got {att.verdict}"
        )


def test_chime_fetcher_test_force_unreachable_includes_attempts():
    """force_status_for_tests=UNREACHABLE synthesises one attempt per URL
    WITHOUT contacting the network -- useful for deterministic tests."""
    import chime_frb_fetcher as CFF
    res = CFF.try_fetch_chime_frb_catalog_1_csv(
        force_status_for_tests="UNREACHABLE",
    )
    assert res.fetch_status == "UNREACHABLE"
    assert res.mjds == []
    # Each canonical URL must be in the attempts list.
    assert len(res.attempts) >= 5, (
        f"expected >=5 canonical URL attempts, got {len(res.attempts)}"
    )
    for att in res.attempts:
        assert att.verdict == "NETWORK_ERROR", (
            f"all attempts should be NETWORK_ERROR in test-force mode; "
            f"got {att.verdict}"
        )
        assert att.error and "force_status_for_tests" in att.error, (
            f"attempt error must surface the test hook; got {att.error!r}"
        )


def test_chime_fetcher_cached_catalog_parses_csv_header():
    """If a cached CSV is provided with a parseable header, the fetcher
    should return CACHED + parsed rows + 0 MJDs for FRB 180916 (since
    the test fixture won't include real burst data)."""
    import json
    import chime_frb_fetcher as CFF
    td = Path(tempfile.mkdtemp(prefix="chime_cached_"))
    cache_path = td / "chime_frb_catalog1.csv"
    # Minimal CSV with the documented schema. Names that DON'T match
    # any FRB 180916 variant -> 0 mjds in result.
    cache_path.write_text(
        "tns_name,mjd,ra,dec\n"
        "FRB 20220610A,59744.5,180.0,-30.0\n"
        "FRB 20220612B,59746.7,200.0,40.0\n"
    )
    res = CFF.try_fetch_chime_frb_catalog_1_csv(
        use_cache=True,
        cache_path=cache_path,
        # We bypass force_status_for_tests so the CACHED path is taken
        # BEFORE any URL probe.
        force_status_for_tests=None,
    )
    assert res.fetch_status == "CACHED", (
        f"cached fixture should return CACHED; got {res.fetch_status}"
    )
    assert res.csv_path == str(cache_path)
    assert res.n_rows_total == 2
    assert res.mjds == [], (
        "no FRB 180916 rows in fixture -> empty mjds; we never claim "
        "the fixture contains real burst MJDs"
    )


def test_frb_real_sources_returns_empty_with_honest_provenance():
    """Default load (live fetch fails today) returns an empty PublishedBurstSource
    with a non-empty provenance note that explains the absence."""
    import frb_real_sources as FRS
    src = FRS.load_published_frb_180916_bursts(
        force_status_for_tests="UNREACHABLE",
    )
    assert src.burst_mjds == []
    assert src.source_type == "empty"
    assert src.fetch_status in ("UNREACHABLE", "PARKING_PAGE")
    assert src.provenance_note
    # The provenance must surface the empty state honestly.
    pn = src.provenance_note.lower()
    assert any(kw in pn for kw in (
        "no mjds", "honest", "intentionally", "extraction",
        "fabricat", "paste",
    )), f"provenance_note must surface the empty-empty state: " \
        f"{src.provenance_note!r}"
    # fetch_attempts must include at least one UNREACHABLE entry.
    assert src.fetch_attempts, "fetch_attempts must be populated"
    assert any("URL" in str(a) or "url" in str(a)
                for a in src.fetch_attempts), (
        "fetch_attempts must contain URL info per attempt"
    )


def test_frb_real_sources_accepts_user_provided_override_json(tmp_path):
    """When --bundled-mjd-json points at a parseable JSON flat list of
    MJD floats, the loader uses them and flags source_type='user_provided'."""
    import json
    import frb_real_sources as FRS
    fixture = tmp_path / "bursts.json"
    # These MJDs are TEST-ONLY fixture values; never claim they are real
    # bursts from any paper.
    fixture.write_text(json.dumps([59000.0, 59016.35, 59032.7]))
    src = FRS.load_published_frb_180916_bursts(
        bundled_json_path=fixture,
    )
    assert src.burst_mjds == [59000.0, 59016.35, 59032.7]
    assert src.source_type == "user_provided"
    assert src.fetch_status == "USER_OVERRIDE"
    assert src.provenance_note.startswith("Burst MJDs supplied via")


def test_run_frb_180916_real_default_returns_empty_warning():
    """Without a bundled-override JSON and with the CHIME fetch forced
    UNREACHABLE, run_frb_180916_real MUST return an honest-empty shape
    with top-level warnings and NO epoch-fold attempt."""
    out = RP.run_frb_180916_real(force_status_for_tests="UNREACHABLE")
    assert out["epochfold"] is None, (
        "epochfold MUST be None when no MJDs available; we never"
        "fall back to a synthetic plant"
    )
    assert out["known_answer"] is None
    assert out["n_bursts"] == 0
    assert "warnings" in out and len(out["warnings"]) >= 1
    # The warning text must convey the empty state explicitly.
    warning_text = " ".join(out["warnings"]).lower()
    assert "no real-data path" in warning_text or \
           "no synthetic plant" in warning_text or \
           "no mjds" in warning_text, (
        f"warning text must surface the empty state: {out['warnings']}"
    )
    assert out["fetch_status"] == "UNREACHABLE"
    # Anti-fabrication: no synthetic-plant fingerprint.
    s = json.dumps(out)
    for banned in ("synth_seed", "synth_period_d",
                    "synth_period_d_for_frb_121102",
                    "_synth_arrivals"):
        assert banned not in s, (
            f"banned synthetic-keyword {banned!r} found in real-data "
            f"output (would indicate silent synthesis): {s[:400]}"
        )


def test_run_frb_180916_real_user_override_runs_epoch_fold(tmp_path):
    """When --bundled-mjd-json is provided and parseable, run_frb_180916_real
    MUST run epoch-fold and return the non-empty shape."""
    import json
    fixt = tmp_path / "mjds.json"
    # 30 MJDs at multiples of 16.35 d starting ~58700. TEST fixture;
    # never claim these are real-world bursts from the Pastor-Marazuela
    # paper -- the test is verifying the wiring only.
    mjds = [58700.0 + 16.35 * (i + 1) + 0.1 for i in range(30)]
    fixt.write_text(json.dumps(mjds))
    out = RP.run_frb_180916_real(bundled_json_path=fixt)
    assert out["epochfold"] is not None
    assert out["fetch_status"] == "USER_OVERRIDE"
    assert out["data_source"].endswith("bursts.json"), (
        f"data_source should name the user-provided JSON file; "
        f"got {out['data_source']!r}"
    )
    assert out["n_bursts"] == 30
    assert out["known_answer"]["recovery_pass"] is True
    # The honest-empty warnings MUST NOT be present.
    assert out["warnings"] == [], (
        f"warnings must be empty when MJDs are user-provided; "
        f"got {out['warnings']}"
    )


def test_run_frb_180916_real_parking_page_does_not_synthesize():
    """When the CHIME mirror returns an HTML parking page (force test hook),
    the real-data path MUST return the honest-empty shape without planting."""
    out = RP.run_frb_180916_real(force_status_for_tests="PARKING_PAGE")
    assert out["epochfold"] is None
    assert out["fetch_status"] == "PARKING_PAGE"
    assert out["n_bursts"] == 0
    s = json.dumps(out)
    # Specifically: no derived synthetic key indicators.
    for banned in ("plant_period_d", "jitter_d", "obs_window_d",
                    "_synth_arrivals"):
        # 'plant_period_d' *is* allowed inside the static base_plant
        # block (it documents the published 16.35 d). It must NOT appear
        # inside epochfold or known_answer (which would mean we ran).
        if banned == "plant_period_d":
            assert "epochfold" not in out or out["epochfold"] is None
            continue
        assert banned not in s, (
            f"banned fabrication-marker {banned!r} found in {s[:400]}"
        )


def test_run_frb_180916_real_writes_lab_motto_in_stance():
    """The lab motto must surface in every real-data run, even on failures."""
    out_failed = RP.run_frb_180916_real(force_status_for_tests="UNREACHABLE")
    assert "Structure != message" in out_failed["stance"], (
        f"lab motto missing from stance: {out_failed['stance']!r}"
    )


def test_analyze_mode_frb_180916_real_is_supported():
    """analyze(mode='frb_180916_real') must dispatch to run_frb_180916_real."""
    import json as _json
    out = RP.analyze(mode="frb_180916_real", seed=0,
                       bundled_real_json=None)
    assert "frb_180916_real_data" in out
    rd = out["frb_180916_real_data"]
    # Will land in UNREACHABLE on the canonical net; honest-empty shape.
    assert rd["epochfold"] is None
    assert rd["fetch_status"] in ("UNREACHABLE", "PARKING_PAGE")
    s = _json.dumps(out)
    for banned in ("synth_seed", "_synth_arrivals"):
        assert banned not in s


# --- markdown notes & end-to-end CLI for the real-data path -------------

def test_write_notes_markdown_for_real_data_path_surfaces_banner():
    """When the real-data path returns warnings, write_notes_markdown
    must surface a yellow 🟡 BANNER. (We use the emoji-style unicode
    banner-text in the markdown for cross-platform safety.)"""
    import json
    out = RP.run_frb_180916_real(force_status_for_tests="UNREACHABLE")
    report = {"label": "radio_probe_real_only",
                "mode": "frb_180916_real",
                "seed": 0,
                "stance": "test",
                "frb_180916_real_data": out}
    md = RP.write_notes_markdown(report)
    assert "REAL-DATA path" in md
    assert "fetch_status=UNREACHABLE" in md or "UNREACHABLE" in md
    assert "Fetch attempts" in md or "no real-data path" in md


def test_cli_frb_180916_real_with_test_force_uses_provided_status():
    """End-to-end CLI: --frb-180916-real + --fetch-status-test-force=UNREACHABLE
    must produce a JSON whose fetch_status reports UNREACHABLE."""
    td = Path(tempfile.mkdtemp(prefix="radio_real_"))
    out_json = td / "real.json"
    res = subprocess.run([
        sys.executable, str(TOOLS_RADIO / "radio_probe.py"),
        "--frb-180916-real",
        "--fetch-status-test-force", "UNREACHABLE",
        "--seed", "0",
        "--out-json", str(out_json),
    ], capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, (
        f"CLI --frb-180916-real failed:\\nSTDOUT: {res.stdout[:600]}\\n"
        f"STDERR: {res.stderr[:600]}"
    )
    d = json.load(open(out_json))
    rd = d["frb_180916_real_data"]
    assert rd["fetch_status"] == "UNREACHABLE"
    assert rd["epochfold"] is None
    assert rd["n_bursts"] == 0
    assert "warnings" in rd and len(rd["warnings"]) >= 1


def test_cli_frb_180916_real_with_user_override_json(tmp_path):
    """End-to-end CLI: --frb-180916-real + --bundled-mjd-json with a parseable
    JSON file MUST use the override and run the epoch-fold."""
    import json
    fixt = tmp_path / "override.json"
    mjds = [58700.0 + 16.35 * (i + 1) + 0.1 for i in range(30)]
    fixt.write_text(json.dumps(mjds))
    out_json = tmp_path / "real_user.json"
    res = subprocess.run([
        sys.executable, str(TOOLS_RADIO / "radio_probe.py"),
        "--frb-180916-real",
        "--bundled-mjd-json", str(fixt),
        "--seed", "0",
        "--out-json", str(out_json),
    ], capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, (
        f"CLI --frb-180916-real --bundled failed:\\n"
        f"STDOUT: {res.stdout[:600]}\\nSTDERR: {res.stderr[:600]}"
    )
    d = json.load(open(out_json))
    rd = d["frb_180916_real_data"]
    assert rd["fetch_status"] == "USER_OVERRIDE"
    assert rd["n_bursts"] == 30
    assert rd["known_answer"]["recovery_pass"] is True


# --- Vela pulsar positive-control tests -----------------------------------

def test_vela_constants_published_in_module():
    """Vela constants must surface and the published period must be
    ~89.328 ms (lab-motto positive-control anchor)."""
    import math
    assert RP.VELA_PSR_B1950 == "B0833-45"
    assert RP.VELA_PSR_J2000 == "J0835-4510"
    assert math.isclose(RP.VELA_P0_PUBLISHED_S, 0.089328385507, rel_tol=1e-9)
    assert math.isclose(RP.VELA_F0_PUBLISHED_HZ,
                          1.0 / RP.VELA_P0_PUBLISHED_S, rel_tol=1e-9)
    assert "1993M" in RP.VELA_BIBCODE_PSRCAT
    assert "CC BY 4.0" in RP.VELA_DATA_LICENSE


def test_synth_pulsar_vela_arrivals_returns_periodic_mjds():
    """The synthetic Vela plant must produce 30 arrival MJDs that fall
    on multiples of P0 (within the synthetic jitter envelope)."""
    import math
    mjds = RP.synth_pulsar_vela_arrivals(seed=0)
    assert len(mjds) == RP.DEFAULT_VELA_N_ARRIVALS
    # Convert to seconds and confirm the differences are close to P0 * N.
    times_s = mjds * 86400.0
    diffs_s = np.diff(times_s)
    P0 = RP.VELA_P0_PUBLISHED_S
    # Each diff should equal +/- a small number of periods; the cleanest
    # is diff[i] / P0 ~ (i+1) - i = 1 (consecutive multiples).
    ratios = diffs_s / P0
    assert np.allclose(ratios, 1.0, atol=1e-4), (
        f"synthetic Vela plant does not plant at multiples of P0: "
        f"diffs_s/P0 = {ratios[:5]}"
    )


def test_run_pulsar_vela_synthetic_recovers_p0_with_z2_dominant():
    """The synthetic Vela plant must recover P0 within 5e-6 s with
    Z^2 well above the shuffled-uniform null."""
    out = RP.run_pulsar_vela_synthetic(seed=0)
    ka = out["known_answer"]
    assert ka["recovery_pass"] is True, (
        f"recovery_pass should be True; recovered_period_s="
        f"{ka['recovered_period_s']}, recovery_error_s="
        f"{ka['recovery_error_s']}"
    )
    # Z^2 should be close to 2*N = 60 for tight clustering.
    assert ka["recovered_z2"] > 30.0, (
        f"Z^2 = {ka['recovered_z2']} below expected ~60 for N=30 tight"
    )
    # Shuffled null is well below the plant.
    assert out["negative_controls"]["shuffled_uniform_z2_max"] < \
        ka["recovered_z2"], (
        "shuffled null Z^2 must NOT outperform the plant"
    )


def test_run_pulsar_vela_synthetic_includes_stance_with_motto():
    """The synthetic-Vela stance string MUST surface the lab motto
    (structure != message AND period = necessary NOT sufficient)."""
    out = RP.run_pulsar_vela_synthetic(seed=0)
    stance = (out["stance"] + " " + out.get("lab_motto_anchor", "")).lower()
    assert "structure" in stance and "message" in stance, (
        f"stance must surface 'Structure != message': {out['stance']!r}"
    )
    assert "necessary" in stance and "sufficient" in stance, (
        f"stance must surface 'necessary, NOT sufficient': {out['stance']!r}"
    )


def test_run_pulsar_vela_real_default_returns_empty_no_synthesis():
    """Without overrides and with the live fetch forced UNREACHABLE,
    run_pulsar_vela MUST return honest-empty shape WITHOUT synthesizing."""
    out = RP.run_pulsar_vela(force_status_for_tests="UNREACHABLE")
    assert out["epochfold"] is None, (
        "epochfold MUST be None when no MJDs available; "
        "we never fall back to a synthetic plant in the real-data path"
    )
    assert out["known_answer"] is None
    assert out["n_arrivals"] == 0
    warning_text = " ".join(out.get("warnings", [])).lower()
    assert "no real-data path" in warning_text or \
        "no synthetic plant" in warning_text or \
        "no mjds" in warning_text, (
        f"warning text must surface the empty state: {out['warnings']}"
    )
    assert out["fetch_status"] in ("UNREACHABLE", "PARKING_PAGE",
                                     "MODULE_MISSING")
    s = json.dumps(out)
    for banned in ("_synth_arrivals", "decoy_real_spin_period_s"):
        assert banned not in s, (
            f"banned fabrication-marker {banned!r} found in real-data "
            f"output: {s[:400]}"
        )


def test_pulsar_fetcher_unreachable_does_not_synthesize():
    """When all canonical URLs are unreachable, the fetcher MUST surface
    UNREACHABLE -- never fabricate arrival MJDs."""
    import pulsar_fetcher as PUL
    res = PUL.try_fetch_atnf_pulsar_vela_timing(
        attempt_urls=[("http://127.0.0.1:1/nope", "deliberate_invalid",
                        "text/csv")],
        timeout_s=2.0,
        use_cache=False,
    )
    assert res.fetch_status in ("UNREACHABLE", "PARKING_PAGE")
    assert res.arrival_mjds == []
    assert res.arrival_mjds_vela == []
    assert len(res.attempts) >= 1
    att0 = res.attempts[0]
    assert att0.verdict in ("NETWORK_ERROR", "TIMEOUT", "4XX",
                              "5XX", "HTML_PARKING")


def test_analyze_mode_pulsar_vela_synthetic_and_real_dispatch():
    """analyze() must dispatch 'pulsar_vela_synthetic' to the synthetic
    plant and 'pulsar_vela_real' to the real-data path (which, under
    the network/canonical-mirror-unreachable state, returns empty)."""
    out_syn = RP.analyze(mode="pulsar_vela_synthetic", seed=0)
    assert "pulsar_vela_synthetic" in out_syn
    assert out_syn["pulsar_vela_synthetic"]["known_answer"]["recovery_pass"] is True
    out_real = RP.analyze(mode="pulsar_vela_real", seed=0)
    assert "pulsar_vela_real_data" in out_real
    rd = out_real["pulsar_vela_real_data"]
    assert rd["source_type"] == "empty"
    # Even though MODULE_MISSING or fetch_status may vary by env,
    # the warnings must surface the empty state.
    assert len(rd.get("warnings", [])) >= 1


def test_cli_pulsar_vela_real_with_test_force_uses_provided_status():
    """End-to-end CLI: --pulsar-vela-real --fetch-status-test-force UNREACHABLE
    must produce a JSON whose real-data path is honest-empty."""
    td = Path(tempfile.mkdtemp(prefix="vela_real_"))
    out_json = td / "vela_real.json"
    res = subprocess.run([
        sys.executable, str(TOOLS_RADIO / "radio_probe.py"),
        "--pulsar-vela-real",
        "--fetch-status-test-force", "UNREACHABLE",
        "--seed", "0",
        "--out-json", str(out_json),
    ], capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, (
        f"CLI --pulsar-vela-real failed:\nSTDOUT: {res.stdout[:600]}\n"
        f"STDERR: {res.stderr[:600]}"
    )
    d = json.load(open(out_json))
    rd = d["pulsar_vela_real_data"]
    assert rd["fetch_status"] == "UNREACHABLE"
    assert rd["epochfold"] is None
    assert rd["n_arrivals"] == 0


def test_cli_pulsar_vela_synthetic_recovers_p0_pass():
    """End-to-end CLI: --pulsar-vela-synthetic must run the math and
    return recovery_pass=True."""
    td = Path(tempfile.mkdtemp(prefix="vela_syn_"))
    out_json = td / "vela_syn.json"
    res = subprocess.run([
        sys.executable, str(TOOLS_RADIO / "radio_probe.py"),
        "--pulsar-vela-synthetic",
        "--seed", "0",
        "--out-json", str(out_json),
    ], capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, (
        f"CLI --pulsar-vela-synthetic failed:\n"
        f"STDOUT: {res.stdout[:600]}\nSTDERR: {res.stderr[:600]}"
    )
    d = json.load(open(out_json))
    out = d["pulsar_vela_synthetic"]
    assert out["known_answer"]["recovery_pass"] is True


# --- Standalone runner ----------------------------------------------------

# === G-BLC1 RFI known-answer tests (mirror of Vela polish pattern) ===

def test_blc1_constants_match_sheikh_2021():
    """BLC1 constants pinned to Sheikh et al. 2021 (Nat. Astron. 5 1169)."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import radio_probe as RP
    assert RP.BLC1_FREQ_MHZ == 982.002
    assert RP.BLC1_DRIFT_HZ_PER_S == -0.26
    assert RP.BLC1_CLOCK_MHZ == 2.0
    assert RP.BLC1_COMB_TOLERANCE_MHZ == 0.01
    assert RP.BLC1_BIBCODE.startswith("2021NatAs")
    assert RP.BLC1_REFERENCE_URL.startswith("https://")


def test_blc1_fetcher_live_probe_disabled_by_default():
    """The 'no TB mirror' stance: try_fetch_blc1_peaks() returns
    NEVER_ATTEMPTED with one attempt per documented URL, WITHOUT
    contacting the network."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import blc1_fetcher as BLC
    res = BLC.try_fetch_blc1_peaks()
    assert res.fetch_status == "NEVER_ATTEMPTED"
    assert res.peak_rows == []
    assert len(res.attempts) >= 5
    for att in res.attempts:
        assert att.verdict == "NEVER_ATTEMPTED"
    note = res.provenance_note.lower()
    assert "disabled" in note or "no tb mirror" in note


def test_blc1_fetcher_test_force_fetched_renders_positive_control_peaks():
    """Test hook FETCHED synthesises the 5-peak positive control set:
    1 BLC1 detection @ 982.002 + 2 clock harmonics + 2 known Parkes RFI freqs."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import blc1_fetcher as BLC
    res = BLC.try_fetch_blc1_peaks(force_status_for_tests="FETCHED")
    assert res.fetch_status == "FETCHED"
    assert len(res.peak_rows) == 5
    freqs = [float(r.raw_freq_mhz) for r in res.peak_rows]
    assert 982.002 in freqs  # BLC1 detection
    assert 440.0 in freqs    # PARKES_UHF_RFI
    assert 1217.0 in freqs   # PARKES_L2_GPS_RFI


def test_blc1_synthetic_comb_plant_recovery_pass():
    """SYNTHETIC G-BLC1 plant: 5 harmonically-spaced peaks around 982.002 MHz
    should trigger all-hits_at_clock and rfi_comb_detected=True."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import radio_probe as RP
    out = RP.run_blc1_synthetic(seed=0)
    ka = out["known_answer"]
    assert out["n_peaks"] >= 5
    assert ka["hits_at_clock"] >= out["n_peaks"] - 1, (
        f"synthetic plant should have hits_at_clock ~ N_peaks, "
        f"got hits={ka['hits_at_clock']} N={out['n_peaks']}"
    )
    assert ka["recovery_pass"] is True
    assert ka["rfi_comb_detected"] is True


def test_blc1_scramble_null_drops_hits_at_clock():
    """Scramble null: shuffling peak freqs uniformly should drop
    hits_at_clock well below the planted value."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import radio_probe as RP
    out = RP.run_blc1_synthetic(seed=0)
    cd = out["comb_detection"]
    nc = out["negative_controls"]
    assert cd["hits_at_clock"] > nc["scramble_null_hits"], (
        f"scramble null should DROP hits; got hits={cd['hits_at_clock']} "
        f"vs scramble={nc['scramble_null_hits']}"
    )


def test_blc1_real_default_yellow_banner_no_synthetic_fallback():
    """--blc1-real WITHOUT bundled override: NEVER_ATTEMPTED + YELLOW BANNER
    warnings. CRITICAL invariant: NO synthetic peaks injected."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import radio_probe as RP
    out = RP.run_blc1_real(bundled_csv_path=None, seed=0)
    assert out["fetch_status"] == "NEVER_ATTEMPTED"
    assert out["n_peaks"] == 0
    assert out["comb_detection"] is None
    assert out["known_answer"] is None
    warnings_text = " ".join(out["warnings"]).lower()
    assert "no tb mirror" in warnings_text or "disabled" in warnings_text
    assert "sheikh" in out["stance"].lower()
    assert "not sufficient" in out["stance"].lower() or \
           "necessary, not sufficient" in out["stance"].lower()


def test_blc1_real_bundled_overrides_fetch_user_override():
    """--bundled-blc1-csv WITH peaks: USER_OVERRIDE + comb detection runs."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import radio_probe as RP
    td = Path(tempfile.mkdtemp(prefix="blc1_ovr_"))
    csv_path = td / "blc1_test.csv"
    csv_path.write_text(
        "freq_mhz,snr_db,drift_hz_per_s,t_start_mjd,t_end_mjd,label\n"
        "982.002,25.0,-0.26,58000,58000,BLC1_DETECTION\n"
        "984.002,12.0,-0.26,58000,58000,BLC1_HARM+1\n"
        "986.002,9.0,-0.26,58000,58000,BLC1_HARM+2\n"
    )
    try:
        out = RP.run_blc1_real(bundled_csv_path=csv_path, seed=0)
        assert out["fetch_status"] == "USER_OVERRIDE"
        assert out["source_type"] == "bundled_override"
        assert out["n_peaks"] == 3
        assert out["comb_detection"]["hits_at_clock"] >= 3
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)


def test_blc1_force_status_propagates_via_post_analyze_rerun():
    """--blc1-real --fetch-status-test-force FETCHED triggers the
    post-analyze re-run block (mirrors Vela/FRB pattern)."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import radio_probe as RP
    # analyze() with mode='blc1_real' runs the default NEVER_ATTEMPTED path.
    rep = RP.analyze(mode="blc1_real", seed=0, bundled_blc1_csv=None)
    assert "blc1_real_data" in rep
    assert rep["blc1_real_data"]["fetch_status"] == "NEVER_ATTEMPTED"
    # Mirror the post-analyze re-run block in main(): re-run with the
    # test-force hook applied.
    rep["blc1_real_data"] = RP.run_blc1_real(
        bundled_csv_path=None, seed=0,
        force_status_for_tests="FETCHED",
    )
    assert rep["blc1_real_data"]["fetch_status"] == "FETCHED"
    assert rep["blc1_real_data"]["n_peaks"] == 5
    assert rep["blc1_real_data"]["known_answer"]["rfi_comb_detected"] is True


# === G3 (Wow! beam-fit) tests ===

def test_wow_beam_synth_recovery_pass():
    """SYNTH G3: noise-free plant at (mu=2.5, sigma=1.5, amp=30) ->
    fit recovers within tolerance."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import radio_probe as RP
    out = RP.run_wow_beam_fit(mode="synthetic", seed=0)
    ka = out["known_answer"]
    assert ka["recovery_pass"] is True, (
        f"recovery_pass should be True, got {ka['recovery_pass']}; "
        f"errors: mu_err={ka['mu_err_idx']}, sigma_err={ka['sigma_err_idx']}, "
        f"amp_err={ka['amplitude_err']}"
    )
    assert ka["mu_err_idx"] is not None and ka["mu_err_idx"] <= 0.5
    assert ka["sigma_err_idx"] is not None and ka["sigma_err_idx"] <= 0.5
    assert ka["amplitude_err"] is not None and ka["amplitude_err"] <= 1e-6


def test_wow_beam_real_beats_constant():
    """Real Wow! (Ehman transcript) should NOT have r²_gaussian < r²_constant.
    With N=6 underdetermined, r²_gaussian >= r²_constant holds trivially."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import radio_probe as RP
    out = RP.run_wow_beam_fit(mode="real", seed=0)
    fit = out["fit"]
    assert fit["n_samples"] == 6
    assert fit["r2_constant"] >= 0
    assert fit["r2_gaussian"] >= fit["r2_constant"], (
        f"Gaussian fit cannot be worse than a constant baseline. "
        f"got r2_gaussian={fit['r2_gaussian']}, r2_constant={fit['r2_constant']}"
    )
    assert out["known_answer"]["recovery_pass"] is None


def test_wow_beam_real_sinc_fit():
    """Real Wow! sinc fit must produce r²_sinc + recovered (mu, sigma, amp)."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import radio_probe as RP
    out = RP.run_wow_beam_fit(mode="real", seed=0)
    fit = out["fit"]
    assert "r2_sinc" in fit, "fit dict must include r2_sinc"
    assert fit["r2_sinc"] is not None
    rs = fit["recovered_sinc"]
    assert rs["mu_idx"] is not None
    assert rs["sigma_idx"] is not None
    assert rs["amplitude"] is not None


def test_wow_beam_scramble_null_baseline():
    """Scramble null: 24 perms -> median + p5/p95 r² distribution."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import radio_probe as RP
    out = RP.run_wow_beam_fit(mode="real", seed=0)
    sn = out["scramble_null"]
    assert sn["n_permutations"] >= 24, (
        f"expected >=24 permutations for stable median+p95, got {sn['n_permutations']}"
    )
    assert sn["r2_median"] is not None
    assert sn["r2_p5"] <= sn["r2_median"] + 1e-6
    assert sn["r2_median"] <= sn["r2_p95"] + 1e-6


def test_wow_beam_degeneracy_pair_and_motto():
    """degeneracy_pair (μ ↔ 6-μ) surfaced; stance cites PHL@UPR 2024."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import radio_probe as RP
    out = RP.run_wow_beam_fit(mode="synthetic", seed=0)
    fit = out["fit"]
    degen = fit["degeneracy_pair"]
    assert isinstance(degen, tuple) and len(degen) == 2
    # mu ↔ 6-mu symmetry: pair sums to 6.
    assert abs((degen[0] + degen[1]) - 6.0) < 0.5, (
        f"degeneracy_pair must sum to 6 (mu + (6-mu) = 6); got {degen}"
    )
    note = fit["underdetermined_note"]
    assert "3 d.o.f." in note.lower() or "3 dof" in note.lower(), (
        f"underdetermined note should mention DOF=3; got: {note[:200]}"
    )
    stance = out["stance"]
    assert "PHL@UPR" in stance or "2408.08513" in stance, (
        f"stance should cite PHL@UPR 2024 / arXiv:2408.08513; got: {stance[:200]}"
    )
    assert "underdetermined" in stance.lower()
    assert "necessary, not sufficient" in stance.lower() or \
           "necessary, NOT sufficient" in stance


# === R1++ Cat 2 (CHIME/FRB Catalog 2) periodicity known-answer tests =====
# Stance: structure != message. FRB activity periodicity is a NATURAL
# cycle. All synthetic recoveries are math-validation; the real path parks
# honestly and NEVER fabricates arrival MJDs.

def test_cat2_real_sources_parking_does_not_synthesize():
    """cat2_real_sources: a PARKING_PAGE fetch yields an honest-empty
    multi-source result -- rows_by_source == {}, no synthesis."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import cat2_real_sources as C2S
    src = C2S.load_published_cat2_bursts(force_status_for_tests="PARKING_PAGE")
    assert src.fetch_status == "PARKING_PAGE"
    assert src.rows_by_source == {}
    assert src.has_any_mjds is False
    assert len(src.fetch_attempts) >= 1
    assert src.source_type == "empty"


def test_cat2_real_sources_unreachable_honest_empty():
    """cat2_real_sources: UNREACHABLE fetch -> honest-empty, attempts kept."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import cat2_real_sources as C2S
    src = C2S.load_published_cat2_bursts(force_status_for_tests="UNREACHABLE")
    assert src.fetch_status == "UNREACHABLE"
    assert src.n_bursts_total == 0
    assert src.rows_by_source == {}
    assert "no synthetic data injected" in src.provenance_note.lower()


def test_cat2_real_sources_bundled_override_parses_multi_source():
    """--bundled-cat2-csv with name,mjd rows -> USER_OVERRIDE, grouped by
    source. NEVER touches the network."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import cat2_real_sources as C2S
    td = Path(tempfile.mkdtemp(prefix="cat2_ovr_"))
    csv_path = td / "cat2_test.csv"
    csv_path.write_text(
        "name,mjd\n"
        "FRB 20180916B,58000.0\n"
        "FRB 20180916B,58016.35\n"
        "FRB 20121102A,58100.0\n"
    )
    try:
        src = C2S.load_published_cat2_bursts(bundled_csv_path=csv_path)
        assert src.fetch_status == "USER_OVERRIDE"
        assert src.source_type == "user_provided_cat2"
        assert src.n_sources == 2
        assert src.has_any_mjds is True
        assert len(src.rows_by_source["FRB 20180916B"]) == 2
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)


def test_run_cat2_synthetic_recovers_16p35d():
    """R1++ headline: the synthetic Cat 2 known-answer recovers 16.35 d for
    FRB 20180916B within 1 d, and recovers every planted source."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import radio_probe as RP
    out = RP.run_cat2_synthetic(seed=0)
    ka = out["known_answer"]
    assert ka["recovers_16p35d"] is True
    assert ka["all_sources_recovery_pass"] is True
    assert ka["primary_recovery_error_d"] <= 1.0
    prim = out["per_source"]["FRB 20180916B"]
    assert abs(prim["recovered_period_d"] - 16.35) <= 1.0


def test_run_cat2_synthetic_scramble_null_below_recovered():
    """Per-source scramble null (uniform-in-window shuffle) must NOT beat
    the recovered Z² -- periodicity is destroyed by the shuffle."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import radio_probe as RP
    out = RP.run_cat2_synthetic(seed=0)
    assert out["negative_controls"]["scramble_null_below_recovered"] is True
    for name, e in out["per_source"].items():
        assert e["scramble_null_z2_max"] < e["recovered_z2"], (
            f"{name}: scramble null Z²={e['scramble_null_z2_max']} should be "
            f"below recovered Z²={e['recovered_z2']}"
        )


def test_run_cat2_synthetic_does_not_confuse_121102_with_16p35():
    """Belt-and-suspenders: FRB 20121102A is published at ~157 d, NOT 16.35 d.
    Its recovery must land near 157 d, never collapse onto 16.35 d."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import radio_probe as RP
    out = RP.run_cat2_synthetic(seed=0)
    e = out["per_source"]["FRB 20121102A"]
    assert e["published_period_d"] == 157.0
    assert 140.0 <= e["recovered_period_d"] <= 175.0
    assert abs(e["recovered_period_d"] - 16.35) > 100.0


def test_run_cat2_real_parking_no_synthesis():
    """run_cat2_real with a PARKING_PAGE fetch: honest-empty, no epoch-fold,
    no fabricated MJDs, warnings present."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import radio_probe as RP
    out = RP.run_cat2_real(force_status_for_tests="PARKING_PAGE", seed=0)
    assert out["fetch_status"] == "PARKING_PAGE"
    assert out["n_sources"] == 0
    assert out["n_bursts_total"] == 0
    assert out["per_source"] == {}
    assert out["known_answer"] is None
    assert out["warnings"], "must warn that no real-data path was attempted"
    assert "no synthetic plant" in " ".join(out["warnings"]).lower()


def test_run_cat2_real_bundled_override_epoch_folds_16p35d():
    """run_cat2_real with a bundled CSV of FRB 20180916B arrivals at 16.35 d
    recovers the period per-source (recovery_pass True). No network."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import radio_probe as RP
    import numpy as np
    td = Path(tempfile.mkdtemp(prefix="cat2_real_ovr_"))
    csv_path = td / "cat2_arrivals.csv"
    times = RP.synth_frb_arrivals(period_d=16.35, n_arrivals=30,
                                  obs_window_d=500.0, jitter_d=0.3, seed=0)
    rows = ["name,mjd"] + [f"FRB 20180916B,{float(t):.6f}" for t in times]
    csv_path.write_text("\n".join(rows) + "\n")
    try:
        out = RP.run_cat2_real(bundled_csv_path=csv_path, seed=0)
        assert out["fetch_status"] == "USER_OVERRIDE"
        assert out["n_sources"] == 1
        e = out["per_source"]["FRB 20180916B"]
        assert e["published_period_d"] == 16.35
        assert abs(e["recovered_period_d"] - 16.35) <= 1.0
        assert e["recovery_pass"] is True
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)


def test_analyze_mode_cat2_dispatch():
    """analyze() routes cat2 modes to the right sub-runs."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import radio_probe as RP
    rep_s = RP.analyze(mode="cat2_synthetic", seed=0)
    assert "cat2_synthetic" in rep_s
    assert rep_s["cat2_synthetic"]["known_answer"]["recovers_16p35d"] is True
    rep_r = RP.analyze(mode="cat2_real", seed=0, bundled_cat2_csv=None)
    assert "cat2_real_data" in rep_r


def test_cli_cat2_real_with_test_force_uses_provided_status():
    """CLI: --cat2-real --fetch-status-test-force PARKING_PAGE exercises the
    post-analyze re-run shim and surfaces PARKING_PAGE without fabrication."""
    td = Path(tempfile.mkdtemp(prefix="cat2_cli_"))
    out_json = td / "cat2.json"
    res = subprocess.run([
        sys.executable, str(TOOLS_RADIO / "radio_probe.py"),
        "--cat2-real", "--fetch-status-test-force", "PARKING_PAGE",
        "--seed", "0", "--out-json", str(out_json),
    ], capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, f"CLI failed:\n{res.stderr[:600]}"
    d = json.load(open(out_json))
    rd = d["cat2_real_data"]
    assert rd["fetch_status"] == "PARKING_PAGE"
    assert rd["n_sources"] == 0
    assert rd["known_answer"] is None
    import shutil
    shutil.rmtree(td, ignore_errors=True)


# === G-BLC1 ON/OFF + harmonic-family interpretation tests ================

def test_blc1_delta_f_regularity_flags_equal_spacing():
    """Equally-spaced peaks -> regular_comb True (low CV); irregular -> False."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import radio_probe as RP
    reg = RP.blc1_delta_f_regularity([980.0, 982.0, 984.0, 986.0, 988.0])
    assert reg["regular_comb"] is True
    assert reg["cv_delta_f"] is not None and reg["cv_delta_f"] <= 0.05
    assert abs(reg["mean_delta_f_mhz"] - 2.0) < 1e-6
    irr = RP.blc1_delta_f_regularity([980.0, 982.0, 990.0, 991.0])
    assert irr["regular_comb"] is False


def test_blc1_on_off_cadence_has_discriminating_power():
    """ON-only injection (OFF = off-comb noise) is cadence-consistent; a comb
    that persists into OFF is flagged terrestrial. The test proves the
    discriminator is not a dead detector."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import radio_probe as RP
    comb = [980.0, 982.0, 984.0, 986.0, 988.0]
    noise = [973.3, 989.7, 1001.1, 968.2, 995.5]
    on_only = RP.blc1_on_off_cadence(on_freqs_mhz=comb, off_freqs_mhz=noise)
    assert on_only["cadence_consistent_with_source"] is True
    assert on_only["persists_in_off"] is False
    persists = RP.blc1_on_off_cadence(on_freqs_mhz=comb, off_freqs_mhz=comb)
    assert persists["persists_in_off"] is True
    assert persists["cadence_consistent_with_source"] is False


def test_blc1_synthetic_verdict_is_rfi_and_persists_in_off():
    """SYNTHETIC BLC1: the planted family persists into OFF and is a regular
    comb -> verdict RFI_COMB_TERRESTRIAL. Existing known_answer keys intact."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import radio_probe as RP
    out = RP.run_blc1_synthetic(seed=0)
    assert out["verdict"] == "RFI_COMB_TERRESTRIAL"
    assert out["on_off_control"]["persists_in_off"] is True
    assert out["harmonic_family"]["regular_comb"] is True
    # the ON-only contrast control must have discriminating power
    assert out["on_off_contrast_on_only"]["cadence_consistent_with_source"] is True
    # existing invariants preserved (no regression)
    assert out["known_answer"]["recovery_pass"] is True
    assert out["known_answer"]["rfi_comb_detected"] is True


def test_blc1_real_default_no_data_verdict_is_not_no_signal():
    """Ulfberht gate-review fix: on the UNMEASURED real path (no TB mirror ->
    NEVER_ATTEMPTED, n_peaks=0), the machine `verdict` must NOT be NO_SIGNAL
    (nothing was measured). It carries BLOCKED_DATA_TOO_LARGE, and Sheikh's
    documented conclusion lives in a separate `literature_verdict` field."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import radio_probe as RP
    out = RP.run_blc1_real(bundled_csv_path=None, seed=0)
    assert out["fetch_status"] == "NEVER_ATTEMPTED"
    assert out["n_peaks"] == 0
    assert out["known_answer"] is None
    # machine verdict reflects what actually happened, NOT an inherited label
    assert out["verdict"] == "BLOCKED_DATA_TOO_LARGE"
    assert out["verdict"] != "NO_SIGNAL"
    # the documented (literature) conclusion is carried separately + honestly
    lit = out["literature_verdict"]
    assert "NO_SIGNAL" in lit and "Sheikh 2021" in lit
    assert "not independently reproduced" in lit.lower()


def test_blc1_real_measured_bundled_keeps_no_signal_verdict():
    """On a MEASURED path (bundled Sheikh-style peaks -> comb detected), a
    NO_SIGNAL verdict IS legitimate (no technosignature), and the literature
    conclusion is still carried separately."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import radio_probe as RP
    td = Path(tempfile.mkdtemp(prefix="blc1_meas_"))
    csv_path = td / "peaks.csv"
    csv_path.write_text(
        "freq_mhz,snr_db,drift_hz_per_s,t_start_mjd,t_end_mjd,label\n"
        "982.002,25.0,-0.26,58000,58000,A\n"
        "984.002,12.0,-0.26,58000,58000,B\n"
        "986.002,9.0,-0.26,58000,58000,C\n"
    )
    try:
        out = RP.run_blc1_real(bundled_csv_path=csv_path, seed=0)
        assert out["fetch_status"] == "USER_OVERRIDE"
        assert out["n_peaks"] == 3
        assert out["verdict"] == "NO_SIGNAL"  # measured RFI comb -> no ET
        assert "Sheikh 2021" in out["literature_verdict"]
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)


def test_blc1_white_noise_negative_finds_no_comb():
    """Skill §4 white-noise waterfall negative: pure-noise frequencies (no
    injected comb) must NOT manufacture a comb -> rfi_comb_detected False,
    hits_at_clock small. Independent of the in-band scramble null."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import radio_probe as RP
    out = RP.run_blc1_synthetic(seed=0)
    wn = out["white_noise_negative"]
    assert wn["rfi_comb_detected"] is False
    assert wn["hits_at_clock"] < 2, (
        f"white-noise negative should not manufacture a comb; got "
        f"hits_at_clock={wn['hits_at_clock']}"
    )


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    def _needs_fixture(f):
        return bool(list(inspect.signature(f).parameters))
    runnable = [f for f in fns if not _needs_fixture(f)]
    skipped = [f for f in fns if _needs_fixture(f)]
    for fn in skipped:
        print(f"SKIP {fn.__name__}  (private pytest-fixture)")
    ok = 0; bad = 0
    for fn in runnable:
        try:
            fn()
            print(f"PASS {fn.__name__}")
            ok += 1
        except Exception as e:
            print(f"FAIL {fn.__name__}: {type(e).__name__}: {e}")
            bad += 1
    print(f"\n{ok}/{len(runnable)} passed, {bad} failed, {len(skipped)} skipped")
    sys.exit(0 if bad == 0 else 1)
