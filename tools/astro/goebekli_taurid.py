#!/usr/bin/env python3
"""
goebekli_taurid.py — Göbekli Tepe × Taurid radiant alignment test (Hecklefish #5).

Measures whether the Taurid radiant's rise/set azimuth at epoch ~9 600 BCE
aligns with the documented face orientations of Enclosure D pillars, then
tests both a random-azimuth null and a scrambled-date null to assess whether
any apparent alignment exceeds chance.

STRUCTURE != MESSAGE.  No "comet cult proven."  No aliens.  Every claim
must beat the control band.

Usage:
    python tools/astro/goebekli_taurid.py --help
    python tools/astro/goebekli_taurid.py --dry-run
    python tools/astro/goebekli_taurid.py --run
"""
from __future__ import annotations

import argparse
import json
import math
import random as rnd
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / "outputs" / "goebekli"
DATA = ROOT / "data" / "astro" / "goebekli"

STANCE = (
    "Göbekli Tepe × Taurid: null-first archaeoastronomy. "
    "No positive alignment claim without beating random-azimuth and "
    "scrambled-date controls. Apophenia is the default."
)

VERDICT_VOCAB = ("ORIENTATION_STRUCTURE", "NO_SIGNAL", "UNDERDETERMINED")

MONTE_CARLO_TRIALS = 10_000
HIT_THRESHOLD_DEG = 10.0
EPOCH_YEAR = -9600

# Pillar face azimuths from data/astro/goebekli/pillars.json (canonical)
# (declared here so tests can import without file I/O; file read overrides)
CANONICAL_AZIMUTHS = {
    "P43": 325, "P18": 215, "P27": 45, "P30": 135,
    "P31": 225, "P32": 180, "P33": 270, "P34": 90,
    "P35": 315, "P36": 35, "P37": 135, "P38": 255,
    "central_E": 0, "central_W": 180,
}

# Taurid complex J2000 centre — Sweatman & Tsikritsis focus on
# the Taurid meteor stream radiant, approximated here.
TAURID_RA_H = 3.50
TAURID_DEC_DEG = 15.0

FORBIDDEN_PHRASES = (
    "comet cult proven",
    "comet cult confirmed",
    "aliens built",
    "extraterrestrial construction",
    "gods from space",
    "ancient astronaut",
    "hyperdimensional",
    "wormhole",
    "stargate",
    "annunaki",
)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _angular_delta_deg(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return min(d, 360 - d)


def _mean_angle(angles_deg: list[float]) -> float:
    if not angles_deg:
        return float("nan")
    s = sum(math.sin(math.radians(a)) for a in angles_deg)
    c = sum(math.cos(math.radians(a)) for a in angles_deg)
    return math.degrees(math.atan2(s, c)) % 360


def _circular_std(angles_deg: list[float]) -> float:
    if len(angles_deg) < 2:
        return float("nan")
    n = len(angles_deg)
    s = sum(math.sin(math.radians(a)) for a in angles_deg)
    c = sum(math.cos(math.radians(a)) for a in angles_deg)
    R = math.hypot(s, c) / n
    return math.sqrt(-2 * math.log(max(R, 1e-15)))


def _rayleigh_z(angles_deg: list[float]) -> tuple[float, float]:
    """Rayleigh test for non-uniformity.  Returns (z, p)."""
    n = len(angles_deg)
    if n < 2:
        return float("nan"), float("nan")
    s = sum(math.sin(math.radians(a)) for a in angles_deg)
    c = sum(math.cos(math.radians(a)) for a in angles_deg)
    R = math.hypot(s, c)
    z = R ** 2 / n
    p = math.exp(-z)
    return z, p


# ---------------------------------------------------------------------------
# precession backend (delegates to astro_probe when possible)
# ---------------------------------------------------------------------------

def _precess_analytic(ra_h: float, dec_deg: float, from_year: int, to_year: int) -> tuple[float, float]:
    dt_yr = to_year - from_year
    ra_rad = math.radians(ra_h * 15)
    dec_rad = math.radians(dec_deg)
    m = 3.074
    n_sec = 1.337
    dra_s = (m + n_sec * math.sin(ra_rad) * math.tan(dec_rad)) * dt_yr
    dec_term_arcsec = n_sec * math.cos(ra_rad) * 15 * dt_yr
    ra_new = (ra_h + dra_s / 3600) % 24
    dec_new = max(-90, min(90, dec_deg + dec_term_arcsec / 3600))
    return ra_new, dec_new


def precess_taurid(year: int) -> tuple[float, float, str]:
    """Precess Taurid radiant from J2000 to `year` BCE.  Returns (ra_h, dec_deg, backend)."""
    try:
        from skyfield.api import load as sf_load, wgs84 as sf_wgs84
        from skyfield.starlib import Star

        sf_dir = str(ROOT)
        sf_load.directory = sf_dir
        eph = sf_load("de441.bsp")
        ts = sf_load.timescale()

        star = Star(ra_hours=TAURID_RA_H, dec_degrees=TAURID_DEC_DEG)
        earth = eph["earth"]
        t_to = ts.utc(year, 7, 1)  # mid-year epoch
        astro = earth.at(t_to).observe(star).apparent()
        ra, dec, _ = astro.radec()
        return ra.hours, dec.degrees, "skyfield"
    except Exception:
        ra, dec = _precess_analytic(TAURID_RA_H, TAURID_DEC_DEG, 2000, year)
        return ra, dec, "analytic"


# ---------------------------------------------------------------------------
# azimuth of a celestial object at rise / culmination
# ---------------------------------------------------------------------------

def _altaz_for_radec(ra_h: float, dec_deg: float, lat: float, lon: float,
                     year: int, month: int, day: int, hour: float) -> tuple[float, float]:
    """Compute (altitude, azimuth) for given RA/Dec at a site/time using Skyfield (preferred)."""
    try:
        from skyfield.api import load as sf_load, wgs84 as sf_wgs84
        from skyfield.starlib import Star

        sf_dir = str(ROOT)
        sf_load.directory = sf_dir
        eph = sf_load("de441.bsp")
        ts = sf_load.timescale()

        star = Star(ra_hours=ra_h, dec_degrees=dec_deg)
        t = ts.utc(year, month, day, hour)
        loc = sf_wgs84.latlon(lat, lon)
        observer = (eph["earth"] + loc).at(t)
        astro = observer.observe(star).apparent()
        alt, az, _ = astro.altaz()
        return alt.degrees, az.degrees
    except Exception:
        return _altaz_fallback(dec_deg, lat, hour)


def _altaz_fallback(dec_deg: float, lat: float, hour_angle: float) -> tuple[float, float]:
    """Rough alt-az from declination, latitude, hour angle."""
    lat_r = math.radians(lat)
    dec_r = math.radians(dec_deg)
    ha_r = math.radians(hour_angle * 15)
    alt = math.asin(math.sin(lat_r) * math.sin(dec_r) + math.cos(lat_r) * math.cos(dec_r) * math.cos(ha_r))
    az = math.atan2(-math.sin(ha_r), math.tan(dec_r) * math.cos(lat_r) - math.sin(lat_r) * math.cos(ha_r))
    return math.degrees(alt), (math.degrees(az) + 180) % 360


def _rise_azimuth_approx(dec_deg: float, lat: float) -> float | None:
    """Rise azimuth for a body at declination dec_deg from latitude lat.
    Returns None if circumpolar / never rises.
    """
    lat_r = math.radians(lat)
    dec_r = math.radians(dec_deg)
    cos_h = -math.tan(lat_r) * math.tan(dec_r)
    if cos_h < -1:
        return None  # circumpolar — always above horizon
    if cos_h > 1:
        return None  # never rises
    az = math.degrees(math.acos(math.sin(dec_r) / math.cos(lat_r)))
    return az % 360


def compute_taurid_azimuth(ra_h: float, dec_deg: float, lat: float, lon: float,
                           year: int) -> dict:
    """Compute the Taurid radiant rise azimuth and culmination azimuth at the site."""
    rise_az = _rise_azimuth_approx(dec_deg, lat)
    if rise_az is None:
        # circumpolar or never rises
        return {
            "rise_azimuth_deg": None,
            "culmination_azimuth_deg": None,
            "rise_possible": False,
            "note": "Radiant circumpolar or never rises at this latitude",
            "dec_deg": round(dec_deg, 2),
            "ra_h": round(ra_h, 4),
        }
    # culmination azimuth = due north (+0°) for upper transit
    # For an object that culminates, the azimuth is either 0° or 180° depending on declination
    if dec_deg > lat:
        cul_az = 0.0  # culminates north
    else:
        cul_az = 180.0  # culminates south
    return {
        "rise_azimuth_deg": round(rise_az, 2),
        "culmination_azimuth_deg": round(cul_az, 2),
        "rise_possible": True,
        "dec_deg": round(dec_deg, 2),
        "ra_h": round(ra_h, 4),
    }


# ---------------------------------------------------------------------------
# data loading
# ---------------------------------------------------------------------------

def load_pillar_azimuths() -> dict[str, float]:
    """Load pillar face azimuths from data file, falling back to CANONICAL_AZIMUTHS."""
    path = DATA / "pillars.json"
    if not path.exists():
        return dict(CANONICAL_AZIMUTHS)
    try:
        data = json.loads(path.read_text())
        result = {}
        for p in data.get("pillars", []):
            pid = p["id"]
            az = p.get("face_azimuth_deg")
            if az is not None:
                result[pid] = az
        return result if result else dict(CANONICAL_AZIMUTHS)
    except Exception:
        return dict(CANONICAL_AZIMUTHS)


# ---------------------------------------------------------------------------
# alignment scoring
# ---------------------------------------------------------------------------

def score_alignments(pillar_azimuths: dict[str, float],
                     target_az: float | None,
                     threshold_deg: float = HIT_THRESHOLD_DEG) -> dict:
    """Score how many pillar face azimuths fall within threshold of target_az.
    Respects 180° line symmetry (a pillar facing θ also aligns at θ+180°).
    """
    if target_az is None:
        return {
            "n_pillars": len(pillar_azimuths),
            "n_hits": 0,
            "hit_pillars": [],
            "mean_delta_deg": None,
            "min_delta_deg": None,
            "deltas_deg": [],
            "note": "No target azimuth available",
        }
    azi_list = list(pillar_azimuths.values())
    deltas = []
    hits = []
    for pid, az in pillar_azimuths.items():
        d0 = _angular_delta_deg(az, target_az)
        d180 = _angular_delta_deg(az, (target_az + 180) % 360)
        d = min(d0, d180)
        deltas.append(d)
        if d <= threshold_deg:
            hits.append({"pillar": pid, "azimuth_deg": az, "delta_deg": round(d, 2)})

    return {
        "n_pillars": len(pillar_azimuths),
        "n_hits": len(hits),
        "hit_pillars": hits,
        "mean_delta_deg": round(statistics.fmean(deltas), 2) if deltas else None,
        "min_delta_deg": round(min(deltas), 2) if deltas else None,
        "deltas_deg": [round(d, 2) for d in deltas],
        "threshold_deg": threshold_deg,
    }


# ---------------------------------------------------------------------------
# negative controls
# ---------------------------------------------------------------------------

def _random_azimuths(n: int, rng: rnd.Random) -> list[float]:
    return [rng.uniform(0, 360) for _ in range(n)]


def run_random_azimuth_null(
    pillar_azimuths: dict[str, float],
    target_az: float | None,
    n_trials: int = MONTE_CARLO_TRIALS,
    threshold_deg: float = HIT_THRESHOLD_DEG,
    seed: int = 1996,
) -> dict:
    """Monte Carlo: replace each pillar azimuth with uniform random [0°, 360°)."""
    rng = rnd.Random(seed)
    n = len(pillar_azimuths)
    hit_counts = []
    for _ in range(n_trials):
        rand_az = _random_azimuths(n, rng)
        pid_list = list(pillar_azimuths.keys())
        rand_dict = dict(zip(pid_list, rand_az))
        sc = score_alignments(rand_dict, target_az, threshold_deg)
        hit_counts.append(sc["n_hits"])

    hit_counts.sort()
    n_hits_obs = score_alignments(pillar_azimuths, target_az, threshold_deg)["n_hits"]

    def pct(p: float) -> float:
        if not hit_counts:
            return float("nan")
        k = (len(hit_counts) - 1) * p
        lo = math.floor(k)
        hi = math.ceil(k)
        if lo == hi:
            return hit_counts[int(k)]
        return hit_counts[lo] + (hit_counts[hi] - hit_counts[lo]) * (k - lo)

    extreme = sum(1 for h in hit_counts if h >= n_hits_obs)
    p_value = extreme / n_trials

    null_mean = statistics.fmean(hit_counts)
    null_sd = statistics.pstdev(hit_counts)

    z = (n_hits_obs - null_mean) / null_sd if null_sd > 0 else float("nan")

    return {
        "n_trials": n_trials,
        "observed_hits": n_hits_obs,
        "null_mean_hits": round(null_mean, 3),
        "null_sd_hits": round(null_sd, 3),
        "null_p2_5": pct(0.025),
        "null_p50": pct(0.50),
        "null_p97_5": pct(0.975),
        "z": round(z, 4),
        "p_empirical": round(p_value, 5),
        "threshold_deg": threshold_deg,
    }


def run_scrambled_date_null(
    pillar_azimuths: dict[str, float],
    ra_h: float, dec_deg: float,
    lat: float, lon: float,
    epoch: int,
    n_trials: int = MONTE_CARLO_TRIALS,
    threshold_deg: float = HIT_THRESHOLD_DEG,
    seed: int = 1997,
) -> dict:
    """Monte Carlo: shuffle pillar azimuths across randomly sampled BCE years.
    For each trial, resample the epoch from ~11 000–7 000 BCE, precess the
    Taurid radiant, recompute target azimuth, and score.
    """
    rng = rnd.Random(seed)
    pid_list = list(pillar_azimuths.keys())

    observed_taz = compute_taurid_azimuth(ra_h, dec_deg, lat, lon, epoch)
    observed_target = observed_taz.get("rise_azimuth_deg")
    observed_score = score_alignments(pillar_azimuths, observed_target, threshold_deg)
    n_hits_obs = observed_score["n_hits"]

    hit_counts = []
    for _ in range(n_trials):
        shuffled_az = list(pillar_azimuths.values())
        rng.shuffle(shuffled_az)
        shuffled_dict = dict(zip(pid_list, shuffled_az))

        yr = rng.randint(-11000, -7000)
        p_ra, p_dec, _ = precess_taurid(yr)
        taz = compute_taurid_azimuth(p_ra, p_dec, lat, lon, yr)
        target = taz.get("rise_azimuth_deg")
        sc = score_alignments(shuffled_dict, target, threshold_deg)
        hit_counts.append(sc["n_hits"])

    hit_counts.sort()

    def pct(p: float) -> float:
        if not hit_counts:
            return float("nan")
        k = (len(hit_counts) - 1) * p
        lo = math.floor(k)
        hi = math.ceil(k)
        if lo == hi:
            return hit_counts[int(k)]
        return hit_counts[lo] + (hit_counts[hi] - hit_counts[lo]) * (k - lo)

    extreme = sum(1 for h in hit_counts if h >= n_hits_obs)
    p_value = extreme / n_trials

    null_mean = statistics.fmean(hit_counts)
    null_sd = statistics.pstdev(hit_counts)
    z = (n_hits_obs - null_mean) / null_sd if null_sd > 0 else float("nan")

    return {
        "n_trials": n_trials,
        "epoch_range": "[-11000, -7000]",
        "scrambling": "azimuths shuffled; epoch resampled uniform",
        "observed_hits": n_hits_obs,
        "null_mean_hits": round(null_mean, 3),
        "null_sd_hits": round(null_sd, 3),
        "null_p2_5": pct(0.025),
        "null_p50": pct(0.50),
        "null_p97_5": pct(0.975),
        "z": round(z, 4),
        "p_empirical": round(p_value, 5),
        "threshold_deg": threshold_deg,
    }


# ---------------------------------------------------------------------------
# verdict
# ---------------------------------------------------------------------------

def classify_verdict(random_az_null: dict, scrambled_null: dict,
                     n_pillars: int) -> tuple[str, str]:
    """Assign verdict from null results.  STRICT rule: both controls must
    fail before any ORIENTATION_STRUCTURE is assigned.
    """
    p_rand = random_az_null.get("p_empirical", 1.0)
    p_scram = scrambled_null.get("p_empirical", 1.0)
    z_rand = random_az_null.get("z", 0.0)
    z_scram = scrambled_null.get("z", 0.0)

    p_threshold = 0.01
    z_threshold = 2.6

    beats_rand = p_rand < p_threshold and abs(z_rand) > z_threshold
    beats_scram = p_scram < p_threshold and abs(z_scram) > z_threshold

    if beats_rand and beats_scram:
        return (
            "ORIENTATION_STRUCTURE",
            f"Both controls beaten (random-azimuth p={p_rand}, z={z_rand}; "
            f"scrambled-date p={p_scram}, z={z_scram}). The pillar-Taurid "
            f"alignment separates from random-chance expectation. This is "
            f"structure, not meaning — no claim of intent or celestial encoding.",
        )

    if n_pillars < 6:
        return (
            "UNDERDETERMINED",
            f"Insufficient pillar sample (n={n_pillars} < 6) for a meaningful "
            f"test. Both nulls apply but lack statistical power.",
        )

    return (
        "NO_SIGNAL",
        f"Pillar-Taurid alignment does not beat controls (random-azimuth "
        f"p={p_rand}, z={z_rand}; scrambled-date p={p_scram}, z={z_scram}). "
        f"Consistent with chance. No signal.",
    )


# ---------------------------------------------------------------------------
# probe
# ---------------------------------------------------------------------------

def _check_forbidden(text: str) -> dict:
    found = []
    for phrase in FORBIDDEN_PHRASES:
        if phrase.lower() in text.lower():
            found.append(phrase)
    return {"all_absent": len(found) == 0, "matches": found}


def run_probe(seed: int = 1996, n_trials: int = MONTE_CARLO_TRIALS) -> dict:
    pillar_azimuths = load_pillar_azimuths()
    n_pillars = len(pillar_azimuths)

    ra_epoch, dec_epoch, precess_backend = precess_taurid(EPOCH_YEAR)

    taurid_az = compute_taurid_azimuth(
        ra_epoch, dec_epoch, 37.2231, 38.9223, EPOCH_YEAR,
    )

    target_az = taurid_az.get("rise_azimuth_deg")
    alignment = score_alignments(pillar_azimuths, target_az)

    random_az_null = run_random_azimuth_null(
        pillar_azimuths, target_az, n_trials=n_trials, seed=seed,
    )
    scrambled_null = run_scrambled_date_null(
        pillar_azimuths, ra_epoch, dec_epoch, 37.2231, 38.9223,
        EPOCH_YEAR, n_trials=n_trials, seed=seed + 1,
    )

    verdict, caveat = classify_verdict(random_az_null, scrambled_null, n_pillars)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stance": STANCE,
        "mission": "Hecklefish #5 — Göbekli Tepe × Taurid",
        "site": {
            "lat": 37.2231,
            "lon": 38.9223,
            "elevation_m": 760,
            "epoch_year": EPOCH_YEAR,
        },
        "taurid_radiant": {
            "j2000": {"ra_h": TAURID_RA_H, "dec_deg": TAURID_DEC_DEG},
            "precessed_to_epoch": {
                "ra_h": round(ra_epoch, 4),
                "dec_deg": round(dec_epoch, 2),
                "backend": precess_backend,
            },
            "azimuth_at_site": taurid_az,
        },
        "pillars": {
            "n_loaded": n_pillars,
            "mean_azimuth_deg": round(_mean_angle(list(pillar_azimuths.values())), 2),
            "rayleigh_z": _rayleigh_z(list(pillar_azimuths.values()))[0],
            "file_source": str(DATA / "pillars.json"),
        },
        "alignment": alignment,
        "negative_controls": {
            "random_azimuth_null": random_az_null,
            "scrambled_date_null": scrambled_null,
        },
        "forbidden_words_check": _check_forbidden(json.dumps(locals())),
        "verdict": verdict,
        "caveat": caveat,
    }
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Göbekli Tepe × Taurid radiant alignment test.",
    )
    ap.add_argument("--dry-run", action="store_true",
                    help="Print plan as JSON and exit")
    ap.add_argument("--run", action="store_true",
                    help="Run the full probe (writes outputs/goebekli/)")
    ap.add_argument("--seed", type=int, default=1996,
                    help="RNG seed for Monte Carlo (default: 1996)")
    ap.add_argument("--trials", type=int, default=MONTE_CARLO_TRIALS,
                    help=f"Monte Carlo trials (default: {MONTE_CARLO_TRIALS})")
    ap.add_argument("--quick", action="store_true",
                    help="Fast run with 1 000 trials (for testing)")
    a = ap.parse_args()

    if a.quick:
        a.trials = 1_000

    plan = {
        "status": "ready",
        "stance": STANCE,
        "claim_under_test": "Sweatman & Tsikritsis 2017: Pillar 43 encodes Taurid comet event at ~10 950 BCE",
        "method": "Taurid radiant rise-azimuth at epoch -9600 vs pillar face orientations. Monte Carlo nulls: random-azimuth and scrambled-date.",
        "forbidden": list(FORBIDDEN_PHRASES),
        "reuse": ["tools/astro/astro_probe.py", "data/astro/goebekli/pillars.json"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    if a.dry_run:
        print(json.dumps(plan, indent=2))
        return

    if not a.run:
        print(json.dumps(plan, indent=2))
        print("\nUse --run to execute the probe and write outputs.")
        return

    OUT.mkdir(parents=True, exist_ok=True)
    report = run_probe(seed=a.seed, n_trials=a.trials)

    run_path = OUT / "run.json"
    run_path.write_text(json.dumps(report, indent=2, default=str))
    print(f"wrote {run_path}")

    _write_notes(report)
    notes_path = OUT / "NOTES.md"
    print(f"wrote {notes_path}")

    print(f"\nVerdict: {report['verdict']}")
    print(f"Caveat: {report['caveat']}")


def _write_notes(report: dict) -> None:
    lines = [
        f"# Hecklefish #5 — Göbekli Tepe × Taurid",
        f"",
        f"Generated: {report['generated_at']}",
        f"",
        f"## Stance",
        f"",
        f"{STANCE}",
        f"",
        f"## Claim under test",
        f"",
        f"Sweatman & Tsikritsis (2017): Pillar 43 (Vulture Stone) encodes the",
        f"Taurid comet event at ~10 950 BCE through animal-asterism mapping.",
        f"",
        f"## Site",
        f"",
        f"- Göbekli Tepe, Enclosure D — 37.2231°N, 38.9223°E, 760 m ASL",
        f"- Epoch: {EPOCH_YEAR} BCE (~11 550 cal BP)",
        f"- Pillars in catalogue: {report['pillars']['n_loaded']}",
        f"- Mean pillar azimuth: {report['pillars']['mean_azimuth_deg']}°",
        f"- Rayleigh z (uniformity test): {report['pillars']['rayleigh_z']:.4f}",
        f"",
        f"## Taurid radiant (epoch {EPOCH_YEAR})",
        f"",
        f"- Precessed RA: {report['taurid_radiant']['precessed_to_epoch']['ra_h']} h",
        f"- Precessed Dec: {report['taurid_radiant']['precessed_to_epoch']['dec_deg']}°",
        f"- Backend: {report['taurid_radiant']['precessed_to_epoch']['backend']}",
    ]
    taz = report["taurid_radiant"]["azimuth_at_site"]
    lines.append(f"- Rise azimuth: {taz.get('rise_azimuth_deg', 'N/A')}°")
    lines.append(f"- Rise possible: {taz.get('rise_possible', 'N/A')}")
    lines.append(f"")

    lines.append(f"## Alignment")
    ali = report["alignment"]
    lines.append(f"- Threshold: {ali['threshold_deg']}°")
    lines.append(f"- Hits: {ali['n_hits']}/{ali['n_pillars']}")
    lines.append(f"- Mean Δ: {ali['mean_delta_deg']}°")
    lines.append(f"- Min Δ: {ali['min_delta_deg']}°")
    lines.append(f"- Hit pillars:")
    for hp in ali["hit_pillars"]:
        lines.append(f"  - {hp['pillar']}: face {hp['azimuth_deg']}° Δ={hp['delta_deg']}°")
    lines.append(f"")

    lines.append(f"## Negative controls")
    for null_name in ("random_azimuth_null", "scrambled_date_null"):
        nul = report["negative_controls"][null_name]
        lines.append(f"")
        lines.append(f"### {null_name}")
        lines.append(f"- Trials: {nul['n_trials']}")
        lines.append(f"- Observed hits: {nul['observed_hits']}")
        lines.append(f"- Null mean hits: {nul['null_mean_hits']}")
        lines.append(f"- Null SD: {nul['null_sd_hits']}")
        lines.append(f"- 95% band: [{nul['null_p2_5']}, {nul['null_p97_5']}]")
        lines.append(f"- z: {nul['z']}")
        lines.append(f"- p (empirical): {nul['p_empirical']}")
    lines.append(f"")

    fw = report["forbidden_words_check"]
    lines.append(f"Forbidden words: {'PASS' if fw['all_absent'] else 'FAIL'}")
    lines.append(f"")

    lines.append(f"## Verdict")
    lines.append(f"")
    lines.append(f"**{report['verdict']}**")
    lines.append(f"")
    lines.append(f"{report['caveat']}")
    lines.append(f"")

    lines.append(f"---")
    lines.append(f"*Göbekli Tepe × Taurid — structure ≠ message. Apophenia is the null. No claim of intent or celestial encoding.*")

    (OUT / "NOTES.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
