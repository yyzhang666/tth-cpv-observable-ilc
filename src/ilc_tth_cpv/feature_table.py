"""Stream v3 reco baselines into compact, derived feature tables."""

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

from ilc_tth_cpv.input_features import (
    FeatureContext,
    feature_columns_from_config,
    resolve_feature_values,
    to_float,
)
from ilc_tth_cpv.reco_baseline import (
    IDENTITY_COLUMNS,
    RECO_BASELINE_COLUMNS,
    WEAVER_SCORE_KEYS,
    WEIGHT_COLUMNS,
)

SCHEMA_VERSION = "feature_table_v3"
STATUS = "augmented_feature_table_v3"
COMPAT_POLICIES = ("canonical", "nana_v2_legacy")
LEGACY_FAMILIES = (
    "wjet_quark",
    "wjet_antiquark",
    "top_side_fermion",
    "anti_top_side_fermion",
    "top_b",
    "antitop_bbar",
    "lepton",
    "neutrino",
    "top",
    "antitop",
    "higgs",
)
LEGACY_BLOCK_FIELDS = ("E", "pt", "theta", "phi", "mass")
LEGACY_DEPENDENCY_FIELDS = ("E", "theta", "phi", "mass", "valid")
LEGACY_PT_CHUNKS = (33, 67)


def parse_chunk_spec(spec: str) -> list[int]:
    """Parse comma-separated positive integers and inclusive ranges."""
    chunks: set[int] = set()
    if not spec.strip():
        raise ValueError("--chunks must not be empty")
    for token in spec.split(","):
        token = token.strip()
        if not token:
            raise ValueError(f"invalid empty chunk token in {spec!r}")
        if "-" in token:
            parts = token.split("-")
            if len(parts) != 2 or not all(part.isdigit() for part in parts):
                raise ValueError(f"invalid chunk range {token!r}")
            first, last = (int(part) for part in parts)
            if first <= 0 or last < first:
                raise ValueError(f"invalid chunk range {token!r}")
            chunks.update(range(first, last + 1))
        else:
            if not token.isdigit() or int(token) <= 0:
                raise ValueError(f"invalid chunk {token!r}")
            chunks.add(int(token))
    return sorted(chunks)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_numeric_zero(value: object) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and value == 0


def _validate_source_metadata(metadata: Mapping[str, object], csv_path: Path, chunk: int) -> None:
    expected = {
        "schema_version": "reco_baseline_v3",
        "frame": "lab_raw",
        "level": "reco",
        "component": "interference",
        "status": "baseline_export",
        "n_columns": 148,
        "table": csv_path.name,
    }
    for key, value in expected.items():
        if metadata.get(key) != value:
            raise ValueError(
                f"invalid source metadata {csv_path}: {key}={metadata.get(key)!r}, expected {value!r}"
            )
    if not _is_numeric_zero(metadata.get("max_events")):
        raise ValueError(f"invalid source metadata {csv_path}: max_events must be numeric zero")
    if str(metadata.get("chunk")) != str(chunk):
        raise ValueError(f"invalid source metadata {csv_path}: chunk does not match {chunk}")
    if not _is_numeric_zero(metadata.get("n_event_number_mismatch")):
        raise ValueError(
            f"invalid source metadata {csv_path}: n_event_number_mismatch must be numeric zero"
        )
    missing = metadata.get("missing_weaver_score_counts")
    if not isinstance(missing, dict) or set(missing) != set(WEAVER_SCORE_KEYS):
        raise ValueError(f"invalid source metadata {csv_path}: Weaver score keys do not match")
    if not all(_is_numeric_zero(value) for value in missing.values()):
        raise ValueError(f"invalid source metadata {csv_path}: Weaver missing counts must be zero")
    n_exported = metadata.get("n_exported")
    if isinstance(n_exported, bool) or not isinstance(n_exported, int) or n_exported < 0:
        raise ValueError(f"invalid source metadata {csv_path}: n_exported must be a non-negative integer")


def _provenance_paths(config_path: Path) -> tuple[Path, ...]:
    repo = Path(__file__).resolve().parents[2]
    return (
        config_path.resolve(),
        (repo / "scripts/export_features_v3.py").resolve(),
        (repo / "src/ilc_tth_cpv/feature_table.py").resolve(),
        (repo / "src/ilc_tth_cpv/input_features.py").resolve(),
        (repo / "src/ilc_tth_cpv/flavor.py").resolve(),
        (repo / "src/ilc_tth_cpv/frames.py").resolve(),
        (repo / "src/ilc_tth_cpv/angles.py").resolve(),
    )


def _legacy_dependency_names(features: Sequence[str]) -> list[str]:
    names = list(features)
    seen = set(names)
    for family in LEGACY_FAMILIES:
        for field in LEGACY_DEPENDENCY_FIELDS:
            name = f"{family}_{field}"
            if name not in seen:
                names.append(name)
                seen.add(name)
    return names


def _same_value(left: object, right: object) -> bool:
    left_float = to_float(left)
    right_float = to_float(right)
    if math.isnan(left_float) and math.isnan(right_float):
        return True
    return left_float == right_float


def _strict_row_chunk(value: object, source_chunk: int) -> int:
    text = str(value)
    if not text.isascii() or not text.isdigit() or text.startswith("0"):
        raise ValueError(f"row chunk must be a canonical positive integer, got {value!r}")
    row_chunk = int(text)
    if row_chunk != source_chunk:
        raise ValueError(
            f"row chunk {row_chunk} does not match source chunk {source_chunk}"
        )
    return row_chunk


def _apply_legacy_policy(
    resolved: Mapping[str, float],
    features: Sequence[str],
    row_chunk: int,
    family_counts: dict[str, dict[str, int]],
    changed_counts: dict[str, int],
) -> tuple[dict[str, float], int, int, int]:
    transformed = {feature: resolved[feature] for feature in features}
    total_changed = 0
    invalidated_objects = 0
    pt_applications = 0
    requested = set(features)
    for family in LEGACY_FAMILIES:
        values = {
            field: to_float(resolved[f"{family}_{field}"])
            for field in LEGACY_DEPENDENCY_FIELDS
        }
        valid = values["valid"] == 1.0 and all(
            math.isfinite(values[field]) for field in ("E", "theta", "phi", "mass")
        )
        if valid and row_chunk in LEGACY_PT_CHUNKS:
            pt_name = f"{family}_pt"
            if pt_name in requested:
                momentum = math.sqrt(max(0.0, values["E"] ** 2 - values["mass"] ** 2))
                transformed[pt_name] = momentum * math.sin(values["theta"])
                family_counts[family]["pt_replacements"] += 1
                pt_applications += 1
        elif not valid:
            family_counts[family]["invalidations"] += 1
            invalidated_objects += 1
            for field in LEGACY_BLOCK_FIELDS:
                name = f"{family}_{field}"
                if name in requested:
                    transformed[name] = float("nan")
            valid_name = f"{family}_valid"
            if valid_name in requested:
                transformed[valid_name] = 0.0

        for field in LEGACY_BLOCK_FIELDS + ("valid",):
            name = f"{family}_{field}"
            if name in requested and not _same_value(resolved[name], transformed[name]):
                changed_counts[name] += 1
                total_changed += 1
    return transformed, total_changed, invalidated_objects, pt_applications


def augment_feature_table(
    cfg: Mapping[str, object],
    *,
    config_path: Path,
    feature_set: str,
    input_pattern: str,
    chunks: Sequence[int],
    output: Path,
    compat_policy: str = "canonical",
) -> Path:
    """Write one compact feature table from ordered v3 baseline chunks."""
    if input_pattern.count("{chunk}") != 1:
        raise ValueError("--input-pattern must contain literal {chunk} exactly once")
    if output.suffix != ".csv":
        raise ValueError("--output must have suffix .csv")
    if compat_policy not in COMPAT_POLICIES:
        raise ValueError(f"unknown compatibility policy {compat_policy!r}")
    ordered_chunks = sorted(set(chunks))
    if not ordered_chunks or any(isinstance(chunk, bool) or not isinstance(chunk, int) or chunk <= 0 for chunk in ordered_chunks):
        raise ValueError("chunks must contain positive integers")

    output = output.resolve()
    output_metadata = output.with_suffix(".meta.json")
    if output.exists() or output_metadata.exists():
        raise FileExistsError(f"refusing existing output pair: {output}, {output_metadata}")

    features = feature_columns_from_config(cfg, feature_set)
    requested_names = (
        features if compat_policy == "canonical" else _legacy_dependency_names(features)
    )
    columns = list(IDENTITY_COLUMNS) + list(WEIGHT_COLUMNS) + ["lepton_flavor"] + features
    if len(columns) != len(set(columns)):
        raise ValueError("compact output columns contain duplicates")

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
        seen_events: set[tuple[str, str, str]] = set()
        split_counts: Counter[str] = Counter()
        lepton_counts: Counter[str] = Counter()
        label_counts: Counter[str] = Counter()
        nonfinite_counts = {feature: 0 for feature in features}
        changed_counts = {feature: 0 for feature in features}
        family_counts = {
            family: {"pt_replacements": 0, "invalidations": 0}
            for family in LEGACY_FAMILIES
        }
        total_changed = 0
        event_key_digest = hashlib.sha256()
        per_chunk_counts: dict[str, int] = {}
        per_chunk_transform_counts = {
            str(chunk): {
                "rows": 0,
                "invalidated_objects": 0,
                "pt_applications": 0,
                "changed_cells": 0,
            }
            for chunk in ordered_chunks
        }
        sources: list[dict[str, object]] = []
        n_input_rows = 0

        with csv_handle:
            writer = csv.DictWriter(csv_handle, fieldnames=columns, extrasaction="raise")
            writer.writeheader()
            for chunk in ordered_chunks:
                source_csv = Path(input_pattern.format(chunk=chunk)).resolve()
                source_metadata = source_csv.with_suffix(".meta.json")
                if not source_csv.is_file() or not source_metadata.is_file():
                    raise FileNotFoundError(
                        f"source CSV/metadata pair is required: {source_csv}, {source_metadata}"
                    )
                metadata = json.loads(source_metadata.read_text())
                if not isinstance(metadata, dict):
                    raise ValueError(f"source metadata must be an object: {source_metadata}")
                _validate_source_metadata(metadata, source_csv, chunk)
                source_csv_hash = _sha256(source_csv)
                source_metadata_hash = _sha256(source_metadata)

                chunk_rows = 0
                with source_csv.open(newline="") as source_handle:
                    reader = csv.DictReader(source_handle)
                    if tuple(reader.fieldnames or ()) != RECO_BASELINE_COLUMNS:
                        raise ValueError(f"source CSV header does not match v3 baseline: {source_csv}")
                    for row in reader:
                        row_chunk = _strict_row_chunk(row["chunk"], chunk)
                        event_key = (row["sample_name"], row["level"], row["event_id"])
                        if event_key in seen_events:
                            raise ValueError(f"duplicate event key across inputs: {event_key}")
                        seen_events.add(event_key)
                        event_key_digest.update(
                            ("\0".join(event_key) + "\n").encode("utf-8")
                        )

                        context = FeatureContext(row)
                        resolved = resolve_feature_values(context, requested_names)
                        if compat_policy == "nana_v2_legacy":
                            (
                                output_values,
                                row_changed,
                                invalidated_objects,
                                pt_applications,
                            ) = _apply_legacy_policy(
                                resolved,
                                features,
                                row_chunk,
                                family_counts,
                                changed_counts,
                            )
                            total_changed += row_changed
                        else:
                            output_values = {feature: resolved[feature] for feature in features}
                            row_changed = 0
                            invalidated_objects = 0
                            pt_applications = 0
                        compact = {name: row[name] for name in IDENTITY_COLUMNS + WEIGHT_COLUMNS}
                        compact["lepton_flavor"] = row["lepton_flavor"]
                        for feature in features:
                            value = output_values[feature]
                            compact[feature] = value
                            if not math.isfinite(to_float(value)):
                                nonfinite_counts[feature] += 1
                        writer.writerow(compact)
                        chunk_rows += 1
                        n_input_rows += 1
                        split_counts[row["split"]] += 1
                        lepton_counts[row["lepton_flavor"]] += 1
                        label_counts[row["label"]] += 1
                        chunk_transforms = per_chunk_transform_counts[str(chunk)]
                        chunk_transforms["rows"] += 1
                        chunk_transforms["invalidated_objects"] += invalidated_objects
                        chunk_transforms["pt_applications"] += pt_applications
                        chunk_transforms["changed_cells"] += row_changed

                if chunk_rows != metadata["n_exported"]:
                    raise ValueError(
                        f"source row count {chunk_rows} != n_exported {metadata['n_exported']}: {source_csv}"
                    )
                per_chunk_counts[str(chunk)] = chunk_rows
                sources.append({
                    "chunk": chunk,
                    "csv": str(source_csv),
                    "metadata": str(source_metadata),
                    "csv_sha256": source_csv_hash,
                    "metadata_sha256": source_metadata_hash,
                    "n_rows": chunk_rows,
                })
            csv_handle.flush()
            os.fsync(csv_handle.fileno())

        provenance_paths = _provenance_paths(config_path)
        provenance = {str(path): _sha256(path) for path in provenance_paths}
        result_metadata = {
            "schema_version": SCHEMA_VERSION,
            "status": STATUS,
            "created": datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(),
            "config": str(config_path.resolve()),
            "feature_set": feature_set,
            "feature_list": features,
            "input_pattern": input_pattern,
            "chunks": ordered_chunks,
            "component": "interference",
            "level": "reco",
            "input_frame": "lab_raw",
            "feature_frame": "higgs_rest",
            "columns": columns,
            "n_columns": len(columns),
            "n_input_rows": n_input_rows,
            "n_output_rows": n_input_rows,
            "duplicate_event_count": 0,
            "per_chunk_counts": per_chunk_counts,
            "split_counts": dict(split_counts),
            "lepton_flavor_counts": dict(lepton_counts),
            "label_counts": dict(label_counts),
            "feature_nonfinite_counts": nonfinite_counts,
            "compatibility": {
                "policy": compat_policy,
                "description": (
                    "archived Nana v2 heterogeneous training-table reproduction"
                    if compat_policy == "nana_v2_legacy" else "canonical resolver output"
                ),
                "version": "nana_v2_legacy_v2" if compat_policy == "nana_v2_legacy" else "canonical_v1",
                "version_number": 2 if compat_policy == "nana_v2_legacy" else 1,
                "formula": (
                    "chunks 33 and 67 only: pt=sqrt(max(0,E^2-mass^2))*sin(theta); other chunks keep canonical pt"
                    if compat_policy == "nana_v2_legacy" else "canonical resolver values unchanged"
                ),
                "invalidation": (
                    "if valid!=1 or E/theta/phi/mass is nonfinite, requested E/pt/theta/phi/mass are NaN and requested valid is 0"
                    if compat_policy == "nana_v2_legacy" else "none"
                ),
                "invalidation_scope": "all_chunks" if compat_policy == "nana_v2_legacy" else "none",
                "legacy_pt_chunks": list(LEGACY_PT_CHUNKS) if compat_policy == "nana_v2_legacy" else [],
                "families": list(LEGACY_FAMILIES),
                "per_family_counts": family_counts,
                "per_chunk_transform_counts": per_chunk_transform_counts,
                "per_feature_changed_counts": changed_counts,
                "total_changed_values": total_changed,
                "ordered_features": features,
            },
            "event_key_sha256": event_key_digest.hexdigest(),
            "event_key_hash_contract": "sha256 over ordered UTF-8 sample_name\\0level\\0event_id\\n records",
            "sources": sources,
            "provenance_sha256": provenance,
            "table": output.name,
        }
        metadata_handle = tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=output.parent,
            prefix=f".{output_metadata.name}.", suffix=".tmp", delete=False,
        )
        metadata_temp = Path(metadata_handle.name)
        with metadata_handle:
            json.dump(result_metadata, metadata_handle, indent=2, sort_keys=True)
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
