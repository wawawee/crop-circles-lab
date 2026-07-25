# Betty Hill Star Map — Data Sources

## Background

In September 1961, Barney and Betty Hill reported an alien abduction near
Groveton, New Hampshire. During later hypnotic regression, Betty Hill produced
a sketch of a "star map" she claimed to have been shown aboard the craft.

The sketch shows ~15 dots connected by solid and dashed lines. The map was
brought to wider attention by Marjorie Fish, a schoolteacher and amateur
astronomer, who built a 3D bead-and-string model of nearby stars and proposed
identifications for each dot. Her results were published in:

- **Dickinson, T. (1974).** "The Zeta Reticuli Incident." *Astronomy*,
  2(6): 4–17.

Fish identified the "home base" of the sketched map as the Zeta Reticuli
binary system (~39 ly, visual separation ~310 AU) and matched the remaining
dots to specific Sun-like stars within ~60 light-years.

Later challenges include:
- **Soter, S. (1978).** "Betty Hill's Star Map." *Astronomy*, 6(11): 6.
  Argued that with enough stars in the local solar neighbourhood (~330 within
  65 ly), the observed matches are consistent with chance.
- **Sturrock, P. (1987).** *An Analysis of the Betty Hill Star Map*.
  SUIPR Report No. 1021. Used statistical cluster analysis; concluded the
  map could match the Fish identification but with low statistical
  significance.

## File inventory

| File       | Contents |
|------------|----------|
| `map.json` | Encoded graph: nodes (stars with Hipparcos IDs / common names) + graph edges (Fish–Hill connectivity). JSON schema includes `metadata` (citable version) + `nodes` + `edges`. |

## Star identification (Fish interpretation)

Nodes are keyed by short IDs. Where available, Hipparcos number (HIP) is
given for J2000 position lookup. All stars are within ~65 ly of the Sun.

| Node  | Common name        | HIP       | HD / other | V mag | Distance (ly) |
|-------|--------------------|-----------|------------|-------|---------------|
| zet1  | Zeta^1 Reticuli    | 15330     | HD 20766   | 5.52  | 39.3          |
| zet2  | Zeta^2 Reticuli    | 15371     | HD 20807   | 5.24  | 39.3          |
| sun   | Sun                | --        | Sol        | -26.7 | --            |
| tau   | Tau Ceti           | 8102      | HD 10700   | 3.50  | 11.9          |
| 82er  | 82 Eridani         | 15510     | HD 20794   | 4.27  | 19.7          |
| delp  | Delta Pavonis      | 99240     | HD 190248  | 3.55  | 19.9          |
| eps   | Epsilon Eridani    | 16537     | HD 22049   | 3.73  | 10.5          |
| hr8832| HR 8832            | 114622    | HD 219134  | 5.57  | 21.3          |
| luy   | Luyten's Star      | 36208     | Gl 273     | 9.87  | 12.4          |
| gl1   | Gliese 1           | 439       | HD 225213  | 8.56  | 14.2          |
| gl86  | Gliese 86          | 10138     | HD 13445   | 6.17  | 35.2          |
| gl832 | Gliese 832         | 106440    | HD 204961  | 8.67  | 16.2          |
| gl754 | Gliese 754         | 93873     | --         | 12.23 | 19.3          |
| gl205 | Gliese 205         | 25878     | HD 36395   | 7.97  | 18.6          |
| gl229 | Gliese 229         | 29295     | HD 42581   | 8.14  | 19.0          |

## Graph connectivity (edges)

Edges represent connections drawn on Betty Hill's original sketch, as
interpreted by Marjorie Fish. The connectivity follows the 1974 *Astronomy*
article diagram (as reproduced in Dickinson 1974 and later references).

The map forms a roughly planar graph with the Zeta Reticuli binary at the
center. The Sun is shown as a small dot at one periphery.

Connected pairs (undirected):
- zet1--zet2 (the Zeta binary pair)
- zet1--gl86, zet2--gl86
- zet1--82er, zet2--82er
- gl86--82er
- gl86--delp, 82er--delp
- gl86--eps
- eps--gl1
- eps--luy
- gl1--gl205, luy--gl205
- gl205--gl229
- gl229--gl832, gl1--gl832
- gl832--gl754
- delp--gl754
- sun--tau
- tau--hr8832
- hr8832--gl754

**Warning:** Different secondary reproductions of the map show minor
variations in edge placement. This encoding represents the best-effort
reconstruction from the primary cited source. The analysis code supports
alternative edge sets via `--edges-version`.

## Caveat emptor

- The 15-star set is one of several proposed identifications. Fish's was the
  most influential but not the only one.
- The Sun is included as a map node but in the original sketch the Sun dot
  may be distinguished (smaller / dashed-line connection). We treat it as a
  full node for graph analysis.
- Statistical results are reported in `outputs/betty_hill/`. As per the
  negative-control rule, the prior expectation is **NO_SIGNAL**.
- The word "Zeta Reticuli" is used only in citations and the data file,
  nowhere in the verdict output.
