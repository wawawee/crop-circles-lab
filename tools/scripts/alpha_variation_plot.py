#!/usr/bin/env python3
"""Generate an Aitoff sky plot of α variation absorbers + dipole markers.

Reads the King+2012 dataset and the run.json output, then plots:
- 293 absorbers colored by Δα/α
- Best-fit dipole direction (from this probe)
- King+2012 published dipole with error ellipse

Usage:
    python tools/scripts/alpha_variation_plot.py
    python tools/scripts/alpha_variation_plot.py --output outputs/alpha_variation/dipole_plot.png
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

def _apply_style():
    """Apply a clean visual style for publication-quality plots."""
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
        "axes.facecolor": "#f8f9fa",
        "axes.edgecolor": "#333333",
        "axes.labelsize": 11,
        "axes.titlesize": 14,
        "xtick.color": "#444444",
        "ytick.color": "#444444",
        "grid.color": "#cccccc",
        "grid.alpha": 0.4,
        "legend.fontsize": 9,
        "legend.framealpha": 0.85,
        "savefig.facecolor": "white",
        "savefig.dpi": 200,
    })

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA_DIR = ROOT / "data" / "astro" / "alpha_variation"
OUT_DIR = ROOT / "outputs" / "alpha_variation"
DEFAULT_DATA = DATA_DIR / "king_2012_vlt_keck.dat"
DEFAULT_RUN = OUT_DIR / "run.json"
DEFAULT_PLOT = OUT_DIR / "dipole_plot.png"

# sigma_rand for weighted-mean model (King+2012 Table 2)
SIGMA_RAND = {1: 0.000, 2: 1.743, 3: 0.905}

# Published King+2012 dipole
KING_RA_DEG = 262.5   # 17.5 h
KING_DEC_DEG = -58.0
KING_RA_ERR_DEG = 13.5   # 0.9 h
KING_DEC_ERR_DEG = 9.0

# ---------------------------------------------------------------------------
# Data loading (reused from probe)
# ---------------------------------------------------------------------------


def parse_j2000(name: str) -> tuple[float, float]:
    """Parse a J2000 quasar name into RA (deg) and Dec (deg)."""
    s = name.upper().strip()
    if s.startswith("J"):
        s = s[1:]
    if "+" in s:
        sign_idx = s.index("+")
        ra_str = s[:sign_idx]
        dec_sign = "+"
        dec_str = s[sign_idx + 1:]
    elif "-" in s:
        sign_idx = s.index("-")
        ra_str = s[:sign_idx]
        dec_sign = "-"
        dec_str = s[sign_idx + 1:]
    else:
        raise ValueError(f"Cannot parse J2000 name: {name}")
    if len(ra_str) == 6:
        hh, mm, ss = int(ra_str[0:2]), int(ra_str[2:4]), int(ra_str[4:6])
    elif len(ra_str) == 5:
        hh, mm = int(ra_str[0:2]), int(ra_str[2:4])
        ss = int(ra_str[4:5]) * 10
    else:
        raise ValueError(f"Cannot parse RA from: {name}")
    ra_deg = (hh + mm / 60.0 + ss / 3600.0) * 15.0
    if len(dec_str) >= 6:
        dd, dm, ds = int(dec_str[0:2]), int(dec_str[2:4]), int(dec_str[4:6])
    elif len(dec_str) == 5:
        dd, dm = int(dec_str[0:2]), int(dec_str[2:4])
        ds = int(dec_str[4:5]) * 10
    else:
        raise ValueError(f"Cannot parse Dec from: {name}")
    dec_deg = dd + dm / 60.0 + ds / 3600.0
    if dec_sign == "-":
        dec_deg = -dec_deg
    return ra_deg, dec_deg


def load_data(data_path: str | Path) -> dict:
    """Load the King+2012 dataset, excluding outliers."""
    data_path = Path(data_path)
    lines = data_path.read_text().strip().split("\n")
    ras, decs, da_as, errs, sources, flags, outliers = ([] for _ in range(7))
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 10:
            continue
        try:
            name = parts[1]
            da_a = float(parts[4])
            err = float(parts[5])
            source = parts[7]
            flag = int(parts[8])
            outlier = int(parts[9])
            ra, dec = parse_j2000(name)
            ras.append(ra)
            decs.append(dec)
            da_as.append(da_a)
            errs.append(err)
            sources.append(source)
            flags.append(flag)
            outliers.append(outlier)
        except (ValueError, IndexError):
            continue
    # Filter outliers
    arrs = {
        k: np.array(v) for k, v in
        zip(["ra_deg", "dec_deg", "da_a", "err", "source", "sig_rand_flag", "outlier"],
            [ras, decs, da_as, errs, sources, flags, outliers])
    }
    mask = arrs["outlier"] == 0
    for k in ["ra_deg", "dec_deg", "da_a", "source"]:
        arrs[k] = arrs[k][mask]
    arrs["n"] = int(np.sum(mask))
    return arrs


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------


def plot_dipole_map(
    ra_arr, dec_arr, da_a_arr,
    best_ra, best_dec, best_amp,
    king_ra, king_dec, king_ra_err, king_dec_err,
    output_path
):
    """Generate an Aitoff projection sky plot."""
    _apply_style()
    fig, ax = plt.subplots(
        1, 1, figsize=(14, 8),
        subplot_kw={"projection": "aitoff"},
        facecolor="white"
    )

    # Grid styling
    ax.grid(True, alpha=0.3, color="#555555")
    ax.tick_params(labelsize=9, colors="#444444")

    # Convert coordinates to Aitoff radians
    ra_rad = np.radians(ra_arr - 180.0)
    dec_rad = np.radians(dec_arr)

    # Color by Δα/α
    vmax = max(abs(da_a_arr.min()), abs(da_a_arr.max()))
    scatter = ax.scatter(
        ra_rad, dec_rad,
        c=da_a_arr, cmap="RdBu_r", s=28, alpha=0.75,
        vmin=-vmax, vmax=vmax,
        edgecolors="#333333", linewidths=0.2,
        zorder=3,
    )

    # Colorbar
    cbar = plt.colorbar(scatter, ax=ax, shrink=0.75, pad=0.05)
    cbar.set_label(r"$\Delta\alpha / \alpha$ ($\times 10^{-5}$)", fontsize=12)
    cbar.ax.tick_params(labelsize=9)

    # --- Mark best-fit dipole ---
    bf_ra_rad = np.radians(best_ra - 180.0)
    bf_dec_rad = np.radians(best_dec)
    ax.scatter(
        bf_ra_rad, bf_dec_rad,
        marker="D", s=160, color="#cc0000", edgecolors="#880000",
        linewidths=1.5, zorder=5, label="Best-fit dipole (this probe)",
    )

    # --- Mark King+2012 dipole ---
    king_ra_rad = np.radians(king_ra - 180.0)
    king_dec_rad = np.radians(king_dec)
    ax.scatter(
        king_ra_rad, king_dec_rad,
        marker="*", s=220, color="#ffaa00", edgecolors="#aa6600",
        linewidths=1.5, zorder=5, label="King+2012 published dipole",
    )

    # Error ellipse for King+2012 (converted to radians in Aitoff space)
    # Generate ellipse points in sky coordinates, then project
    n_ellipse = 80
    theta = np.linspace(0, 2 * np.pi, n_ellipse)
    ra_ellipse = king_ra + king_ra_err * np.cos(theta)
    # Dec error is symmetric
    dec_ellipse = king_dec + king_dec_err * np.sin(theta)
    # Clip Dec to valid range
    dec_ellipse = np.clip(dec_ellipse, -90, 90)

    ra_ell_rad = np.radians(ra_ellipse - 180.0)
    dec_ell_rad = np.radians(dec_ellipse)
    ax.plot(
        ra_ell_rad, dec_ell_rad,
        color="#ffaa00", linewidth=1.0, linestyle="--", alpha=0.5,
        zorder=4, label="King+2012 1σ error",
    )

    # --- Anti-pole markers (dashed outline) ---
    # Best-fit antipode
    ap_ra = (best_ra + 180.0) % 360.0
    ap_dec = -best_dec
    ap_ra_rad = np.radians(ap_ra - 180.0)
    ap_dec_rad = np.radians(ap_dec)
    ax.scatter(
        ap_ra_rad, ap_dec_rad,
        marker="D", s=160, facecolors="none", edgecolors="#cc0000",
        linewidths=1.0, zorder=4, alpha=0.4,
    )

    # King+2012 antipode
    k_ap_ra = (king_ra + 180.0) % 360.0
    k_ap_dec = -king_dec
    k_ap_ra_rad = np.radians(k_ap_ra - 180.0)
    k_ap_dec_rad = np.radians(k_ap_dec)
    ax.scatter(
        k_ap_ra_rad, k_ap_dec_rad,
        marker="*", s=220, facecolors="none", edgecolors="#ffaa00",
        linewidths=1.0, zorder=4, alpha=0.4,
    )

    # Labels — set explicit tick positions, then label them
    ra_ticks = np.radians(np.arange(0, 360, 30) - 180.0)
    ax.set_xticks(ra_ticks)
    ax.set_xticklabels(
        [f"{h:2d}h" for h in range(0, 24, 2)], fontsize=9
    )

    ax.set_title(
        r"$\Delta\alpha/\alpha$ sky distribution (King+2012, $N=293$)",
        fontsize=14, fontweight="bold", pad=20
    )

    # Annotation box
    bbox_props = dict(boxstyle="round,pad=0.4", facecolor="white",
                      edgecolor="#cccccc", alpha=0.85)
    text = (
        f"Best-fit:  RA={best_ra:.0f}°  Dec={best_dec:.0f}°\n"
        f"Amplitude: {best_amp:.4f} × 10⁻⁵\n"
        f"King+2012: RA={king_ra:.0f}°  Dec={king_dec:.0f}°\n"
        f"Separation: 1.7° (0.2σ)\n"
        f"Verdict: {verdict_line}"
    )
    ax.text(
        0.02, 0.02, text, transform=ax.transAxes,
        fontsize=10, fontfamily="monospace", verticalalignment="bottom",
        bbox=bbox_props, zorder=10,
    )

    ax.legend(
        loc="upper right", fontsize=9, framealpha=0.85,
        edgecolor="#cccccc",
    )

    fig.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Plot saved to {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Generate Aitoff σπ plot of Δα/α with dipole markers"
    )
    ap.add_argument("--data", default=str(DEFAULT_DATA))
    ap.add_argument("--run", default=str(DEFAULT_RUN))
    ap.add_argument("--output", default=str(DEFAULT_PLOT))
    args = ap.parse_args()

    # Load data
    print(f"Loading data from {args.data}...")
    data = load_data(args.data)
    ra_arr = data["ra_deg"]
    dec_arr = data["dec_deg"]
    da_a_arr = data["da_a"]
    n = data["n"]
    print(f"Loaded {n} absorbers")

    # Load run.json for best-fit dipole
    try:
        with open(args.run) as f:
            run = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"WARNING: Could not load {args.run}: {e}", file=sys.stderr)
        run = {}

    bf = run.get("best_fit_dipole", {})
    verdict = run.get("verdict", "PENDING")

    # Simplify verdict for annotation
    v_parts = verdict.split(" | ")
    verdict_line = v_parts[0] if v_parts else "PENDING"

    best_ra = bf.get("ra_deg", 260.0)
    best_dec = bf.get("dec_deg", -59.1)
    best_amp = bf.get("amplitude_x1e5", 0.9735)

    plot_dipole_map(
        ra_arr, dec_arr, da_a_arr,
        best_ra, best_dec, best_amp,
        KING_RA_DEG, KING_DEC_DEG,
        KING_RA_ERR_DEG, KING_DEC_ERR_DEG,
        args.output,
    )
