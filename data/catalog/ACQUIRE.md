# Priority image wishlist (manual download)

Many of the strongest BLT / complex cases are **copyrighted aerials**.
Wikimedia only covers a few. Drop files into `data/images/` using these names.

## Priority 1 — BLT / microwave fingerprint

| Target file | Formation | Where to grab |
|-------------|-----------|---------------|
| `julia_set_1996.jpg` | Stonehenge Julia Set | Temporary Temples 1996 gallery, Lucy Pringle 1996, CropCircleConnector classics |
| `cherhill_1993.jpg` | Cherhill iron glaze | Lucy Pringle 1993, BLT lab #104 context |
| `logan_utah_1996.jpg` | Logan UT | BLT / local news archives |
| `edmonton_1999.jpg` | Edmonton AB | Unsolved Mysteries wiki (low-res) — seek better aerial |
| `eltopia_1998.jpg` | Eltopia WA | BLT fieldwork pages |

## Priority 2 — Complex geometry

| Target file | Formation | Where to grab |
|-------------|-----------|---------------|
| `milk_hill_galaxy_2001.jpg` | Milk Hill | Lucy Pringle 2001, Temporary Temples |
| `barbury_pi_2008.jpg` | Barbury Pi | ✅ already local (Wikimedia CC BY 3.0) |
| `chilbolton_arecibo_2001.jpg` | Chilbolton reply | CropCircleConnector / Temporary Temples |
| `dna_alton_barnes_1996.jpg` | DNA helix | Temporary Temples 1996 |
| `allington_cube_1999.jpg` | The Cube | Lucy Pringle |
| `triple_julia_1996.jpg` | Windmill Hill | Temporary Temples 1996 |

## Already local (starter set)

- `barbury_pi_2008.jpg` — Pi formation aerial
- `swirl_reference.jpg` — swirl texture reference
- `vacaville_ca.jpg` — modern CA formation (high-res)
- `berbah_indonesia.jpg` — Indonesia formation
- `lay_wood_diagram.png` — geometric reconstruction diagram
- `arecibo_message_original.svg` — original Arecibo message (compare to Chilbolton)
- `synthetic_julia_*.png` — generated Julia sets for matching

After dropping files, run:

```bash
source .venv/bin/activate
python tools/ccat/ccat.py --batch data/images --debug outputs/debug --out outputs/batch.json
```
