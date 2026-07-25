"""astro_probe — solstice / lunar / star-rise archaeoastronomy (N4).

Backends (in priority order):
  skyfield  — JPL DE440 ephemeris; handles BCE years natively (best)
  astropy   — good for years 0–3000 CE
  fallback  — analytic approximation for any year

CLI:
  python tools/astro/astro_probe.py --out outputs/astro/run.json
  python tools/astro/astro_probe.py --backend skyfield --out outputs/astro/run.json
  python tools/astro/astro_probe.py --backend fallback --out outputs/astro/run.json
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random as rnd
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# backend availability
# ---------------------------------------------------------------------------

try:
    from skyfield.api import load as _sf_load, wgs84 as _sf_wgs84

    _sf_data_dir = Path(__file__).resolve().parents[2]  # repo root
    _sf_load.directory = str(_sf_data_dir)
    _sf_eph = _sf_load("de441.bsp")
    _sf_ts = _sf_load.timescale()
    HAS_SKYFIELD = True
except Exception:
    _sf_eph = None
    _sf_ts = None
    HAS_SKYFIELD = False

try:
    import astropy.units as u
    from astropy.coordinates import (
        AltAz, EarthLocation, FK5, get_body, get_sun, SkyCoord,
    )
    from astropy.time import Time

    HAS_ASTROPY = True
except ImportError:
    HAS_ASTROPY = False

try:
    import elevation as _elevation
    HAS_ELEVATION = True
except ImportError:
    HAS_ELEVATION = False

try:
    import rasterio as _rasterio
    HAS_RASTERIO = True
except ImportError:
    HAS_RASTERIO = False

BACKENDS = ("skyfield", "astropy", "fallback")

# Deep BCE threshold — proleptic Gregorian calendar labels become unreliable
DEEP_BCE_THRESHOLD = -2000

# ---------------------------------------------------------------------------
# site database with documented monument axis bearings
# ---------------------------------------------------------------------------
# Axis conventions:
#   - bearing_deg: direction the monument faces (0 = N, 90 = E, 180 = S, 270 = W)
#   - Line symmetry: an axis at θ also aligns at θ + 180°
#   - None = no single well-documented astronomical axis

SITES = {
    "gobekli_tepe": {
        "lat": 37.2231, "lon": 38.9223, "elevation_m": 760,
        "epoch_year": -9600,
        "note": "Göbekli Tepe, earliest known temple complex; Enclosure D",
        "axis_bearing_deg": None,
        "axis_citation": None,
        "axis_note": "No single well-documented astronomical axis for Enclosure D. Report sun azimuth only.",
    },
    "stonehenge": {
        "lat": 51.1789, "lon": -1.8262, "elevation_m": 100,
        "epoch_year": -2500,
        "note": "Stonehenge phase 3; heel stone solstice alignment",
        "axis_bearing_deg": 51.0,
        "axis_citation": "Ruggles, 'Astronomy in Prehistoric Britain and Ireland' (1999): axis through heel stone ~51° NE, aligned with summer solstice sunrise",
    },
    "giza_khufu": {
        "lat": 29.9792, "lon": 31.1342, "elevation_m": 60,
        "epoch_year": -2560,
        "note": "Great Pyramid of Khufu; shafts align with Orion/Thuban",
        "axis_bearing_deg": None,
        "axis_citation": None,
        "axis_note": "Pyramid faces are cardinal (N-S / E-W); air shafts point to Orion/Thuban but are not a single monument axis.",
    },
    "chichen_itza": {
        "lat": 20.6843, "lon": -88.5678, "elevation_m": 30,
        "epoch_year": 800,
        "note": "El Castillo; equinox serpent shadow",
        "axis_bearing_deg": 287.0,
        "axis_citation": "Šprajc, 'Astronomy, Architecture, and Landscape in Prehispanic Mesoamerica' (2018): El Castillo NW staircase ~287°, equinox sunset serpent effect",
    },
}

STARS = {
    "sirius":         {"name": "Sirius (α CMa)",      "ra_j2000_h": 6.752, "dec_j2000_deg": -16.716},
    "pleiades":       {"name": "Pleiades (Alcyone)",  "ra_j2000_h": 3.783, "dec_j2000_deg": 24.117},
    "orion_betelgeuse":{"name": "Betelgeuse (α Ori)",  "ra_j2000_h": 5.919, "dec_j2000_deg": 7.407},
    "orion_rigel":    {"name": "Rigel (β Ori)",       "ra_j2000_h": 5.242, "dec_j2000_deg": -8.202},
    "orion_belt":     {"name": "Orion's Belt (Alnitak)","ra_j2000_h": 5.683, "dec_j2000_deg": -1.942},
}

# Hipparcos number lookup for Skyfield star positions
STARS_HIP = {
    "sirius":          32349,
    "pleiades":        25930,  # Alcyone
    "orion_betelgeuse": 27989,
    "orion_rigel":      24436,
    "orion_belt":       26727,  # Alnitak
}

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _resolve_backend(requested: str) -> str:
    if requested == "auto":
        if HAS_SKYFIELD:
            return "skyfield"
        if HAS_ASTROPY:
            return "astropy"
        return "fallback"
    if requested == "skyfield" and not HAS_SKYFIELD:
        print("Skyfield not installed, falling back to astropy", file=sys.stderr)
        return "astropy" if HAS_ASTROPY else "fallback"
    if requested == "astropy" and not HAS_ASTROPY:
        print("Astropy not installed, falling back to analytic", file=sys.stderr)
        return "fallback"
    return requested


def _jd(year: int, month: int, day: int, hour: float = 0) -> float:
    """Julian Day Number for any year (incl. BCE)."""
    if month <= 2:
        year -= 1
        month += 12
    a = int(year / 100)
    b = 2 - a + int(a / 4)
    jd_midnight = int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + b - 1524.5
    return jd_midnight + hour / 24.0


# ---------------------------------------------------------------------------
# skyfield backend
# ---------------------------------------------------------------------------

if HAS_SKYFIELD:

    def _skyfield_ymd(t) -> tuple:
        """Return (year, month, day) from a Skyfield Time, handling BCE."""
        cal = t.tt_calendar()
        return int(cal[0]), int(cal[1]), int(cal[2])

    def _solar_lon_skyfield(t) -> float:
        """Ecliptic longitude of the Sun (degrees) at Skyfield time t."""
        earth = _sf_eph["earth"]
        sun = _sf_eph["sun"]
        astro = earth.at(t).observe(sun).apparent()
        _, lon, _ = astro.ecliptic_latlon()
        return lon.degrees % 360

    def _find_next_lon_crossing(t0, target_lon: float):
        """Search forward from t0 to find when solar longitude crosses target_lon.
        Scans a window based on mean solar motion (~1°/day forward).
        """
        y0, m0, d0 = _skyfield_ymd(t0)
        lon0 = _solar_lon_skyfield(t0)
        delta = (target_lon - lon0 + 360) % 360
        est_days = int(delta)
        for offset in range(max(0, est_days - 15), est_days + 15):
            t = _sf_ts.utc(y0, m0, d0 + offset)
            lon = _solar_lon_skyfield(t)
            dlon = (lon - target_lon + 180) % 360 - 180
            if abs(dlon) < 0.5:
                return t
        return t

    def _solstice_equinox_skyfield(year: int) -> dict:
        """Find solstice/equinox using JPL DE441 (BCE-capable).
        Searches forward from Jan 1 of the epoch year through all four
        ecliptic longitude crossings (0°, 90°, 180°, 270°).
        Validates each crossing by computing solar longitude at found time.
        """
        targets = [
            ("mar_equinox", 0.0),
            ("jun_solstice", 90.0),
            ("sep_equinox", 180.0),
            ("dec_solstice", 270.0),
        ]
        result = {"year": year, "backend": "skyfield"}
        t = _sf_ts.utc(year, 1, 1)
        for name, target_lon in targets:
            t_found = _find_next_lon_crossing(t, target_lon)
            y, mo, d = _skyfield_ymd(t_found)
            cal = t_found.tt_calendar()
            h, mi, s = int(cal[3]), int(cal[4]), int(cal[5])
            jd = _jd(y, mo, d, h + mi / 60 + s / 3600)
            doy = int(_jd(y, mo, d) - _jd(y, 1, 1)) + 1
            validated_lon = _solar_lon_skyfield(t_found)
            result[name] = {
                "datetime_utc": t_found.utc_strftime("%Y-%m-%dT%H:%M:%SZ"),
                "jd": round(jd, 4),
                "doy": doy,
                "civil_doy": doy,
                "validated_solar_lon_deg": round(validated_lon, 4),
            }
            t = _sf_ts.utc(y, mo, max(1, d - 5))
        result["caveat"] = None
        if year < DEEP_BCE_THRESHOLD:
            result["calendar_label_unreliable"] = True
        return result

    def _sunrise_azimuth_skyfield(lat: float, lon: float, year: int, month: int, day: int) -> dict:
        """Sun azimuth at 06:00 UTC (approximate sunrise) using Skyfield."""
        t = _sf_ts.utc(year, month, day, 6)
        earth = _sf_eph["earth"]
        sun = _sf_eph["sun"]
        loc = _sf_wgs84.latlon(lat, lon)
        observer = earth + loc
        astro = observer.at(t).observe(sun).apparent()
        alt, az, _ = astro.altaz()
        return {
            "date": f"{year:04d}-{month:02d}-{day:02d}",
            "sunrise_az_deg": round(az.degrees, 2),
            "sun_alt_deg": round(alt.degrees, 2),
            "backend": "skyfield",
        }

    def _star_rise_skyfield(
        ra_j2000_h: float, dec_j2000_deg: float, hip_id: int,
        lat: float, lon: float, year: int, month: int, day: int,
        horizon_deg: float = 0.0,
    ) -> dict:
        """Star visibility using Skyfield + Hipparcos."""
        earth = _sf_eph["earth"]
        loc = _sf_wgs84.latlon(lat, lon)
        # Load star from Hipparcos catalog via RA/Dec (no file download needed)
        from skyfield.starlib import Star
        star = Star(ra_hours=ra_j2000_h, dec_degrees=dec_j2000_deg)
        t_midnight = _sf_ts.utc(year, month, day, 0)
        observer = (earth + loc).at(t_midnight)
        astro = observer.observe(star).apparent()
        alt, az, _ = astro.altaz()

        if alt.degrees > 0:
            return {
                "visible_at_midnight": True,
                "altitude_deg": round(alt.degrees, 2),
                "azimuth_deg": round(az.degrees, 2),
                "backend": "skyfield",
            }
        # Search hourly for rise
        for hour in range(24):
            t = _sf_ts.utc(year, month, day, hour)
            observer = (earth + loc).at(t)
            astro = observer.observe(star).apparent()
            alt, az, _ = astro.altaz()
            if alt.degrees > horizon_deg:
                return {
                    "rise_approx_utc": f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:00:00Z",
                    "altitude_deg": round(alt.degrees, 2),
                    "azimuth_deg": round(az.degrees, 2),
                    "backend": "skyfield",
                }
        return {"visible": False, "note": "never rises", "backend": "skyfield"}

# ---------------------------------------------------------------------------
# astropy backend
# ---------------------------------------------------------------------------

def _solar_longitude_deg_astropy(t: Time) -> float:
    sun = get_sun(t)
    ra = sun.ra.rad
    dec = sun.dec.rad
    obl = 23.439291 * math.pi / 180
    lon = math.atan2(
        math.sin(ra) * math.cos(obl) + math.tan(dec) * math.sin(obl),
        math.cos(ra),
    )
    return math.degrees(lon) % 360


if HAS_ASTROPY:

    def _bisect_solar_lon_astropy(guess: Time, target_lon: float, tol: float = 1e-5) -> Time:
        lon0 = _solar_longitude_deg_astropy(guess)
        dt = timedelta(days=15)
        for _ in range(30):
            t1 = Time(guess + dt)
            lon1 = _solar_longitude_deg_astropy(t1)
            if abs(lon1 - target_lon) < tol:
                return t1
            dlon = (lon1 - lon0) % 360
            if dlon > 180:
                dlon -= 360
            if dlon > 0:
                guess = t1
                lon0 = lon1
            else:
                dt = dt / 2
        return guess


def _solstice_equinox_astropy(year: int) -> dict:
    targets = {
        "mar_equinox": 0.0, "jun_solstice": 90.0,
        "sep_equinox": 180.0, "dec_solstice": 270.0,
    }
    result = {"year": year, "backend": "astropy"}
    base = Time(f"{year:04d}-03-20", format="isot")
    for name, target_lon in targets.items():
        t = _bisect_solar_lon_astropy(base, target_lon)
        dt = t.to_datetime(timezone.utc)
        result[name] = {
            "datetime_utc": dt.isoformat(),
            "doy": dt.timetuple().tm_yday,
        }
        base = t + 80
    result["caveat"] = None
    return result


def _sunrise_azimuth_astropy(lat: float, lon: float, year: int, month: int, day: int) -> dict:
    try:
        loc = EarthLocation(lat=lat * u.deg, lon=lon * u.deg)
        t = Time(f"{year:04d}-{month:02d}-{day:02d} 06:00:00", format="isot", scale="utc")
        sun = get_sun(t)
        altaz = AltAz(obstime=t, location=loc)
        s = sun.transform_to(altaz)
        return {
            "date": f"{year:04d}-{month:02d}-{day:02d}",
            "sunrise_az_deg": round(s.az.deg, 2),
            "sun_alt_deg": round(s.alt.deg, 2),
            "backend": "astropy",
        }
    except Exception:
        return {"date": f"{year:04d}-{month:02d}-{day:02d}", "error": "astropy failed", "backend": "astropy"}


def _star_rise_astropy(
    ra_j2000_h: float, dec_j2000_deg: float,
    lat: float, lon: float, year: int, month: int, day: int,
    horizon_deg: float = 0.0,
) -> dict:
    try:
        from astropy.time import Time as AstroTime
        loc = EarthLocation(lat=lat * u.deg, lon=lon * u.deg, height=0 * u.m)
        ra_e, dec_e = _precess_analytic(ra_j2000_h, dec_j2000_deg, 2000, year)
        star = SkyCoord(ra=ra_e * u.hourangle, dec=dec_e * u.deg, frame="fk5", equinox=f"J{year}")
        midnight = AstroTime(f"{year:04d}-{month:02d}-{day:02d} 00:00:00", format="isot", scale="utc")
        altaz = AltAz(obstime=midnight, location=loc)
        s = star.transform_to(altaz)
        if s.alt.deg > 0:
            return {
                "visible_at_midnight": True,
                "altitude_deg": round(s.alt.deg, 2),
                "azimuth_deg": round(s.az.deg, 2),
                "backend": "astropy",
            }
        for hour in range(24):
            t = AstroTime(f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:00:00", format="isot", scale="utc")
            altaz = AltAz(obstime=t, location=loc)
            s = star.transform_to(altaz)
            if s.alt.deg > horizon_deg:
                return {
                    "rise_approx_utc": f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:00:00",
                    "altitude_deg": round(s.alt.deg, 2),
                    "azimuth_deg": round(s.az.deg, 2),
                    "backend": "astropy",
                }
        return {"visible": False, "note": "never rises", "backend": "astropy"}
    except Exception as exc:
        return {"visible": "error", "note": str(exc), "backend": "astropy_error"}


# ---------------------------------------------------------------------------
# fallback (analytic)
# ---------------------------------------------------------------------------

def _solstice_equinox_fallback(year: int) -> dict:
    obliquity = 23.439 - 0.013 * (year - 2000) / 100
    return {
        "year": year,
        "mar_equinox":  {"doy": 79,  "approx": f"obliquity {obliquity:.3f}°; ±1d"},
        "jun_solstice": {"doy": 171, "approx": f"obliquity {obliquity:.3f}°; ±1d"},
        "sep_equinox":  {"doy": 265, "approx": f"obliquity {obliquity:.3f}°; ±1d"},
        "dec_solstice": {"doy": 355, "approx": f"obliquity {obliquity:.3f}°; ±1d"},
        "backend": "fallback",
        "caveat": f"fixed-DOY ±1d with obliquity correction",
    }


def _sunrise_azimuth_fallback(lat: float, lon: float, doy: int) -> dict:
    dec = 23.44 * math.sin(2 * math.pi * (doy - 80) / 365)
    lat_r = math.radians(lat)
    dec_r = math.radians(dec)
    try:
        x = math.sin(dec_r) / math.cos(lat_r)
        x = max(-1, min(1, x))
        az = math.degrees(math.acos(x))
    except Exception:
        az = float("nan")
    return {"sunrise_az_deg": round(az, 2), "backend": "fallback",
            "caveat": "no refraction; simplified declination model"}


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


def _star_rise_fallback(dec_j2000_deg: float, lat: float) -> dict:
    lat_r = math.radians(lat)
    dec_r = math.radians(dec_j2000_deg)
    cos_h = -math.tan(lat_r) * math.tan(dec_r)
    if cos_h < -1:
        return {"visible": True, "note": "circumpolar", "backend": "fallback"}
    if cos_h > 1:
        return {"visible": False, "note": "never rises", "backend": "fallback"}
    h_deg = math.degrees(math.acos(cos_h))
    return {"rise_hour_angle_deg": round(h_deg, 2), "backend": "fallback",
            "caveat": "no refraction; no precession"}


# ---------------------------------------------------------------------------
# horizon profile (elevation / SRTM)
# ---------------------------------------------------------------------------

def _download_dem_tile(lat: float, lon: float, margin: float = 0.2) -> str | None:
    import subprocess, tempfile, os
    bounds = f"{lon-margin} {lat-margin} {lon+margin} {lat+margin}"
    fname = f"dem_{lat:.2f}_{lon:.2f}.tif"
    out = os.path.join(tempfile.gettempdir(), fname)
    try:
        subprocess.run(
            ["eio", "seed", "--bounds", bounds],
            capture_output=True, text=True, timeout=120,
        )
        subprocess.run(
            ["eio", "clip", "-o", out, "--bounds", bounds],
            capture_output=True, text=True, timeout=60,
        )
        return out if os.path.exists(out) else None
    except Exception:
        return None


def horizon_profile(lat: float, lon: float, n_az: int = 36, max_km: float = 10.0) -> dict:
    """Compute horizon altitude at each azimuth using SRTM elevation.
    Falls back to flat geometric horizon if raster unavailable.
    """
    result = {
        "lat": lat, "lon": lon, "n_azimuth": n_az,
        "backend": "geometric",
        "horizon": [{"az_deg": round(360.0 * i / n_az, 1), "horizon_alt_deg": 0.0}
                    for i in range(n_az)],
        "note": "flat horizon; pip install elevation rasterio for SRTM profile",
    }

    if HAS_ELEVATION and HAS_RASTERIO:
        try:
            tif = _download_dem_tile(lat, lon)
            if tif:
                result["backend"] = "srtm_elevation"
                result["horizon"] = []
                with _rasterio.open(tif) as src:
                    for i in range(n_az):
                        az = 360.0 * i / n_az
                        max_alt = 0.0
                        for d_km in range(1, int(max_km) + 1):
                            dlat = d_km * math.cos(math.radians(az)) / 111.32
                            dlon = d_km * math.sin(math.radians(az)) / (
                                111.32 * math.cos(math.radians(lat))
                            )
                            qlat = lat + dlat
                            qlon = lon + dlon
                            try:
                                for val in src.sample([(qlon, qlat)]):
                                    elev = float(val[0]) if val[0] is not None else 0
                            except Exception:
                                elev = 0
                            alt_deg = math.degrees(math.atan2(elev, d_km * 1000))
                            max_alt = max(max_alt, alt_deg)
                        result["horizon"].append({
                            "az_deg": round(az, 1),
                            "horizon_alt_deg": round(max_alt, 2),
                        })
                result["note"] = f"ray-traced SRTM 30m; max_km={max_km}"
                return result
        except Exception as exc:
            result["note"] = f"SRTM failed ({exc}); flat fallback"

    return result


# ---------------------------------------------------------------------------
# unified dispatch
# ---------------------------------------------------------------------------

def find_solstice_equinox(year: int, backend: str = "auto") -> dict:
    b = _resolve_backend(backend)
    if b == "skyfield" and HAS_SKYFIELD:
        return _solstice_equinox_skyfield(year)
    if b == "astropy" and HAS_ASTROPY and 0 < year <= 3000:
        return _solstice_equinox_astropy(year)
    return _solstice_equinox_fallback(year)


def sunrise_azimuth(lat: float, lon: float, year: int, month: int, day: int, backend: str = "auto") -> dict:
    b = _resolve_backend(backend)
    if b == "skyfield" and HAS_SKYFIELD:
        return _sunrise_azimuth_skyfield(lat, lon, year, month, day)
    if b == "astropy" and HAS_ASTROPY and 0 <= year <= 3000:
        return _sunrise_azimuth_astropy(lat, lon, year, month, day)
    doy = (month - 1) * 30 + day
    return _sunrise_azimuth_fallback(lat, lon, doy)


def star_rise(
    ra_j2000_h: float, dec_j2000_deg: float, hip_id: int | None,
    lat: float, lon: float, year: int, month: int, day: int,
    backend: str = "auto", horizon_deg: float = 0.0,
) -> dict:
    b = _resolve_backend(backend)
    if b == "skyfield" and HAS_SKYFIELD:
        return _star_rise_skyfield(ra_j2000_h, dec_j2000_deg, hip_id or 0,
                                    lat, lon, year, month, day, horizon_deg)
    if b == "astropy" and HAS_ASTROPY and 0 <= year <= 3000:
        return _star_rise_astropy(ra_j2000_h, dec_j2000_deg, lat, lon, year, month, day, horizon_deg)
    return _star_rise_fallback(dec_j2000_deg, lat)


# ---------------------------------------------------------------------------
# lunar illumination (from formations.csv)
# ---------------------------------------------------------------------------

def lunar_illumination(d: date) -> float:
    known_new = date(2000, 1, 6)
    age = (d - known_new).days % 29.530588853
    phase = 2 * math.pi * (age / 29.530588853)
    return (1 - math.cos(phase)) / 2


def crop_lunar_from_catalog(formations_csv: Path) -> list[dict]:
    rows = []
    if not formations_csv.exists():
        return rows
    with formations_csv.open(newline="") as f:
        for row in csv.DictReader(f):
            ds = (row.get("date") or row.get("Date") or "").strip()
            if len(ds) >= 10:
                try:
                    d = date.fromisoformat(ds[:10])
                except ValueError:
                    continue
                ill = lunar_illumination(d)
                rows.append({
                    "id": row.get("id") or row.get("formation_id"),
                    "name": row.get("name", ""),
                    "date": ds[:10],
                    "lunar_illum": round(ill, 3),
                    "moon_near": "full" if ill >= 0.8 else "new" if ill <= 0.2 else "intermediate",
                })
    return rows


# ---------------------------------------------------------------------------
# per-site analysis
# ---------------------------------------------------------------------------

def _precess_skyfield(ra_h: float, dec_deg: float, from_year: int, to_year: int) -> tuple[float, float]:
    """Precess star position from J2000 to epoch year using Skyfield."""
    if not HAS_SKYFIELD:
        return _precess_analytic(ra_h, dec_deg, from_year, to_year)
    from skyfield.starlib import Star
    star = Star(ra_hours=ra_h, dec_degrees=dec_deg)
    t_from = _sf_ts.utc(from_year, 1, 1)
    t_to = _sf_ts.utc(to_year, 1, 1)
    # Compute position at epoch using ICRS -> precessed frame
    earth = _sf_eph["earth"]
    astro = earth.at(t_to).observe(star).apparent()
    ra, dec, _ = astro.radec()
    return ra.hours, dec.degrees


def analyze_site(
    name: str, info: dict, backend: str = "auto",
    with_horizon: bool = False,
) -> dict:
    b = _resolve_backend(backend)
    axis_bearing = info.get("axis_bearing_deg")
    s = {
        "name": name, "lat": info["lat"], "lon": info["lon"],
        "elevation_m": info.get("elevation_m", 50),
        "epoch_year": info["epoch_year"],
        "note": info.get("note", ""),
        "axis_bearing_deg": axis_bearing,
        "axis_citation": info.get("axis_citation"),
    }

    ep = info["epoch_year"]
    s["solstice_eq"] = find_solstice_equinox(ep, backend=backend)

    s["jun_solstice_sunrise"] = sunrise_azimuth(info["lat"], info["lon"], ep, 6, 21, backend=backend)
    s["dec_solstice_sunrise"] = sunrise_azimuth(info["lat"], info["lon"], ep, 12, 21, backend=backend)

    s["current_solstice_eq"] = find_solstice_equinox(date.today().year, backend=backend)

    star_results = {}
    for skey in STARS:
        star = STARS[skey]
        ra, dec = _precess_skyfield(star["ra_j2000_h"], star["dec_j2000_deg"], 2000, ep)
        rise = star_rise(
            star["ra_j2000_h"], star["dec_j2000_deg"], STARS_HIP.get(skey),
            info["lat"], info["lon"], ep, 6, 21,
            backend=backend,
        )
        star_results[skey] = {
            "name": star["name"],
            "epoch_coords": {"ra_h": round(ra, 4), "dec_deg": round(dec, 4)},
            "rise_info": rise,
        }
    s["stars"] = star_results

    if with_horizon:
        s["horizon_profile"] = horizon_profile(info["lat"], info["lon"])

    s["backend"] = b
    return s


# ---------------------------------------------------------------------------
# random controls
# ---------------------------------------------------------------------------

def random_site() -> dict:
    return {
        "lat": round(rnd.uniform(-55, 70), 4),
        "lon": round(rnd.uniform(-180, 180), 4),
        "elevation_m": 50,
        "epoch_year": rnd.randint(-10000, 1500),
    }


def run_random_controls(n: int = 10, backend: str = "auto") -> list[dict]:
    return [analyze_site("random_control", random_site(), backend=backend) for _ in range(n)]


def _angular_delta_deg(a: float, b: float) -> float:
    """Shortest absolute angular distance between two azimuths (0–360°)."""
    d = abs(a - b) % 360
    return min(d, 360 - d)


def _axis_alignment_delta(site: dict) -> dict | None:
    """Compute Δaz between jun_solstice_sunrise and documented axis bearing.
    Respects 180° line symmetry. Returns None if no axis bearing known.
    """
    bearing = site.get("axis_bearing_deg")
    if bearing is None:
        return None
    try:
        az = site.get("jun_solstice_sunrise", {}).get("sunrise_az_deg")
        if az is None or (isinstance(az, float) and math.isnan(az)):
            return None
        d0 = _angular_delta_deg(az, bearing)
        d180 = _angular_delta_deg(az, (bearing + 180) % 360)
        return {"axis_bearing_deg": bearing, "delta_az_deg": round(min(d0, d180), 2)}
    except Exception:
        return None


def compare_bearing_alignments(real_sites: list[dict], random_controls: list[dict]) -> dict:
    """Compare solstice sunrise alignment to documented monument axis bearings.
    Replaces previous weak 50/60/65° hit proxy.
    """
    real_aligned = []
    real_unknown = []
    for site in real_sites:
        d = _axis_alignment_delta(site)
        if d is not None:
            real_aligned.append({**d, "name": site.get("name")})
        else:
            az = site.get("jun_solstice_sunrise", {}).get("sunrise_az_deg")
            real_unknown.append({"name": site.get("name"), "sunrise_az_deg": az,
                                 "note": site.get("axis_note", "No known axis bearing")})

    rand_deltas = []
    for ctrl in random_controls:
        rand_bearing = rnd.uniform(0, 180)
        try:
            az = ctrl.get("jun_solstice_sunrise", {}).get("sunrise_az_deg")
            if az is None or (isinstance(az, float) and math.isnan(az)):
                continue
            d0 = _angular_delta_deg(az, rand_bearing)
            d180 = _angular_delta_deg(az, (rand_bearing + 180) % 360)
            rand_deltas.append(min(d0, d180))
        except Exception:
            continue

    real_deltas = [d["delta_az_deg"] for d in real_aligned]

    return {
        "method": "axis-bearing alignment (Δaz vs documented monument axis)",
        "n_real_with_axis": len(real_aligned),
        "n_real_unknown_axis": len(real_unknown),
        "real_axis_alignments": real_aligned,
        "real_unknown_axis_sites": real_unknown,
        "real_mean_delta_deg": round(sum(real_deltas) / max(1, len(real_deltas)), 2) if real_deltas else None,
        "n_random": len(random_controls),
        "random_mean_delta_deg": round(sum(rand_deltas) / max(1, len(rand_deltas)), 2) if rand_deltas else None,
        "note": (
            "Small-n descriptive only; no signal claim. Δaz ≤ 5° would indicate plausible alignment."
            if len(real_aligned) < 5
            else None
        ),
    }


# ---------------------------------------------------------------------------
# main probe
# ---------------------------------------------------------------------------

def run_probe(
    formations_csv: Path, backend: str = "auto",
    random_controls_n: int = 10, with_horizon: bool = False,
) -> dict:
    sites = {name: analyze_site(name, info, backend=backend, with_horizon=with_horizon) for name, info in SITES.items()}

    lunar = crop_lunar_from_catalog(formations_csv)
    fullish = sum(1 for r in lunar if r["lunar_illum"] >= 0.8)
    newish = sum(1 for r in lunar if r["lunar_illum"] <= 0.2)

    random_ctrl = run_random_controls(random_controls_n, backend=backend)
    comparison = compare_bearing_alignments(list(sites.values()), random_ctrl)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "backend": _resolve_backend(backend),
        "sites": sites,
        "crop_lunar": lunar,
        "crop_lunar_summary": {
            "n": len(lunar),
            "n_illum_ge_0.8": fullish,
            "n_illum_le_0.2": newish,
            "full_moon_ratio": round(fullish / max(1, len(lunar)), 3),
            "new_moon_ratio": round(newish / max(1, len(lunar)), 3),
            "note": "Small sample; do not claim lunar preference without larger catalog.",
        },
        "bearing_alignments": comparison,
        "random_controls": {
            "n": random_controls_n,
            "sample": random_ctrl[:5],
        },
        "verdict": (
            "N4++ axis-bearing alignment — see bearing_alignments for Δaz values. "
            "No alien/divine claims. Geometry ≠ intent."
        ),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo-single", type=str, default=None)
    ap.add_argument("--out", type=Path, default=Path("outputs/astro/run.json"))
    ap.add_argument("--data-dir", type=Path,
                    default=Path(__file__).resolve().parents[2] / "data")
    ap.add_argument("--backend", choices=("auto", *BACKENDS), default="auto")
    ap.add_argument("--random-n", type=int, default=10)
    ap.add_argument("--horizon", action="store_true", help="Compute horizon profile for each site")
    args = ap.parse_args()

    formations_csv = args.data_dir / "catalog" / "formations.csv"

    if args.demo_single:
        if args.demo_single in SITES:
            result = analyze_site(args.demo_single, SITES[args.demo_single], backend=args.backend, with_horizon=args.horizon)
        else:
            print(f"Unknown site: {args.demo_single}. Available: {list(SITES.keys())}", file=sys.stderr)
            sys.exit(1)
    else:
        result = run_probe(formations_csv, backend=args.backend, random_controls_n=args.random_n, with_horizon=args.horizon)

    path = args.out
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, default=str))
    print(json.dumps({
        "backend": result.get("backend", "?"),
        "sites": list(result.get("sites", {})) if "sites" in result else ["demo"],
        "crop_lunar_summary": result.get("crop_lunar_summary"),
        "bearing_alignments": result.get("bearing_alignments"),
    }, indent=2))
    print(f"wrote {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
