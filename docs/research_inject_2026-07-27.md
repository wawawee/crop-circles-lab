# Research inject — 2026-07-27 (Captain scout)

Grounded open-data notes for the next queue. Stance unchanged: **structure ≠ meaning**.

## G22 Nazca — remote sensing

| Field | Value |
|-------|--------|
| Center (approx) | −14.73°, −75.13° |
| UTM | Zone **18**, MGRS band **L** |
| Primary Sentinel-2 tile | **18LTD** (L2A / ARD preferred) |
| Adjacent | 18LTE, 18LUD, 18LUC |
| Access | Copernicus Data Space Ecosystem (open). **No** Bing/ESRI programmatic download |
| UAVSAR (optional) | `PeruVo_12006_13043-008_14045-004_0396d_s01_L090_01` via ASF DAAC; PI Paul Lundgren |
| Resolution honesty | 10 m → line/trapezoid class only; figurative reliefs UNDERDETERMINED |

## G2-REAL — Proto-Elamite / CDLI

| Field | Value |
|-------|--------|
| Search | https://cdli.earth/search |
| Format | ATF, `#atf: lang qpc` |
| Example tablets | **P272825** (fragment), **P008012** (MDP 06, 215) |
| Method fit | n-gram / entropy / numeral vs commodity structure — **not** phonetic decipherment |
| Caveat | Image-based ML can latch onto scan hardware; prefer ATF text streams |

## Next (not yet assigned) — khipu

| Field | Value |
|-------|--------|
| OKR | https://github.com/khipulab/open-khipu-repository (`khipu.db` SQLite; v2 `okr_num`) |
| KFG | https://www.khipufieldguide.com/ |
| Known-answer pair | KH0082 (AS69) ↔ KH0083 (AS70/UR35) aggregation; rare knot `3L*` |
| Probe fit | `network_probe` / pendant-tree graphs vs ER null; structure ≠ narrative decipherment |

## Next — Hecklefish #7 = Göbekli **relief** (not crop-circle lore)

**Use:** Wikimedia Commons open photos of Pillar 18 H-glyphs:

- `Gobekli_Tepe_stela,_with_side_arms_and_belt,_Şanlıurfa_-_Archeology_Museum.jpg`
- `Göbekli_Tepe_Pillar.JPG` (note: reportedly mirrored)
- `GobeklitepeHeykel.jpg`

**Ignore for this ticket:** Why Files / electromagnetic crop-circle anecdotes — wrong domain; not our #7.

## Next — G14+ Chankillo DEM

| Field | Value |
|-------|--------|
| Site | −12.22°, −78.18° |
| DEM | Copernicus **GLO-30** (30 m) via OpenTopography / Copernicus |
| Goal | Real ridge null to harden G14 `CONTROL_NOT_SEPARATED` (22% synthetic ridge hit) |

## Dispatch hygiene

Nazca and CDLI must stay on **separate branches / PRs**. Kitchen-sink = merge block.
