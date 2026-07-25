"""
lde_probe.py — G19: Long Delayed Echoes historic series probe.

Stance: structure != meaning. LDE is a real ionospheric/magnetospheric
propagation phenomenon. Honest prior = NO_SIGNAL. Lunan's Epsilon Boötis
interpretation is a claim-under-test, not fact. Lunan withdrew in 1976.

This probe:
  1. Digitized delay series from Stormer (1928), Appleton (1934), Crawford (1967)
  2. Delay histogram + mode clustering
  3. FFT-ish recurrence analysis (delay-value periodicity via
     autocorrelation / power spectrum)
  4. Scramble null: unigram-preserving shuffle of observed delays
  5. Uniform null: delays drawn from uniform [min, max]

Outputs:
  outputs/lde/run.json + NOTES.md

Usage:
    python tools/scripts/lde_probe.py
"""
from __future__ import annotations

import json
import math
import random as rnd
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA_DIR = ROOT / "data" / "radio" / "lde"
OUT_DIR = ROOT / "outputs" / "lde"

STANCE = (
    "Long Delayed Echoes (LDEs) are a real ionospheric/magnetospheric "
    "propagation phenomenon with documented natural explanations (ducting, "
    "mode conversion, multi-round-the-world, plasma cloud reflection; "
    "cf. Holm 2004 / UiO review). This probe measures delay distribution "
    "and recurrence structure ONLY. The honest prior is NO_SIGNAL. "
    "Duncan Lunan's 1973 'Epsilon Boötis space probe' interpretation "
    "is a claim-under-test — not a fact. Lunan withdrew the claim in 1976 "
    "acknowledging methodological flaws. STRUCTURE != MESSAGE."
)

FORBIDDEN_PHRASES = (
    "alien relay confirmed",
    "Lunan proved",
    "Epsilon Boötis probe",
    "extraterrestrial communication",
    "ET probe",
    "Bracewell probe verified",
    "world echo is alien",
    "space probe confirmed",
    "alien relay",
    "extraterrestrial relay",
)

SOURCE = (
    "Datasets digitized from Faizullin (2010) arXiv:1007.4054: "
    "Stormer 1928 series (5 series, 58 delays, stopwatch ~0.5 s precision), "
    "Appleton 1934 histogram (77 delays, digitized from Fig. 1), "
    "Crawford 1967 histogram (50 delays, estimated from qualitative "
    "description in Faizullin 2010 / Vidmar & Crawford 1985 JGR)."
)


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def load_stormer_series() -> dict:
    path = DATA_DIR / "stormer_1928_series.json"
    raw = json.loads(path.read_text())
    return raw


def load_appleton_histogram() -> dict:
    path = DATA_DIR / "appleton_1934_histogram.json"
    raw = json.loads(path.read_text())
    return raw


def load_crawford_histogram() -> dict:
    path = DATA_DIR / "crawford_1967_distribution.json"
    raw = json.loads(path.read_text())
    return raw


def histogram_to_delays(h: dict) -> list[float]:
    delays = h["histogram_bins"]["delay_s"]
    counts = h["histogram_bins"]["counts"]
    out = []
    for d, c in zip(delays, counts):
        out.extend([float(d)] * c)
    return out


# ---------------------------------------------------------------------------
# Analysis functions
# ---------------------------------------------------------------------------

def delay_histogram(delays: list[float], bins: range) -> dict:
    counts = [0] * (bins.stop - bins.start)
    for d in delays:
        idx = int(d) - bins.start
        if 0 <= idx < len(counts):
            counts[idx] += 1
    return {
        "bin_start": bins.start,
        "bin_end": bins.stop,
        "counts": counts,
        "n": len(delays),
    }


def mode_clustering(delays: list[float]) -> dict:
    if not delays:
        return {}
    c = Counter(int(d) for d in delays)
    total = len(delays)
    modes = c.most_common(5)
    n_unique = len(c)
    return {
        "top_modes": [(int(k), int(v)) for k, v in modes],
        "n_unique_delays": n_unique,
        "entropy_bits": round(
            -sum((v / total) * math.log2(v / total) for v in c.values()), 4
        ),
    }


def autocorr_delays(delays: list[float], max_lag: int | None = None) -> dict:
    if len(delays) < 3:
        return {"note": "too few delays for autocorrelation"}
    n = len(delays)
    if max_lag is None:
        max_lag = min(n // 2, 20)
    mean = sum(delays) / n
    var = sum((d - mean) ** 2 for d in delays)
    if var < 1e-12:
        return {"note": "zero variance"}
    lags = list(range(1, max_lag + 1))
    ac = []
    for lag in lags:
        num = sum((delays[i] - mean) * (delays[i + lag] - mean)
                  for i in range(n - lag))
        ac.append(num / var if var else 0.0)
    peak_lag = lags[ac.index(max(ac))] if ac else 0
    peak_val = max(ac) if ac else 0.0
    return {
        "lags": lags,
        "values": [round(v, 4) for v in ac],
        "peak_lag": peak_lag,
        "peak_value": round(peak_val, 4),
        "n": n,
    }


def fft_power_spectrum(delays: list[float]) -> dict:
    if len(delays) < 4:
        return {"note": "too few delays for FFT"}
    n = len(delays)
    mean = sum(delays) / n
    detrended = [d - mean for d in delays]
    fft = _fft(detrended)
    power = [abs(x) ** 2 for x in fft]
    power = power[:n // 2]
    freqs = [k / n for k in range(len(power))]
    peak_idx = power.index(max(power))
    return {
        "n": n,
        "peak_bin": peak_idx,
        "peak_freq": round(freqs[peak_idx], 4),
        "peak_power": round(power[peak_idx], 4),
        "power_mean": round(sum(power) / len(power), 4),
        "power_sd": round(
            (sum((p - sum(power) / len(power)) ** 2 for p in power)
             / len(power)) ** 0.5, 4
        ) if power else 0.0,
        "peak_over_mean": round(
            power[peak_idx] / (sum(power) / len(power)), 4
        ) if power and sum(power) > 0 else 0.0,
    }


def _fft(x: list[float]) -> list[complex]:
    n = len(x)
    if n <= 1:
        return [complex(v, 0) for v in x]
    even = _fft([x[i] for i in range(0, n, 2)])
    odd = _fft([x[i] for i in range(1, n, 2)])
    out = [0j] * n
    for k in range(n // 2):
        t = complex(math.cos(-2 * math.pi * k / n),
                     math.sin(-2 * math.pi * k / n)) * odd[k]
        out[k] = even[k] + t
        out[k + n // 2] = even[k] - t
    return out


# ---------------------------------------------------------------------------
# Null controls
# ---------------------------------------------------------------------------

def scramble_null(delays: list[float], n_sims: int = 1000,
                  seed: int = 0) -> dict:
    if len(delays) < 3:
        return {"note": "too few delays"}
    rng = rnd.Random(seed)
    obs_auto = autocorr_delays(delays)

    peak_lags = []
    peak_vals = []
    for s in range(n_sims):
        shuffled = list(delays)
        rng.shuffle(shuffled)
        ac = autocorr_delays(shuffled)
        if "peak_lag" in ac:
            peak_lags.append(ac["peak_lag"])
            peak_vals.append(ac["peak_value"])

    mu_peak = sum(peak_vals) / len(peak_vals) if peak_vals else 0.0
    sd_peak = (
        (sum((p - mu_peak) ** 2 for p in peak_vals) / len(peak_vals)) ** 0.5
        if len(peak_vals) > 1 else 1e-12
    )
    obs_peak = obs_auto.get("peak_value", 0.0)
    z = (obs_peak - mu_peak) / sd_peak if sd_peak > 1e-12 else 0.0

    return {
        "n_sims": n_sims,
        "observed_peak_ac": round(obs_peak, 4),
        "scramble_mean_peak_ac": round(mu_peak, 4),
        "scramble_sd_peak_ac": round(sd_peak, 4),
        "z": round(z, 2),
        "excess_over_null": obs_peak > mu_peak + 2 * sd_peak,
    }


def uniform_null(delays: list[float], n_sims: int = 1000,
                 seed: int = 0) -> dict:
    if len(delays) < 3:
        return {"note": "too few delays"}
    rng = rnd.Random(seed)
    d_min, d_max = min(delays), max(delays)
    obs_auto = autocorr_delays(delays)

    peak_vals = []
    for s in range(n_sims):
        uni = [d_min + rng.random() * (d_max - d_min) for _ in delays]
        ac = autocorr_delays(uni)
        if "peak_value" in ac:
            peak_vals.append(ac["peak_value"])

    mu_peak = sum(peak_vals) / len(peak_vals) if peak_vals else 0.0
    sd_peak = (
        (sum((p - mu_peak) ** 2 for p in peak_vals) / len(peak_vals)) ** 0.5
        if len(peak_vals) > 1 else 1e-12
    )
    obs_peak = obs_auto.get("peak_value", 0.0)
    z = (obs_peak - mu_peak) / sd_peak if sd_peak > 1e-12 else 0.0

    return {
        "n_sims": n_sims,
        "observed_peak_ac": round(obs_peak, 4),
        "uniform_mean_peak_ac": round(mu_peak, 4),
        "uniform_sd_peak_ac": round(sd_peak, 4),
        "z": round(z, 2),
        "excess_over_null": obs_peak > mu_peak + 2 * sd_peak,
    }


# ---------------------------------------------------------------------------
# Forbidden-phrase guard
# ---------------------------------------------------------------------------

def assert_no_forbidden_phrases(text: str, where: str = "") -> None:
    text_lower = text.lower()
    for phrase in FORBIDDEN_PHRASES:
        if phrase.lower() in text_lower:
            raise ValueError(
                f"FORBIDDEN phrase {phrase!r} found in {where}"
            )


# ---------------------------------------------------------------------------
# Verdict builder
# ---------------------------------------------------------------------------

def build_verdict(stormer_ac_z: float | None, appleton_ac_z: float | None,
                  crawford_ac_z: float | None) -> str:
    parts = []
    zs = [z for z in (stormer_ac_z, appleton_ac_z, crawford_ac_z)
          if z is not None]
    if not zs:
        return "UNDERDETERMINED"
    n_signal = sum(1 for z in zs if z > 3.0)
    n_under = sum(1 for z in zs if abs(z) <= 3.0)
    n_noise = sum(1 for z in zs if z < -3.0)
    if n_noise > len(zs) / 2:
        parts.append("NO_SIGNAL")
    elif n_signal > len(zs) / 2:
        parts.append("STRUCTURE_SIGNAL")
    else:
        parts.append("UNDERDETERMINED")
    parts.append(f"z_stormer={stormer_ac_z}" if stormer_ac_z is not None
                 else "z_stormer=NA")
    parts.append(f"z_appleton={appleton_ac_z}" if appleton_ac_z is not None
                 else "z_appleton=NA")
    parts.append(f"z_crawford={crawford_ac_z}" if crawford_ac_z is not None
                 else "z_crawford=NA")
    return " | ".join(parts)


# ---------------------------------------------------------------------------
# Per-dataset analysis
# ---------------------------------------------------------------------------

def analyze_dataset(label: str, delays: list[float],
                    seed: int = 0) -> dict:
    if not delays:
        return {"label": label, "error": "empty dataset"}
    n = len(delays)
    d_min, d_max = min(delays), max(delays)
    mean = sum(delays) / n
    sd = (sum((d - mean) ** 2 for d in delays) / n) ** 0.5 if n > 1 else 0.0

    hist = delay_histogram(delays, range(int(d_min), int(d_max) + 2))
    modes = mode_clustering(delays)
    ac = autocorr_delays(delays)
    fft = fft_power_spectrum(delays)
    scrm = scramble_null(delays, seed=seed)
    uni = uniform_null(delays, seed=seed + 1000)

    ac_z = scrm.get("z", 0) if scrm.get("z") is not None else None

    return {
        "label": label,
        "n": n,
        "min_s": d_min,
        "max_s": d_max,
        "mean_s": round(mean, 4),
        "sd_s": round(sd, 4),
        "histogram": hist,
        "modes": modes,
        "autocorr": ac,
        "fft": fft,
        "scramble_null": scrm,
        "uniform_null": uni,
        "ac_z_vs_scramble": ac_z,
    }


# ---------------------------------------------------------------------------
# Markdown writer
# ---------------------------------------------------------------------------

def write_notes_md(report: dict) -> str:
    parts = []
    verdict = report.get("verdict", "PENDING")
    icon_map = {"STRUCTURE_SIGNAL": "\U0001f7e2", "NO_SIGNAL": "\U0001f534",
                "UNDERDETERMINED": "\U0001f7e1"}
    icon = icon_map.get(verdict.split(" | ")[0], "\U0001f7e1")

    parts.append(f"# G19 — Long Delayed Echoes historic series probe  {icon}")
    parts.append(f"*Generated: {report.get('generated_at', '?')}*")
    parts.append("")
    parts.append("## Stance")
    parts.append(STANCE)
    parts.append("")
    parts.append("### Forbidden phrases (logged)")
    for fp in FORBIDDEN_PHRASES:
        parts.append(f"- `{fp}`")
    parts.append("")

    parts.append("## Source / data")
    parts.append(SOURCE)
    parts.append("")

    for r in report.get("datasets", []):
        label = r.get("label", "?")
        parts.append(f"### {label}")
        parts.append(f"- N={r.get('n')}  "
                     f"min={r.get('min_s')}s  max={r.get('max_s')}s  "
                     f"mean={r.get('mean_s')}s  sd={r.get('sd_s')}s")
        modes = r.get("modes", {})
        if modes:
            parts.append(f"- Top modes: {modes.get('top_modes', [])}")
            parts.append(f"- H delay bits: {modes.get('entropy_bits')}")
        ac = r.get("autocorr", {})
        if "peak_value" in ac:
            parts.append(f"- AC peak: lag={ac.get('peak_lag')}, "
                         f"val={ac.get('peak_value')}")
        fft = r.get("fft", {})
        if "peak_power" in fft:
            parts.append(f"- FFT peak: bin={fft.get('peak_bin')}, "
                         f"freq={fft.get('peak_freq')}, "
                         f"power={fft.get('peak_power')}, "
                         f"P/mean={fft.get('peak_over_mean')}")
        scrm = r.get("scramble_null", {})
        if "z" in scrm:
            parts.append(f"- Scramble null z={scrm.get('z')} "
                         f"{'STRUCTURE' if scrm.get('excess_over_null') else 'NO_EXCESS'}")
        uni = r.get("uniform_null", {})
        if "z" in uni:
            parts.append(f"- Uniform null z={uni.get('z')} "
                         f"{'STRUCTURE' if uni.get('excess_over_null') else 'NO_EXCESS'}")
        parts.append("")

    parts.append(f"## Verdict: **{verdict}**")
    parts.append("")
    parts.append(report.get("caveat", ""))
    parts.append("")

    parts.append("## Caveats")
    parts.append("1. **Stormer series** were timed by stopwatch (~0.5–1 s "
                 "precision). The 5 series are not independent — they are "
                 "sequential registrations from the same session.")
    parts.append("2. **Appleton histogram** is digitized from a "
                 "hand-drawn figure (arXiv:1007.4054 Fig. 1). Bin counts "
                 "are approximate (±1).")
    parts.append("3. **Crawford distribution** is estimated from "
                 "qualitative description ('2 and 8 s most frequent'). "
                 "The Sears 1974 PhD thesis may contain tabulated values "
                 "not accessed.")
    parts.append("4. **LDEs have natural explanations.** Magnetospheric "
                 "ducting (Muldrew 1979), mode conversion (Crawford et al. "
                 "1970), and multi-round-the-world propagation (Goodacre "
                 "1980) explain delays of 1–40 s without invoking "
                 "extraterrestrial probes.")
    parts.append("5. **Lunan withdrew his claim** in 1976, acknowledging "
                 "methodological flaws in the Epsilon Boötis interpretation.")
    parts.append("6. **Delay clustering around integer seconds** may "
                 "reflect measurement rounding (stopwatch resolution), not "
                 "an underlying quantized process.")
    parts.append("")
    parts.append("---")
    parts.append("*G19 LDE historic series — structure != meaning. "
                 "No alien relay, no Epsilon Boötis, no Bracewell probe "
                 "endorsement. Honest prior: NO_SIGNAL.*")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="G19 LDE historic series probe.")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--n-sims", type=int, default=1000)
    ap.add_argument("--out-json", type=str, default=None)
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    stormer_raw = load_stormer_series()
    delays_s = stormer_raw["all_delays_s"]
    s_result = analyze_dataset("Stormer_1928", delays_s, seed=args.seed)
    print(f"  Stormer 1928: N={s_result['n']}, "
          f"AC z={s_result.get('ac_z_vs_scramble', '?')}")

    appleton_raw = load_appleton_histogram()
    delays_a = histogram_to_delays(appleton_raw)
    a_result = analyze_dataset("Appleton_1934", delays_a, seed=args.seed + 1)
    print(f"  Appleton 1934: N={a_result['n']}, "
          f"AC z={a_result.get('ac_z_vs_scramble', '?')}")

    crawford_raw = load_crawford_histogram()
    delays_c = histogram_to_delays(crawford_raw)
    c_result = analyze_dataset("Crawford_1967", delays_c, seed=args.seed + 2)
    print(f"  Crawford 1967: N={c_result['n']}, "
          f"AC z={c_result.get('ac_z_vs_scramble', '?')}")

    stormer_z = s_result.get("ac_z_vs_scramble")
    appleton_z = a_result.get("ac_z_vs_scramble")
    crawford_z = c_result.get("ac_z_vs_scramble")

    verdict = build_verdict(stormer_z, appleton_z, crawford_z)

    metadata = {
        "n_stormer": s_result["n"],
        "n_appleton": a_result["n"],
        "n_crawford": c_result["n"],
        "datasets": ["Stormer_1928", "Appleton_1934", "Crawford_1967"],
    }

    caveats = (
        "Three independent LDE datasets analyzed. Honest prior: NO_SIGNAL. "
        "Delay distributions cluster around small integers (3–15 s for "
        "Stormer/Appleton; 2–8 s for Crawford). This likely reflects "
        "measurement precision (stopwatch rounding) and the real physics of "
        "magnetospheric ducting paths — not an alien communication protocol."
    )

    report = {
        "mission": "G19",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "metadata": metadata,
        "datasets": [s_result, a_result, c_result],
        "data_source": SOURCE,
        "stance": STANCE,
        "forbidden_phrases": list(FORBIDDEN_PHRASES),
        "caveat": caveats,
        "pipeline": {
            "tool": "tools/scripts/lde_probe.py",
            "dependencies": [],
            "parameters": {
                "seed": args.seed,
                "n_sims": args.n_sims,
            },
        },
    }

    out_json = OUT_DIR / "run.json"
    out_md = OUT_DIR / "NOTES.md"
    out_json.write_text(json.dumps(report, indent=2, default=str))
    out_md.write_text(write_notes_md(report))

    print(f"\nwrote {out_json}")
    print(f"wrote {out_md}")
    print(f"Verdict: {verdict}")


if __name__ == "__main__":
    main()
