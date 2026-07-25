# MISSION — what this lab is

This project began as crop-circle forensics. It has become a **general instrument for
computational / forensic anomalistics** — the scientific study of anomalies — practised
in a **zetetic** spirit: *inquire*, neither believe nor debunk by reflex.

> **Prior art / kin:** Marcello Truzzi's *anomalistics* & *zeteticism*; the Society for
> Scientific Exploration / Journal of Scientific Exploration; SETI-style signal analysis.

## The goal
Turn the question **"is there a real signal here?"** into a **reusable, open,
control-first toolkit** that runs on any contested dataset — wheat, stone, script, sky,
genome — and returns an **honest verdict** (signal vs no-signal *against a control*),
not a belief.

## The cardinal rules (what makes it science, not a tin-foil hat)
1. **Structure ≠ meaning.** We can prove a pattern is non-random and still not know what
   (if anything) it *means*. Phaistos is our lodestar: conditional-entropy **z = −14**
   and a period-3 refrain — decisively structured — yet undeciphered. Measure the beat;
   don't pretend to read the words.
2. **Every result faces a negative control.** Same analysis on (a) random data of matched
   size/entropy, (b) a known hoax, (c) a known natural process. If the result doesn't beat
   the control → file as **"no signal."**
3. **Validate on known answers first.** Every module ships with tests that recover a
   planted truth (a 4:3 ratio, a Koch dimension, "HELLO WORLD" in a grid) before we trust
   it on real data.
4. **Debunk your own best cases.** We downgraded Cherhill, called the 1996 "Julia Set"
   human, and flagged the Wiltshire cluster as selection bias. The sword cuts both ways.

## The four borrowed fields (one toolkit)
- **Archaeoastronomy** — monument alignments, solstice/lunar (`spatial_report`, `astro_probe*`)
- **Quantitative linguistics & cryptanalysis** — entropy, IC, Markov, bit decoding
  (`symbolseq`, `bitstream`, `encoding`, `ratios`)
- **Digital image forensics** — masks, geometry, ELA/tamper screens (`preprocess`,
  `circle_extract`, `grid_analyze`, metadata)
- **Signal detection** — is there structure above noise, with a null control (all of the above)

## Scope & ethics
Private, non-commercial research. Third-party imagery is analysis input only, not
redistributed; freely-licensed items are flagged (`NOTICE.md`). The deliverable is
**reproducible methods + honest verdicts** that other researchers can reuse — regardless
of whether the answer is aliens, ancient coders, or human creativity.

*Ulfberht was always the method, not the sword.* 🌾→🌌
