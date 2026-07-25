#!/usr/bin/env bash
# Helper: open priority archive pages so you can save high-res aerials into data/images/
# Usage: ./tools/open_archives.sh

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMG="$ROOT/data/images"

echo "Drop downloaded aerials into: $IMG"
echo "Expected filenames (from catalog):"
echo "  julia_set_1996.jpg"
echo "  cherhill_1993.jpg"
echo "  logan_utah_1996.jpg"
echo "  edmonton_1999.jpg"
echo "  eltopia_1998.jpg"
echo "  dna_alton_barnes_1996.jpg"
echo "  chilbolton_arecibo_2001.jpg"
echo "  milk_hill_galaxy_2001.jpg"
echo "  allington_cube_1999.jpg"
echo "  triple_julia_1996.jpg"
echo

URLS=(
  "https://temporarytemples.co.uk/crop-circles/1996-crop-circles"
  "https://lucypringle.co.uk/photos/1996/uk1996ay.shtml"
  "https://lucypringle.co.uk/photos/2001/uk2001df.shtml"
  "https://www.cropcircleconnector.com/Sorensen/classics/classics.html"
  "http://bltresearch.com/labreports.php"
  "https://skepticalinquirer.org/2022/05/revisiting-the-stonehenge-surprise-the-best-case-for-crop-circles/"
  "https://commons.wikimedia.org/wiki/File:Lucy_Pringle_Aerial_Shot_of_Pi_Crop_Circle_-_panoramio.jpg"
)

if command -v open >/dev/null 2>&1; then
  for u in "${URLS[@]}"; do
    open "$u"
    sleep 0.3
  done
else
  printf '%s\n' "${URLS[@]}"
fi
