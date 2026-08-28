#!/usr/bin/env python3
"""Event-level Fisher from the public eLpR MVA-v0 CSV datasets.

Examples:
    python3 scripts/evaluate_event_csv_fisher.py \
        --ml-model wbjets_lepton_v0 --bins 64 --plot

    python3 scripts/evaluate_event_csv_fisher.py \
        --angle O_lnu --bins 20 --q-sel-threshold 0.97 --plot

The three input files already contain expected event weights at 8 ab^-1.
Therefore no additional luminosity or cross-section factor is applied here.
Electron and muon categories are evaluated independently and their Fisher
information is added only at the likelihood level.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ilc_tth_cpv.csv_observables import (  # noqa: E402
    CsvObservableError,
    available_csv_angles,
    compute_csv_angle,
)
from ilc_tth_cpv.fisher import fisher_information  # noqa: E402


DATA_ROOT = REPO_ROOT / "data/event_csv/v0"
DEFAULT_BACKGROUND = DATA_ROOT / "eLpR_backgroud_dataset_mva_v0.csv"
DEFAULT_SM = DATA_ROOT / "eLpR_sm_test_dataset_mva_v0.csv"
DEFAULT_CPV = DATA_ROOT / "eLpR_cpv_test_dataset_mva_v0.csv"
DEFAULT_Q_SEL_THRESHOLD = 0.954
DEFAULT_BACKGROUND_Q_SEL_FLOOR = 0.954
FLAVORS = ("electron", "muon")

# These aliases identify CP-observable score columns.  q_sel remains the
# separate signal/background selection score and is never used as the Fisher
# histogram axis.
ML_MODEL_COLUMNS = {
    "wbjets_lepton": "q_CPV_wbjets_lepton",
    "wbjets_lepton_v0": "q_CPV_wbjets_lepton",
}


@dataclass
class SelectedEvents:
    values: dict[str, np.ndarray]
    weights: dict[str, np.ndarray]
    rows_total: int
    rows_pass_q_sel: int
    rows_selected_finite: int
    rows_invalid: int


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _finite(row: dict[str, str], column: str) -> float:
    try:
        value = float(row[column])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"missing/non-numeric column {column!r}") from exc
    if not math.isfinite(value):
        raise ValueError(f"non-finite column {column!r}")
    return value


def strict_q_sel_pass(score: float, threshold: float) -> bool:
    """The selection contract is strictly greater-than, never greater-or-equal."""
    return math.isfinite(score) and score > threshold


def event_key(row: dict[str, str], role: str) -> tuple[str, ...]:
    if role == "background":
        try:
            return (row["job_key"], row["event_index"])
        except KeyError as exc:
            raise ValueError("background CSV requires job_key,event_index") from exc
    if "event_id" in row:
        return (row["event_id"],)
    try:
        return (row["chunk"], row["event_index"])
    except KeyError as exc:
        raise ValueError(f"{role} CSV requires event_id or chunk,event_index") from exc


def read_and_select(
    path: Path,
    role: str,
    q_sel_threshold: float,
    angle: Optional[str],
    score_column: Optional[str],
) -> SelectedEvents:
    values: dict[str, list[float]] = {flavor: [] for flavor in FLAVORS}
    weights: dict[str, list[float]] = {flavor: [] for flavor in FLAVORS}
    seen: set[tuple[str, ...]] = set()
    total = passed = invalid = 0
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        for row in reader:
            total += 1
            key = event_key(row, role)
            if key in seen:
                raise ValueError(f"duplicate {role} event key {key} in {path}")
            seen.add(key)
            try:
                q_sel = _finite(row, "q_sel")
            except ValueError:
                invalid += 1
                continue
            if not strict_q_sel_pass(q_sel, q_sel_threshold):
                continue
            passed += 1
            try:
                flavor = row["lepton_flavor"]
                if flavor not in FLAVORS:
                    raise ValueError(f"unexpected lepton_flavor {flavor!r}")
                weight = _finite(row, "weight_8ab")
                if role in {"background", "sm"} and weight < 0.0:
                    raise ValueError(f"negative {role} weight")
                if angle is not None:
                    value = compute_csv_angle(angle, row)
                else:
                    assert score_column is not None
                    value = _finite(row, score_column)
                if not math.isfinite(value):
                    raise ValueError("non-finite observable")
            except (AssertionError, CsvObservableError, KeyError, ValueError):
                invalid += 1
                continue
            values[flavor].append(value)
            weights[flavor].append(weight)

    selected = sum(len(entries) for entries in values.values())
    if selected == 0:
        raise ValueError(f"no finite selected {role} events in {path}")
    if role == "cpv":
        cpv_weights = np.concatenate(
            [np.asarray(weights[flavor], dtype=np.float64) for flavor in FLAVORS]
        )
        if not ((cpv_weights < 0.0).any() and (cpv_weights > 0.0).any()):
            raise ValueError("CPV CSV must retain both signed-weight branches")
    return SelectedEvents(
        values={flavor: np.asarray(values[flavor], dtype=np.float64) for flavor in FLAVORS},
        weights={flavor: np.asarray(weights[flavor], dtype=np.float64) for flavor in FLAVORS},
        rows_total=total,
        rows_pass_q_sel=passed,
        rows_selected_finite=selected,
        rows_invalid=invalid,
    )


def histogram(events: SelectedEvents, flavor: str, edges: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    values = events.values[flavor]
    if ((values < edges[0]) | (values > edges[-1])).any():
        low = float(values.min())
        high = float(values.max())
        raise ValueError(
            f"observable outside requested range [{edges[0]}, {edges[-1]}]: [{low}, {high}]"
        )
    weighted, _ = np.histogram(values, bins=edges, weights=events.weights[flavor])
    entries, _ = np.histogram(values, bins=edges)
    return weighted.astype(np.float64), entries.astype(np.int64)


def build_fisher(
    background: SelectedEvents,
    sm: SelectedEvents,
    cpv: SelectedEvents,
    edges: np.ndarray,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    bin_rows: list[dict[str, Any]] = []
    flavor_summary: dict[str, Any] = {}
    for flavor in FLAVORS:
        b, b_entries = histogram(background, flavor, edges)
        s0, s0_entries = histogram(sm, flavor, edges)
        s1, s1_entries = histogram(cpv, flavor, edges)
        result = fisher_information(s0, s1, background=b)
        flavor_summary[flavor] = {
            "fisher": float(result["fisher_absolute"]),
            "sigma_c": float(result["sigma_c"]),
            "c95": float(result["c95"]),
            "n_invalid_bins": int(result["n_invalid_bins"]),
            "S0_8ab": float(s0.sum()),
            "S1_8ab_signed": float(s1.sum()),
            "B_8ab": float(b.sum()),
            "sm_entries": int(s0_entries.sum()),
            "cpv_entries": int(s1_entries.sum()),
            "background_entries": int(b_entries.sum()),
        }
        for index, fisher_row in enumerate(result["per_bin"]):
            bin_rows.append(
                {
                    "lepton_flavor": flavor,
                    "bin_index": index,
                    "bin_low": float(edges[index]),
                    "bin_high": float(edges[index + 1]),
                    "bin_center": float(0.5 * (edges[index] + edges[index + 1])),
                    "S0_8ab": float(s0[index]),
                    "S1_8ab": float(s1[index]),
                    "B_8ab": float(b[index]),
                    "denominator_8ab": float(s0[index] + b[index]),
                    "fisher": float(fisher_row["fisher"]),
                    "invalid": fisher_row["invalid"] or "",
                    "sm_entries": int(s0_entries[index]),
                    "cpv_entries": int(s1_entries[index]),
                    "background_entries": int(b_entries[index]),
                }
            )
    total = sum(flavor_summary[flavor]["fisher"] for flavor in FLAVORS)
    flavor_summary["combined_likelihood"] = {
        "fisher": total,
        "sigma_c": 1.0 / math.sqrt(total) if total > 0.0 else math.inf,
        "c95": 1.96 / math.sqrt(total) if total > 0.0 else math.inf,
        "combination": "I_electron + I_muon",
    }
    return bin_rows, flavor_summary


def write_bins(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def make_plots(
    output_dir: Path,
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    xlabel: str,
) -> list[str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    by_flavor = {
        flavor: [row for row in rows if row["lepton_flavor"] == flavor]
        for flavor in FLAVORS
    }
    fig, axes = plt.subplots(2, 2, figsize=(11.0, 7.2), sharex="col")
    for column, flavor in enumerate(FLAVORS):
        current = by_flavor[flavor]
        edges = np.asarray([row["bin_low"] for row in current] + [current[-1]["bin_high"]])
        s0 = np.asarray([row["S0_8ab"] for row in current])
        b = np.asarray([row["B_8ab"] for row in current])
        s1 = np.asarray([row["S1_8ab"] for row in current])
        axes[0, column].step(edges, np.r_[s0, s0[-1]], where="post", label=r"SM $S_0$")
        axes[0, column].step(edges, np.r_[b, b[-1]], where="post", label="background")
        axes[0, column].set_title(flavor)
        axes[0, column].grid(alpha=0.22)
        axes[1, column].step(edges, np.r_[s1, s1[-1]], where="post", color="#2ca02c")
        axes[1, column].axhline(0.0, color="black", lw=0.7)
        axes[1, column].set_xlabel(xlabel)
        axes[1, column].grid(alpha=0.22)
    axes[0, 0].set_ylabel(r"expected events at $8\,\mathrm{ab}^{-1}$")
    axes[1, 0].set_ylabel(r"signed CPV $S_1$ at $8\,\mathrm{ab}^{-1}$")
    axes[0, 0].legend(frameon=False)
    fig.tight_layout()
    templates_path = output_dir / "event_templates.png"
    fig.savefig(templates_path, dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.4), sharey=True)
    for ax, flavor in zip(axes, FLAVORS):
        current = by_flavor[flavor]
        centers = np.asarray([row["bin_center"] for row in current])
        widths = np.asarray([row["bin_high"] - row["bin_low"] for row in current])
        fisher = np.asarray([row["fisher"] for row in current])
        ax.bar(centers, fisher, width=0.88 * widths, color="#2ca02c")
        ax.set_title(f"{flavor}: I={summary[flavor]['fisher']:.4f}")
        ax.set_xlabel(xlabel)
        ax.grid(axis="y", alpha=0.22)
    axes[0].set_ylabel("per-bin Fisher information")
    fig.tight_layout()
    fisher_path = output_dir / "fisher_per_bin.png"
    fig.savefig(fisher_path, dpi=180)
    plt.close(fig)
    return [str(templates_path), str(fisher_path)]


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    choice = result.add_mutually_exclusive_group()
    choice.add_argument("--ml-model", choices=sorted(ML_MODEL_COLUMNS))
    choice.add_argument("--ml-score-column")
    choice.add_argument("--angle", choices=available_csv_angles())
    result.add_argument("--list-observables", action="store_true")
    result.add_argument("--background-csv", type=Path, default=DEFAULT_BACKGROUND)
    result.add_argument("--sm-csv", type=Path, default=DEFAULT_SM)
    result.add_argument("--cpv-csv", type=Path, default=DEFAULT_CPV)
    result.add_argument("--q-sel-threshold", type=float, default=DEFAULT_Q_SEL_THRESHOLD)
    result.add_argument(
        "--background-q-sel-floor",
        type=float,
        default=DEFAULT_BACKGROUND_Q_SEL_FLOOR,
        help="lowest q_sel represented by the supplied background CSV",
    )
    result.add_argument("--bins", type=int, default=20)
    result.add_argument("--range", nargs=2, type=float, metavar=("LOW", "HIGH"))
    result.add_argument("--output-dir", type=Path)
    result.add_argument("--plot", action="store_true")
    return result


def main(argv: Optional[List[str]] = None) -> int:
    args = parser().parse_args(argv)
    if args.list_observables:
        print("ML models:")
        for name, column in ML_MODEL_COLUMNS.items():
            print(f"  {name}: {column}")
        print("CSV angles:")
        for name in available_csv_angles():
            print(f"  {name}")
        return 0
    if not (args.ml_model or args.ml_score_column or args.angle):
        raise SystemExit("choose exactly one of --ml-model, --ml-score-column, or --angle")
    if args.bins <= 0:
        raise SystemExit("--bins must be positive")
    if not math.isfinite(args.q_sel_threshold):
        raise SystemExit("--q-sel-threshold must be finite")
    if args.q_sel_threshold < args.background_q_sel_floor:
        raise SystemExit(
            f"requested q_sel>{args.q_sel_threshold} is below the background CSV floor "
            f"{args.background_q_sel_floor}; supply a background CSV complete to the lower threshold"
        )

    score_column = args.ml_score_column
    observable_name = args.angle
    if args.ml_model:
        score_column = ML_MODEL_COLUMNS[args.ml_model]
        observable_name = args.ml_model
    elif args.ml_score_column:
        observable_name = args.ml_score_column
    assert observable_name is not None
    low, high = (
        tuple(args.range)
        if args.range is not None
        else (-math.pi, math.pi)
        if args.angle
        else (-1.0, 1.0)
    )
    if not (math.isfinite(low) and math.isfinite(high) and low < high):
        raise SystemExit("invalid --range")
    edges = np.linspace(low, high, args.bins + 1)

    background = read_and_select(
        args.background_csv, "background", args.q_sel_threshold, args.angle, score_column
    )
    sm = read_and_select(args.sm_csv, "sm", args.q_sel_threshold, args.angle, score_column)
    cpv = read_and_select(args.cpv_csv, "cpv", args.q_sel_threshold, args.angle, score_column)
    bin_rows, fisher_summary = build_fisher(background, sm, cpv, edges)

    threshold_tag = str(args.q_sel_threshold).replace(".", "p")
    output_dir = args.output_dir or (
        REPO_ROOT / "outputs/event_csv_fisher" / f"{observable_name}_qsel_gt_{threshold_tag}"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    bins_path = output_dir / "fisher_bins.csv"
    write_bins(bins_path, bin_rows)

    payload: dict[str, Any] = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "eLpR test-covered-background diagnostic",
        "observable": {
            "kind": "angle" if args.angle else "ml_score",
            "name": observable_name,
            "score_column": score_column,
            "bins": args.bins,
            "range": [low, high],
        },
        "selection": {
            "expression": f"q_sel > {args.q_sel_threshold}",
            "strict_greater_than": True,
            "background_q_sel_floor": args.background_q_sel_floor,
        },
        "weights": "weight_8ab from CSV; no additional luminosity scaling",
        "fisher": "sum over e/mu and bins of S1^2/(S0+B)",
        "inputs": {
            "background": str(args.background_csv),
            "sm": str(args.sm_csv),
            "cpv": str(args.cpv_csv),
        },
        "input_sha256": {
            "background": sha256(args.background_csv),
            "sm": sha256(args.sm_csv),
            "cpv": sha256(args.cpv_csv),
        },
        "event_accounting": {
            "background": background.__dict__,
            "sm": sm.__dict__,
            "cpv": cpv.__dict__,
        },
        "summary": fisher_summary,
        "outputs": {"bins": str(bins_path)},
    }
    # NumPy arrays are useful during calculation but not in accounting JSON.
    for role in ("background", "sm", "cpv"):
        payload["event_accounting"][role].pop("values")
        payload["event_accounting"][role].pop("weights")
    if args.plot:
        xlabel = f"{args.angle} [rad]" if args.angle else observable_name
        payload["outputs"]["plots"] = make_plots(
            output_dir, bin_rows, fisher_summary, xlabel
        )
    summary_path = output_dir / "fisher_summary.json"
    payload["outputs"]["summary"] = str(summary_path)
    with summary_path.open("w") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")

    for flavor in FLAVORS:
        print(
            f"{flavor:8s} I={fisher_summary[flavor]['fisher']:.12g} "
            f"S0={fisher_summary[flavor]['S0_8ab']:.6g} "
            f"S1={fisher_summary[flavor]['S1_8ab_signed']:+.6g} "
            f"B={fisher_summary[flavor]['B_8ab']:.6g}"
        )
    print(f"combined I={fisher_summary['combined_likelihood']['fisher']:.12g}")
    print(f"outputs: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
