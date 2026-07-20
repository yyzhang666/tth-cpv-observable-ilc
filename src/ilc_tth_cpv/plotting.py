"""Plotting in the theory-study style: line-only, no fill, no error bars, PNG.

matplotlib is imported lazily with the same cache workaround as the
authoritative scripts.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .histograms import SignedHistogram


def import_plotting():
    os.environ.setdefault("XDG_CACHE_HOME", "/tmp/ilc-tth-cpv-cache")
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-ilc-tth-cpv")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def plot_signed_histogram(
    hist: SignedHistogram,
    out_path: Path,
    title: str = "",
    xlabel: str = "",
    ylabel: str = "signed weight [fb]",
    show_abs: bool = True,
) -> Path:
    """Theory-study style step plot of signed (and optional |w|) contents."""
    plt = import_plotting()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    edges = hist.edges
    fig, ax = plt.subplots(figsize=(8.0, 5.0))
    ax.step(edges, hist.signed + [hist.signed[-1]], where="post",
            color="#2458a4", linewidth=1.4, label="signed")
    if show_abs:
        ax.step(edges, hist.absw + [hist.absw[-1]], where="post",
                color="#b34d2e", linewidth=1.0, linestyle="--", label="|w|")
    ax.axhline(0.0, color="#222222", linewidth=0.8)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    if title:
        ax.set_title(title)
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def plot_scan(
    c_values: list,
    m2dll_values: list,
    out_path: Path,
    title: str = "",
    level_lines: Optional[list] = None,
) -> Path:
    plt = import_plotting()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.0, 5.0))
    ax.plot(c_values, m2dll_values, color="#2458a4", linewidth=1.4)
    for level in level_lines or (1.0, 3.84):
        ax.axhline(level, color="#888888", linewidth=0.8, linestyle=":")
    ax.set_xlabel("c")
    ax.set_ylabel(r"$-2\,\Delta\ln L$")
    if title:
        ax.set_title(title)
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path
