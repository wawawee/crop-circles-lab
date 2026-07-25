# `data/radio/lde/` — Long Delayed Echoes (LDE) historic datasets

## Stance

Structure != meaning. LDE is a real ionospheric/magnetospheric propagation
phenomenon — this lab measures delay distribution, not "alien relay." The
honest prior is NO_SIGNAL: LDEs have documented natural explanations
(magnetospheric ducting, mode conversion, multiple round-the-world, plasma
cloud reflection). See Holm 2004 / UiO review for the five natural
hypotheses.

Duncan Lunan's 1973 "Epsilon Boötis space probe" interpretation is a
**claim-under-test**, not a fact. Lunan himself withdrew the claim in 1976
acknowledging methodological flaws.

## Datasets

| File | Source | Years | N | Delays (s) | Precision |
|------|--------|-------|---|------------|-----------|
| `stormer_1928_series.json` | Stormer & van der Pol, Eindhoven–Oslo (Faizullin 2010) | 1928–1929 | 58 | 3–15 (series), up to 3.5 min stated | ~0.5 s (stopwatch) |
| `appleton_1934_histogram.json` | Appleton, World Radio Research League (Faizullin 2010 Fig. 1) | 1934 | 77 | 2–15 | ~1 s (histogram bins) |
| `crawford_1967_distribution.json` | Crawford, Sears, Bruce, Stanford (JGR 1970, 1985) | 1967 | 50 | 1–40 | ~1 s (histogram bins) |

### Columns (all sets)

- `delay_s`: echo delay in seconds
- (in histograms) `counts`: number of observed echoes at that delay
- (in series) `values`: raw ordered delay values as registered

## Provenance

### Stormer 1928 series (primary source)

The five series are transcribed from Faizullin (2010) arXiv:1007.4054 section
2, which itself cites the original Stormer & van der Pol 1928–1929
experiments. The series were recorded on **1928-10-11** during coordinated
transmissions from PCJJ Eindhoven (31.4 m, ~9.55 MHz) received by Hals in
Oslo. Van der Pol's telegram: "echo time ranged between 3 and 15 seconds,
half of the echoes lasted more than 8 seconds!"

### Appleton 1934 histogram (digitized from figure)

The histogram is Fig. 1 in Faizullin (2010), originally from Appleton's 1934
LDE study using World Radio Research League transmissions. The figure is a
hand-drawn bar chart showing "Number delays" vs "Time delays (sec)". Bin
counts were digitized manually; estimated error ±1 count per bin.

### Crawford 1967 distribution (estimated from qualitative description)

Crawford et al. (1970) report that "delays with 2 and 8 seconds were the
most frequent." The full histogram shape is not published in accessible
machine-readable form; bin counts here are estimated to match the qualitative
description and known total N (~50). The Sears 1974 PhD thesis (DTIC
ADA003070) may contain tabulated values — not accessed.

## Forbidden claims

- "alien relay confirmed"
- "Lunan proved"
- "Epsilon Boötis probe"
- "extraterrestrial communication"
- "ET probe"
- "Bracewell probe verified"
- "world echo is alien"

## References

1. Faizullin, R.T. (2010). "Geometrical joke(r?)s for SETI." arXiv:1007.4054.
2. Stormer, C. (1928). "Short Wave Echoes and the Aurora Borealis." *Nature* 122, 681.
3. van der Pol, B. (1928). *Nature* 122, 878–879.
4. Crawford, F.W., Sears, D.M., Bruce, R.L. (1970). JGR 75(34), 7326–7332.
5. Vidmar, R.J. & Crawford, F.W. (1985). JGR 90(A2), 1523–1530.
6. Holm, S. (2004). "The Five Most Likely Explanations for Long Delayed Echoes." UiO.
7. Lunan, D. (1973). "Space Probe from Epsilon Boötis." *Spaceflight* 16, 122–131.
8. Lunan, D. (1976). Withdrawal of Epsilon Boötis claim. (Cited in Holm 2004.)
9. Bracewell, R. (1960). "Communications from Superior Galactic Communities." *Nature* 186, 670–671.
10. Muldrew, D.B. (1979). "Generation of long delay echoes." JGR 84, 5199–5215.
