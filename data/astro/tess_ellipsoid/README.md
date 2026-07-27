# G17 — TESS SN 1987A SETI Ellipsoid (v2)

## Source

**Cabrales et al. 2024, AJ 167:101** — *Searching the SN 1987A SETI Ellipsoid with TESS*  
DOI: [10.3847/1538-3881/ad2064](https://doi.org/10.3847/1538-3881/ad2064) (open access, CC-BY 4.0)  
arXiv: [2402.11037](https://arxiv.org/abs/2402.11037)

TESS PDCSAP light curves: CC-BY 4.0 (NASA / MAST).

## The SETI Ellipsoid — 3–5 sentences

The SETI Ellipsoid is a geometric target-prioritisation strategy for technosignature
searches. It assumes an extraterrestrial agent could use a rare, galactic-scale event —
here, supernova SN 1987A (observed 1987 February 23 at Earth, at a distance of
51.4 ± 1.2 kpc in the LMC) — as a *Schelling point* to broadcast a synchronised
beacon. The locus of stars that have seen the supernova and whose line-of-sight
distance allows a light-speed signal to arrive at Earth at a given epoch sweeps out
an ellipsoid with Earth and SN 1987A as its foci. By matching precise 3D positions
from *Gaia* EDR3 (Bailer-Jones+2021) to TESS CVZ light curves, Cabrales+2024
identified 32 targets whose Ellipsoid crossing falls within TESS 2-minute data.

## Paper result (ground truth)

> **"We examined the TESS light curves of these stars during the Ellipsoid crossing
> event and found no anomalous signatures."**  
> — Cabrales+2024, §4.2, abstract

No dips, no flares with anomalous morphology, no outlier-detection "weirdness" scores
coordinated with the crossing time. The paper's honest result is a **non-detection**.

## This catalog

`cabrales_2024_targets.json` contains all 32 targets transcribed from Table 2 of
Cabrales+2024. Each entry includes TIC ID, coordinates (RA, Dec) with uncertainties,
geometric distance from Bailer-Jones+2021 (with asymmetric 16%/84% uncertainties),
Ellipsoid crossing time in decimal years (with σ_et timing uncertainty), and the
TESS cycle (12 targets in Cycle 1 [crossing 2018–2019], 20 targets in Cycle 3
[crossing 2020–2021]). The crossing time is also given as an approximate TBJD value
(BJD − 2457000, the convention used by TESS data products); see the conversion note
in the JSON metadata.

## Stance (mission rule)

**Structure ≠ message. Ellipsoid geometry ≠ technosignature. Cabrales non-detection
≠ "we found dips."** The catalog exists to anchor an honest null-sharpen or
replication, not to manufacture a discovery claim.

## Off-ellipsoid controls

A small set of control TIC IDs is included for FPR calibration. These are real TESS
CVZ stars that are **not** within 0.5 ly of the SN 1987A Ellipsoid at any TESS epoch.
Selection rules are documented in the JSON.

## Licensing note

TESS PDCSAP photometry is provided under CC-BY 4.0 via the Mikulski Archive for
Space Telescopes (MAST). The Cabrales+2024 paper is open-access (CC-BY 4.0). This
derivative catalog is distributed for research purposes only; no claim is made to
the original data.

## Do NOT touch

G20 (Boyajian), G13 (VASCO), radio/BLC1, Amazon, script probes, or
MISSION_BOARD.md (except a board row if Captain later requests).
