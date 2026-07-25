# Crop Circles Lab — local geometry / fractal / forensic toolkit

> **Agents: read [`TASKLIST.md`](TASKLIST.md) + [`MISSION_BOARD.md`](MISSION_BOARD.md) first** — night-shift domains beyond wheat live on the mission board / [`reports/mission_dashboard.html`](reports/mission_dashboard.html).
>
> **Images:** see [`NOTICE.md`](NOTICE.md) + `data/images/ATTRIBUTION.txt` — private research use; no commercial redistribution of aerials.

Personal research lab (foil-hat optional). Combines:
- **CCAT** — OpenCV image analysis (edges, Hough, DBSCAN clustering, swirl, dashboards)
- **Forensics cores** — Hawkins ratios, fractal dimension, message encoding (π / Crabwood / Arecibo / Julia classification)
- **Signal** — bitstream / LSB / window-entropy probes (multiplex + genomic-DSP heritage) for hunting *encoded messages* anywhere

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python tools/ccat/dashboard.py data/images/julia_set_1996_tt_oh.jpg --out outputs/julia_dash.png
python tools/ccat/report.py --batch data/images --out outputs/batch_table.csv
python tools/forensics/tests/test_ratios.py
python tools/forensics/tests/test_fractal.py
python tools/forensics/tests/test_encoding.py
```

## Layout

```
tools/ccat/        computer vision toolkit
tools/forensics/   validated math/encoding cores (+ tests)
tools/signal/      bitstream / LSB / window-entropy message probes
data/images/       aerials & references (see ATTRIBUTION.txt)
data/catalog/      formation metadata / acquisition status
outputs/           generated reports & dashboards
```

## Deep-dive tools (message / preprocess / lab)

```bash
# 1) Preprocess → binary mask
python tools/ccat/preprocess.py data/images/crabwood_2002_tt_disc.jpg --out outputs/mask.png

# 2) Crabwood spiral ASCII sampler (BER vs known plaintext)
python tools/ccat/crabwood_bits.py data/images/crabwood_2002_tt_disc.jpg --out outputs/crabwood_bits.json

# 3) Chilbolton 23×73 grid sampler
python tools/ccat/chilbolton_grid.py data/images/chilbolton_message_2001_tt.jpg --out outputs/chilbolton_grid.json

# 4) Radius entropy / log-spiral / diatonic probes
python tools/ccat/info_theory.py --synthetic-julia
python tools/ccat/info_theory.py data/images/julia_set_1996_getty.png

# 5) Archive BLT lab reports from Wayback
python tools/ccat/blt_archive.py --out data/reports/blt_wayback

# 6) Message-hunting signal probes (multiplex / stego / Shannon windows)
python tools/signal/bitstream_probe.py --demo-multiplex
python tools/signal/lsb_probe.py data/images/chualar_2013_nvidia_hoax.png
python tools/signal/tests/test_bitstream.py
```

Findings so far: web-res Crabwood discs give BER≈0.5 (random) — need higher-res disc crop.
Synthetic Julia confirms log-spiral classification. Logan BLT lab #79 + field photos archived.

## Licensing / images

Many aerials are © Temporary Temples, Lucy Pringle, Getty, etc.
See `data/images/ATTRIBUTION.txt`. This repo is intended as a **private** research backup.
Do not redistribute photographer originals.

## Missing targets

Edmonton 1999, BLT iron-glaze plant close-ups (Cherhill 1993), Logan UT 1996, Eltopia WA 1998 —
still hunting (BLT site currently offline).
