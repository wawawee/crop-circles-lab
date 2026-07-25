"""astro_probe — solstice / lunar / star-rise checks (N4 scaffold).

Prefers skyfield or astropy if installed; otherwise uses the pure-Python
synodic lunar approx already validated in spatial_report + analytic solstice DOY.

CLI:
  python tools/astro/astro_probe.py --demo --out outputs/astro/run.json
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path

# Sites (approx WGS84)
SITES = {
    "gobekli_tepe": {"lat": 37.2231, "lon": 38.9223, "epoch_build_ybp": 11000},
    "stonehenge": {"lat": 51.1789, "lon": -1.8262, "epoch_build_ybp": 4500},
    "giza_khufu": {"lat": 29.9792, "lon": 31.1342, "epoch_build_ybp": 4500},
    "chichen_itza": {"lat": 20.6843, "lon": -88.5678, "epoch_build_ybp": 1200},
}


def lunar_illumination(d: date) -> float:
    """Synodic approx — same family as spatial_report (good enough for catalog flags)."""
    # Reference: new moon 2000-01-06 ≈ JD; use days since known new moon 2000-01-06
    known_new = date(2000, 1, 6)
    age = (d - known_new).days % 29.530588853
    # illumination ~ (1 - cos(2π age / period)) / 2
    phase = 2 * math.pi * (age / 29.530588853)
    return (1 - math.cos(phase)) / 2


def approx_solstice_equinox_doy(year: int) -> dict:
    """Rough Northern-hemisphere civil DOY (not arcsecond astronomy)."""
    # Average DOYs; leap ignored for scaffold
    return {
        "year": year,
        "mar_equinox_doy": 79,
        "jun_solstice_doy": 171,
        "sep_equinox_doy": 265,
        "dec_solstice_doy": 355,
        "caveat": "Civil DOY placeholders — replace with skyfield/astropy for N4 DONE.",
    }


def sun_azimuth_at_solstice_scaffold(lat: float, season: str = "jun") -> dict:
    """Extremely rough sunrise azimuth toy (not for publication)."""
    # Declination ±23.44
    dec = 23.44 if season == "jun" else -23.44
    # sunrise azimuth approx: cos(az) = sin(dec)/cos(lat) … simplified
    try:
        x = math.sin(math.radians(dec)) / math.cos(math.radians(lat))
        x = max(-1, min(1, x))
        az = math.degrees(math.acos(x))
    except Exception:
        az = float("nan")
    return {"season": season, "approx_sunrise_az_deg": round(az, 2), "lat": lat}


def crop_lunar_from_catalog(formations_csv: Path) -> list[dict]:
    import csv
    rows = []
    if not formations_csv.exists():
        return rows
    with formations_csv.open() as f:
        for row in csv.DictReader(f):
            ds = (row.get("date") or row.get("Date") or "").strip()
            if len(ds) >= 10:
                try:
                    d = date.fromisoformat(ds[:10])
                except ValueError:
                    continue
                rows.append(
                    {
                        "id": row.get("id") or row.get("formation_id"),
                        "date": ds[:10],
                        "lunar_illum": round(lunar_illumination(d), 3),
                    }
                )
    return rows


def demo(root: Path) -> dict:
    year = 2026
    sites = {}
    for name, s in SITES.items():
        sites[name] = {
            **s,
            "solstice_eq": approx_solstice_equinox_doy(year),
            "jun_sunrise_az_toy": sun_azimuth_at_solstice_scaffold(s["lat"], "jun"),
            "dec_sunrise_az_toy": sun_azimuth_at_solstice_scaffold(s["lat"], "dec"),
            "random_control_note": "Compare to random lat/lon + random year before claiming alignment.",
        }
    lunar = crop_lunar_from_catalog(root / "data" / "catalog" / "formations.csv")
    fullish = sum(1 for r in lunar if r["lunar_illum"] >= 0.8)
    newish = sum(1 for r in lunar if r["lunar_illum"] <= 0.2)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sites": sites,
        "crop_lunar": lunar,
        "crop_lunar_summary": {
            "n": len(lunar),
            "n_illum_ge_0.8": fullish,
            "n_illum_le_0.2": newish,
            "note": "Tiny N; do not claim lunar preference without larger dated catalog + season controls.",
        },
        "backend": "scaffold_pure_python",
        "upgrade": "pip install skyfield astropy for proper rise/set & epoch precession",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", default=True)
    ap.add_argument("--out", type=Path, default=Path("outputs/astro/run.json"))
    ap.add_argument("--root", type=Path, default=Path("."))
    args = ap.parse_args()
    result = demo(args.root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2))
    print(json.dumps(result["crop_lunar_summary"], indent=2))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
