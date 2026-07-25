# Scout briefs — "beyond wheat" targets (grounded, 2026-07-25)

Three background scouts researched Kimi's top-3 expansion targets. Distilled specs
below; each carries a data-access reality check + a mandatory negative control.

---

## 1. Nazca Lines  🛰️  (fastest win — `ccat` is ~90% there)

**Grounded facts**
- Sakai et al., **PNAS 2024** (IBM PAIRS Geoscope CNN): **303 new figurative geoglyphs**
  confirmed in ~6 months of fieldwork from AI candidates, nearly doubling the ~430
  known → ~733 total. Discovery rate: 1.5/yr (1940s–2000s) → 18.7/yr (satellite) →
  ~16× with AI. 2019 proof-of-concept: 143 new, 1 by AI (Watson CNN).
- The AI targeted **small relief-type** geoglyphs (often <50 m), NOT the km-scale
  line-type. Relief contrast is tiny (desert-varnish pebble removal, ~5–15% reflectance),
  needs sub-meter (10 cm airplane) imagery.
- Sources: yamagata-u press release (2019); research.ibm.com Nazca blog; PNAS 2024
  (CC BY-NC-ND); Masini & Lasaponara 2019 (UAVSAR).

**Data we can actually load**
- **Sentinel-2** (ESA Copernicus, free, 10 m): usable for LINE-type / trapezoids only;
  too coarse for figurative reliefs. NASA UAVSAR coherence products (free).
- Bing/ESRI basemaps: ToS forbids programmatic download — **do not use**.
- No labeled Nazca tile dataset released with the 2024 paper; airplane imagery is proprietary.

**Module spec `nazca_line_detect`** — CLAHE contrast-normalise → low-threshold Canny →
`cv2.HoughLinesP` tuned for long thin lines (minLineLength from GSD, large maxLineGap) →
skimage `sato`/`frangi` ridge filter → angle/proximity merge. Mask out roads/wadis first.
**Negative control:** run identical pipeline on an Atacama desert tile (no archaeology) —
false-positive line density must not exceed Nazca, else you're finding geology.

---

## 2. Phaistos Disc  🌀  (DONE — first result landed)

**Grounded facts + our run** (see `outputs/phaistos_notes.md`, `symbolseq.py`)
- Evans 45-sign inventory; 241 tokens; 61 word-groups; reading clockwise rim→centre
  (5-dot marker). Machine-readable sequence transcribed to `data/beyond/phaistos_sequence.json`
  (also: `pip install phaistos-disc`, MIT).
- Our `symbolseq` reproduced: H1 **4.99 bits**, IC **0.0361**, H(next|prev) **2.07 vs
  shuffled 2.64 (z=−14)**, top bigram 02→12 ×13, refrain `02 12 31 26` ×3.
- Prior work: Handzel & Gajer 2022 (entropy ≈ natural language); Rumpel 1994 (open-syllable
  model); Braovic et al. 2024 (Computational Linguistics review).

**Negative control:** frequency-matched shuffle (built into `structured_vs_shuffled`) +
a Linear-B syllabary text as a known-script positive control.
**Caveat:** necessary-not-sufficient; N=241 too small to separate language from a
structured non-linguistic template; no bilingual → no decipherment.

---

## 3. Wow! Signal & FRB 121102  📡  (needs `radio_probe`)

**Grounded facts**
- **Wow! (1977)** is NOT a time series — it is **6 intensity samples** ("6EQUJ5",
  SNR ~[6.5,14.5,26.5,30.5,19.5,5.5]σ) over ~72 s (6×12 s), 1420 MHz. The 2024 PHL@UPR
  reanalysis (arXiv:2408.08513, CC BY 4.0, github PHL-UPRA/Ohio-SETI) released an 82×50
  SNR grid and attributes it to a **hydrogen cloud near a solar-type star** — natural.
  Blunt: any FFT/periodicity claim on 82 samples (6 signal) is numerically meaningless.
- **FRB 121102** has PUBLIC data: Breakthrough Listen GBT (21 burst PSRFITS snippets +
  380 TB raw); 93 burst arrival times (Gajjar 2018 / Zhang 2018); **CHIME/FRB Catalog 1**
  (536 FRBs, machine-readable CSV). Activity cycle **~157–161 d** (Rajwade 2020 / Cruces
  2021) — favored explanation orbital/precession (natural). CORRECTION: the 16.35-d period
  belongs to **FRB 180916**, not 121102.

**Module spec `radio_probe`** — FFT power spectrum, autocorrelation, **epoch-folding
(Rayleigh Z²)** for sparse event times, wavelet scalogram, permutation entropy.
**Negative control:** a known pulsar timing series (ATNF/Parkes Vela, CC BY 4.0) +
a synthesised periodic train with noise (known-answer). 
**Caveat (blunt):** pulsars are the universe's most precise natural clocks — periodicity
is necessary, NOT sufficient, for artificiality.

---

*All three keep the lab's rule: known-answer test + negative control + "structure ≠ message."*
