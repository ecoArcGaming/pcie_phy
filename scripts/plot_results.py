#!/usr/bin/env python3
"""
Generate the Phase-5 result plots into docs/ from sim/perf_results.json.

Design choices (per the dataviz method): each chart is a single-series magnitude
plot -> one hue, no legend, direct value labels, recessive grid, one axis. The
clock-tolerance chart encodes a pass/fail *state*, so it uses reserved status
colors (green/red) with text labels -- never color alone.

    python scripts/plot_results.py
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / "sim" / "perf_results.json").read_text())
OUT = ROOT / "docs"

PRIMARY = "#3b6ea5"   # magnitude hue
CEIL    = "#c9d6e5"   # recessive reference
GOOD    = "#2e7d32"   # status: survived
BAD     = "#c62828"   # status: failed
INK     = "#222222"
MUTED   = "#666666"


def _style(ax, title):
    ax.set_title(title, color=INK, fontsize=12, fontweight="bold", pad=12)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(MUTED)
    ax.tick_params(colors=MUTED)
    ax.yaxis.grid(True, color="#e6e6e6", linewidth=0.8)
    ax.set_axisbelow(True)


def _label_bars(ax, bars, fmt):
    for b in bars:
        ax.text(b.get_x() + b.get_width() / 2, b.get_height(),
                fmt(b.get_height()), ha="center", va="bottom",
                color=INK, fontsize=10)


def plot_throughput():
    fig, ax = plt.subplots(figsize=(5, 4))
    labels = ["Gen1\n(2.5 GT/s)", "Gen2\n(5.0 GT/s)"]
    ceil = [250, 500]
    meas = [DATA["throughput_gen1_MBps"], DATA["throughput_gen2_MBps"]]
    ax.bar(labels, ceil, color=CEIL, width=0.6, label="_ceiling")
    bars = ax.bar(labels, meas, color=PRIMARY, width=0.6)
    _label_bars(ax, bars, lambda v: f"{v:.0f}")
    _style(ax, "Effective per-lane throughput vs ceiling")
    ax.set_ylabel("MB/s", color=MUTED)
    fig.tight_layout(); fig.savefig(OUT / "throughput.png", dpi=130); plt.close(fig)


def plot_timing():
    fig, ax = plt.subplots(figsize=(5, 4))
    labels = ["Train to L0\n(2.5 GT/s)", "Speed change\n(2.5→5.0)"]
    vals = [DATA["train_cycles"], DATA["speed_change_cycles"]]
    bars = ax.bar(labels, vals, color=PRIMARY, width=0.6)
    _label_bars(ax, bars, lambda v: f"{v:.0f} cyc\n(~{v*4/1000:.1f} µs)")
    _style(ax, "Link training / speed-change time")
    ax.set_ylabel("symbol clocks", color=MUTED)
    ax.set_ylim(0, max(vals) * 1.25)
    fig.tight_layout(); fig.savefig(OUT / "timing.png", dpi=130); plt.close(fig)


def plot_ber():
    fig, ax = plt.subplots(figsize=(5, 4))
    ber = sorted(DATA["ber"], key=lambda e: e["nbits"])
    labels = [f"{e['nbits']}-bit" for e in ber]
    vals = [e["detected_frac"] * 100 for e in ber]
    bars = ax.bar(labels, vals, color=PRIMARY, width=0.6)
    _label_bars(ax, bars, lambda v: f"{v:.1f}%")
    _style(ax, "8b/10b error detection by error weight")
    ax.set_ylabel("detected (%)", color=MUTED)
    ax.set_ylim(0, 108)
    fig.tight_layout(); fig.savefig(OUT / "ber.png", dpi=130); plt.close(fig)


def plot_clk_tol():
    fig, ax = plt.subplots(figsize=(6, 4))
    pts = sorted(DATA["clk_tol"], key=lambda e: e["ppm"])
    labels = [f"{e['ppm']:+}" for e in pts]
    # magnitude of corrective SKP ops, colored by survival state
    mag = [max(e["adds"], e["dels"]) for e in pts]
    colors = [GOOD if e["survived"] else BAD for e in pts]
    bars = ax.bar(labels, mag, color=colors, width=0.7)
    for b, e in zip(bars, pts):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height(),
                "ok" if e["survived"] else "FAIL", ha="center", va="bottom",
                color=GOOD if e["survived"] else BAD, fontsize=9, fontweight="bold")
    _style(ax, "Elastic-buffer clock tolerance (spec ±300 ppm)")
    ax.set_ylabel("SKP add/delete ops", color=MUTED)
    ax.set_xlabel("write-vs-read clock offset (ppm)", color=MUTED)
    fig.tight_layout(); fig.savefig(OUT / "clock_tolerance.png", dpi=130); plt.close(fig)


def main():
    OUT.mkdir(exist_ok=True)
    plot_throughput(); plot_timing(); plot_ber(); plot_clk_tol()
    print(f"wrote plots to {OUT}: throughput.png, timing.png, ber.png, "
          f"clock_tolerance.png")


if __name__ == "__main__":
    main()
