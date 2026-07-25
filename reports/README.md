# reports/

Two static, offline-first pages for the Mystery Analysis Lab. Both are pure
HTML/CSS/SVG/vanilla-JS — no build step, no framework, no external chart
libraries. Open by double-clicking (they run fine over `file://`).

## Pages

### `findings_gallery.html` — the findings gallery (flagship)
The visual write-up of what the lab has actually measured. Every panel shows a
result **next to its negative control**, so structure is never mistaken for
meaning. Sections:

- **Hero** — ethos, doc links, the verdict-tag legend, and a `N of 8 domains`
  coverage line.
- **Phaistos** (the star panel) — two independent facts side by side:
  1. *Conditional entropy vs shuffle* — observed `H(next|prev) ≈ 2.07 bits`
     drawn against the shuffle null (Gaussian bell centred at 2.64), with the
     `z ≈ −14 (13.9σ below chance)` bracket.
  2. *Refrain metre* — the 31 groups of side A, with the refrain `02 12 31 26`
     at A16/A19/A22 highlighted, `gap 3` brackets, and the period-6 couplets.
- **Wheat closeout** — Crabwood / Chilbolton / Multiplex, each a gauge with its
  noise-floor control marker.
- **Domain heatmap** — all 8 beyond-wheat domains; covered ones link to their
  panel.
- **Constants** — real filtered hits vs Null A / Null B medians, with the
  chance-zone band.
- **Archaeoastronomy** — the 16 formations in space and time:
  1. *Coordinate scatter* — a hand-rolled `lon × lat` map (north up), zoomed to
     the data bounds, markers coloured by priority. It is a coordinate scatter,
     **not** a geographic basemap.
  2. *Lunar-phase test* — observed mean lunar illuminated fraction drawn against
     the Monte-Carlo **uniform-phase null** (`f=(1-cosθ)/2, θ~U(0,2π)`, E[f]=0.5),
     with the ±2σ negative-control band, the exact-date subset mean, and the
     `z`/`p` annotation. Verdict is read straight from the statistic.
  3. *Monument proximity* — mean / median / within-5 km, **descriptive only**
     (tagged `UNDERDETERMINED`: no matched spatial null yet).
- **Output index** — the `outputs/*.json` artifacts, collapsed in a `<details>`.

### `mission_dashboard.html` — the mission board
Crew / agent status, domain coverage, and recent JSON outputs. Fed by
`mission_status.embed.js`.

## How to open
Double-click either `.html` file, or open it in a browser via `file://`. No
server needed. Data is loaded from a sibling `*.embed.js` file next to the page.

## Data flow
```
data/catalog/formations.csv  →  tools/astro/archaeo_probe.py  →  outputs/astro/archaeo_probe.json  ┐
                                                                                                     ├→ tools/build_findings.py → reports/findings_data.embed.js → findings_gallery.html
other outputs/*.json  ───────────────────────────────────────────────────────────────────────────┘
outputs/*.json  →  tools/mission_status.py   →  reports/mission_status.embed.js  →  mission_dashboard.html
```
`tools/astro/archaeo_probe.py` is run **first** to (re)produce
`outputs/astro/archaeo_probe.json` (the control-first lunar-phase probe +
monument read-out + formations scatter); `tools/build_findings.py` then
aggregates it (as `FINDINGS_DATA.archaeo`) alongside the other outputs.
`findings_gallery.html` reads `window.FINDINGS_DATA` from
`findings_data.embed.js`; the page is fully data-driven, so a fresh build
auto-updates every panel (the archaeo section guards for absent data). If the
embed is missing, the page shows a graceful banner with the regenerate command.

## Regenerate
```
python tools/astro/archaeo_probe.py \
  && python tools/mission_status.py \
  && python tools/build_findings.py
```
Then reload the page.

## Honesty stance
Structure ≠ meaning. Every panel carries its control. Ulfberht sharp; foil hat =
nightcap.
