"""Dashboard visualization (ported/upgraded from Kimi CCAT demo)."""

from __future__ import annotations

from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np

try:
    from .ccat import detect_circles, edge_ratio, load_bgr
except ImportError:
    from ccat import detect_circles, edge_ratio, load_bgr


def render_dashboard(path: Path, out: Path | None = None, show: bool = False) -> Path:
    """6-panel dashboard matching the classic Kimi demo layout."""
    bgr = load_bgr(path)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    ratio, edges = edge_ratio(gray)
    circs, n_circ = detect_circles(gray, return_array=True)

    circ_img = rgb.copy()
    if circs is not None:
        for x, y, r in np.round(circs[0]).astype(int)[:200]:
            cv2.circle(circ_img, (x, y), r, (0, 255, 0), 1)
            cv2.circle(circ_img, (x, y), 2, (255, 0, 0), 2)

    line_img = rgb.copy()
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=60,
        minLineLength=max(20, edges.shape[1] // 40),
        maxLineGap=8,
    )
    if lines is not None:
        segs = lines.reshape(-1, 4)
        for x1, y1, x2, y2 in segs[:300]:
            cv2.line(line_img, (int(x1), int(y1)), (int(x2), int(y2)), (255, 40, 40), 1)
        n_lines = int(len(segs))
    else:
        n_lines = 0

    fig, axes = plt.subplots(2, 3, figsize=(15, 9))
    fig.suptitle(f"CCAT Demo: {path.name}", fontsize=14)

    axes[0, 0].imshow(rgb)
    axes[0, 0].set_title("Original")
    axes[0, 0].axis("off")

    axes[0, 1].imshow(gray, cmap="gray")
    axes[0, 1].set_title("Grayscale")
    axes[0, 1].axis("off")

    axes[0, 2].imshow(edges, cmap="gray")
    axes[0, 2].set_title(f"Edges (Canny) — {int(ratio * edges.size)} edge pixels")
    axes[0, 2].axis("off")

    axes[1, 0].imshow(circ_img)
    axes[1, 0].set_title(f"Circle Detection — {n_circ} circles found")
    axes[1, 0].axis("off")

    axes[1, 1].imshow(line_img)
    axes[1, 1].set_title(f"Line Detection — {n_lines} lines found")
    axes[1, 1].axis("off")

    axes[1, 2].hist(gray.ravel(), bins=256, range=(0, 256), color="#4a6fa5")
    mean_i = float(np.mean(gray))
    med_i = float(np.median(gray))
    axes[1, 2].axvline(mean_i, color="red", ls="--", label=f"Mean: {mean_i:.1f}")
    axes[1, 2].axvline(med_i, color="green", ls="--", label=f"Median: {med_i:.1f}")
    axes[1, 2].set_title("Intensity Distribution")
    axes[1, 2].set_xlabel("Pixel Value")
    axes[1, 2].set_ylabel("Frequency")
    axes[1, 2].legend(fontsize=8)

    plt.tight_layout()
    if out is None:
        out = Path("outputs") / f"{path.stem}_dashboard.png"
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    if show:
        plt.show()
    plt.close(fig)
    return out


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    path = render_dashboard(Path(args.image), out=args.out)
    print(f"Wrote {path}")
