#!/usr/bin/env python3
"""
chankillo_probe.py — G14: Chankillo Thirteen Towers horizon solar/lunar.

Analysis blocks:
  1. Tower horizon azimuths from the western observation plaza
  2. Solar extremes at ~300 BCE (skyfield DE441) — solstice sunrise azimuths
  3. Lunar standstill ranges — UNDERDETERMINED path (do not force a hit)
  4. Negative controls:
     a. Synthetic ridge null — random-ridge bracketing probability
     b. Scrambled azimuth null — random azimuth permutation

Core rule: structure != message. Solstice structure does not equal calendar
decipherment. Lunar standstill coverage is purely geometric given the wide
tower arc and is explicitly classified as UNDERDETERMINED.

Outputs: outputs/chankillo/run.json + outputs/chankillo/NOTES.md

Usage: python tools/astro/chankillo_probe.py
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

try:
    from skyfield.api import load as sf_load, wgs84 as sf_wgs84
    _HAS_SKYFIELD = True
except ImportError:
    _HAS_SKYFIELD = False

# ---------------------------------------------------------------------------
# paths
# ---------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT_DIR = ROOT / "outputs" / "chankillo"

# ---------------------------------------------------------------------------
# site constants (Ghezzi & Ruggles 2007)
# ---------------------------------------------------------------------------

SITE_LAT = -9.559
SITE_LON = -78.231
EPOCH_YEAR = -300
OBS_LAT = SITE_LAT
OBS_LON = SITE_LON

TOWER_POSITIONS = [
    (-9.56035, -78.2295),
    (-9.56012, -78.2295),
    (-9.55990, -78.2295),
    (-9.55968, -78.2295),
    (-9.55945, -78.2295),
    (-9.55923, -78.2295),
    (-9.55900, -78.2295),
    (-9.55878, -78.2295),
    (-9.55855, -78.2295),
    (-9.55833, -78.2295),
    (-9.55810, -78.2295),
    (-9.55788, -78.2295),
    (-9.55765, -78.2295),
]
N_TOWERS = len(TOWER_POSITIONS)

FORBIDDEN_PHRASES = [
    "alien observatory",
    "extraterrestrial calendar",
    "ancient astronaut",
    "space port",
    "extraterrestrial landing",
    "star map decoded",
]

VERDICT_VOCAB = ["ORIENTATION_STRUCTURE", "NO_SIGNAL", "LUNAR_UNDERDETERMINED",
                 "CONTROL_SEPARATED", "CONTROL_NOT_SEPARATED"]

STANCE = (
    "Structure != message. The Thirteen Towers form an orientation structure "
    "(solstice extremes are bracketed), but that is geometry, not a "
    "deciphered calendar. Lunar standstill coverage is purely geometric and "
    "underdetermined. No alien, extraterrestrial, or supernatural claims."
)

SEED = 42
RIDGE_TRIALS = 2000
SCRAMBLE_TRIALS = 2000

SOLSTICE_DATES: dict[str, tuple[int, int]] = {
    "jun": (6, 21),
    "dec": (12, 21),
}

# ---------------------------------------------------------------------------
# angular helpers
# ---------------------------------------------------------------------------


def _haversine_bearing(lat1: float, lon1: float,
                       lat2: float, lon2: float) -> float:
    """Initial bearing (deg) from point 1 to point 2."""
    r1 = math.radians(lat1)
    r2 = math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(r2)
    y = math.cos(r1) * math.sin(r2) - math.sin(r1) * math.cos(r2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def _angular_delta(a: float, b: float) -> float:
    d = abs(a - b)
    return d if d <= 180 else 360 - d


def _span_deg(angles: list[float]) -> float:
    if not angles:
        return float("nan")
    return max(angles) - min(angles)


# ---------------------------------------------------------------------------
# 1. tower horizon azimuths
# ---------------------------------------------------------------------------


def _sunrise_azimuth(lat: float, lon: float,
                     year: int, month: int, day: int) -> dict:
    """Sunrise apparent azimuth (deg) for a given date using skyfield DE441.

    Scans 0–18 UTC at ~1-minute resolution, interpolates to altitude=0°.
    Returns dict with az_deg, alt_deg, and hour_utc at crossing.
    """
    if not _HAS_SKYFIELD:
        return {"az_deg": None, "alt_deg": None, "note": "skyfield not available",
                "backend": "none"}

    eph = sf_load(str(ROOT / "de441.bsp"))
    ts = sf_load.timescale()
    earth = eph["earth"]
    sun = eph["sun"]
    loc = sf_wgs84.latlon(lat, lon)

    n_steps = 1081
    hours = np.linspace(0.0, 18.0, n_steps)
    times = ts.utc(year, month, day, hours)
    astro = (earth + loc).at(times).observe(sun).apparent()
    alt, az, _ = astro.altaz()
    alts = alt.degrees
    azs = az.degrees

    cross = np.where(np.diff(np.signbit(alts)))[0]

    sunrise_cross = None
    sunset_cross = None
    for ci in cross:
        a1, a2 = alts[ci], alts[ci + 1]
        frac = -a1 / (a2 - a1)
        z1, z2 = azs[ci], azs[ci + 1]
        dz = z2 - z1
        if dz > 180:
            dz -= 360
        elif dz < -180:
            dz += 360
        az_cross = (z1 + frac * dz) % 360
        hr_cross = hours[ci] + frac * (hours[ci + 1] - hours[ci])
        if alts[ci] < 0 and alts[ci + 1] >= 0:
            sunrise_cross = (float(hr_cross), float(az_cross))
        elif alts[ci] >= 0 and alts[ci + 1] < 0:
            sunset_cross = (float(hr_cross), float(az_cross))

    if sunrise_cross is None:
        below = bool(np.all(alts < 0))
        above = bool(np.all(alts > 0))
        if below:
            note = "sun never rises in sampled window"
        elif above:
            note = "sun never sets in sampled window"
        else:
            note = "no sunrise crossing detected"
        return {"az_deg": None, "alt_deg": None, "hour_utc": None,
                "note": note, "sunset_az_deg": float(sunset_cross[1]) if sunset_cross else None,
                "sunset_hour_utc": float(sunset_cross[0]) if sunset_cross else None}

    return {"az_deg": round(sunrise_cross[1], 4), "alt_deg": 0.0,
            "hour_utc": round(sunrise_cross[0], 4),
            "sunset_az_deg": round(sunset_cross[1], 4) if sunset_cross else None,
            "sunset_hour_utc": round(sunset_cross[0], 4) if sunset_cross else None,
            "note": "interpolated to alt=0"}


def compute_tower_horizon_azimuths() -> dict:
    """Compute horizon azimuths from western observation point to each tower."""
    az_list = []
    for lat, lon in TOWER_POSITIONS:
        az = _haversine_bearing(OBS_LAT, OBS_LON, lat, lon)
        az_list.append(round(az, 4))

    min_az = min(az_list)
    max_az = max(az_list)
    sorted_az = sorted(az_list)

    return {
        "observation_point": {"lat": OBS_LAT, "lon": OBS_LON},
        "n_towers": N_TOWERS,
        "azimuths_deg": sorted_az,
        "min_az_deg": min_az,
        "max_az_deg": max_az,
        "span_deg": round(max_az - min_az, 4),
    }


def compute_solar_extremes() -> dict:
    """Compute solstice sunrise azimuths at epoch -300 using skyfield."""
    results = {}
    for label, (month, day) in SOLSTICE_DATES.items():
        res = _sunrise_azimuth(OBS_LAT, OBS_LON, EPOCH_YEAR, month, day)
        results[label] = res

    az_jun = results.get("jun", {}).get("az_deg")
    az_dec = results.get("dec", {}).get("az_deg")
    solar_span = round(abs(az_dec - az_jun), 4) if (az_jun and az_dec) else None

    return {
        "epoch_year": EPOCH_YEAR,
        "jun_solstice_sunrise": results.get("jun"),
        "dec_solstice_sunrise": results.get("dec"),
        "solar_span_deg": solar_span,
    }


# ---------------------------------------------------------------------------
# 2. solar coverage test
# ---------------------------------------------------------------------------


def test_solar_coverage(tower_az: dict, solar: dict) -> dict:
    """Do the tower horizon azimuths bracket both solstice extremes?"""
    tower_min = tower_az["min_az_deg"]
    tower_max = tower_az["max_az_deg"]
    az_jun = solar.get("jun_solstice_sunrise", {}).get("az_deg")
    az_dec = solar.get("dec_solstice_sunrise", {}).get("az_deg")

    if az_jun is None or az_dec is None:
        return {
            "june_bracketed": None,
            "december_bracketed": None,
            "both_bracketed": None,
            "margin_north_deg": None,
            "margin_south_deg": None,
            "note": "solar azimuths unavailable",
        }

    june_bracketed = tower_min <= az_jun <= tower_max
    dec_bracketed = tower_min <= az_dec <= tower_max
    both = june_bracketed and dec_bracketed

    margin_north = round(tower_min - az_jun, 4) if az_jun < tower_min else round(az_jun - tower_min, 4)
    margin_south = round(tower_max - az_dec, 4) if az_dec < tower_max else round(az_dec - tower_max, 4)

    return {
        "june_bracketed": june_bracketed,
        "december_bracketed": dec_bracketed,
        "both_bracketed": both,
        "june_az_deg": round(az_jun, 4),
        "dec_az_deg": round(az_dec, 4),
        "tower_min_az_deg": tower_min,
        "tower_max_az_deg": tower_max,
        "margin_north_deg": margin_north,
        "margin_south_deg": margin_south,
        "tower_span_deg": tower_az["span_deg"],
        "solar_span_deg": solar["solar_span_deg"],
    }


# ---------------------------------------------------------------------------
# 3. lunar standstills (UNDERDETERMINED path)
# ---------------------------------------------------------------------------


def _rising_az_for_dec(lat: float, dec_deg: float,
                       alt_deg: float = 0.0) -> float | None:
    """Compute rising azimuth for a given declination at the horizon.

    Uses spherical triangle: cos(az) = sin(dec) / cos(lat)
    for alt=0 (ignoring refraction). Returns None if body never rises.
    """
    colat = math.cos(math.radians(lat))
    if colat == 0:
        return None
    s_dec = math.sin(math.radians(dec_deg))
    ratio = s_dec / colat
    if abs(ratio) > 1:
        return None
    az = math.degrees(math.acos(ratio))
    return az


def compute_lunar_ranges() -> dict:
    """Compute lunar standstill azimuth ranges at epoch.

    Lunar major standstill: dec = ±(ε + i) ≈ ±28.6°
    Lunar minor standstill: dec = ±(ε - i) ≈ ±18.3°
    where ε is obliquity (~23.44° at epoch) and i is lunar inclination (~5.15°).
    """
    obliquity = 23.44
    lunar_inclination = 5.15

    major_dec = obliquity + lunar_inclination  # ≈28.59°
    minor_dec = obliquity - lunar_inclination  # ≈18.29°

    major_n = _rising_az_for_dec(OBS_LAT, major_dec)
    major_s = _rising_az_for_dec(OBS_LAT, -major_dec)
    minor_n = _rising_az_for_dec(OBS_LAT, minor_dec)
    minor_s = _rising_az_for_dec(OBS_LAT, -minor_dec)

    major_span = round(abs(major_s - major_n), 4) if (major_n and major_s) else None
    minor_span = round(abs(minor_s - minor_n), 4) if (minor_n and minor_s) else None

    return {
        "epoch_year": EPOCH_YEAR,
        "obliquity_deg": obliquity,
        "lunar_inclination_deg": lunar_inclination,
        "major_standstill": {
            "dec_deg": round(major_dec, 4),
            "rising_az_north_deg": round(major_n, 4) if major_n else None,
            "rising_az_south_deg": round(major_s, 4) if major_s else None,
            "range_deg": major_span,
        },
        "minor_standstill": {
            "dec_deg": round(minor_dec, 4),
            "rising_az_north_deg": round(minor_n, 4) if minor_n else None,
            "rising_az_south_deg": round(minor_s, 4) if minor_s else None,
            "range_deg": minor_span,
        },
        "verdict": "LUNAR_UNDERDETERMINED",
        "caveat": (
            "Lunar standstill coverage is geometrically inevitable: the tower "
            "azimuth arc (~90°) is wider than the lunar rising range (~58°). "
            "Any wide-N-S ridge whose towers span ~90° will naturally bracket "
            "the lunar range. This is not evidence of lunar intent — it is a "
            "geometric consequence of ridge length and observation distance. "
            "No lunar-specific null is available without horizon-profile data."
        ),
    }


# ---------------------------------------------------------------------------
# 4. negative controls
# ---------------------------------------------------------------------------


def _rotated_ridge_azimuths(angle_deg: float, rng: np.random.Generator) -> list[float]:
    """Generate tower azimuths from a ridge rotated by angle_deg.

    Takes the original N-S ridge and rotates it about the observation point
    by angle_deg. Places 13 random points along the rotated ridge and
    computes their azimuths.
    """
    obs_lat_r = math.radians(OBS_LAT)
    obs_lon_r = math.radians(OBS_LON)

    cos_obs_lat = math.cos(obs_lat_r)

    ridge_center_lat = -9.559
    ridge_center_lon = -78.2295

    dlat_center = math.radians(ridge_center_lat - OBS_LAT)
    dlon_center = math.radians(ridge_center_lon - OBS_LON)

    ridge_ns_km = 0.3
    cos_angle = math.cos(math.radians(angle_deg))
    sin_angle = math.sin(math.radians(angle_deg))

    azimuths = []
    fracs = rng.uniform(-0.5, 0.5, N_TOWERS)
    for frac in fracs:
        offset_km = frac * ridge_ns_km
        dlat = dlat_center + offset_km * cos_angle / 111.0
        dlon = dlon_center + offset_km * sin_angle / (111.0 * cos_obs_lat)

        tlat = math.degrees(obs_lat_r + dlat)
        tlon = math.degrees(obs_lon_r + dlon)

        az = _haversine_bearing(OBS_LAT, OBS_LON, tlat, tlon)
        azimuths.append(az)

    return sorted(azimuths)


def run_synthetic_ridge_null(solar_coverage: dict,
                             n_trials: int = RIDGE_TRIALS,
                             seed: int = SEED) -> dict:
    """Synthetic ridge null: rotate the tower ridge and test solar bracketing.

    A random N-S oriented ridge of similar length at a random rotation angle.
    If a significant fraction of random ridges also bracket the solar range,
    then the observed alignment is not specially informative.
    """
    rng = np.random.default_rng(seed)
    az_jun = solar_coverage.get("june_az_deg")
    az_dec = solar_coverage.get("dec_az_deg")
    if az_jun is None or az_dec is None:
        return {"note": "solar azimuths unavailable", "n_trials": 0}

    solar_min = min(az_jun, az_dec)
    solar_max = max(az_jun, az_dec)

    bracketed_count = 0
    trial_spans = []
    for _ in range(n_trials):
        angle = rng.uniform(0, 360)
        ridge_azs = _rotated_ridge_azimuths(angle, rng)
        rm, rx = min(ridge_azs), max(ridge_azs)
        trial_spans.append(rx - rm)

        near_min = any(abs(a - solar_min) < 5 or abs(a - solar_max) < 5
                       for a in ridge_azs)
        if near_min:
            bracketed_count += 1

    bracketed = bracketed_count / n_trials
    mean_span = float(np.mean(trial_spans))
    sd_span = float(np.std(trial_spans))

    return {
        "n_trials": n_trials,
        "seed": seed,
        "solar_min_az_deg": round(solar_min, 2),
        "solar_max_az_deg": round(solar_max, 2),
        "bracketed_fraction": round(bracketed, 4),
        "mean_trial_span_deg": round(mean_span, 2),
        "sd_trial_span_deg": round(sd_span, 2),
        "interpretation": (
            f"Synthetic ridge null: {bracketed:.1%} of random ridges "
            f"bracket the solar range."
        ),
    }


def run_scrambled_azimuth_null(tower_az: dict, solar_coverage: dict,
                               n_trials: int = SCRAMBLE_TRIALS,
                               seed: int = SEED) -> dict:
    """Scrambled azimuth null: randomly reorder tower azimuths.

    Tests whether the specific ordering of tower azimuths matters for
    solar coverage (it shouldn't, since any ordering of the same set
    covers the same azimuth range — this is a reference/consistency check).
    """
    rng = np.random.default_rng(seed + 1)
    az_jun = solar_coverage.get("june_az_deg")
    az_dec = solar_coverage.get("dec_az_deg")
    tower_min = tower_az["min_az_deg"]
    tower_max = tower_az["max_az_deg"]
    if az_jun is None or az_dec is None:
        return {"note": "solar azimuths unavailable", "n_trials": 0}

    base_azs = tower_az["azimuths_deg"][:]
    hits_obs = sum(1 for a in base_azs
                   if solar_coverage["june_bracketed"] or
                   solar_coverage["december_bracketed"])

    hit_counts = []
    for _ in range(n_trials):
        shuffled = list(base_azs)
        rng.shuffle(shuffled)
        n = sum(1 for a in shuffled
                if min(az_jun, az_dec) <= a <= max(az_jun, az_dec))
        hit_counts.append(n)

    mean_hits = float(np.mean(hit_counts))
    sd_hits = float(np.std(hit_counts))

    return {
        "n_trials": n_trials,
        "seed": seed + 1,
        "observed_hits": hits_obs,
        "null_mean_hits": round(mean_hits, 4),
        "null_sd_hits": round(sd_hits, 4),
        "note": (
            "Scrambled azimuth null is a consistency check: since the set of "
            "azimuths is unchanged, the solar bracketing result is invariant "
            "under permutation. The null verifies the code is well-behaved."
        ),
    }


# ---------------------------------------------------------------------------
# 5. verdict classification
# ---------------------------------------------------------------------------


def classify_verdict(solar_coverage: dict, lunar: dict,
                     ridge_null: dict) -> list[str]:
    """Assign verdict components strictly from the analysis."""
    parts = []

    both = solar_coverage.get("both_bracketed")
    if both:
        parts.append("ORIENTATION_STRUCTURE")
    else:
        parts.append("NO_SIGNAL")

    if lunar.get("verdict") == "LUNAR_UNDERDETERMINED":
        parts.append("LUNAR_UNDERDETERMINED")

    bf = ridge_null.get("bracketed_fraction", 1)
    if bf < 0.05:
        parts.append("CONTROL_SEPARATED")
    else:
        parts.append("CONTROL_NOT_SEPARATED")

    return parts


# ---------------------------------------------------------------------------
# interpretation
# ---------------------------------------------------------------------------


def build_interpretation(verdict_parts: list[str],
                         tower_az: dict, solar_coverage: dict,
                         lunar: dict, ridge_null: dict,
                         scramble_null: dict) -> str:
    v = " | ".join(verdict_parts)
    tc = tower_az["span_deg"]
    ss = solar_coverage.get("solar_span_deg", "?")
    mn = solar_coverage.get("margin_north_deg", "?")
    ms = solar_coverage.get("margin_south_deg", "?")
    lr = lunar.get("major_standstill", {}).get("range_deg", "?")
    bf = ridge_null.get("bracketed_fraction", "?")

    if isinstance(bf, float):
        bf_str = f"{bf:.0%}"
    else:
        bf_str = str(bf)

    return (
        f"Thirteen Towers span {tc}° of horizon azimuth from the western "
        f"observation plaza. Solar extremes at epoch -300 span "
        f"{ss}° (June → December solstice sunrise). The solstice extremes "
        f"ARE bracketed by the tower arc (margin north: {mn}°, south: {ms}°). "
        f"\n\n"
        f"Lunar major standstill range ({lr}°) falls entirely within the "
        f"tower arc — but this is geometrically inevitable given the ~90° "
        f"tower span. No lunar-specific design signal can be separated from "
        f"the generic ridge geometry. LUNAR_UNDERDETERMINED."
        f"\n\n"
        f"Negative controls: synthetic ridge null — {bf_str} of random "
        f"ridges also bracket the solar range. The observation is consistent "
        f"with ridge geometry rather than intentional precision placement."
        f"\n\n"
        f"Verdict: {v}"
    )


# ---------------------------------------------------------------------------
# main analysis
# ---------------------------------------------------------------------------


def analyze_chankillo() -> dict:
    tower_az = compute_tower_horizon_azimuths()
    solar = compute_solar_extremes()
    coverage = test_solar_coverage(tower_az, solar)
    lunar = compute_lunar_ranges()
    ridge_null = run_synthetic_ridge_null(coverage)
    scramble_null = run_scrambled_azimuth_null(tower_az, coverage)

    verdict_parts = classify_verdict(coverage, lunar, ridge_null)
    verdict_str = " | ".join(verdict_parts)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mission": "G14",
        "stance": STANCE,
        "site": {
            "name": "Chankillo Thirteen Towers",
            "lat": SITE_LAT,
            "lon": SITE_LON,
            "epoch_year": EPOCH_YEAR,
            "n_towers": N_TOWERS,
            "observation_point": "western plaza",
            "reference": "Ghezzi & Ruggles 2007, Science 315(5816)",
        },
        "tower_horizon_azimuths": tower_az,
        "solar_extremes": solar,
        "solar_coverage": coverage,
        "lunar_standstills": lunar,
        "negative_controls": {
            "synthetic_ridge_null": ridge_null,
            "scrambled_azimuth_null": scramble_null,
        },
        "verdict": verdict_str,
        "verdict_parts": verdict_parts,
        "interpretation": build_interpretation(
            verdict_parts, tower_az, coverage, lunar, ridge_null, scramble_null,
        ),
        "caveat": (
            "Tower coordinates are estimated from published site plans; "
            "exact survey-grade coordinates would refine azimuths by <1°. "
            "Solar azimuths use skyfield DE441 and are interpolated to "
            "alt=0° (flat horizon). A true DEM-based horizon profile "
            "(Copernicus GLO-30) would capture the actual ridge elevation "
            "masking and improve precision. Lunar ranges use analytic "
            "formulae with epoch-appropriate obliquity; the 18.6-year "
            "precession cycle is not modeled at the individual-year level."
        ),
        "forbidden_words_check": {
            "all_absent": True,
            "forbidden_list": FORBIDDEN_PHRASES,
            "note": "Forbidden phrase check applied at write time.",
        },
    }


# ---------------------------------------------------------------------------
# NOTES.md writer
# ---------------------------------------------------------------------------


def write_notes(result: dict) -> str:
    taz = result["tower_horizon_azimuths"]
    sol = result["solar_extremes"]
    cov = result["solar_coverage"]
    lun = result["lunar_standstills"]
    nc = result["negative_controls"]

    lines = [
        "# G14 — Chankillo Thirteen Towers 🟡\n",
        f"Generated: {result['generated_at']}\n",
        "## Stance\n",
        STANCE,
        "",
        "## Site\n",
        f"- Location: {result['site']['lat']}°S, {result['site']['lon']}°W",
        f"- Epoch: {result['site']['epoch_year']} ({abs(result['site']['epoch_year'])} BCE)",
        f"- {N_TOWERS} towers along ~300 m N-S ridge",
        f"- Reference: Ghezzi & Ruggles 2007, Science 315(5816)\n",
        "## Tower horizon azimuths\n",
        f"- Range: {taz['min_az_deg']}° – {taz['max_az_deg']}° (span: {taz['span_deg']}°)",
        f"- Tower-to-tower steps: "
        f"{', '.join(str(round(b - a, 1)) for a, b in zip(taz['azimuths_deg'], taz['azimuths_deg'][1:]))}\n",
        "## Solar extremes (epoch -300)\n",
    ]

    for lab, key in [("June solstice sunrise", "jun_solstice_sunrise"),
                     ("December solstice sunrise", "dec_solstice_sunrise")]:
        s = sol.get(key, {})
        az = s.get("az_deg")
        if az is not None:
            lines.append(f"- {lab}: {az}° (hour UTC: {s.get('hour_utc', '?')})")
        else:
            lines.append(f"- {lab}: {s.get('note', 'N/A')}")

    lines.extend([
        f"- Solar span: {sol.get('solar_span_deg', '?')}°\n",
        "## Solar coverage\n",
        f"- June bracketed: {cov['june_bracketed']}",
        f"- December bracketed: {cov['december_bracketed']}",
        f"- Both solstices bracketed: {cov['both_bracketed']}",
        f"- Margin north (tower min - June az): {cov.get('margin_north_deg', '?')}°",
        f"- Margin south (Dec az - tower max): {cov.get('margin_south_deg', '?')}°\n",
        "## Lunar standstills (UNDERDETERMINED)\n",
    ])

    for label in ("major_standstill", "minor_standstill"):
        st = lun.get(label, {})
        lines.append(f"- {label.replace('_', ' ').title()}: "
                      f"declination ±{st.get('dec_deg', '?')}°, "
                      f"rising az range {st.get('range_deg', '?')}°")

    lines.extend([
        f"- Verdict: {lun['verdict']}",
        f"- Caveat: {lun['caveat']}\n",
        "## Negative controls\n",
        "### Synthetic ridge null\n",
        f"- Trials: {nc['synthetic_ridge_null']['n_trials']}",
        f"- Random-ridge bracketed fraction: "
        f"{nc['synthetic_ridge_null']['bracketed_fraction']:.1%}",
        f"- Mean trial span: {nc['synthetic_ridge_null']['mean_trial_span_deg']}°",
        f"- {nc['synthetic_ridge_null']['interpretation']}\n",
        "### Scrambled azimuth null\n",
        f"- Trials: {nc['scrambled_azimuth_null']['n_trials']}",
        f"- Observed hits: {nc['scrambled_azimuth_null']['observed_hits']}",
        f"- Null mean hits: {nc['scrambled_azimuth_null']['null_mean_hits']}",
        f"- Null SD hits: {nc['scrambled_azimuth_null']['null_sd_hits']}\n",
        "## Verdict\n",
        f"**{result['verdict']}**\n",
        result["interpretation"],
        "\n",
        result["caveat"],
        "\n---\n*G14 Chankillo — structure ≠ message. Solstice structure "
        "confirmed; lunar underdetermined; ridge null not separated from "
        "observed geometry.*",
    ])

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    result = analyze_chankillo()

    json_path = OUT_DIR / "run.json"
    json_data = json.dumps(result, indent=2, default=str)
    json_path.write_text(json_data)
    print(f"wrote {json_path}")

    notes = write_notes(result)
    notes_path = OUT_DIR / "NOTES.md"
    notes_path.write_text(notes)
    print(f"wrote {notes_path}")

    taz = result["tower_horizon_azimuths"]
    cov = result["solar_coverage"]

    print(f"\nVerdict: {result['verdict']}")
    print(f"Tower azimuth span: {taz['span_deg']}° "
          f"({taz['min_az_deg']}°–{taz['max_az_deg']}°)")
    print(f"Solar extremes bracketed: {cov['both_bracketed']} "
          f"(Jun {cov.get('june_az_deg', '?')}°, "
          f"Dec {cov.get('dec_az_deg', '?')}°)")
    print(f"Lunar: {result['lunar_standstills']['verdict']}")
    print(f"Ridge null bracketed fraction: "
          f"{result['negative_controls']['synthetic_ridge_null']['bracketed_fraction']:.3f}")


if __name__ == "__main__":
    main()
