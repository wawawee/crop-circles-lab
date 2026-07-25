# data/scripts/cretan_hieroglyphic/

Public droplet for the **G15 — Cretan Hieroglyphic (CH)** bipartite admin /
network-isomorphism probe (`tools/scripts/cretan_hieroglyphic_probe.py`).

## Honest provenance — 2026-07-25

### What is NOT here, and why

- **CHIC** (`Corpus Hieroglyphicarum Inscriptionum Cretae`, Godart &
  Olivier, Trismegistos / Fabiola 1996) is the standard printed
  catalogue of Cretan Hieroglyphic. It is a **copyrighted book**: there
  is currently **no** public CSV / JSON / TSV machine-readable dump of
  the full CHIC corpus on Zenodo, GitHub, Mnamon, Aegeus Society, or
  any other open archive.
- The Unicode block `U+10100–U+1013F` (Aegean Scripts) encodes the
  *sign inventory* but does **not** ship a corpus dump.
- **GORILA / SigLA / mwenge** are Linear A, not Cretan Hieroglyphic.
  Same Aegean provenance, different script.

Until CHIC is licensed for redistribution, the probe **must** fall back
to a clearly-labelled synthetic corpus that mirrors the publicly-known
Evans sign-inventory shape.

### What IS here

- `README.md` — this file (provenance + swap-in instructions).
- `corpus.json` — optional. When present **and** matching the agreed
  schema, the probe uses it and writes `is_synthetic = False`. Until a
  real drop is licensed, **do not commit** `corpus.json` to the public
  repo. Drop it locally and re-run.

### The synthetic fallback (transparent)

The synthetic corpus is generated at run-time inside the probe
(see `tools/scripts/cretan_hieroglyphic_probe.py:synth_ch_corpus`) when
`corpus.json` is absent. It draws sign IDs from an Evans-style
inventory (CH_001 … CH_096), with `SEP` markers that abstract the
arithmogram slots, so the **synthetic = clearly labelled** invariant
holds. Run with `--synthetic` to force the synthetic path even if a
local real `corpus.json` happens to be on disk.

## Swap-in instructions (when a real CHIC dump lands)

1. Convert the dump to the agreed schema and drop in as `corpus.json`:
   ```json
   {
     "sequences": {
       "KNOSSO_PK_01": ["CH_017", "CH_004", "CH_004", "SEP", "01"],
       "KNOSSO_PK_02": ["CH_017", "CH_005", "SEP", "08"]
     }
   }
   ```
   The probe splits on `SEP` to give each inscription a slot / row
   decomposition; without `SEP`, every inscription is one row.

2. Do **not** commit real CHIC transcriptions to the public repo —
   they are copyrighted. The loader reads them locally and writes
   `is_synthetic = False`.

3. Re-run the probe. The output `run.json` will have
   `is_synthetic = False` and a `data_source` line naming the new dump.

## Notes

- `tools/scripts/linear_a_probe.py` already owns the Linear A/B side of
  the comparison; G15 reuses only its **structural shape** as the
  network-isomorphism comparator.
- The probe will keep refusing to call its output "CHIC" regardless of
  input — that label is reserved for the actual Godart & Olivier
  printed corpus.
