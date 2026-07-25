"""Batch analysis → pandas DataFrame / CSV (merge of our metrics + Kimi-style table)."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

try:
    from .ccat import analyze_image
    from .circle_cluster import cluster_circles
    from .exif_probe import extract_exiftool, exiftool_available
except ImportError:
    from ccat import analyze_image
    from circle_cluster import cluster_circles
    from exif_probe import extract_exiftool, exiftool_available


def batch_table(image_dir: Path, pattern: str = "*") -> pd.DataFrame:
    exts = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"}
    rows = []
    for path in sorted(image_dir.glob(pattern)):
        if path.suffix.lower() not in exts:
            continue
        try:
            res = analyze_image(path)
            cl = cluster_circles(path)
            row = {
                "file": path.name,
                "width": res.width,
                "height": res.height,
                "mean_intensity": res.mean_intensity,
                "edge_ratio": res.edge_pixel_ratio,
                "circles_raw": res.circles_detected,
                "circles_clustered": cl["clustered_circles"],
                "lines": res.lines_detected,
                "fractal_dim": res.fractal_dimension,
                "rot_best": max(v for k, v in res.symmetry.items() if k.startswith("rot_")),
                "mirror": res.symmetry.get("mirror"),
                "notes": "|".join(res.notes),
            }
            if exiftool_available():
                meta = extract_exiftool(path)
                row["camera"] = meta.get("Model") or meta.get("Make")
                row["create_date"] = meta.get("CreateDate") or meta.get("DateTimeOriginal")
            rows.append(row)
            print(f"✓ {path.name}")
        except Exception as exc:  # noqa: BLE001
            print(f"✗ {path.name}: {exc}")
            rows.append({"file": path.name, "error": str(exc)})
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("outputs/batch_table.csv"))
    args = ap.parse_args()
    df = batch_table(args.batch)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)
    json_out = args.out.with_suffix(".json")
    df.to_json(json_out, orient="records", indent=2)
    print(df.to_string(index=False))
    print(f"\nWrote {args.out} and {json_out}")


if __name__ == "__main__":
    main()
