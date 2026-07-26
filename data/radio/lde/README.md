# Long Delayed Echoes (LDE) Historic Data — G19 Mission

**Mission**: G19 — Long Delayed Echoes historic series  
**Stance**: structure ≠ message. Historic delay series ≠ lunar relay.  
**Source seed**: arXiv:1007.4054 (Faizullin 2010) — Stormer/Appleton/Crawford digitization  
**Curated**: 2026-07-27 (this repo)

---

## Files

| File | Description |
|------|-------------|
| `lde_master.csv` | Machine-readable master table (100 delay observations, 1927–1978) |
| `lde_master.json` | Same data as JSON array of objects |
| `stormer_1928_oct11.csv` | Stormer 1928 Oct 11 Oslo series (14 delays) — Lunan's "Bootes" series |
| `vdpol_1928_oct24.csv` | van der Pol 1928 Oct 24 simultaneous Oslo+Eindhoven (20 delays) |
| `hals_1934.csv` | Hals 1934 World Radio summary (11 delays, 1927–1934) |
| `appleton_1934.csv` | Appleton 1934 World Radio Research League (32 delays, UK/Switzerland) |
| `crawford_1970.csv` | Crawford et al. 1970 JGR + 1978 Alaska (20 delays, up to 40s) |

---

## Schema (CSV / JSON)

| Field | Type | Description |
|-------|------|-------------|
| `index` | int | Row index (1-based) |
| `delay_s` | float | Echo delay in seconds |
| `source` | string | Short citation tag (e.g., `Stormer_1928`, `Crawford_1970`) |
| `date` | string | Observation date (YYYY-MM-DD or YYYY-YYYY for campaigns) |
| `observer` | string | Primary observer |
| `location` | string | Receiver location |
| `frequency_mhz` | string/float | Transmit frequency (or band) |
| `notes` | string | Provenance / accuracy caveats |

---

## Primary Sources (Cite These)

1. **C. Størmer**, "Short wave echoes and the aurora borealis," *Nature* **122**, 681 (1928). DOI: 10.1038/122681a0  
   — 14 delays from Oslo, 11 Oct 1928, 15:45–16:00 UTC, 9.55 MHz. Størmer's accuracy caveat: "The times noted by me can lay no claim to great accuracy, because I was not adequately prepared."

2. **B. van der Pol**, "Short wave echoes and the aurora borealis," *Nature* **122**, 878–879 (1928). DOI: 10.1038/122878a0  
   — Simultaneous Oslo + Eindhoven observations, 24 Oct 1928, 16–17 UTC. Timing: stopwatch + "second hand of an ordinary watch."

3. **J. Hals**, "The discovery of echoes of long delay," *World Radio* (BBC), 4 parts Nov–Dec 1934.  
   — 1927–1934 Oslo observations, delays 2–30 s. "Delays of 2 and 8 seconds were the most frequent."

4. **E. V. Appleton**, "Short wave echoes and the aurora borealis," *Nature* **122**, 879 (1928).  
   — 1934 World Radio Research League experiments, UK & Switzerland transmitters.

5. **F. W. Crawford, D. M. Sears, R. L. Bruce**, "Possible observations and mechanism of very long delayed radio echoes," *J. Geophys. Res.* **75**, 7326–7332 (1970). DOI: 10.1029/JA075i034p07326  
   — Stanford 1967–1970, 5–12 MHz, delays up to 40 s. "Delays of 2 and 8 seconds were the most frequent."

6. **R. J. Vidmar & F. W. Crawford**, "Long-delayed radio echoes: Mechanisms and observations," *J. Geophys. Res.* **90**, 1523–1530 (1985). DOI: 10.1029/JA090iA02p01523  
   — Five most likely natural explanations (magnetospheric ducts, etc.).

7. **R. T. Faizullin**, "Geometrical joke(r?)s for SETI," arXiv:1007.4054 (2010).  
   — Digitization source for this repository; discusses Lunan/Filipenko geometrical interpretations.

---

## Known Interpretation Claims (Under Test — **NOT** Confirmed)

| Claim | Proponent | Core Assertion | Status in This Repo |
|-------|-----------|----------------|---------------------|
| "Lunan probe" / Epsilon Bootis | Duncan Lunan (1973) | Stormer delays plot constellation Bootes; 3s dot = Epsilon Bootis | **CLAIM_UNDER_TEST** — shuffle + prosaic nulls applied |
| Periodic table encoding | Filipenko | Integer delays map to element numbers | **CLAIM_UNDER_TEST** |
| Moon-Earth L4/L5 relay | Bracewell / Lunan | Delay times = probe at lunar Lagrange point | **CLAIM_UNDER_TEST** |

**Policy**: This repo digitizes the *observations*, not the interpretations. The probe tool (`tools/radio/lde_probe.py`) tests the Lunan "moon relay" claim with shuffle controls and prosaic nulls. Verdict must be one of: `NO_SIGNAL`, `UNDETERMINED`, `CLAIM_FAILS_NULL`. Never confirms Lunan.

---

## Accuracy & Provenance Notes

- **1920s timing**: Stopwatch or second-hand watch — ±1–2 s uncertainty typical.
- **Størmer 1955 recollection**: "I noted in seconds... no claim to great accuracy."
- **Crawford 1970**: "Delays with 2 and 8 seconds were the most frequent with the rate shift and time contraction compared to the time between the impulses of the original signal."
- **Frequency dependence**: Most 1920s obs at ~9.55 MHz (31.4 m); Crawford 5–12 MHz; modern amateur 1.8–1296 MHz.
- **No digital baseband exists** — these are human-logged delay estimates, not IQ recordings. The probe tool operates on delay *values only*.

---

## Usage

```bash
# Run the LDE probe (period/FFT-ish/clustering + shuffle nulls)
python3 tools/radio/lde_probe.py --data data/radio/lde/lde_master.json \
    --out-json outputs/radio/lde_run.json \
    --out-md outputs/radio/lde_NOTES.md

# Run tests (≥12 required)
python3 -m pytest tools/radio/tests/test_lde_probe.py -v
```

---

## License

Data: Public domain historical observations (pre-1930 publications) + fair-use transcription of later papers.  
Code: MIT (this repository).