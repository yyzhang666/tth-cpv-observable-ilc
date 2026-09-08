#!/usr/bin/env python3
"""Prepare a validated SM/CPV/background event table for future training.

This command does not train a model.  CPV signed interference remains the
physics ``template_weight`` and is never passed directly to a classification
loss.  The caller must explicitly select ``unit`` or ``abs_template`` for the
nonnegative CPV training weight.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Optional


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ilc_tth_cpv.event_workflow import event_key, finite_value, strict_q_sel_pass  # noqa: E402
from ilc_tth_cpv.io import load_yaml  # noqa: E402
from ilc_tth_cpv.provenance import (  # noqa: E402
    atomic_write_json,
    file_record,
    git_state,
    runtime_state,
)


CLASS_ORDER = ("background", "sm", "cpv")
DEFAULT_CONFIG = REPO_ROOT / "configs/workflows/observable_research_v1.yaml"


def deterministic_fraction(identity: str, seed: int) -> float:
    digest = hashlib.sha256(f"{seed}:{identity}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / float(1 << 64)


def deterministic_split(identity: str, seed: int) -> str:
    value = deterministic_fraction(identity, seed)
    if value < 0.70:
        return "train"
    if value < 0.85:
        return "validation"
    return "test"


def stable_identity(row: dict[str, str], role: str) -> str:
    # NECESSITY: the role prefix prevents equal source IDs from colliding across classes.
    return f"{role}:" + ":".join(event_key(row, role))


def cpv_training_weight(template_weight: float, policy: str) -> float:
    if policy == "unit":
        return 1.0
    if policy == "abs_template":
        return abs(template_weight)
    raise ValueError(f"unsupported CPV training-weight policy {policy!r}")


def ordinary_training_weight(template_weight: float, policy: str) -> float:
    if template_weight < 0.0:
        raise ValueError("SM/background template weight must be nonnegative")
    if policy == "unit":
        return 1.0
    if policy == "template":
        return template_weight
    raise ValueError(f"unsupported ordinary training-weight policy {policy!r}")


def choose_path(override: Optional[Path], configured: str) -> Path:
    path = override if override is not None else Path(configured)
    return path if path.is_absolute() else REPO_ROOT / path


def read_role(
    path: Path,
    role: str,
    feature_columns: list[str],
    q_sel_threshold: Optional[float],
    split_seed: int,
    cpv_policy: str,
    ordinary_policy: str,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    output: list[dict[str, Any]] = []
    counts = Counter(total=0, pass_q_sel=0, selected=0, invalid=0)
    seen: set[str] = set()
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        missing = sorted(set(feature_columns + ["weight_8ab"]) - set(reader.fieldnames))
        if missing:
            raise ValueError(f"{role} CSV missing columns: {missing}")
        if q_sel_threshold is not None and "q_sel" not in reader.fieldnames:
            raise ValueError(f"{role} CSV missing q_sel required by selection")
        for row in reader:
            counts["total"] += 1
            identity = stable_identity(row, role)
            # NECESSITY: duplicated events would leak exact copies into training statistics.
            if identity in seen:
                raise ValueError(f"duplicate event identity {identity}")
            seen.add(identity)
            try:
                q_sel = (
                    finite_value(row, "q_sel")
                    if q_sel_threshold is not None or row.get("q_sel", "") != ""
                    else math.nan
                )
                if q_sel_threshold is not None and not strict_q_sel_pass(q_sel, q_sel_threshold):
                    continue
                counts["pass_q_sel"] += 1
                template_weight = finite_value(row, "weight_8ab")
                features = {column: finite_value(row, column) for column in feature_columns}
            except (KeyError, TypeError, ValueError):
                counts["invalid"] += 1
                continue
            if role == "cpv":
                training_weight = cpv_training_weight(template_weight, cpv_policy)
            else:
                # NECESSITY: a signed SM/background yield is not a valid likelihood denominator.
                training_weight = ordinary_training_weight(template_weight, ordinary_policy)
            if not math.isfinite(training_weight) or training_weight < 0.0:
                raise ValueError("training weight must be finite and nonnegative")
            split_group = row.get("split_group") or row.get("chunk") or identity
            split = row.get("split") or deterministic_split(str(split_group), split_seed)
            if split not in {"train", "validation", "test"}:
                raise ValueError(f"unexpected split {split!r}")
            output.append(
                {
                    "event_id": identity,
                    "class_label": role,
                    "class_index": CLASS_ORDER.index(role),
                    "split_group": split_group,
                    "split": split,
                    "process": row.get("process", role),
                    "helicity": row.get("helicity", ""),
                    "category": row.get("category", ""),
                    "lepton_flavor": row.get("lepton_flavor", ""),
                    "q_sel": q_sel,
                    "training_weight": training_weight,
                    "template_weight": template_weight,
                    **features,
                }
            )
            counts["selected"] += 1
    if not output:
        raise ValueError(f"no valid {role} rows in {path}")
    return output, dict(counts)


def write_rows(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    materialized = list(rows)
    if not materialized:
        raise ValueError("refusing to write empty multiclass table")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(materialized[0]))
        writer.writeheader()
        writer.writerows(materialized)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    result.add_argument("--background-csv", type=Path)
    result.add_argument("--sm-csv", type=Path)
    result.add_argument("--cpv-csv", type=Path)
    result.add_argument("--feature-column", action="append", required=True)
    result.add_argument("--q-sel-threshold", type=float)
    result.add_argument("--background-q-sel-floor", type=float)
    result.add_argument(
        "--cpv-training-weight-policy",
        required=True,
        choices=("unit", "abs_template"),
    )
    result.add_argument(
        "--ordinary-training-weight-policy",
        choices=("unit", "template"),
        default="unit",
    )
    result.add_argument("--split-seed", type=int, default=20260907)
    result.add_argument("--allow-test-only-v0", action="store_true")
    result.add_argument("--output", type=Path, required=True)
    return result


def main(argv: Optional[list[str]] = None) -> int:
    args = parser().parse_args(argv)
    config = load_yaml(args.config)
    dataset = config["event_csv_v0"]
    overrides = (args.background_csv, args.sm_csv, args.cpv_csv)
    # NECESSITY: mixing one replacement table with two v0 tables breaks dataset provenance.
    if any(overrides) and not all(overrides):
        raise SystemExit("override --background-csv, --sm-csv, and --cpv-csv together")
    using_defaults = not any(overrides)
    # NECESSITY: the bundled signal rows are a held-out test split, not training material.
    if using_defaults and not args.allow_test_only_v0:
        raise SystemExit(
            "the bundled v0 signal files are test-only; pass full training CSVs or "
            "use --allow-test-only-v0 for a schema smoke test"
        )
    background = choose_path(args.background_csv, dataset["background"])
    sm = choose_path(args.sm_csv, dataset["sm"])
    cpv = choose_path(args.cpv_csv, dataset["cpv"])
    threshold = (
        float(dataset["q_sel"]["default_threshold"])
        if using_defaults and args.q_sel_threshold is None
        else args.q_sel_threshold
    )
    if threshold is not None and not math.isfinite(threshold):
        raise SystemExit("--q-sel-threshold must be finite")
    floor = args.background_q_sel_floor
    if floor is None and using_defaults:
        floor = float(dataset["q_sel"]["background_coverage_floor"])
    # NECESSITY: a lower cut needs background events absent from the truncated v0 CSV.
    if threshold is not None and floor is not None and threshold < floor:
        raise SystemExit(
            f"q_sel>{threshold} is below background coverage floor {floor}"
        )

    all_rows: list[dict[str, Any]] = []
    accounting: dict[str, dict[str, int]] = {}
    paths = {"background": background, "sm": sm, "cpv": cpv}
    for role in CLASS_ORDER:
        rows, counts = read_role(
            paths[role],
            role,
            args.feature_column,
            threshold,
            args.split_seed,
            args.cpv_training_weight_policy,
            args.ordinary_training_weight_policy,
        )
        all_rows.extend(rows)
        accounting[role] = counts
    identities = [row["event_id"] for row in all_rows]
    if len(identities) != len(set(identities)):
        raise SystemExit("cross-class event identity collision")
    write_rows(args.output, all_rows)

    split_counts = Counter((row["class_label"], row["split"]) for row in all_rows)
    manifest = {
        "status": "analysis-development multiclass table; no model trained",
        "class_order": list(CLASS_ORDER),
        "feature_columns": args.feature_column,
        "selection": None if threshold is None else f"q_sel > {threshold}",
        "background_q_sel_floor": floor,
        "training_weights": {
            "cpv": args.cpv_training_weight_policy,
            "sm_background": args.ordinary_training_weight_policy,
            "signed_interference_used_for_loss": False,
        },
        "split_seed": args.split_seed,
        "accounting": accounting,
        "split_counts": {
            f"{label}:{split}": count
            for (label, split), count in sorted(split_counts.items())
        },
        "inputs": {role: file_record(path) for role, path in paths.items()},
        "output": file_record(args.output),
        "config": file_record(args.config),
        "git": git_state(REPO_ROOT),
        "runtime": runtime_state(("PyYAML",)),
    }
    manifest_path = args.output.with_suffix(args.output.suffix + ".manifest.json")
    atomic_write_json(manifest_path, manifest)
    print(json.dumps({"output": str(args.output), "rows": len(all_rows)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
