# External tools — honest triage (2026-07-25, Hyperagent/finasteos)

A long third-party tool list was proposed. Triaged against our **measure-first, no-woo**
stance. Repo existence/maintenance for the KEEP/MAYBE items is being verified by
sub-agents; anything unconfirmed is marked *(pending verify)* — do not add a tool to the
pipeline until its repo is confirmed real + maintained.

## KEEP — adopted
- **GLYPH-style grid analysis** → implemented natively as `tools/ccat/grid_analyze.py` (task B9).
  Shannon entropy, bit balance, row/col autocorrelation period, 2D-FFT peakiness, mirror/rot
  symmetry, and an "absence signal" (neighbour-agreement z-score vs density-matched shuffles).
  numpy-only, 6/6 known-answer tests. We built it rather than vendor a single-file HTML toy so
  it is scriptable, testable, and feeds directly off `chilbolton_grid.py` output.
  Rationale: its capabilities are fully covered by numpy FFT + entropy, so a native module beats
  a browser dependency.

## MAYBE — only as NEGATIVE CONTROLS / tamper-forensics (repos verified 2026-07-25)
- **Decipher** — github.com/matthewdgreen/decipher — VERIFIED (40★, GPL-3.0, actively
  maintained; CLI `decipher diagnose` / `decipher crack` + MCP server). Use = task **B11**:
  pipe recovered Crabwood/Chilbolton symbol streams through `decipher diagnose` and *expect
  failure* (Crabwood is plain 8-bit ASCII; Arecibo is a bitmap, not a cipher). Failure is the
  informative result. Caveats: GPL-3.0 (copyleft — don't vendor into proprietary code) and it
  needs Python 3.11+ + Rust/C toolchain → run **LOCAL**, not in the py3.9 sandbox.
- **DecryptionToolkeet** — github.com/Aarav2709/DecryptionToolkeet — **404 / DELETED**. Do not use.
- **stegoVeritas** — github.com/bannsec/stegoVeritas — VERIFIED (~408★, GPL-2.0, `pip install
  stegoveritas` + Docker/BlackArch). Use = task **B10**, photo TAMPER detection ONLY:
  `stegoveritas img.jpg -meta -exif -xmp -imageTransform -trailing -carve` → inspect EXIF/XMP
  mismatches, trailing data after the JPEG EOI, carved embedded blobs, colour-plane splice edges.
  Do NOT use `-bruteLSB` / `-password`. **Never** treat a "hidden message" on a field photo as real.
- **ST3GG / StegMaster / StegoForge** — SKIP: zero-activity/one-commit personal repos or
  offensive message-hiding toolkits; nothing stegoVeritas doesn't cover more reliably.

## SKIP — category errors for crop circles (pseudo-science if used)
- **DNA genomics** (Genomi, dna-decode, AlphaGenome, Carbon, open-genome-agent) and
  **DNA data-storage** (Helix, AeonScript, bi0cyph3r): crop formations contain **no real
  DNA / VCF sequence data**. The "DNA double helix" formation is a *shape*, not a genome —
  there is literally nothing to feed a variant caller or an oligo decoder. Using them would
  manufacture the appearance of genetic analysis where none exists.
- **Ancient-script decoders** (Voynich "DECODED", Linear A `Linear_Analytica`, Indus catalogue):
  no matching symbol corpus in our data. The Voynich "decoded → coherent Latin" claim is itself a
  red flag (Voynich is not accepted as decoded). The one transferable idea — Indus' clean-room
  "shape catalogue without claiming to read a language" — is already our stance.

## Bottom line
For the **decoding** question the kit is now Ulfberht-grade: the message formations (π, Arecibo
reply, Crabwood) are already solved and known-human-feasible, and `grid_analyze` answers
"is there a hidden channel?" with a number. Remaining value is **rigor** (BER floors, the Chualar
control, rectified re-measurement) — not more tools. Most likely honest finding: **no hidden
information beyond the known human-made encodings.**
