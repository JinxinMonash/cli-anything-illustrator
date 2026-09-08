#!/usr/bin/env python3
"""Generate four SYNTHETIC demonstration panels as SVG (editable text).

All data are explicitly synthetic (fixed seed) and labelled as such in each
panel; these files exist only to exercise figure assembly.

matplotlib is configured with svg.fonttype='none' so text is exported as real
<text> elements: Illustrator then imports it as live, editable type instead
of outlined paths.
"""
import argparse
import os

import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams.update({
    "svg.fonttype": "none",          # keep text editable in the SVG
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 8,
    "axes.linewidth": 0.8,
})
import matplotlib.pyplot as plt
import numpy as np

PANEL_W_IN = 88 / 25.4   # 88 mm
PANEL_H_IN = 58 / 25.4   # 58 mm


def _fig():
    fig, ax = plt.subplots(figsize=(PANEL_W_IN, PANEL_H_IN))
    fig.subplots_adjust(left=0.17, right=0.96, top=0.88, bottom=0.20)
    return fig, ax


def panel_a(rng):
    fig, ax = _fig()
    x = rng.uniform(0, 10, 40)
    y = 1.8 * x + rng.normal(0, 2.0, 40)
    ax.scatter(x, y, s=8, alpha=0.75, edgecolors="none")
    coef = np.polyfit(x, y, 1)
    xs = np.linspace(0, 10, 50)
    ax.plot(xs, np.polyval(coef, xs), lw=1)
    ax.set_xlabel("Dose (a.u.)")
    ax.set_ylabel("Response (a.u.)")
    ax.set_title("Synthetic dose-response", fontsize=8)
    return fig


def panel_b(rng):
    fig, ax = _fig()
    groups = ["Ctrl", "T1", "T2", "T3"]
    means = [1.0, 1.6, 2.3, 2.1]
    sd = [0.15, 0.22, 0.30, 0.28]
    ax.bar(groups, means, yerr=sd, capsize=3, width=0.6)
    ax.set_ylabel("Fold change (synthetic)")
    ax.set_title("Synthetic group means ± SD", fontsize=8)
    return fig


def panel_c(rng):
    fig, ax = _fig()
    t = np.linspace(0, 48, 97)
    for k, lab in ((0.06, "Strain α"), (0.09, "Strain β")):
        y = 1 / (1 + np.exp(-k * (t - 24))) + rng.normal(0, 0.01, t.size)
        ax.plot(t, y, lw=1, label=lab)
    ax.set_xlabel("Time (h)")
    ax.set_ylabel("OD600 (synthetic)")
    ax.legend(frameon=False, fontsize=7)
    ax.set_title("Synthetic growth curves", fontsize=8)
    return fig


def panel_d(rng):
    fig, ax = _fig()
    data = [rng.normal(mu, 0.6, 60) for mu in (2.0, 2.8, 4.1)]
    ax.boxplot(data, tick_labels=["WT", "KO", "KO+R"], widths=0.5)
    ax.set_ylabel("Activity (synthetic)")
    ax.set_title("Synthetic distributions", fontsize=8)
    return fig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default="panels")
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    rng = np.random.default_rng(20260908)
    for pid, maker in zip("ABCD", (panel_a, panel_b, panel_c, panel_d)):
        fig = maker(rng)
        out = os.path.join(args.outdir, f"panel_{pid}.svg")
        fig.savefig(out, format="svg")
        plt.close(fig)
        print(out)


if __name__ == "__main__":
    main()
