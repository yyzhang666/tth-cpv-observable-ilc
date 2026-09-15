#!/usr/bin/env python3
"""Redraw an existing Whizard jet-flavor CM with conference-size annotations."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


TITLE = (
    r"$t\bar t H,\ H\to b\bar b,\ \mathrm{semileptonic}$"
    + "\nRefinedJets6–TrueJets six-positive-Dice matching; Weaver 10x10"
)
DISPLAY_LABELS = [r"$b$", r"$\bar{b}$", r"$c$", r"$\bar{c}$", r"$s$", r"$\bar{s}$", r"$u$", r"$\bar{u}$", r"$d$", r"$\bar{d}$"]


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def annotation_color(value, vmax):
    """Use white only on the dark part of cividis for readable contrast."""
    return "white" if float(value) / float(vmax) < 0.34 else "black"


def plot(norm, output):
    fig, ax = plt.subplots(figsize=(10.5, 8.3), dpi=180)
    vmax = max(0.7, float(np.max(norm)) if norm.size else 0.7)
    image = ax.imshow(norm, origin="upper", aspect="auto", vmin=0.0, vmax=vmax, cmap="cividis")
    ax.set_xticks(range(len(DISPLAY_LABELS)))
    ax.set_xticklabels(DISPLAY_LABELS, fontsize=14)
    ax.set_yticks(range(len(DISPLAY_LABELS)))
    ax.set_yticklabels(DISPLAY_LABELS, fontsize=14)
    ax.set_xlabel("True flavor", fontsize=20)
    ax.set_ylabel("Predicted flavor", fontsize=20)
    ax.set_title(TITLE, fontsize=20)
    for row in range(norm.shape[0]):
        for column in range(norm.shape[1]):
            value = float(norm[row, column])
            ax.text(
                column,
                row,
                f"{value:.3f}",
                ha="center",
                va="center",
                fontsize=14,
                fontweight="bold",
                color=annotation_color(value, vmax),
            )
    colorbar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    colorbar.ax.tick_params(labelsize=12)
    fig.tight_layout()
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-npz", type=Path, required=True)
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--numeric-csv", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() or args.output_dir.is_symlink():
        raise RuntimeError(f"refusing to reuse output directory: {args.output_dir}")
    archive = np.load(args.input_npz, allow_pickle=True)
    norm = archive["norm"]
    counts = archive["counts"]
    class_order = [str(value) for value in archive["class_order"]]
    if norm.shape != (10, 10) or counts.shape != (10, 10) or len(class_order) != 10:
        raise RuntimeError("input NPZ is not the frozen 10x10 confusion matrix")
    if not np.array_equal(counts.sum(axis=0) > 0, np.ones(10, dtype=bool)):
        raise RuntimeError("input NPZ contains an empty true-flavor column")
    expected = counts / counts.sum(axis=0, keepdims=True)
    if not np.allclose(norm, expected, rtol=0.0, atol=1e-15):
        raise RuntimeError("input normalization is not exact true-flavor column normalization")
    args.output_dir.mkdir(parents=True)
    copied = []
    for source in args.numeric_csv:
        target = args.output_dir / source.name
        shutil.copyfile(source, target)
        if sha256(source) != sha256(target):
            raise RuntimeError(f"numeric CSV copy changed bytes: {source}")
        copied.append(target)
    png = args.output_dir / "whizard_truejet_weaver_cm10_conference_large_bold_numbers.png"
    pdf = args.output_dir / "whizard_truejet_weaver_cm10_conference_large_bold_numbers.pdf"
    plot(norm, png)
    plot(norm, pdf)
    command = [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]]
    manifest = {
        "status": "presentation-only redraw; physics values and denominator unchanged",
        "style_change": "14 pt bold annotations with adaptive black/white contrast",
        "physics_contract": "same raw counts, true-flavor column normalization, class order, cividis limits, title, axes, and colorbar",
        "command": command,
        "inputs": {
            "npz": {"path": str(args.input_npz.resolve()), "sha256": sha256(args.input_npz)},
            "manifest": {"path": str(args.input_manifest.resolve()), "sha256": sha256(args.input_manifest)},
            "numeric_csv": [{"path": str(path.resolve()), "sha256": sha256(path)} for path in args.numeric_csv],
        },
        "source_manifest": json.loads(args.input_manifest.read_text(encoding="utf-8")),
        "script": {"path": str(Path(__file__).resolve()), "sha256": sha256(Path(__file__).resolve())},
        "outputs": {},
    }
    for path in [*copied, png, pdf]:
        manifest["outputs"][path.name] = {"path": str(path), "sha256": sha256(path)}
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
