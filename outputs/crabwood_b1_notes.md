# B1 — Crabwood disc crop + BER sweep

## Crop
- Source: `crabwood_2002_tt_oh2.jpg` (true face+CD aerial)
- Output: `data/images/crabwood_2002_disc_crop.png` (246×246) + `data/catalog/crabwood_disc_crop.json`
- **Do not use** `crabwood_2002_tt_disc.jpg` / `*_disc2.jpg` — appear mislabeled (tufted circle / Julia Set)

## Sweep
- Tool: `tools/ccat/crabwood_bits.py --sweep` (center→outward default; turns 8–20; θ; polarity; MSB; CCW/CW)
- Trials: 4992
- **BER floor: 0.4495** (best vs Red Collie; Vigay ~0.46)
- Best preview is gibberish — not near plaintext

## Verdict
Web-res disc (~110 px radius, ~1200 bits) is below sampling Nyquist for independent decode.
B1 done as framework + resolution floor; further BER gains need **C1** high-res disc master.
