# G8 — Betty Hill × Gaia star-map null — Landing notes

## Verdict

**🟢 UNDERDETERMINED** — landed with honest caveats.

The Betty Hill map (Fish interpretation) graph shows **weak structure** against
random-star-field nulls (z ≈ −2.0, 97th percentile for MST edge length), but
does **not** reach the 3-sigma separation that planted asterisms achieve
(Big Dipper z ≈ −3.2; Orion's Belt z ≈ −2.8).

## What was done

1. **Encoded map** — 15 stars (Fish interpretation) + 21 graph edges from
   published map (Dickinson 1974) → `data/astro/betty_hill/map.json` + README.
   J2000 coordinates embedded from Hipparcos. Sun excluded from geometry
   (no sky position).

2. **Star resolution** — Skyfield + DE441 ephemeris with embedded J2000
   Hipparcos coordinates.

3. **Metrics** — MST edge-length mean (primary), MST total, pairwise mean,
   graph energy. Compared vs:
   - Random-star-field in same bounding-box sky patch (N=500 trials)
   - Degree-preserving edge shuffle (preserves node degrees)

4. **Known-answer controls** — Big Dipper core (7 stars) and Orion's Belt
   (3 stars) both separate cleanly from null at >3σ / ~3σ.

## Caveats

- **Selection bias** (critical): Fish selected ~15 stars from ~330 within 65 ly
  that **best** matched the sketch. Our null generates random positions in the
  same sky patch but does **not** model the selection of "best-fitting" subset
  from a large candidate pool. Soter (1978) argued this selection alone explains
  the apparent match. The graph-structure analysis here is a partial correction
  but not a full selection-bias model.

- **Graph connectivity uncertainty**: Different reproductions of the Hill sketch
  show minor variations in which stars are connected by dashed vs solid lines.
  Edge set v1.0 is based on Dickinson (1974). Alternative edge sets can be
  analyzed by editing `data/astro/betty_hill/map.json`.

- **Sun treatment**: The Sun is shown on the original map but excluded from
  angular-distance computations (no sky position — it's the observer, not a
  point on the celestial sphere). Its inclusion as a graph node with edges
  to Tau Ceti and HR 8832 is purely topological.

- **No proper-motion correction**: J2000 coordinates used directly.
  Proper motion over 50-year timescale is <0.1" for all stars listed;
  pairwise separations unaffected at 1° scale.

## Outputs

| File | Contents |
|------|----------|
| `outputs/betty_hill/run.json` | Full analysis results (all statistics, null ensembles, known-answer tests) |
| `outputs/betty_hill/NOTES.md` | This file |
| `data/astro/betty_hill/map.json` | Encoded Hill–Fish star map graph (v1.1) |
| `data/astro/betty_hill/README.md` | Sources, star catalog, edge attribution |

## Re-run

```bash
python tools/astro/betty_hill_probe.py --n-null 500 --seed 42
```

## Forbidden content check

- ✅ No "Zeta Reticuli confirmed" claim
- ✅ No alien navigation claims
- ✅ No cherry-picked star IDs without citing the map edition
- ✅ No radio, BLC1, Amazon, G2++, or bio references

## Board

| ID | Status |
|----|--------|
| G8 | 🟢 UNDERDETERMINED — landed on `feat/g8-betty-hill-gaia` |
