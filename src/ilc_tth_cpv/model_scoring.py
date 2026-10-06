"""Score compact v3 feature tables with fixed electron/muon CatBoost models."""

from __future__ import annotations

import csv
import datetime
import hashlib
import json
import math
import os
import tempfile
from collections import Counter
from pathlib import Path
from typing import Mapping, Sequence

COMPONENTS = ("interference", "sm", "background")
FLAVORS = ("electron", "muon")
CLASS_ORDER = (-1, 1)
WEIGHT_8AB_FACTOR = 8000.0 / (79.0 * 0.2)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _float(value: object) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return float("nan")


def _event_key(row: Mapping[str, object]) -> tuple[str, str, str]:
    return (str(row["sample_name"]), str(row["level"]), str(row["event_id"]))


def _load_catboost_model(path: Path):
    try:
        from catboost import CatBoostClassifier
    except Exception as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(f"Cannot import CatBoost; source the ZHH environment ({exc})") from exc
    model = CatBoostClassifier()
    model.load_model(str(path))
    return model


def _model_paths(model_root: Path, flavor: str, model_tag: str) -> tuple[Path, Path]:
    tag = Path(model_tag)
    if tag.is_absolute() or len(tag.parts) != 1 or model_tag in {"", ".", ".."}:
        raise ValueError("--model-tag must be one relative directory name")
    directory = model_root.resolve() / flavor / model_tag
    return directory / "cpv_catboost.cbm", directory / "model_metadata.json"


def _load_models(model_root: Path, model_tag: str) -> tuple[dict[str, object], list[str], dict]:
    models: dict[str, object] = {}
    feature_list: list[str] | None = None
    provenance: dict[str, dict[str, object]] = {}
    for flavor in FLAVORS:
        model_path, metadata_path = _model_paths(model_root, flavor, model_tag)
        if not model_path.is_file() or not metadata_path.is_file():
            raise FileNotFoundError(f"missing model/metadata pair for {flavor}: {model_path}, {metadata_path}")
        metadata = json.loads(metadata_path.read_text())
        if not isinstance(metadata, dict):
            raise ValueError(f"model metadata must be an object: {metadata_path}")
        features = metadata.get("feature_list")
        if not isinstance(features, list) or not features or not all(isinstance(item, str) for item in features):
            raise ValueError(f"invalid feature_list in {metadata_path}")
        if feature_list is None:
            feature_list = list(features)
        elif features != feature_list:
            raise ValueError("electron and muon model feature_list values differ")
        if metadata.get("class_order_model") != list(CLASS_ORDER):
            raise ValueError(f"class_order_model must be [-1, 1]: {metadata_path}")
        if metadata.get("lepton_flavor") not in (None, flavor):
            raise ValueError(f"model flavor metadata mismatch: {metadata_path}")

        model = _load_catboost_model(model_path)
        classes = [int(value) for value in list(model.classes_)]
        if classes != list(CLASS_ORDER):
            raise ValueError(f"CatBoost classes must be [-1, 1] for {flavor}, got {classes}")
        models[flavor] = model
        provenance[flavor] = {
            "model": str(model_path.resolve()),
            "model_sha256": _sha256(model_path),
            "metadata": str(metadata_path.resolve()),
            "metadata_sha256": _sha256(metadata_path),
            "classes": classes,
        }
    assert feature_list is not None
    return models, feature_list, provenance


def _validate_input_metadata(metadata: Mapping[str, object], input_csv: Path, component: str) -> None:
    if metadata.get("component") != component:
        raise ValueError(
            f"input component {metadata.get('component')!r} does not match requested {component!r}"
        )
    if metadata.get("table") != input_csv.name:
        raise ValueError(f"input metadata table does not match {input_csv.name}")
    columns = metadata.get("columns")
    if not isinstance(columns, list) or not all(isinstance(item, str) for item in columns):
        raise ValueError("input metadata must contain ordered columns")


def _probability_pair(probabilities: Sequence[object]) -> tuple[float, float, float]:
    if len(probabilities) != 2:
        raise ValueError(f"expected two class probabilities, got {len(probabilities)}")
    p_minus, p_plus = (_float(value) for value in probabilities)
    if not all(math.isfinite(value) and 0.0 <= value <= 1.0 for value in (p_minus, p_plus)):
        raise ValueError(f"invalid model probabilities: {p_minus}, {p_plus}")
    if abs((p_minus + p_plus) - 1.0) > 1e-10:
        raise ValueError(f"model probabilities do not sum to one: {p_minus}, {p_plus}")
    score = p_plus - p_minus
    if not -1.0 <= score <= 1.0:
        raise ValueError(f"score outside [-1, 1]: {score}")
    if abs(score - (p_plus - p_minus)) > 1e-12:
        raise ValueError("score differs from p_plus-p_minus")
    return p_plus, p_minus, score


def score_feature_table(
    *,
    input_csv: Path,
    component: str,
    model_root: Path,
    model_tag: str,
    output: Path,
    score_column: str = "q_CPV_wtype_v0",
) -> Path:
    """Filter one feature table to usable test rows and append model scores."""
    if component not in COMPONENTS:
        raise ValueError(f"unsupported component {component!r}")
    if output.suffix != ".csv":
        raise ValueError("--output must have suffix .csv")
    if not score_column or score_column in {"p_plus", "p_minus", "weight_8ab"}:
        raise ValueError("invalid --score-column")
    output = output.resolve()
    output_metadata = output.with_suffix(".meta.json")
    if output.exists() or output_metadata.exists():
        raise FileExistsError(f"refusing existing output pair: {output}, {output_metadata}")

    input_csv = input_csv.resolve()
    input_metadata_path = input_csv.with_suffix(".meta.json")
    if not input_csv.is_file() or not input_metadata_path.is_file():
        raise FileNotFoundError(f"input CSV/metadata pair is required: {input_csv}, {input_metadata_path}")
    input_metadata = json.loads(input_metadata_path.read_text())
    if not isinstance(input_metadata, dict):
        raise ValueError(f"input metadata must be an object: {input_metadata_path}")
    _validate_input_metadata(input_metadata, input_csv, component)
    models, feature_list, model_provenance = _load_models(model_root, model_tag)
    if input_metadata.get("feature_list") != feature_list:
        raise ValueError("input metadata feature_list differs from model feature_list")

    with input_csv.open(newline="") as handle:
        reader = csv.DictReader(handle)
        input_columns = list(reader.fieldnames or ())
        if input_columns != input_metadata["columns"]:
            raise ValueError("input CSV header differs from metadata columns")
        missing_columns = [name for name in ("sample_name", "level", "event_id", "split", "lepton_flavor", *feature_list) if name not in input_columns]
        if missing_columns:
            raise ValueError("input table missing columns: " + ", ".join(missing_columns))
        for name in ("p_plus", "p_minus", score_column):
            if name in input_columns:
                raise ValueError(f"input table already contains output column {name}")

        has_weight_8ab = "weight_8ab" in input_columns
        if component == "background" and not has_weight_8ab:
            raise ValueError("background input requires an existing weight_8ab column")
        if component != "background" and "weight_template" not in input_columns:
            raise ValueError(f"{component} input requires weight_template")

        seen: set[tuple[str, str, str]] = set()
        nonfinite_counts = {name: 0 for name in feature_list}
        dropped_event_keys: list[dict[str, str]] = []
        test_flavor_counts: Counter[str] = Counter()
        scored_flavor_counts: Counter[str] = Counter()
        work: dict[str, list[tuple[int, dict[str, str], list[float], float | str]]] = {
            flavor: [] for flavor in FLAVORS
        }
        n_input_rows = 0
        n_test_rows = 0
        n_skipped_non_test = 0
        for row_index, row in enumerate(reader):
            n_input_rows += 1
            key = _event_key(row)
            if key in seen:
                raise ValueError(f"duplicate event key: {key}")
            seen.add(key)
            if row["split"] != "test":
                n_skipped_non_test += 1
                continue
            n_test_rows += 1
            flavor = row["lepton_flavor"]
            if flavor not in FLAVORS:
                raise ValueError(f"unsupported lepton_flavor {flavor!r} for event {key}")
            test_flavor_counts[flavor] += 1
            values = [_float(row[name]) for name in feature_list]
            bad = [name for name, value in zip(feature_list, values) if not math.isfinite(value)]
            if bad:
                for name in bad:
                    nonfinite_counts[name] += 1
                dropped_event_keys.append({
                    "sample_name": key[0], "level": key[1], "event_id": key[2],
                    "lepton_flavor": flavor, "nonfinite_features": bad,
                })
                continue

            if has_weight_8ab:
                weight_value = _float(row["weight_8ab"])
                if not math.isfinite(weight_value):
                    raise ValueError(f"nonfinite weight_8ab for event {key}")
                if component != "background":
                    expected = _float(row["weight_template"]) * WEIGHT_8AB_FACTOR
                    if not math.isfinite(expected) or not math.isclose(
                        weight_value, expected, rel_tol=1e-12, abs_tol=1e-12
                    ):
                        raise ValueError(f"weight_8ab disagrees with derived value for event {key}")
                output_weight: float | str = row["weight_8ab"]
            else:
                template_weight = _float(row["weight_template"])
                if not math.isfinite(template_weight):
                    raise ValueError(f"nonfinite weight_template for event {key}")
                output_weight = template_weight * WEIGHT_8AB_FACTOR
            work[flavor].append((row_index, row, values, output_weight))

    metadata_rows = input_metadata.get("n_output_rows")
    if isinstance(metadata_rows, int) and not isinstance(metadata_rows, bool) and metadata_rows != n_input_rows:
        raise ValueError(f"input row count {n_input_rows} != metadata n_output_rows {metadata_rows}")
    metadata_test = input_metadata.get("n_test")
    if component == "interference" and isinstance(metadata_test, int) and metadata_test != n_test_rows:
        raise ValueError(f"test row count {n_test_rows} != metadata n_test {metadata_test}")

    scored: list[tuple[int, dict[str, object]]] = []
    for flavor in FLAVORS:
        items = work[flavor]
        if not items:
            continue
        probabilities = list(models[flavor].predict_proba([item[2] for item in items]))
        if len(probabilities) != len(items):
            raise ValueError(f"model returned wrong prediction count for {flavor}")
        for (row_index, row, _values, output_weight), probability in zip(items, probabilities):
            p_plus, p_minus, score = _probability_pair(probability)
            result: dict[str, object] = dict(row)
            result["p_plus"] = p_plus
            result["p_minus"] = p_minus
            result[score_column] = score
            result["weight_8ab"] = output_weight
            scored.append((row_index, result))
            scored_flavor_counts[flavor] += 1
    scored.sort(key=lambda item: item[0])

    output_columns = input_columns + ["p_plus", "p_minus", score_column]
    if not has_weight_8ab:
        output_columns.append("weight_8ab")
    output.parent.mkdir(parents=True, exist_ok=True)
    csv_temp: Path | None = None
    metadata_temp: Path | None = None
    published: list[Path] = []
    try:
        csv_handle = tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=output.parent,
            prefix=f".{output.name}.", suffix=".tmp", delete=False,
        )
        csv_temp = Path(csv_handle.name)
        with csv_handle:
            writer = csv.DictWriter(csv_handle, fieldnames=output_columns, extrasaction="raise")
            writer.writeheader()
            writer.writerows(row for _index, row in scored)
            csv_handle.flush()
            os.fsync(csv_handle.fileno())

        metadata = {
            "schema_version": "scored_feature_table_v3",
            "status": "scored_feature_table_v3",
            "created": datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(),
            "component": component,
            "input": str(input_csv),
            "input_metadata": str(input_metadata_path),
            "input_sha256": _sha256(input_csv),
            "input_metadata_sha256": _sha256(input_metadata_path),
            "model_root": str(model_root.resolve()),
            "model_tag": model_tag,
            "models": model_provenance,
            "feature_list": feature_list,
            "class_order_model": list(CLASS_ORDER),
            "probability_columns": {"p_minus": -1, "p_plus": 1},
            "score_column": score_column,
            "score_definition": "p_plus-p_minus",
            "columns": output_columns,
            "n_columns": len(output_columns),
            "n_input_rows": n_input_rows,
            "n_test_rows": n_test_rows,
            "n_skipped_non_test": n_skipped_non_test,
            "n_dropped_nonfinite": len(dropped_event_keys),
            "n_output_rows": len(scored),
            "test_flavor_counts": dict(test_flavor_counts),
            "scored_flavor_counts": dict(scored_flavor_counts),
            "feature_nonfinite_counts": nonfinite_counts,
            "dropped_event_keys": dropped_event_keys,
            "duplicate_event_count": 0,
            "weight_8ab": {
                "mode": "required_existing" if component == "background" else (
                    "validated_existing" if has_weight_8ab else "derived"
                ),
                "formula": None if component == "background" else "weight_template*8000/(79*0.2)",
            },
            "table": output.name,
        }
        metadata_handle = tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=output.parent,
            prefix=f".{output_metadata.name}.", suffix=".tmp", delete=False,
        )
        metadata_temp = Path(metadata_handle.name)
        with metadata_handle:
            json.dump(metadata, metadata_handle, indent=2, sort_keys=True)
            metadata_handle.write("\n")
            metadata_handle.flush()
            os.fsync(metadata_handle.fileno())

        os.replace(csv_temp, output)
        published.append(output)
        csv_temp = None
        os.replace(metadata_temp, output_metadata)
        published.append(output_metadata)
        metadata_temp = None
        return output
    except Exception:
        for path in published:
            path.unlink(missing_ok=True)
        raise
    finally:
        if csv_temp is not None:
            csv_temp.unlink(missing_ok=True)
        if metadata_temp is not None:
            metadata_temp.unlink(missing_ok=True)
