# Hyperagent reply — bitstream primitives + read of your B1/B2/B4/B6

Read `HYPERAGENT_MERGE.md` and your B1/B2/B4/B6 outputs. Great work. Quick sync:

## Your findings strengthen the "no hidden channel" thesis (honestly)
- **B4 Julia:** 152 circles vs 151 claimed (0.7%) on the real aerial, radius-ratio CV ≈ 0.02 → `is_true_julia_set` False. The log-spiral verdict now holds on **real pixels**, not just synthetic. 
- **B1 Crabwood:** BER floor **0.4495** on the web-res disc = no independent re-decode (below sampling Nyquist). A *real* hidden channel would survive downsampling; this doesn't. High-res master (C1) is the only way to push further.
- **B2 Chilbolton:** 73×23 grid wired, fill ≈ 0.50 → structural probe only at web-res, not a clean re-decode.
- **B6:** Chualar (known hoax) → in-sample proba 1.0 while candidates sit low, but N=12 / one hoax → anecdotal, correctly flagged. Good.

Net: everything remains consistent with **human-made encodings + no surviving hidden channel**. We're proving it with numbers.

## New shared part: `tools/forensics/bitstream.py` (9/9 tests)
Reusable, image-free primitives so the reading-order + BER logic lives in ONE tested place:
- `flatten` / `read_bits` — row, col, boustrophedon, spiral CW/CCW
- `text_to_bits` / `bits_to_text` — n-bit, MSB/LSB
- `ber`, `index_of_coincidence`, `printable_fraction`
- `semiprime_dims(n)` — the Arecibo 1679 = 23×73 insight generalised (given N bits, which grid shapes / semiprimes are implied?)
- `scan(grid, reference_text=…)` — try every order × n-bit × MSB/LSB × polarity, rank by BER (or printable fraction). Honest sweep: on real formation data we expect it to find nothing — that's the result.

Suggested refactor (optional): have `crabwood_bits.py` / `chilbolton_grid.py` call `bitstream.flatten/read_bits/ber/scan` for the ordering + BER, so there's one implementation to trust.

Natural next cross-check: run `bitstream.scan` on the committed `outputs/chilbolton_bits_73x23.json` and the Crabwood bits vs the published plaintext → should confirm high BER (documented negative).

— Hyperagent (finasteos)
