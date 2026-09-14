#!/usr/bin/env python3
"""Plot Whizard masses from the exact four-method selected-common CSV."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path


BINS = 60
OBJECTS = {
    "W": {"range": (40.0, 130.0), "target": 80.4, "prefit": "mW_had_prefit", "postfit": "mW_had_postfit"},
    "top": {"range": (100.0, 240.0), "target": 172.5, "prefit": "mt_had_prefit", "postfit": "mt_had_postfit"},
    "H": {"range": (40.0, 210.0), "target": 125.0, "prefit": "mH_prefit", "postfit": "mH_postfit"},
}
KEY_FIELDS = ("source_file_id", "local_index", "run_number", "event_number")
REQUIRED_FIELDS = {
    *KEY_FIELDS,
    "mass_constraint_signed_combo_id",
    "kinfit_signed_combo_id",
    *(spec[field] for spec in OBJECTS.values() for field in ("prefit", "postfit")),
}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_selected_common(path):
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or ())
        missing = sorted(REQUIRED_FIELDS - fields)
        if missing:
            raise RuntimeError(f"selected-common CSV missing fields: {missing}")
        rows = list(reader)
    if not rows:
        raise RuntimeError("selected-common CSV is empty")
    seen = set()
    for row in rows:
        key = tuple(row[field] for field in KEY_FIELDS)
        if key in seen:
            raise RuntimeError(f"duplicate selected-common event key: {key}")
        seen.add(key)
        for spec in OBJECTS.values():
            for field in ("prefit", "postfit"):
                if not math.isfinite(float(row[spec[field]])):
                    raise RuntimeError(f"non-finite {spec[field]} for event {key}")
    return rows


def histogram(values, low, high):
    counts = [0] * BINS
    underflow = overflow = 0
    width = (high - low) / BINS
    for value in values:
        if value < low:
            underflow += 1
        elif value > high:
            overflow += 1
        else:
            index = BINS - 1 if value == high else int((value - low) / width)
            counts[index] += 1
    if underflow + sum(counts) + overflow != len(values):
        raise RuntimeError("histogram accounting failed")
    return {
        "counts": counts,
        "edges": [low + index * width for index in range(BINS + 1)],
        "underflow": underflow,
        "in_range": sum(counts),
        "overflow": overflow,
    }


def generate(input_csv, output_dir, plt):
    if output_dir.exists() or output_dir.is_symlink():
        raise RuntimeError(f"refusing to reuse output directory: {output_dir}")
    rows = read_selected_common(input_csv)
    denominator = len(rows)
    output_dir.mkdir(parents=True)
    figure, axes = plt.subplots(1, 3, figsize=(15, 4.8), dpi=180)
    histograms = {}
    summary_rows = []
    for axis, (name, spec) in zip(axes, OBJECTS.items()):
        low, high = spec["range"]
        histograms[name] = {}
        for stage, field, label, color in (
            ("prefit", spec["prefit"], "mass-constraint-only + signed flavor (PREFIT)", "#2364aa"),
            ("postfit", spec["postfit"], "kinfit + signed flavor (POSTFIT)", "#d95f02"),
        ):
            values = [float(row[field]) for row in rows]
            accounting = histogram(values, low, high)
            histograms[name][stage] = accounting
            axis.hist(values, bins=BINS, range=(low, high), weights=[1.0 / denominator] * denominator,
                      histtype="step", linewidth=1.8, color=color, label=label)
            summary_rows.append(
                {
                    "object": name,
                    "stage": stage,
                    "column": field,
                    "common_events": denominator,
                    "mean_GeV": sum(values) / denominator,
                    "underflow": accounting["underflow"],
                    "in_range": accounting["in_range"],
                    "overflow": accounting["overflow"],
                }
            )
        axis.axvline(spec["target"], color="#222222", linestyle=":", linewidth=1.2)
        axis.set_xlim(low, high)
        axis.set_xlabel(f"{name} mass [GeV]")
        axis.set_ylabel("fraction of common events / bin")
        axis.set_title(name)
        axis.grid(alpha=0.25)
    axes[-1].legend(fontsize=8)
    figure.suptitle(f"Whizard eL.pR selected assignment masses; common {denominator}-event denominator")
    figure.tight_layout()
    png = output_dir / "whizard_mass_constraint_prefit_vs_kinfit_postfit.png"
    pdf = output_dir / "whizard_mass_constraint_prefit_vs_kinfit_postfit.pdf"
    figure.savefig(png, bbox_inches="tight")
    figure.savefig(pdf, bbox_inches="tight")
    plt.close(figure)
    summary_csv = output_dir / "summary.csv"
    with summary_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0]))
        writer.writeheader()
        writer.writerows(summary_rows)
    command = [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]]
    manifest = {
        "status": "NAF diagnostic drawn without re-selection from the assignment common denominator",
        "input_csv": {"path": str(input_csv.resolve()), "sha256": sha256(input_csv)},
        "denominator": denominator,
        "event_key": list(KEY_FIELDS),
        "bins": BINS,
        "objects": OBJECTS,
        "normalization": "each common event has weight 1/N_common",
        "truth_evaluated": False,
        "assignment_accuracy_claim": False,
        "command": command,
        "histograms": histograms,
        "outputs": {
            path.name: {"path": str(path), "sha256": sha256(path)}
            for path in (png, pdf, summary_csv)
        },
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    result = generate(args.input_csv.resolve(strict=True), args.output_dir, plt)
    print(json.dumps({"denominator": result["denominator"], "output_dir": str(args.output_dir)}, sort_keys=True))


if __name__ == "__main__":
    main()
