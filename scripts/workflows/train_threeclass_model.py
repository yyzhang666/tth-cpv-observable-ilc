#!/usr/bin/env python3
"""Train per-flavor CP-aware three-class CatBoost models and score test events."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Optional

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ilc_tth_cpv.provenance import (  # noqa: E402
    atomic_write_json,
    file_record,
    git_state,
    runtime_state,
    sha256_file,
)

CLASS_ORDER = (-1, 0, 1)
FLAVORS = ("electron", "muon")
SCORE_COLUMN = "q_threeclass"


def parse_include(value: object) -> bool:
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes"}:
        return True
    if normalized in {"0", "false", "no"}:
        return False
    raise ValueError(f"invalid training_include {value!r}")


def read_table(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        rows = list(reader)
    if not rows:
        raise ValueError(f"empty dataset: {path}")
    return rows


def finite(row: dict[str, str], column: str) -> float:
    try:
        value = float(row[column])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid {column!r} for {row.get('event_id', '?')}") from exc
    if not math.isfinite(value):
        raise ValueError(f"non-finite {column!r} for {row.get('event_id', '?')}")
    return value


def target(row: dict[str, str]) -> int:
    try:
        value = int(row["target_label"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid target for {row.get('event_id', '?')}") from exc
    if value not in CLASS_ORDER:
        raise ValueError(f"unexpected target {value}")
    return value


def validate_contract(
    rows: list[dict[str, str]],
    neutral_class: str,
    q_sel_threshold: float,
    test_weight_scales: dict[tuple[str, str], float],
) -> None:
    seen: set[str] = set()
    for row in rows:
        event_id = row.get("event_id", "")
        if not event_id or event_id in seen:
            raise ValueError(f"missing or duplicate event_id {event_id!r}")
        seen.add(event_id)
        role = row.get("source_role")
        include = parse_include(row.get("training_include"))
        template_weight = finite(row, "template_weight")
        source_template_weight = finite(row, "source_template_weight")
        row_scale = finite(row, "test_weight_scale")
        base_weight = finite(row, "base_training_weight")
        if base_weight < 0.0:
            raise ValueError(f"negative base_training_weight for {event_id}")
        if finite(row, "q_sel") <= q_sel_threshold:
            raise ValueError(f"{event_id} violates strict q_sel>{q_sel_threshold}")
        if row.get("lepton_flavor") not in FLAVORS:
            raise ValueError(f"invalid lepton_flavor for {event_id}")
        if row.get("split") not in {"train", "validation", "test"}:
            raise ValueError(f"invalid split for {event_id}")
        expected_scale = (
            test_weight_scales[(str(role), str(row["lepton_flavor"]))]
            if row["split"] == "test"
            else 1.0
        )
        if not math.isclose(row_scale, expected_scale, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError(f"invalid test projection scale for {event_id}")
        if not math.isclose(
            template_weight,
            source_template_weight * expected_scale,
            rel_tol=1e-12,
            abs_tol=1e-15,
        ):
            raise ValueError(f"invalid projected template_weight for {event_id}")
        if role == "cpv":
            label = target(row)
            expected_label = 1 if template_weight > 0.0 else -1
            if (
                not include
                or base_weight <= 0.0
                or template_weight == 0.0
                or label != expected_label
            ):
                raise ValueError(f"invalid CPV target/weight contract for {event_id}")
        elif role == "sm":
            if not include or target(row) != 0 or template_weight < 0.0:
                raise ValueError(f"invalid SM neutral contract for {event_id}")
        elif role == "background":
            if template_weight < 0.0:
                raise ValueError(f"negative background template_weight for {event_id}")
            expected_include = neutral_class == "sm-plus-background"
            if include != expected_include:
                raise ValueError(f"invalid background inclusion for {event_id}")
            if include and target(row) != 0:
                raise ValueError(f"invalid background neutral target for {event_id}")
            if not include and row.get("target_label", "") != "":
                raise ValueError(f"inference-only background has a target for {event_id}")
        else:
            raise ValueError(f"unexpected source_role {role!r} for {event_id}")


def class_scales(rows: list[dict[str, str]], flavor: str) -> dict[int, float]:
    totals = Counter({label: 0.0 for label in CLASS_ORDER})
    for row in rows:
        if (
            row.get("lepton_flavor") == flavor
            and row.get("split") == "train"
            and parse_include(row.get("training_include"))
        ):
            weight = finite(row, "base_training_weight")
            if weight < 0.0:
                raise ValueError("base_training_weight must be nonnegative")
            totals[target(row)] += weight
    missing = [label for label in CLASS_ORDER if totals[label] <= 0.0]
    if missing:
        raise ValueError(f"{flavor} train split missing class weights for {missing}")
    # NECESSITY: equal class totals prevent the physical neutral yield from erasing CP signs.
    return {label: 1.0 / totals[label] for label in CLASS_ORDER}


def training_rows(
    rows: list[dict[str, str]], flavor: str, split: str
) -> list[dict[str, str]]:
    selected = [
        row
        for row in rows
        if row.get("lepton_flavor") == flavor
        and row.get("split") == split
        and parse_include(row.get("training_include"))
    ]
    labels = {target(row) for row in selected}
    if labels != set(CLASS_ORDER):
        raise ValueError(
            f"{flavor} {split} classes are {sorted(labels)}, expected {CLASS_ORDER}"
        )
    return selected


def arrays(
    rows: list[dict[str, str]],
    columns: list[str],
    scales: dict[int, float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x = np.asarray([[finite(row, column) for column in columns] for row in rows])
    y = np.asarray([target(row) for row in rows], dtype=np.int64)
    weights = np.asarray(
        [finite(row, "base_training_weight") * scales[target(row)] for row in rows]
    )
    return x, y, weights


def threeclass_score(probabilities: Iterable[float], classes: Iterable[int]) -> float:
    mapping = {int(label): float(value) for label, value in zip(classes, probabilities)}
    if set(mapping) != set(CLASS_ORDER):
        raise ValueError(f"model classes are {sorted(mapping)}, expected {CLASS_ORDER}")
    if not math.isclose(sum(mapping.values()), 1.0, rel_tol=0.0, abs_tol=1e-7):
        raise ValueError("class probabilities do not sum to one")
    score = mapping[1] - mapping[-1]
    if not -1.0000001 <= score <= 1.0000001:
        raise ValueError(f"three-class score outside [-1,1]: {score}")
    return score


def weighted_metrics(
    model: Any,
    rows: list[dict[str, str]],
    columns: list[str],
    scales: dict[int, float],
) -> dict[str, float]:
    x, y, weights = arrays(rows, columns, scales)
    probabilities = np.asarray(model.predict_proba(x), dtype=np.float64)
    classes = [int(value) for value in model.classes_]
    indices = {label: index for index, label in enumerate(classes)}
    predictions = np.asarray([classes[index] for index in probabilities.argmax(axis=1)])
    accuracy = float(np.average(predictions == y, weights=weights))
    chosen = np.asarray(
        [
            probabilities[index, indices[int(label)]]
            for index, label in enumerate(y)
        ]
    )
    logloss = float(np.average(-np.log(np.clip(chosen, 1e-15, 1.0)), weights=weights))
    return {"weighted_accuracy": accuracy, "weighted_multiclass_logloss": logloss}


def prediction_row(
    row: dict[str, str], probabilities: Iterable[float], classes: Iterable[int]
) -> dict[str, Any]:
    class_values = list(classes)
    probability_values = list(probabilities)
    mapping = {
        int(label): float(value)
        for label, value in zip(class_values, probability_values)
    }
    score = threeclass_score(probability_values, class_values)
    return {
        "event_id": row["event_id"],
        "source_role": row["source_role"],
        "source_identity": row["source_identity"],
        "split_group": row["split_group"],
        "split": row["split"],
        "process": row["process"],
        "lepton_flavor": row["lepton_flavor"],
        "q_sel": finite(row, "q_sel"),
        "target_label": row["target_label"],
        "training_include": row["training_include"],
        "source_template_weight": finite(row, "source_template_weight"),
        "test_weight_scale": finite(row, "test_weight_scale"),
        "weight_8ab": finite(row, "template_weight"),
        "p_minus": mapping[-1],
        "p_neutral": mapping[0],
        "p_plus": mapping[1],
        SCORE_COLUMN: score,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"refusing empty output {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot_history(path: Path, history: dict[str, list[float]], flavor: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axis = plt.subplots(figsize=(7.2, 4.6))
    axis.plot(history["train"], label="train")
    axis.plot(history["validation"], label="validation")
    axis.set_xlabel("boosting iteration")
    axis.set_ylabel("MultiClass loss")
    axis.set_title(f"Three-class training — {flavor}")
    axis.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--dataset", type=Path, required=True)
    result.add_argument("--out-dir", type=Path, required=True)
    result.add_argument("--iterations", type=int, default=1000)
    result.add_argument("--depth", type=int, default=7)
    result.add_argument("--learning-rate", type=float, default=0.05)
    result.add_argument("--random-seed", type=int, default=20260720)
    result.add_argument("--thread-count", type=int, default=1)
    result.add_argument("--plot", action="store_true")
    return result


def main(argv: Optional[list[str]] = None) -> int:
    args = parser().parse_args(argv)
    manifest_path = args.dataset.with_suffix(args.dataset.suffix + ".manifest.json")
    manifest = json.loads(manifest_path.read_text())
    if not manifest.get("formal_training_allowed"):
        raise SystemExit(
            "dataset is not formal-training-ready: "
            + ", ".join(manifest.get("missing_training_cells", []))
        )
    if manifest.get("class_order") != [
        {"target": label, "name": name}
        for label, name in ((-1, "cpv_negative"), (0, "neutral"), (1, "cpv_positive"))
    ]:
        raise SystemExit("dataset manifest has unexpected class order")
    expected_hash = manifest.get("output", {}).get("sha256")
    if expected_hash != sha256_file(args.dataset):
        raise SystemExit("dataset content does not match its manifest SHA-256")
    if manifest.get("neutral_class") not in {"sm", "sm-plus-background"}:
        raise SystemExit("dataset manifest has unexpected neutral_class")
    projection = manifest.get("test_weight_projection", {})
    try:
        target_exposure_fb = float(projection.get("target_exposure_fb", math.nan))
    except (AttributeError, TypeError, ValueError) as exc:
        raise SystemExit("invalid test projection exposure in dataset manifest") from exc
    if (
        projection.get("status")
        not in {
            "v0-already-projected-to-8ab",
            "caller-asserted-already-projected-to-8ab",
            "explicit-per-role-flavor-test-projection-to-8ab",
        }
        or target_exposure_fb != 8000.0
    ):
        raise SystemExit("dataset manifest lacks a valid 8 ab-1 test projection")
    try:
        projection_scales = {
            tuple(key.split(":")): float(value)
            for key, value in projection["scales"].items()
        }
    except (AttributeError, TypeError, ValueError) as exc:
        raise SystemExit("invalid test projection scales in dataset manifest") from exc
    expected_scale_keys = {
        (role, flavor)
        for role in ("background", "sm", "cpv")
        for flavor in FLAVORS
    }
    if set(projection_scales) != expected_scale_keys or any(
        not math.isfinite(value) or value <= 0.0
        for value in projection_scales.values()
    ):
        raise SystemExit("test projection scales are incomplete or invalid")
    columns = list(manifest["feature_columns"])
    rows = read_table(args.dataset)
    try:
        q_sel_threshold = float(manifest["q_sel_threshold"])
        if not math.isfinite(q_sel_threshold):
            raise ValueError("non-finite q_sel_threshold")
        validate_contract(
            rows,
            str(manifest["neutral_class"]),
            q_sel_threshold,
            projection_scales,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise SystemExit(f"invalid three-class dataset: {exc}") from exc
    args.out_dir.mkdir(parents=True, exist_ok=True)

    try:
        from catboost import CatBoostClassifier, Pool
    except ImportError as exc:
        raise SystemExit("CatBoost is required; source the ZHH environment") from exc

    scored: list[dict[str, Any]] = []
    model_records: dict[str, Any] = {}
    for flavor in FLAVORS:
        scales = class_scales(rows, flavor)
        train = training_rows(rows, flavor, "train")
        validation = training_rows(rows, flavor, "validation")
        test_training = training_rows(rows, flavor, "test")
        x_train, y_train, w_train = arrays(train, columns, scales)
        x_validation, y_validation, w_validation = arrays(validation, columns, scales)
        model = CatBoostClassifier(
            loss_function="MultiClass",
            eval_metric="MultiClass",
            iterations=args.iterations,
            depth=args.depth,
            learning_rate=args.learning_rate,
            random_seed=args.random_seed,
            thread_count=args.thread_count,
            allow_writing_files=False,
            use_best_model=True,
            verbose=max(1, min(100, args.iterations)),
        )
        model.fit(
            Pool(x_train, y_train, weight=w_train, feature_names=columns),
            eval_set=Pool(
                x_validation,
                y_validation,
                weight=w_validation,
                feature_names=columns,
            ),
        )
        classes = [int(value) for value in model.classes_]
        if set(classes) != set(CLASS_ORDER):
            raise ValueError(f"CatBoost classes {classes} != {CLASS_ORDER}")
        flavor_dir = args.out_dir / flavor
        flavor_dir.mkdir(parents=True, exist_ok=True)
        model_path = flavor_dir / "threeclass_catboost.cbm"
        model.save_model(str(model_path))
        evaluations = model.get_evals_result()
        history = {
            "train": evaluations["learn"]["MultiClass"],
            "validation": evaluations["validation"]["MultiClass"],
        }
        history_path = flavor_dir / "training_history.json"
        atomic_write_json(history_path, history)
        plot_path: Optional[Path] = None
        if args.plot:
            plot_path = flavor_dir / "training_history.png"
            plot_history(plot_path, history, flavor)

        metrics = {
            split: weighted_metrics(model, subset, columns, scales)
            for split, subset in (
                ("train", train),
                ("validation", validation),
                ("test", test_training),
            )
        }
        inference = [
            row
            for row in rows
            if row.get("lepton_flavor") == flavor and row.get("split") == "test"
        ]
        x_inference = np.asarray(
            [[finite(row, column) for column in columns] for row in inference]
        )
        probabilities = model.predict_proba(x_inference)
        scored.extend(
            prediction_row(row, probability, classes)
            for row, probability in zip(inference, probabilities)
        )
        metadata = {
            "lepton_flavor": flavor,
            "neutral_class": manifest["neutral_class"],
            "class_order": classes,
            "feature_columns": columns,
            "class_scales_from_train": {str(key): value for key, value in scales.items()},
            "metrics": metrics,
            "counts": {
                "train": len(train),
                "validation": len(validation),
                "test_training": len(test_training),
                "test_scored_all_roles": len(inference),
            },
            "model": file_record(model_path),
            "dataset": file_record(args.dataset),
            "dataset_manifest": file_record(manifest_path),
        }
        metadata_path = flavor_dir / "model_metadata.json"
        atomic_write_json(metadata_path, metadata)
        model_records[flavor] = {
            "model": file_record(model_path),
            "metadata": file_record(metadata_path),
            "history": file_record(history_path),
        }
        if plot_path is not None:
            model_records[flavor]["plot"] = file_record(plot_path)

    score_paths: dict[str, Path] = {}
    for role in ("background", "sm", "cpv"):
        role_rows = [row for row in scored if row["source_role"] == role]
        path = args.out_dir / "scores" / f"{role}_scores.csv"
        write_csv(path, role_rows)
        score_paths[role] = path
    output_manifest = {
        "status": "trained CP-aware three-class observable",
        "neutral_class": manifest["neutral_class"],
        "class_order": list(CLASS_ORDER),
        "observable": "q_threeclass = p_plus - p_minus",
        "test_weight_projection": projection,
        "feature_columns": columns,
        "hyperparameters": {
            "iterations": args.iterations,
            "depth": args.depth,
            "learning_rate": args.learning_rate,
            "random_seed": args.random_seed,
            "thread_count": args.thread_count,
        },
        "models": model_records,
        "score_files": {role: file_record(path) for role, path in score_paths.items()},
        "dataset": file_record(args.dataset),
        "dataset_manifest": file_record(manifest_path),
        "git": git_state(REPO_ROOT),
        "runtime": runtime_state(("numpy", "catboost", "matplotlib")),
    }
    atomic_write_json(args.out_dir / "training_manifest.json", output_manifest)
    print(json.dumps({"out_dir": str(args.out_dir), "scored": len(scored)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
