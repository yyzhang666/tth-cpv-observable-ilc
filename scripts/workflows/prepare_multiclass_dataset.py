#!/usr/bin/env python3
"""Build a CP-aware three-class table for observable training.

Targets are ``-1=CPV-``, ``0=neutral``, ``+1=CPV+``.  With ``neutral=sm``
background is retained for scoring/Fisher but excluded from training.  With
``neutral=sm-plus-background`` it joins SM in the neutral training class.
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

from ilc_tth_cpv.event_workflow import (  # noqa: E402
    event_key,
    finite_value,
    strict_q_sel_pass,
)
from ilc_tth_cpv.io import load_analysis_config, load_yaml  # noqa: E402
from ilc_tth_cpv.ml_features import (  # noqa: E402
    feature_columns_from_config,
    resolve_feature_value,
)
from ilc_tth_cpv.provenance import (  # noqa: E402
    atomic_write_json,
    file_record,
    git_state,
    runtime_state,
)

CLASS_ORDER = (-1, 0, 1)
CLASS_NAMES = {-1: "cpv_negative", 0: "neutral", 1: "cpv_positive"}
ROLES = ("background", "sm", "cpv")
FLAVORS = ("electron", "muon")
DEFAULT_CONFIG = REPO_ROOT / "configs/workflows/observable_research_v1.yaml"


def deterministic_split(group: str, seed: int) -> str:
    digest = hashlib.sha256(f"{seed}:{group}".encode()).digest()
    value = int.from_bytes(digest[:8], "big") / float(1 << 64)
    return "train" if value < 0.70 else "validation" if value < 0.85 else "test"


def source_identity(row: dict[str, str], role: str) -> str:
    return ":".join(event_key(row, role))


def stable_identity(row: dict[str, str], role: str) -> str:
    # NECESSITY: role prefixes prevent equal source IDs from colliding across samples.
    return f"{role}:{source_identity(row, role)}"


def split_group(row: dict[str, str]) -> str:
    # NECESSITY: event-wise splitting can divide correlated rows from one production job.
    group = row.get("split_group") or row.get("job_key") or row.get("chunk")
    if not group:
        raise ValueError("missing split_group, job_key, or chunk")
    return str(group)


def resolved_split(
    row: dict[str, str], group: str, seed: int, fallback_split: Optional[str] = None
) -> str:
    value = row.get("split") or fallback_split or deterministic_split(group, seed)
    if value not in {"train", "validation", "test"}:
        raise ValueError(f"unexpected split {value!r}")
    return value


def cpv_target(row: dict[str, str], template_weight: float) -> int:
    # NECESSITY: zero interference has no CP sign and cannot define a target class.
    if not math.isfinite(template_weight) or template_weight == 0.0:
        raise ValueError("CPV template_weight must be finite and nonzero")
    target = 1 if template_weight > 0.0 else -1
    if row.get("label", "") != "":
        try:
            supplied = int(float(row["label"]))
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid CPV label") from exc
        if supplied != target:
            raise ValueError(
                f"CPV label/sign mismatch: label={supplied}, weight={template_weight}"
            )
    return target


def base_training_weight(role: str, template_weight: float, policy: str) -> float:
    if role == "cpv":
        value = 1.0 if policy == "unit" else abs(template_weight)
    else:
        if template_weight < 0.0:
            raise ValueError(f"{role} template_weight must be nonnegative")
        value = 1.0 if policy == "unit" else template_weight
    if not math.isfinite(value) or value < 0.0:
        raise ValueError(f"invalid {role} base_training_weight {value}")
    return value


def choose_path(override: Optional[Path], configured: str) -> Path:
    path = override if override is not None else Path(configured)
    return path if path.is_absolute() else REPO_ROOT / path


def feature_columns(args: argparse.Namespace) -> list[str]:
    if args.feature_column and (args.analysis_config or args.feature_set):
        raise SystemExit(
            "use --feature-column or --analysis-config/--feature-set, not both"
        )
    if args.feature_column:
        return list(dict.fromkeys(args.feature_column))
    if not (args.analysis_config and args.feature_set):
        raise SystemExit(
            "provide --feature-column or both --analysis-config and --feature-set"
        )
    try:
        return feature_columns_from_config(
            load_analysis_config(args.analysis_config), args.feature_set
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc


def parse_test_weight_scale(specification: str) -> tuple[tuple[str, str], float]:
    try:
        key, raw_factor = specification.split("=", 1)
        role, flavor = key.split(":", 1)
        factor = float(raw_factor)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "test-weight scale must be ROLE:FLAVOR=FACTOR"
        ) from exc
    if role not in ROLES or flavor not in FLAVORS:
        raise ValueError(f"invalid test-weight scale key {key!r}")
    if not math.isfinite(factor) or factor <= 0.0:
        raise ValueError(f"invalid test-weight scale factor {raw_factor!r}")
    return (role, flavor), factor


def projection_contract(
    args: argparse.Namespace, using_defaults: bool
) -> tuple[dict[tuple[str, str], float], str]:
    expected = {(role, flavor) for role in ROLES for flavor in FLAVORS}
    if using_defaults:
        if args.test_weights_already_8ab or args.test_weight_scale:
            raise SystemExit("v0 test-weight projection is fixed by the workflow config")
        return {key: 1.0 for key in expected}, "v0-already-projected-to-8ab"
    if args.test_weights_already_8ab and args.test_weight_scale:
        raise SystemExit(
            "choose --test-weights-already-8ab or explicit --test-weight-scale values"
        )
    if args.test_weights_already_8ab:
        return {key: 1.0 for key in expected}, "caller-asserted-already-projected-to-8ab"
    if not args.test_weight_scale:
        raise SystemExit(
            "explicit input CSVs require --test-weights-already-8ab or six "
            "--test-weight-scale ROLE:FLAVOR=FACTOR values"
        )
    scales: dict[tuple[str, str], float] = {}
    try:
        for specification in args.test_weight_scale:
            key, factor = parse_test_weight_scale(specification)
            if key in scales:
                raise ValueError(f"duplicate test-weight scale for {key}")
            scales[key] = factor
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    missing = sorted(expected - set(scales))
    extra = sorted(set(scales) - expected)
    if missing or extra:
        raise SystemExit(f"test-weight scales missing={missing}, extra={extra}")
    return scales, "explicit-per-role-flavor-test-projection-to-8ab"


def read_role(
    path: Path,
    role: str,
    columns: list[str],
    threshold: float,
    seed: int,
    neutral_class: str,
    cpv_weight_policy: str,
    ordinary_weight_policy: str,
    fallback_split: Optional[str] = None,
    test_weight_scales: Optional[dict[tuple[str, str], float]] = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    counts = Counter(total=0, pass_q_sel=0, selected=0, invalid_features=0)
    seen: set[str] = set()
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        for row in reader:
            counts["total"] += 1
            identity = stable_identity(row, role)
            if identity in seen:
                raise ValueError(f"duplicate {role} event {identity}")
            seen.add(identity)
            try:
                q_sel = finite_value(row, "q_sel")
            except ValueError as exc:
                raise ValueError(f"invalid {role} q_sel in {path}") from exc
            if not strict_q_sel_pass(q_sel, threshold):
                continue
            counts["pass_q_sel"] += 1
            try:
                source_template_weight = finite_value(row, "weight_8ab")
            except ValueError as exc:
                raise ValueError(f"invalid {role} weight_8ab in {path}") from exc
            if role != "cpv" and source_template_weight < 0.0:
                raise ValueError(f"negative {role} weight_8ab in {path}")
            values = {column: resolve_feature_value(row, column) for column in columns}
            if not all(math.isfinite(value) for value in values.values()):
                counts["invalid_features"] += 1
                continue
            group = split_group(row)
            split = resolved_split(row, group, seed, fallback_split)
            flavor = row.get("lepton_flavor", "")
            if flavor not in {"electron", "muon"}:
                raise ValueError(
                    f"unexpected lepton_flavor {flavor!r} for {identity}"
                )
            projection_factor = (
                (test_weight_scales or {}).get((role, flavor), 1.0)
                if split == "test"
                else 1.0
            )
            template_weight = source_template_weight * projection_factor
            if role == "cpv":
                target: Any = cpv_target(row, template_weight)
                include, policy = 1, cpv_weight_policy
            elif role == "sm":
                target, include, policy = 0, 1, ordinary_weight_policy
            else:
                include = int(neutral_class == "sm-plus-background")
                target = 0 if include else ""
                policy = ordinary_weight_policy
            rows.append(
                {
                    "event_id": identity,
                    "source_role": role,
                    "source_identity": source_identity(row, role),
                    "split_group": group,
                    "split": split,
                    "process": row.get("process") or row.get("sample_key") or role,
                    "lepton_flavor": flavor,
                    "q_sel": q_sel,
                    "target_label": target,
                    "target_name": CLASS_NAMES.get(target, "inference_only"),
                    "training_include": include,
                    "base_training_weight": base_training_weight(
                        role, template_weight, policy
                    ),
                    "source_template_weight": source_template_weight,
                    "test_weight_scale": projection_factor,
                    "template_weight": template_weight,
                    **values,
                }
            )
            counts["selected"] += 1
    if not rows:
        raise ValueError(f"no valid {role} rows in {path}")
    return rows, dict(counts)


def validate_groups(rows: list[dict[str, Any]]) -> None:
    assignments: dict[str, str] = {}
    for row in rows:
        group, split = str(row["split_group"]), str(row["split"])
        previous = assignments.setdefault(group, split)
        if previous != split:
            raise ValueError(f"split group {group!r} appears in {previous} and {split}")


def split_class_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(
        (str(row["lepton_flavor"]), str(row["split"]), int(row["target_label"]))
        for row in rows
        if row["training_include"]
    )
    return {
        f"{flavor}:{split}:{label}": count
        for (flavor, split, label), count in sorted(counts.items())
    }


def formal_training_allowed(
    rows: list[dict[str, Any]], neutral_class: str
) -> tuple[bool, list[str]]:
    available: Counter[tuple[str, str, int]] = Counter()
    for row in rows:
        if row["training_include"]:
            key = (
                str(row["lepton_flavor"]),
                str(row["split"]),
                int(row["target_label"]),
            )
            available[key] += float(row["base_training_weight"])
    missing = [
        f"{flavor}:{split}:{label}"
        for flavor in FLAVORS
        for split in ("train", "validation", "test")
        for label in CLASS_ORDER
        if available[(flavor, split, label)] <= 0.0
    ]
    background_required_splits = (
        ("train", "validation", "test")
        if neutral_class == "sm-plus-background"
        else ("test",)
    )
    for flavor in FLAVORS:
        for split in ("train", "validation", "test"):
            sm_total = sum(
                float(row["template_weight"])
                for row in rows
                if row["source_role"] == "sm"
                and row["lepton_flavor"] == flavor
                and row["split"] == split
            )
            if sm_total <= 0.0:
                missing.append(f"sm:{flavor}:{split}:positive_weight")
        for split in background_required_splits:
            background_total = sum(
                float(row["template_weight"])
                for row in rows
                if row["source_role"] == "background"
                and row["lepton_flavor"] == flavor
                and row["split"] == split
            )
            if background_total <= 0.0:
                missing.append(f"background:{flavor}:{split}:positive_weight")
    return not missing, missing


def write_rows(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    materialized = list(rows)
    if not materialized:
        raise ValueError("refusing to write empty table")
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
    result.add_argument(
        "--neutral-class", required=True, choices=("sm", "sm-plus-background")
    )
    result.add_argument("--feature-column", action="append")
    result.add_argument("--analysis-config", type=Path)
    result.add_argument("--feature-set")
    result.add_argument("--q-sel-threshold", type=float)
    result.add_argument("--background-q-sel-floor", type=float)
    result.add_argument(
        "--cpv-training-weight-policy",
        choices=("abs_template", "unit"),
        default="abs_template",
    )
    result.add_argument(
        "--ordinary-training-weight-policy",
        choices=("template", "unit"),
        default="template",
    )
    result.add_argument("--split-seed", type=int, default=20260907)
    result.add_argument("--test-weights-already-8ab", action="store_true")
    result.add_argument(
        "--test-weight-scale",
        action="append",
        metavar="ROLE:FLAVOR=FACTOR",
        help="explicit test-only projection; repeat for all 3 roles x 2 flavors",
    )
    result.add_argument("--allow-test-only-v0", action="store_true")
    result.add_argument("--output", type=Path, required=True)
    return result


def main(argv: Optional[list[str]] = None) -> int:
    args = parser().parse_args(argv)
    config = load_yaml(args.config)
    dataset = config["event_csv_v0"]
    overrides = (args.background_csv, args.sm_csv, args.cpv_csv)
    if any(overrides) and not all(overrides):
        raise SystemExit("override all three input CSVs together")
    using_defaults = not any(overrides)
    if using_defaults and not args.allow_test_only_v0:
        raise SystemExit("v0 signal files are test-only; explicit schema smoke only")
    paths = {
        "background": choose_path(args.background_csv, dataset["background"]),
        "sm": choose_path(args.sm_csv, dataset["sm"]),
        "cpv": choose_path(args.cpv_csv, dataset["cpv"]),
    }
    threshold = (
        float(dataset["q_sel"]["default_threshold"])
        if args.q_sel_threshold is None
        else args.q_sel_threshold
    )
    floor = (
        float(dataset["q_sel"]["background_coverage_floor"])
        if args.background_q_sel_floor is None and using_defaults
        else args.background_q_sel_floor
    )
    if not math.isfinite(threshold):
        raise SystemExit("--q-sel-threshold must be finite")
    if floor is not None and threshold < floor:
        raise SystemExit(f"q_sel>{threshold} is below background coverage floor {floor}")
    columns = feature_columns(args)
    test_weight_scales, projection_status = projection_contract(args, using_defaults)

    all_rows: list[dict[str, Any]] = []
    accounting: dict[str, dict[str, int]] = {}
    for role in ROLES:
        rows, counts = read_role(
            paths[role],
            role,
            columns,
            threshold,
            args.split_seed,
            args.neutral_class,
            args.cpv_training_weight_policy,
            args.ordinary_training_weight_policy,
            str(dataset["default_split"]) if using_defaults else None,
            test_weight_scales,
        )
        all_rows.extend(rows)
        accounting[role] = counts
    validate_groups(all_rows)
    allowed, missing = formal_training_allowed(all_rows, args.neutral_class)
    if using_defaults and allowed:
        raise SystemExit("internal error: v0 test-only inputs unexpectedly look trainable")
    write_rows(args.output, all_rows)

    manifest = {
        "status": "formal-candidate" if allowed else "schema-smoke-not-trainable",
        "formal_training_allowed": allowed,
        "missing_training_cells": missing,
        "neutral_class": args.neutral_class,
        "class_order": [
            {"target": label, "name": CLASS_NAMES[label]} for label in CLASS_ORDER
        ],
        "observable_definition": "q_threeclass = P(+1) - P(-1)",
        "feature_columns": columns,
        "selection": f"q_sel > {threshold}",
        "q_sel_threshold": threshold,
        "background_q_sel_floor": floor,
        "training_weights": {
            "cpv": args.cpv_training_weight_policy,
            "sm_background": args.ordinary_training_weight_policy,
            "signed_interference_used_for_loss": False,
            "class_balancing": "performed from train split by trainer",
        },
        "test_weight_projection": {
            "status": projection_status,
            "target_exposure_fb": 8000,
            "scales": {
                f"{role}:{flavor}": test_weight_scales[(role, flavor)]
                for role in ROLES
                for flavor in FLAVORS
            },
            "source_column": "source_template_weight",
            "projected_column": "template_weight",
        },
        "split_seed": args.split_seed,
        "split_policy": (
            f"dataset default {dataset['default_split']}"
            if using_defaults
            else "preserve row split, otherwise hash split_group/job/chunk"
        ),
        "accounting": accounting,
        "split_class_counts": split_class_counts(all_rows),
        "inputs": {role: file_record(path) for role, path in paths.items()},
        "output": file_record(args.output),
        "config": file_record(args.config),
        "git": git_state(REPO_ROOT),
        "runtime": runtime_state(("PyYAML",)),
    }
    atomic_write_json(
        args.output.with_suffix(args.output.suffix + ".manifest.json"), manifest
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "rows": len(all_rows),
                "formal_training_allowed": allowed,
                "missing_training_cells": missing,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
