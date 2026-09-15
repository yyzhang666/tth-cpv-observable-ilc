#!/usr/bin/env python3
"""Redraw the frozen historical nine-point TopN figure with current legend names."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
from pathlib import Path

import matplotlib.pyplot as plt


TOP_NS = (1, 5, 10, 20, 30, 45, 60, 90, 180)
PREFIT_LABEL = "mass constraint-only + q_flavor minimize"
POSTFIT_LABEL = "q_reco minimize"


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_frozen_rows(path):
    with Path(path).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    observed = tuple(int(row["top_n"]) for row in rows)
    if observed != TOP_NS:
        raise RuntimeError(f"historical TopN grid changed: {observed}")
    required = {
        "price2014_signed_A_all",
        "kinfit_signed_A_all",
        "wall_seconds",
    }
    if not rows or not required.issubset(rows[0]):
        raise RuntimeError("historical TopN CSV schema changed")
    return rows


def plot(rows, output):
    top_n = [int(row["top_n"]) for row in rows]
    prefit = [float(row["price2014_signed_A_all"]) for row in rows]
    postfit = [float(row["kinfit_signed_A_all"]) for row in rows]
    timed = [row for row in rows if row["wall_seconds"].strip()]

    fig, (accuracy_axis, runtime_axis) = plt.subplots(1, 2, figsize=(12, 4.8))
    accuracy_axis.plot(
        top_n,
        prefit,
        marker="o",
        linewidth=2.0,
        color="#6a4c93",
        label=PREFIT_LABEL,
    )
    accuracy_axis.plot(
        top_n,
        postfit,
        marker="o",
        linewidth=2.0,
        color="#2a9d8f",
        label=POSTFIT_LABEL,
    )
    accuracy_axis.set_xlabel("TopN kept by signed flavor")
    accuracy_axis.set_ylabel("A_all")
    accuracy_axis.set_xticks(TOP_NS)
    accuracy_axis.grid(alpha=0.25)
    accuracy_axis.legend(loc="lower right")

    runtime_axis.plot(
        [int(row["top_n"]) for row in timed],
        [float(row["wall_seconds"]) for row in timed],
        marker="s",
        linewidth=2.0,
        color="#d95f02",
    )
    runtime_axis.set_xlabel("TopN timed by Marlin")
    runtime_axis.set_ylabel("Marlin wall time [s]")
    runtime_axis.set_xticks(TOP_NS)
    runtime_axis.grid(alpha=0.25)

    fig.suptitle("TopN accuracy and measured Marlin runtime")
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--original-png", type=Path, required=True)
    parser.add_argument("--original-script", type=Path, action="append", default=[])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() or args.output_dir.is_symlink():
        raise RuntimeError(f"refusing to reuse output directory: {args.output_dir}")
    rows = read_frozen_rows(args.input_csv)
    args.output_dir.mkdir(parents=True)

    copied_csv = args.output_dir / args.input_csv.name
    shutil.copyfile(args.input_csv, copied_csv)
    if sha256(copied_csv) != sha256(args.input_csv):
        raise RuntimeError("copied historical numeric data changed bytes")
    copied_scripts = []
    for source in args.original_script:
        target = args.output_dir / f"original_{source.name}"
        shutil.copyfile(source, target)
        copied_scripts.append(target)

    png = args.output_dir / "historical_topn_accuracy_runtime_current_legend.png"
    pdf = args.output_dir / "historical_topn_accuracy_runtime_current_legend.pdf"
    plot(rows, png)
    plot(rows, pdf)
    command = [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]]
    manifest = {
        "status": "presentation-only legend relabel of frozen historical nine-point TopN data",
        "changes": {
            "Price2014 + signed flavor": PREFIT_LABEL,
            "kinfit + signed flavor": POSTFIT_LABEL,
        },
        "unchanged": "numeric values, TopN points, axes, title, runtime points, colors, markers, and two-panel layout",
        "command": command,
        "inputs": {
            "csv": {"path": str(args.input_csv.resolve()), "sha256": sha256(args.input_csv)},
            "original_png": {"path": str(args.original_png.resolve()), "sha256": sha256(args.original_png)},
            "original_scripts": [
                {"path": str(path.resolve()), "sha256": sha256(path)}
                for path in args.original_script
            ],
        },
        "top_n": list(TOP_NS),
        "numeric_rows": rows,
        "script": {"path": str(Path(__file__).resolve()), "sha256": sha256(Path(__file__).resolve())},
        "outputs": {},
    }
    for path in [copied_csv, *copied_scripts, png, pdf]:
        manifest["outputs"][path.name] = {"path": str(path), "sha256": sha256(path)}
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
