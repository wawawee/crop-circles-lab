#!/usr/bin/env python3
"""
fetch_data.py -- reproducible fetch for G-Amazon (Mode A).

Downloads (into data/amazon/raw/, which is git-ignored):
  * Zenodo ade2541-v1.0.0.zip  -> extract Earthworks.rds -> earthworks_zenodo.csv
  * jqjacobs amazon_geoglyphs.kml (LOCAL cross-check only; NOT redistributed)

Does NOT download the 1 km IPP rasters (not needed for Mode A) and never mirrors
multi-GB products. Requires: pip install rdata  (pure python, no R / no C build).
"""
import csv
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ZENODO_ZIP = ("https://zenodo.org/api/records/10214943/files/"
              "Vperipato/ade2541-v1.0.0.zip/content")
JQ_KML = "https://www.jqjacobs.net/amazon/amazon_geoglyphs.kml"
RDS_MEMBER = "Vperipato-ade2541-78f685a/Database/Earthworks.rds"


def _get(url, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        print("exists:", dest); return
    print("GET", url)
    req = urllib.request.Request(url, headers={"User-Agent": "crop-circles-lab/geo"})
    with urllib.request.urlopen(req, timeout=180) as r, open(dest, "wb") as fh:
        fh.write(r.read())
    print("  ->", dest, os.path.getsize(dest), "bytes")


def main():
    os.makedirs(RAW, exist_ok=True)
    zip_path = os.path.join(RAW, "zenodo_ade2541.zip")
    _get(ZENODO_ZIP, zip_path)

    import zipfile
    rds_path = os.path.join(RAW, "Earthworks.rds")
    with zipfile.ZipFile(zip_path) as z:
        with z.open(RDS_MEMBER) as src, open(rds_path, "wb") as dst:
            dst.write(src.read())
    print("extracted", rds_path)

    try:
        import rdata
    except ImportError:
        sys.exit("pip install rdata  (needed to read Earthworks.rds)")

    df = rdata.read_rds(rds_path)
    out_csv = os.path.join(HERE, "earthworks_zenodo.csv")
    with open(out_csv, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "lat", "lon", "type", "source"])
        for i, (_, row) in enumerate(df.iterrows(), 1):
            w.writerow([f"ZEN{i:04d}", f"{float(row['Latitude']):.6f}",
                        f"{float(row['Longitude']):.6f}",
                        str(row["Database"]).strip(),
                        "Peripato2023_Zenodo_10214943"])
    print("wrote", out_csv, "rows:", len(df))

    # jqjacobs KML -- LOCAL cross-check only, git-ignored, NOT redistributed
    _get(JQ_KML, os.path.join(RAW, "jq_amazon_geoglyphs.kml"))
    print("NOTE: jqjacobs KML is © all-rights-reserved; used for cross-check "
          "aggregate stats only, never committed.")


if __name__ == "__main__":
    main()
