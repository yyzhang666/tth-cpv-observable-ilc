#!/usr/bin/env python3
"""Signal-only Fisher information from scored CPV and SM event CSVs."""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
FLAVORS = ("electron", "muon")


def _read_events(path: Path, role: str, score_column: str) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    values = {flavor: [] for flavor in FLAVORS}
    weights = {flavor: [] for flavor in FLAVORS}
    seen: set[str] = set()
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"event_id", "lepton_flavor", "weight_8ab", score_column}
        missing = sorted(required - set(reader.fieldnames or ()))
        if missing:
            raise ValueError(f"{path} missing required columns: {missing}")
        for row in reader:
            event_id = row["event_id"]
            if event_id in seen:
                raise ValueError(f"duplicate {role} event_id={event_id} in {path}")
            seen.add(event_id)
            if row.get("split", "test") != "test":
                raise ValueError(f"{role} contains a non-test row: event_id={event_id}")
            flavor = row["lepton_flavor"]
            if flavor not in FLAVORS:
                raise ValueError(f"unexpected lepton_flavor={flavor!r} in {path}")
            try:
                score = float(row[score_column])
                weight = float(row["weight_8ab"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"non-numeric score/weight for event_id={event_id}") from exc
            if not (math.isfinite(score) and -1.0 <= score <= 1.0):
                raise ValueError(f"invalid score for event_id={event_id}: {score}")
            if not math.isfinite(weight):
                raise ValueError(f"non-finite weight for event_id={event_id}")
            if role == "sm" and weight < 0.0:
                raise ValueError(f"negative SM weight for event_id={event_id}")
            values[flavor].append(score)
            weights[flavor].append(weight)
    arrays = {
        flavor: (
            np.asarray(values[flavor], dtype=np.float64),
            np.asarray(weights[flavor], dtype=np.float64),
        )
        for flavor in FLAVORS
    }
    if role == "cpv":
        all_weights = np.concatenate([arrays[flavor][1] for flavor in FLAVORS])
        if not ((all_weights < 0.0).any() and (all_weights > 0.0).any()):
            raise ValueError("CPV CSV must contain both signed-weight branches")
    return arrays


def _fisher_per_bin(sm: tuple[np.ndarray, np.ndarray], cpv: tuple[np.ndarray, np.ndarray], edges: np.ndarray):
    sm_hist, _ = np.histogram(sm[0], bins=edges, weights=sm[1])
    cpv_hist, _ = np.histogram(cpv[0], bins=edges, weights=cpv[1])
    sm_entries, _ = np.histogram(sm[0], bins=edges)
    cpv_entries, _ = np.histogram(cpv[0], bins=edges)
    terms = np.divide(cpv_hist * cpv_hist, sm_hist, out=np.zeros_like(cpv_hist), where=sm_hist > 0.0)
    return sm_hist.astype(float), cpv_hist.astype(float), terms.astype(float), sm_entries, cpv_entries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sm-csv", type=Path, required=True)
    parser.add_argument("--cpv-csv", type=Path, required=True)
    parser.add_argument("--ml-score-column", required=True)
    parser.add_argument("--bins", type=int, default=20)
    parser.add_argument("--range", nargs=2, type=float, default=(-1.0, 1.0), metavar=("LOW", "HIGH"))
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--plot", action="store_true")
    args = parser.parse_args(argv)
    if args.bins <= 0:
        raise SystemExit("--bins must be positive")
    low, high = (float(args.range[0]), float(args.range[1]))
    if not (math.isfinite(low) and math.isfinite(high) and low < high):
        raise SystemExit("invalid --range")
    for path in (args.sm_csv, args.cpv_csv):
        if not path.is_file():
            raise SystemExit(f"missing input CSV: {path}")
    edges = np.linspace(low, high, args.bins + 1)
    sm = _read_events(args.sm_csv, "sm", args.ml_score_column)
    cpv = _read_events(args.cpv_csv, "cpv", args.ml_score_column)

    bin_rows = []
    summary = {}
    for flavor in FLAVORS:
        sm_hist, cpv_hist, fisher_bins, sm_entries, cpv_entries = _fisher_per_bin(sm[flavor], cpv[flavor], edges)
        fisher_value = float(fisher_bins.sum())
        summary[flavor] = {
            "fisher": fisher_value,
            "S0_8ab": float(sm_hist.sum()),
            "S1_8ab_signed": float(cpv_hist.sum()),
            "sm_entries": int(sm[flavor][0].size),
            "cpv_entries": int(cpv[flavor][0].size),
        }
        for index in range(args.bins):
            bin_rows.append({
                "lepton_flavor": flavor,
                "bin_index": index,
                "bin_low": float(edges[index]),
                "bin_high": float(edges[index + 1]),
                "bin_center": float(0.5 * (edges[index] + edges[index + 1])),
                "S0_8ab": float(sm_hist[index]),
                "S1_8ab": float(cpv_hist[index]),
                "B_8ab": 0.0,
                "denominator_8ab": float(sm_hist[index]),
                "fisher": float(fisher_bins[index]),
                "invalid": "" if sm_hist[index] > 0.0 else "nonpositive_S0",
                "sm_entries": int(sm_entries[index]),
                "cpv_entries": int(cpv_entries[index]),
                "background_entries": 0,
            })
    combined = float(sum(summary[flavor]["fisher"] for flavor in FLAVORS))
    summary["combined_likelihood"] = {
        "fisher": combined,
        "sigma_c": 1.0 / math.sqrt(combined) if combined > 0.0 else math.inf,
        "c95": 1.96 / math.sqrt(combined) if combined > 0.0 else math.inf,
        "combination": "I_electron + I_muon",
    }

    output_dir = args.output_dir or REPO_ROOT / "outputs/event_csv_fisher" / f"{args.ml_score_column}_signal_only"
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    bins_path = output_dir / "fisher_bins.csv"
    summary_path = output_dir / "fisher_summary.json"
    if bins_path.exists() or summary_path.exists():
        raise FileExistsError(f"refusing existing output: {bins_path} or {summary_path}")
    with bins_path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(bin_rows[0]))
        writer.writeheader()
        writer.writerows(bin_rows)
    payload = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "eLpR signal-only diagnostic",
        "observable": {"kind": "ml_score", "name": args.ml_score_column, "score_column": args.ml_score_column, "bins": args.bins, "range": [low, high]},
        "selection": {"expression": "none (signal-only)", "strict_greater_than": False},
        "weights": "weight_8ab from CSV; no additional luminosity scaling",
        "fisher": "sum over e/mu and bins of S1^2/S0",
        "inputs": {"sm": str(args.sm_csv.resolve()), "cpv": str(args.cpv_csv.resolve())},
        "summary": summary,
        "outputs": {"bins": str(bins_path), "summary": str(summary_path)},
    }
    summary_path.write_text(json.dumps(payload, indent=2) + "\n")

    if args.plot:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
        for axis, flavor in zip(axes, FLAVORS):
            current = [row for row in bin_rows if row["lepton_flavor"] == flavor]
            axis.bar([row["bin_center"] for row in current], [row["fisher"] for row in current], width=0.88 * (edges[1] - edges[0]), color="#2ca02c")
            axis.set_title(f"{flavor}: I={summary[flavor]['fisher']:.4f}")
            axis.set_xlabel(args.ml_score_column)
            axis.grid(axis="y", alpha=0.22)
        axes[0].set_ylabel("per-bin Fisher information")
        fig.tight_layout()
        fig.savefig(output_dir / "fisher_per_bin.png", dpi=180)
        plt.close(fig)

    print(f"electron: Fisher = {summary['electron']['fisher']:.12g}")
    print(f"muon: Fisher = {summary['muon']['fisher']:.12g}")
    print(f"combined signal-only Fisher = {combined:.12g}")
    print(f"sigma_c = {summary['combined_likelihood']['sigma_c']:.12g}")
    print(f"c95 = {summary['combined_likelihood']['c95']:.12g}")
    print(f"outputs: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
