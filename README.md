# Crop Circles Lab — local geometry / fractal / forensic toolkit

Personal research lab (foil-hat optional). Combines:
- **CCAT** — OpenCV image analysis (edges, Hough, DBSCAN clustering, swirl, dashboards)
- **Forensics cores** — Hawkins ratios, fractal dimension, message encoding (π / Crabwood / Arecibo / Julia classification)

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
data/images/       aerials & references (see ATTRIBUTION.txt)
data/catalog/      formation metadata / acquisition status
outputs/           generated reports & dashboards
```

## Licensing / images

Many aerials are © Temporary Temples, Lucy Pringle, Getty, etc.
See `data/images/ATTRIBUTION.txt`. This repo is intended as a **private** research backup.
Do not redistribute photographer originals.

## Missing targets

Edmonton 1999, BLT iron-glaze plant close-ups (Cherhill 1993), Logan UT 1996, Eltopia WA 1998 —
still hunting (BLT site currently offline).
