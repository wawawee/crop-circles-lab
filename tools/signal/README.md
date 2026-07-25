# tools/signal — message hunting (not crop-or-aliens)

Slim port of the **Jeremy Weeks multiplex** lab (Dec 2025) + **covid19-genomic-dsp** Shannon windows + a **TRUsteg-inspired** LSB probe (no Tk GUI).

**Stance:** Look for *encoded payloads* anywhere — human puzzle, stego, crypto, or weird geometry. High entropy ≠ aliens; it often means “someone balanced the bits on purpose.”

## Tools

| CLI | What |
|-----|------|
| `bitstream_probe.py` | Entropy, balance, run density, LZ76, autocorr, 2D reshape, ASCII candidates |
| `lsb_probe.py` | RGB bitplane / LSB entropy + light χ²; optional `stegano` extract |
| `window_entropy.py` | Sliding-window Shannon on bits or image bands |

```bash
source .venv/bin/activate

# Replay the Weeks L20 finding (entropy ≈ 0.9991)
python tools/signal/bitstream_probe.py --demo-multiplex --out outputs/signal/multiplex_l20.json

# Any recovered 01 string (Crabwood sweep bits, puzzle dumps, …)
python tools/signal/bitstream_probe.py --bits 0100110001101111...

# Image LSB triage
python tools/signal/lsb_probe.py data/images/chualar_2013_nvidia_hoax.png --out outputs/signal/chualar_lsb.json

# Low-entropy bands (captions / panels / flat sky)
python tools/signal/window_entropy.py data/images/chilbolton_message_2001_tt.jpg --window 24 --step 8

python tools/signal/tests/test_bitstream.py
```

## Provenance

- `data/reports/multiplex/` — archived README + final report from `~/MULTIPLEX_ANALYSIS_*`
- Original analyzer `.py` scripts were missing on disk; metrics reimplemented from the report
- Genomic DSP parent: `~/covid19-genomic-dsp/`
- Stego GUI parent: `~/TRUsteg/` (logic only; CLI here)

## How this sits next to CCAT

- **CCAT / forensics** — geometry in the field (circles, spirals, grids)
- **signal/** — whatever bits you pull out of that geometry (or any other file)
