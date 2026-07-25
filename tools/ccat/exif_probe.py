"""ExifTool wrapper — deeper metadata than Pillow EXIF."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


def exiftool_available() -> bool:
    return shutil.which("exiftool") is not None


def extract_exiftool(path: Path) -> dict:
    if not exiftool_available():
        return {"error": "exiftool not found — brew install exiftool"}
    proc = subprocess.run(
        ["exiftool", "-json", "-n", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return {"error": proc.stderr.strip() or "exiftool failed"}
    data = json.loads(proc.stdout)
    return data[0] if data else {}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    result = extract_exiftool(Path(args.image))
    text = json.dumps(result, indent=2, default=str)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)


if __name__ == "__main__":
    main()
