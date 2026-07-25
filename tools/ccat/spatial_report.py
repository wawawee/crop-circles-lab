#!/usr/bin/env python3
"""
spatial_report.py -- TASKLIST B7: turn the spatial/temporal stub into a real catalog.

Loads data/catalog/priority_formations.json + data/catalog/coordinates.json, then:
  * computes the nearest ancient monument for each formation (great-circle /
    haversine distance -- NO geopy dependency),
  * computes the Moon's illuminated fraction on the formation date (pure-Python
    synodic approximation, no astropy), handling partial dates (YYYY-MM ->
    mid-month, YYYY -> skipped) with the basis recorded,
  * writes data/catalog/formations.csv,
  * prints a nearest-monument report and the Wiltshire cluster count.

Coordinates are approximate (see coordinates.json 'confidence'); this is a
proximity/clustering aid, not a survey claim.

Usage:  python tools/ccat/spatial_report.py
"""
from __future__ import annotations

import csv
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
CATALOG = os.path.join(ROOT, "data", "catalog")

# Ancient monuments / observatory reference points (lat, lon).
MONUMENTS = {
    "Stonehenge":                 (51.1789, -1.8262),
    "Avebury Henge":              (51.4286, -1.8541),
    "Silbury Hill":               (51.4156, -1.8577),
    "West Kennet Long Barrow":    (51.4008, -1.8511),
    "Barbury Castle":             (51.4866, -1.7810),
    "Windmill Hill (Avebury)":    (51.4340, -1.8620),
    "Adam's Grave (Alton Barnes)":(51.3676, -1.8360),
    "Old Sarum":                  (51.0933, -1.8043),
    "Chilbolton Observatory":     (51.1450, -1.4370),
}


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def nearest_monument(lat, lon):
    best, best_d = None, float("inf")
    for name, (mlat, mlon) in MONUMENTS.items():
        d = haversine_km(lat, lon, mlat, mlon)
        if d < best_d:
            best, best_d = name, d
    return best, best_d


def normalize_date(d):
    """Return (iso_date_or_None, basis). YYYY-MM-DD exact; YYYY-MM -> day 15; YYYY -> None."""
    parts = str(d).split("-")
    if len(parts) == 3:
        return d, "exact"
    if len(parts) == 2:
        return f"{d}-15", "approx-mid-month"
    return None, "year-only-skipped"


def lunar_illumination(date_iso):
    """Moon illuminated fraction via a pure-Python synodic-month approximation.

    No astropy dependency (so it runs anywhere), accurate to a few percent --
    plenty for 'near full / near new' hypothesis tests. phase 0 = new, 0.5 = full;
    k = (1 - cos(2*pi * phase)) / 2.
    """
    from datetime import datetime, timezone
    try:
        dt = datetime.fromisoformat(date_iso).replace(tzinfo=timezone.utc)
        jd = dt.timestamp() / 86400.0 + 2440587.5            # Unix epoch -> Julian Date
        synodic = 29.530588853
        ref_new_moon_jd = 2451550.1                          # 2000-01-06 ~18:14 UTC (a new moon)
        phase = ((jd - ref_new_moon_jd) % synodic) / synodic
        return round((1 - math.cos(2 * math.pi * phase)) / 2, 3)
    except Exception:
        return None


def main():
    with open(os.path.join(CATALOG, "priority_formations.json")) as f:
        formations = json.load(f)["formations"]
    with open(os.path.join(CATALOG, "coordinates.json")) as f:
        coords = json.load(f)["coordinates"]

    rows = []
    for it in formations:
        c = coords.get(it["id"], {})
        lat, lon = c.get("lat"), c.get("lon")
        nm, nmkm = "", ""
        if lat is not None and lon is not None:
            nm, d = nearest_monument(lat, lon)
            nmkm = round(d, 2)
        iso, basis = normalize_date(it.get("date", ""))
        illum = lunar_illumination(iso) if iso else None
        rows.append({
            "id": it["id"],
            "name": it["name"],
            "date": it.get("date", ""),
            "lat": lat if lat is not None else "",
            "lon": lon if lon is not None else "",
            "coord_confidence": c.get("confidence", ""),
            "nearest_monument": nm,
            "monument_km": nmkm,
            "lunar_illum": illum if illum is not None else "",
            "lunar_date_basis": basis,
            "priority": it.get("priority", ""),
            "tags": "|".join(it.get("tags", [])),
            "image_files": "|".join(it.get("image_files", [])),
        })

    out = os.path.join(CATALOG, "formations.csv")
    cols = list(rows[0].keys())
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote {os.path.relpath(out, ROOT)}  ({len(rows)} formations)\n")
    print(f"{'id':34s} {'nearest monument':28s} {'km':>8s} {'lunar':>6s}")
    print("-" * 82)
    for r in rows:
        print(f"{r['id']:34s} {str(r['nearest_monument']):28s} "
              f"{str(r['monument_km']):>8s} {str(r['lunar_illum']):>6s}")

    av = MONUMENTS["Avebury Henge"]
    wilt = [r for r in rows if r["lat"] != "" and haversine_km(r["lat"], r["lon"], av[0], av[1]) <= 30]
    print(f"\nWiltshire cluster (<=30 km of Avebury): {len(wilt)}/{len(rows)}")
    print("  " + ", ".join(r["id"] for r in wilt))
    non_uk = [r for r in rows if r["nearest_monument"] and r["monument_km"] != "" and r["monument_km"] > 500]
    if non_uk:
        print(f"\nNon-UK sites (no ancient monument within our set): "
              + ", ".join(r["id"] for r in non_uk))


if __name__ == "__main__":
    main()
