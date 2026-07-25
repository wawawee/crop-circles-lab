# ROADMAP — Beyond Wheat 🌾 → 🌌

The lab started on crop circles, but the machinery — **measure structure, decode
candidate signals, and always run a negative control** — is domain-agnostic. This
is the plan to grow it into a general *mystery-analysis* toolkit without losing the
scientific spine.

## The one rule that keeps this science
Every new domain must ship with:
1. a **known-answer test** (the tool recovers a planted signal it is supposed to), and
2. a **negative control** (a natural/random source it must NOT light up on).

And the cardinal caveat, stated once for all domains:
> "Structured" / "natural-language-like entropy" / "periodic" is **necessary, not
> sufficient**. Pulsars are periodic. Coastlines are fractal. Noise is high-entropy.
> We report a number and a control — never a conclusion the data hasn't earned.

## What already generalises (reuse map)

| Existing module | Already usable for |
|---|---|
| `forensics/bitstream.py` | any discrete symbol/bit sequence: Phaistos spiral, Wow! code, Arecibo-style grids |
| `forensics/ratios.py` | any geometry with circle/length ratios (megaliths, geoglyph spacing) |
| `forensics/fractal.py` | coastlines, geoglyphs, reliefs, any binary mask |
| `ccat/grid_analyze.py` | any binary grid: reliefs, petroglyph panels, message bitmaps |
| `ccat/info_theory.py` | entropy / LZ of any symbol stream (scripts, signals) |
| `ccat/preprocess.py` | perspective-correct / mask any aerial or scan |
| `ccat/spatial_report.py` | monument/site proximity + date/lunar tests, any lat/lon set |

## New probe modules (specs)

| Module | Lib | Input | Method | Negative control |
|---|---|---|---|---|
| `nazca_line_detect` | OpenCV | satellite/aerial | HoughLinesP tuned for long thin low-contrast lines; ridge filter | random desert tile must yield ~0 long lines |
| `relief_probe` | OpenCV/skimage | stone-relief photo | low-contrast edge + repeat-motif detection (Göbekli H-glyphs) | blank rock face |
| `radio_probe` | numpy/scipy | 1D time series | FFT power spectrum, autocorrelation, epoch-folding, entropy | a known pulsar (periodic ≠ artificial) |
| `pointcloud_probe` | Open3D/PDAL | LIDAR/sonar cloud | plane/edge fit, 90-degree-corner test (Yonaguni, Dwarka) | natural rock outcrop scan |
| `bio_probe` | BioPython | FASTA/haplogroup | k-mer entropy, motif/cluster stats | shuffled genome |
| `astro_probe` | astropy/skyfield | date + lat/lon | solstice/star-alignment, sky-at-epoch (Göbekli, Voynich charts) | random date/site |
| `network_probe` | networkx | sites/symbols graph | centrality, community, alignment edges | Erdos-Renyi random graph |
| `stego_probe` | Pillow/OpenCV | image file | ELA / bit-plane / LSB — TAMPER only, never "hidden alien msg" | clean camera JPEG |
| `synth_probe` | diffusion/GAN | — | generate synthetic formations as extra hoax negatives for the B6 classifier | — |

## First three white rabbits (Kimi's top-3) — scouts dispatched 2026-07-25
1. **Nazca Lines** — `ccat` is ~90% there; add `nazca_line_detect`. Scout: data access + the Yamagata/IBM AI finds (hundreds of new geoglyphs). *Fastest win.*
2. **Phaistos Disc** — perfect fit for `bitstream` + `info_theory`: a 3700-year-old spiral of 45 signs (241 tokens). The sign SEQUENCE is published → we can run entropy / IC / first-order Markov / LZ vs shuffled + Linear-B baselines **today, no images**. Scout: fetch the machine-readable sequence.
3. **FRB 121102 / Wow!** — `radio_probe` on public burst time series; pulsar as the negative control. Scout: what raw data actually exists (Wow! is only ~6 intensity samples; FRB has real public series).

*(Background scouts N/P/W are grounding items 1-3 with concrete data sources; findings fold in next.)*

## Sanity note
This stays a **private analysis toolkit**, not a claims factory. The most likely
honest outcome in most of these — as with crop circles — is "human/natural, no
surviving hidden channel." The value is the rigor and the reusable machinery.
