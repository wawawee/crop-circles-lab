# data/astro/chankillo/

Public droplet for **G14 — Chankillo Thirteen Towers** archaeo-astronomical
alignment probe (`tools/scripts/chankillo_probe.py`).

## Honest provenance (2026-07-25)

### What is here

- `tower_coords.json` — approximate WGS84 Lat/Lon for the 13 towers
  (Tower 1 = southernmost, Tower 13 = northernmost) and the Western
  Observing Point (WOP). Sourced from the **published schematic** in
  **Ghezzi, I. & Ruggles, C.L.N. (2007). "Chankillo: A 2300-Year-Old Solar
  Observatory in Coastal Peru." *Science* 315(5816): 1239-1243**.
  Coordinates are approximate (±0.001° lat, ±0.001° lon) and are flagged
  in the run.json as `coord_source="ghezzi_ruggles_2007_fig1_schematic"`.
  No published geodetic-grade dump exists for these specific points under
  an open licence (as of 2026-07-25).
- `solar_arc_300BCE.json` — expected Sun-arc annual range at the Chankillo
  latitude at ~300 BCE (declination bracket, June solstice sunrise
  azimuth, December solstice sunrise azimuth, equinox sunrise azimuth,
  derived analytically — cite high-school astronomy plus JPL DE441 solar
  ephemeris at the same epoch). PURE-FIXTURE, not a skyfield output;
  skyfield is consulted at runtime to *verify* but the fixture can be
  checked in tests without skyfield installed.

### What is NOT here, and why

- **No DEM tile**. OpenTopography and Copernicus DEM 30m tiles for this
  grid cell would be ~50 MB; their bulk download is out of band for a
  single-PR lab probe and the tile hosted in our `data/raw/` is gitignored.
  The probe therefore uses a **synthetic ridge null** generator
  (`null_synthetic_ridge` in chankillo_probe.py) that approximates the
  horizon altitude profile as a piecewise-linear segment along the
  east-facing horizon from the WOP.
- **No monuments/origins file**. The 13 tower coordinates are the only
  geometry we need for the alignment test; the fortified temple /
  observing flanking platforms are out of scope for this probe.

### How to swap in a real DEM tile (future)

When an open licence covers a Copernicus DEM or ASTER GDEM tile for
grid cell `(-9.6, -78.3) ~ (50 MB)`, drop the GeoTIFF into
`data/astro/chankillo/dem.tif` (gitignored or .gitkeep + attribution).
The probe does **not** auto-load it (SyncFusion of ENVI / rasterio
plumbing is out of scope), but the synthetic-ridge null is
already structured so a follow-up agent can drop its real horizon
heights into `data/astro/chankillo/horizon_profile_real.json` and the
same probe will compare tower azimuths against the **observed** horizon.

## Cite-as

```
@data{chankillo_2026,
  title = {Synthetic Chankillo Thirteen Towers fixture (G14)},
  author = {{ANOMALISTIK Freebuff}},
  year = {2026},
  note = {Approx. WGS84 lat/lon from Ghezzi \& Ruggles (2007) schematic},
  url = {data/astro/chankillo/tower_coords.json}
}
```

The actual published reference for the published interpretation
(claim-under-test, NOT endorsement) is:

```
Ghezzi, I., Ruggles, C.L.N. (2007). "Chankillo: A 2300-Year-Old Solar
   Observatory in Coastal Peru." Science 315(5816): 1239-1243.
   DOI: 10.1126/science.1136299
```

The probe will keep refusing to call its output "the Chankillo calendar"
regardless of input — the published interpretation is the claim-under-test,
not a verified reading.
