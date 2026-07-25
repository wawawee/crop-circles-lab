"""ela_screen — light Error Level Analysis for photo TAMPER screening (B10).

HOAX / splice detector only. Never treat high ELA as a "hidden message".

Method (classic JPEG ELA):
  1. Load image → RGB
  2. Re-encode as JPEG at quality Q
  3. Absolute difference |orig − resaved|, optionally amplify
  4. Report residual stats + write heatmap PNG

Known-answer: a synthetic image with a high-quality patch pasted into a
low-quality JPEG background should show elevated residual in the patch.

Negative control: a clean single-pass camera-style JPEG should be relatively
uniform (low spatial contrast in the residual).

CLI:
  python tools/ccat/ela_screen.py IMG.jpg --out-dir outputs/forensics/ela/<id>
  python tools/ccat/ela_screen.py --batch data/images --ids chualar,julia,crabwood
"""

from __future__ import annotations

import argparse
import json
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageChops, ImageEnhance, ImageDraw
import numpy as np


def _to_rgb(img: Image.Image) -> Image.Image:
    if img.mode == "RGB":
        return img
    if img.mode in ("RGBA", "LA"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        return bg
    return img.convert("RGB")


def jpeg_resave(img: Image.Image, quality: int = 90) -> Image.Image:
    buf = BytesIO()
    _to_rgb(img).save(buf, format="JPEG", quality=quality, optimize=False)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def ela_residual(img: Image.Image, quality: int = 90) -> tuple[Image.Image, np.ndarray]:
    """Return amplified ELA preview (RGB) and raw mean-abs residual array [0..255]."""
    rgb = _to_rgb(img)
    resaved = jpeg_resave(rgb, quality=quality)
    diff = ImageChops.difference(rgb, resaved)
    arr = np.asarray(diff, dtype=np.float32).mean(axis=2)  # luma-ish residual
    # Amplify for viewing (classic ELA look)
    amp = ImageEnhance.Brightness(diff).enhance(12.0)
    return amp.convert("RGB"), arr


def residual_stats(arr: np.ndarray) -> dict:
    flat = arr.ravel()
    p95 = float(np.percentile(flat, 95))
    p99 = float(np.percentile(flat, 99))
    # Spatial contrast: std of block means (8×8) — splices often raise this
    h, w = arr.shape
    bh, bw = max(1, h // 8), max(1, w // 8)
    blocks = []
    for i in range(0, h - bh + 1, bh):
        for j in range(0, w - bw + 1, bw):
            blocks.append(float(arr[i : i + bh, j : j + bw].mean()))
    block_std = float(np.std(blocks)) if blocks else 0.0
    return {
        "mean": round(float(flat.mean()), 4),
        "std": round(float(flat.std()), 4),
        "max": round(float(flat.max()), 4),
        "p95": round(p95, 4),
        "p99": round(p99, 4),
        "block_mean_std": round(block_std, 4),
        "n_pixels": int(flat.size),
    }


def verdict_from_stats(stats: dict, *, control_block_std: float | None = None) -> str:
    """Heuristic only — calibrate against Chualar vs field corpus, not gospel."""
    bstd = stats["block_mean_std"]
    if control_block_std is not None and control_block_std > 0:
        ratio = bstd / control_block_std
        if ratio >= 2.0 and stats["p99"] > 25:
            return "ELEVATED vs control — possible heavy edit / multi-generation JPEG (tamper screen only)"
        if ratio >= 1.4:
            return "MILDLY ELEVATED vs control — inspect heatmap; may be compression/scale"
        return "SIMILAR to control — no strong ELA splice flag"
    # Absolute fallback (weak without calibration)
    if bstd >= 8.0 and stats["p99"] >= 40:
        return "HIGH residual contrast — inspect heatmap (could be edit OR aggressive prior JPEG)"
    if bstd >= 4.0:
        return "MODERATE residual contrast — inconclusive alone"
    return "LOW/UNIFORM residual — consistent with single-pass compress (weak negative for splice)"


def screen_one(
    path: Path,
    out_dir: Path,
    quality: int = 90,
    control_block_std: float | None = None,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    img = Image.open(path)
    ela_img, arr = ela_residual(img, quality=quality)
    stats = residual_stats(arr)
    verdict = verdict_from_stats(stats, control_block_std=control_block_std)

    stem = path.stem
    ela_path = out_dir / f"{stem}_ela_q{quality}.png"
    ela_img.save(ela_path)

    # Tiny side-by-side strip for quick glance
    rgb = _to_rgb(img)
    thumb_w = 360
    scale = thumb_w / rgb.width
    th = max(1, int(rgb.height * scale))
    left = rgb.resize((thumb_w, th), Image.Resampling.LANCZOS)
    right = ela_img.resize((thumb_w, th), Image.Resampling.LANCZOS)
    pair = Image.new("RGB", (thumb_w * 2 + 8, th + 28), (30, 30, 28))
    pair.paste(left, (0, 24))
    pair.paste(right, (thumb_w + 8, 24))
    draw = ImageDraw.Draw(pair)
    draw.text((4, 4), f"{stem[:40]}  |  ELA q={quality}", fill=(220, 220, 210))
    pair_path = out_dir / f"{stem}_pair_q{quality}.png"
    pair.save(pair_path)

    report = {
        "source": str(path).replace("\\", "/"),
        "quality": quality,
        "stats": stats,
        "verdict": verdict,
        "ela_png": str(ela_path),
        "pair_png": str(pair_path),
        "caveat": (
            "ELA flags compression inconsistency / possible splice — NOT a message decoder. "
            "Web-resaved Temporary Temples JPEGs often look 'edited' because they are multi-generation."
        ),
    }
    (out_dir / f"{stem}_ela.json").write_text(json.dumps(report, indent=2))
    return report


def make_known_answer_pair(tmp: Path) -> tuple[Path, Path]:
    """Clean uniform JPEG vs spliced (HQ patch into LQ background)."""
    tmp.mkdir(parents=True, exist_ok=True)
    # Background: noisy, saved low quality
    rng = np.random.default_rng(0)
    bg = (rng.random((256, 256, 3)) * 80 + 40).astype(np.uint8)
    bg_img = Image.fromarray(bg, "RGB")
    clean = tmp / "clean_single_pass.jpg"
    bg_img.save(clean, quality=85)

    # Splice: high-detail patch saved once at q=98, pasted into q=40 background
    detail = (rng.random((80, 80, 3)) * 200 + 30).astype(np.uint8)
    # Add sharp edges
    detail[20:60, 20:60] = [240, 40, 40]
    patch = Image.fromarray(detail, "RGB")
    buf = BytesIO()
    patch.save(buf, format="JPEG", quality=98)
    buf.seek(0)
    patch_hq = Image.open(buf).convert("RGB")

    lq_buf = BytesIO()
    bg_img.save(lq_buf, format="JPEG", quality=40)
    lq_buf.seek(0)
    canvas = Image.open(lq_buf).convert("RGB")
    canvas.paste(patch_hq, (88, 88))
    spliced = tmp / "spliced_hq_into_lq.jpg"
    canvas.save(spliced, quality=90)
    return clean, spliced


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("images", nargs="*", type=Path, help="Image paths")
    ap.add_argument("--out-dir", type=Path, default=Path("outputs/forensics/ela"))
    ap.add_argument("--quality", type=int, default=90)
    ap.add_argument(
        "--batch-lab",
        action="store_true",
        help="Screen Chualar (hoax control) + Julia + Crabwood + Chilbolton from data/images/",
    )
    ap.add_argument("--self-test", action="store_true", help="Known-answer synthetic splice test")
    args = ap.parse_args(argv)

    root = Path(__file__).resolve().parents[2]
    if args.self_test:
        tmp = root / "outputs" / "forensics" / "ela" / "_selftest"
        clean, spliced = make_known_answer_pair(tmp)
        r_clean = screen_one(clean, tmp / "clean", args.quality)
        r_spl = screen_one(
            spliced, tmp / "spliced", args.quality,
            control_block_std=r_clean["stats"]["block_mean_std"],
        )
        ok = r_spl["stats"]["block_mean_std"] > r_clean["stats"]["block_mean_std"] * 1.2
        summary = {
            "clean": r_clean["stats"],
            "spliced": r_spl["stats"],
            "spliced_higher_block_std": ok,
            "pass": ok,
        }
        (tmp / "selftest_summary.json").write_text(json.dumps(summary, indent=2))
        print(json.dumps(summary, indent=2))
        return 0 if ok else 1

    paths: list[Path] = list(args.images)
    if args.batch_lab:
        img_dir = root / "data" / "images"
        for name in [
            "chualar_2013_nvidia_hoax.png",
            "julia_set_1996_tt_oh.jpg",
            "crabwood_2002_tt_oh2.jpg",
            "chilbolton_message_2001_tt.jpg",
            "crabwood_2002_disc_crop.png",
        ]:
            p = img_dir / name
            if p.exists():
                paths.append(p)

    if not paths:
        ap.error("pass image paths or --batch-lab / --self-test")

    # First pass: use Chualar as calibration control if present
    control_std = None
    reports = []
    chualar = next((p for p in paths if "chualar" in p.name.lower()), None)
    ordered = ([chualar] if chualar else []) + [p for p in paths if p != chualar]

    for p in ordered:
        sub = args.out_dir / p.stem
        # After Chualar screened, use its block_std as control for field photos
        rep = screen_one(p, sub, args.quality, control_block_std=control_std)
        if "chualar" in p.name.lower():
            control_std = rep["stats"]["block_mean_std"]
            rep["role"] = "known_hoax_digital_control"
        else:
            rep["role"] = "field_or_candidate"
            rep["calibrated_against"] = "chualar" if control_std is not None else None
        # rewrite json with role
        (sub / f"{p.stem}_ela.json").write_text(json.dumps(rep, indent=2))
        reports.append(rep)
        print(f"{p.name}: block_std={rep['stats']['block_mean_std']}  {rep['verdict'][:70]}")

    summary = {
        "n": len(reports),
        "quality": args.quality,
        "control_block_std": control_std,
        "rows": [
            {
                "file": Path(r["source"]).name,
                "role": r.get("role"),
                "block_mean_std": r["stats"]["block_mean_std"],
                "p99": r["stats"]["p99"],
                "verdict": r["verdict"],
            }
            for r in reports
        ],
        "reading": (
            "Chualar is born-digital marketing art — ELA may look 'busy' for different "
            "reasons than a camera JPEG. Field TT web JPEGs are multi-generation; elevated "
            "ELA vs a clean camera original is expected and NOT proof of formation fakery. "
            "Use ELA to catch crude Photoshop splices in stills, not to authenticate circles."
        ),
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "SUMMARY.json").write_text(json.dumps(summary, indent=2))
    (args.out_dir / "NOTES.md").write_text(
        "# B10 ELA screen (Pillow)\n\n"
        + summary["reading"]
        + "\n\n## Results\n\n"
        + "\n".join(
            f"- `{row['file']}` ({row['role']}): block_std={row['block_mean_std']}, "
            f"p99={row['p99']} — {row['verdict']}"
            for row in summary["rows"]
        )
        + "\n"
    )
    print(f"wrote {args.out_dir / 'SUMMARY.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
