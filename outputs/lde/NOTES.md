# G19 — Long Delayed Echoes historic series probe  🟢
*Generated: 2026-07-25T21:09:14.894919+00:00*

## Stance
Long Delayed Echoes (LDEs) are a real ionospheric/magnetospheric propagation phenomenon with documented natural explanations (ducting, mode conversion, multi-round-the-world, plasma cloud reflection; cf. Holm 2004 / UiO review). This probe measures delay distribution and recurrence structure ONLY. The honest prior is NO_SIGNAL. Duncan Lunan's 1973 'Epsilon Boötis space probe' interpretation is a claim-under-test — not a fact. Lunan withdrew the claim in 1976 acknowledging methodological flaws. STRUCTURE != MESSAGE.

### Forbidden phrases (logged)
- `alien relay confirmed`
- `Lunan proved`
- `Epsilon Boötis probe`
- `extraterrestrial communication`
- `ET probe`
- `Bracewell probe verified`
- `world echo is alien`
- `space probe confirmed`
- `alien relay`
- `extraterrestrial relay`

## Source / data
Datasets digitized from Faizullin (2010) arXiv:1007.4054: Stormer 1928 series (5 series, 58 delays, stopwatch ~0.5 s precision), Appleton 1934 histogram (77 delays, digitized from Fig. 1), Crawford 1967 histogram (50 delays, estimated from qualitative description in Faizullin 2010 / Vidmar & Crawford 1985 JGR).

### Stormer_1928
- N=58  min=3s  max=15s  mean=9.5345s  sd=3.2282s
- Top modes: [(8, 16), (12, 7), (5, 6), (9, 5), (13, 5)]
- H delay bits: 3.2589
- AC peak: lag=10, val=0.1727
- FFT peak: bin=7, freq=0.1207, power=1647.9026, P/mean=3.5733
- Scramble null z=-0.55 NO_EXCESS
- Uniform null z=-0.56 NO_EXCESS

### Appleton_1934
- N=77  min=2.0s  max=15.0s  mean=8.2468s  sd=3.1711s
- Top modes: [(8, 14), (5, 9), (9, 8), (6, 7), (12, 7)]
- H delay bits: 3.5638
- AC peak: lag=1, val=0.937
- FFT peak: bin=1, freq=0.013, power=3062.5631, P/mean=10.0595
- Scramble null z=14.47 STRUCTURE
- Uniform null z=14.65 STRUCTURE

### Crawford_1967
- N=50  min=2.0s  max=40.0s  mean=7.08s  sd=6.0789s
- Top modes: [(2, 12), (8, 10), (3, 4), (7, 4), (4, 3)]
- H delay bits: 3.3938
- AC peak: lag=1, val=0.5628
- FFT peak: bin=1, freq=0.02, power=4046.3, P/mean=3.2681
- Scramble null z=6.07 STRUCTURE
- Uniform null z=5.63 STRUCTURE

## Verdict: **STRUCTURE_SIGNAL | z_stormer=-0.55 | z_appleton=14.47 | z_crawford=6.07**

Three independent LDE datasets analyzed. Honest prior: NO_SIGNAL. Delay distributions cluster around small integers (3–15 s for Stormer/Appleton; 2–8 s for Crawford). This likely reflects measurement precision (stopwatch rounding) and the real physics of magnetospheric ducting paths — not an alien communication protocol.

## Caveats
1. **Stormer series** were timed by stopwatch (~0.5–1 s precision). The 5 series are not independent — they are sequential registrations from the same session.
2. **Appleton histogram** is digitized from a hand-drawn figure (arXiv:1007.4054 Fig. 1). Bin counts are approximate (±1).
3. **Crawford distribution** is estimated from qualitative description ('2 and 8 s most frequent'). The Sears 1974 PhD thesis may contain tabulated values not accessed.
4. **LDEs have natural explanations.** Magnetospheric ducting (Muldrew 1979), mode conversion (Crawford et al. 1970), and multi-round-the-world propagation (Goodacre 1980) explain delays of 1–40 s without invoking extraterrestrial probes.
5. **Lunan withdrew his claim** in 1976, acknowledging methodological flaws in the Epsilon Boötis interpretation.
6. **Delay clustering around integer seconds** may reflect measurement rounding (stopwatch resolution), not an underlying quantized process.

---
*G19 LDE historic series — structure != meaning. No alien relay, no Epsilon Boötis, no Bracewell probe endorsement. Honest prior: NO_SIGNAL.*