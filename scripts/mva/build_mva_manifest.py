#!/usr/bin/env python3
"""Build the formal MVA input manifest from the KinFit production job plan.

The input job_plan.jsonl is authoritative. This script does not glob production
directories and does not infer sample, shard, polarization, or production
branch from filenames.

The only derived paths are the KinFit output products:

    <output_dir>/<job_key>/kinfit_<job_key>.root
    <output_dir>/<job_key>/kinfit_<job_key>.xml
    <output_dir>/<job_key>/kinfit_<job_key>.log
    <output_dir>/<job_key>/kinfit_<job_key>.validation.json
    <output_dir>/<job_key>/kinfit_<job_key>.provenance.json

Usage:
    python3 scripts/mva/build_mva_manifest.py \
        --config configs/mva_samples.yaml

Skip filesystem checks:
    python3 scripts/mva/build_mva_manifest.py \
        --config configs/mva_samples.yaml \
        --no-file-checks

Inspect the source schema:
    python3 scripts/mva/build_mva_manifest.py \
        --config configs/mva_samples.yaml \
        --inspect-source
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ilc_tth_cpv.io import load_yaml  # noqa: E402


MANIFEST_COLUMNS = [
    # Source identity
    "source_row",
    "job_key",
    "tag",
    "event_namespace",
    "split_group",

    # Physics/sample identity
    "sample_key",
    "source_class_label",
    "class_label",
    "event_category",
    "role",
    "use_for_training",
    "source_process",
    "process_mask",
    "source",
    "generator",
    "channel",
    "stage",

    # Beam/domain identity
    "polarization",
    "helicity",

    # Shard identity
    "logical_shard",
    "physical_part",
    "multipart",

    # Production provenance
    "production_branch",
    "truejet_available",
    "partial",
    "probe_status",
    "processor_lib",
    "processor_lib_sha256",

    # Input/output paths
    "input_path",
    "output_dir",
    "kinfit_root_path",
    "kinfit_xml_path",
    "kinfit_log_path",
    "validation_json_path",
    "provenance_json_path",
    "pathology_override_json_path",

    # Input accounting
    "expected_input_events",
    "input_readable_events",
    "readable_events",
    "readable_events_source",
    "source_expected_readable_events",
    "source_n_iso1_events",
    "source_readable_events",
    "denominator_stage",

    # Inclusion
    "include",
    "exclusion_reason",

    # Future normalization enrichment
    "generator_events",
    "sgv_events",
    "xsec_fb",
    "normalization_denominator",
    "luminosity_fb_inv",
    "weight_phys",
    "normalization_status",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the formal KinFit-to-MVA input manifest."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/mva_samples.yaml"),
        help="MVA sample configuration YAML.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Override meta.output_manifest.",
    )
    parser.add_argument(
        "--inspect-source",
        action="store_true",
        help="Print source keys and representative rows, then exit.",
    )
    parser.add_argument(
        "--no-file-checks",
        action="store_true",
        help="Skip input and KinFit output filesystem checks.",
    )
    return parser.parse_args()


def resolve_repo_path(path_value: str | Path) -> Path:
    """Resolve repository-relative paths while preserving absolute paths."""
    path = Path(path_value)
    return path if path.is_absolute() else REPO_ROOT / path


def normalized_path(path_value: Any) -> str:
    """Normalize a path string without requiring the path to exist."""
    return os.path.normpath(str(path_value))


def sha256_file(path: Path, block_size: int = 1 << 20) -> str:
    """Return the complete SHA256 digest of a file."""
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        while True:
            block = stream.read(block_size)
            if not block:
                break
            digest.update(block)

    return digest.hexdigest()


def read_jsonl(path: Path) -> list[tuple[int, dict[str, Any]]]:
    """Read non-empty JSON objects from a JSONL file."""
    rows: list[tuple[int, dict[str, Any]]] = []

    with path.open() as stream:
        for line_number, line in enumerate(stream, start=1):
            stripped = line.strip()

            if not stripped:
                continue

            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON at {path}:{line_number}: {exc}"
                ) from exc

            if not isinstance(payload, dict):
                raise TypeError(
                    f"Expected a JSON object at {path}:{line_number}"
                )

            rows.append((line_number, payload))

    if not rows:
        raise ValueError(f"Job plan is empty: {path}")

    return rows


def inspect_source(rows: list[tuple[int, dict[str, Any]]]) -> None:
    """Print the observed source schema and representative rows."""
    keys = sorted(
        {
            key
            for _, row in rows
            for key in row
        }
    )

    print("Observed JSONL keys:")
    for key in keys:
        print(f"  - {key}")

    print("\nFirst row:")
    print(
        json.dumps(
            rows[0][1],
            indent=2,
            sort_keys=True,
            default=str,
        )
    )

    sample_counts = Counter(
        row["sample_key"]
        for _, row in rows
    )

    print("\nRows by sample_key:")
    for sample_key, count in sorted(sample_counts.items()):
        print(f"  {sample_key}: {count}")

    combinations = Counter(
        (
            row["sample_key"],
            row["polarization"],
        )
        for _, row in rows
    )

    print("\nRows by sample_key and polarization:")
    for identity, count in sorted(combinations.items()):
        print(f"  {identity}: {count}")


def require_source_fields(
    row: dict[str, Any],
    line_number: int,
    required_fields: list[str],
) -> None:
    """Require fields needed for path and identity construction."""
    missing = [
        field
        for field in required_fields
        if field not in row
    ]

    if missing:
        raise KeyError(
            f"Source row {line_number} is missing fields: {missing}"
        )


def required_string(
    row: dict[str, Any],
    field: str,
) -> str:
    """Read a required non-empty string."""
    value = row.get(field)

    if value is None or not str(value).strip():
        raise ValueError(
            f"Required source field {field!r} is empty"
        )

    return str(value)


def optional_string(
    row: dict[str, Any],
    field: str,
) -> str:
    """Read an optional source value as a string."""
    value = row.get(field)
    return "" if value is None else str(value)


def required_nonnegative_int(
    row: dict[str, Any],
    field: str,
) -> int:
    """Read a required non-negative integer."""
    value = row.get(field)

    if value is None:
        raise ValueError(
            f"Required integer field {field!r} is null"
        )

    if isinstance(value, bool):
        raise TypeError(
            f"Field {field!r} must be an integer, not bool"
        )

    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Cannot convert {field}={value!r} to integer"
        ) from exc

    if result < 0:
        raise ValueError(
            f"Field {field!r} must be non-negative"
        )

    return result


def derive_kinfit_paths(
    output_dir: str,
    job_key: str,
) -> dict[str, str]:
    """Derive the formal nested KinFit product paths."""
    job_dir = Path(output_dir) / job_key
    stem = f"kinfit_{job_key}"

    return {
        "kinfit_root_path": str(
            job_dir / f"{stem}.root"
        ),
        "kinfit_xml_path": str(
            job_dir / f"{stem}.xml"
        ),
        "kinfit_log_path": str(
            job_dir / f"{stem}.log"
        ),
        "validation_json_path": str(
            job_dir / f"{stem}.validation.json"
        ),
        "provenance_json_path": str(
            job_dir / f"{stem}.provenance.json"
        ),
        "pathology_override_json_path": str(
            job_dir / f"{stem}.pathology-override.json"
        ),
    }


def build_manifest_row(
    source_line: int,
    source_row: dict[str, Any],
    cfg: dict,
) -> dict[str, Any]:
    """Convert one formal job-plan row into one MVA manifest row."""
    require_source_fields(
        source_row,
        source_line,
        cfg["checks"]["required_source_fields"],
    )

    allowed_versions = {
        int(version)
        for version in cfg["checks"][
            "allowed_job_plan_schema_versions"
        ]
    }
    source_schema_version = int(
        source_row["schema_version"]
    )

    if source_schema_version not in allowed_versions:
        raise ValueError(
            f"Unsupported job-plan schema_version="
            f"{source_schema_version}; "
            f"allowed={sorted(allowed_versions)}"
        )

    sample_key = required_string(
        source_row,
        "sample_key",
    )

    if sample_key not in cfg["samples"]:
        raise ValueError(
            f"Unknown sample_key={sample_key!r}"
        )

    sample_cfg = cfg["samples"][sample_key]

    polarization = required_string(
        source_row,
        "polarization",
    )

    if polarization not in cfg["polarizations"]:
        raise ValueError(
            f"Unknown polarization={polarization!r}"
        )

    helicity = str(
        cfg["polarizations"][polarization]
    )

    job_key = required_string(
        source_row,
        "job_key",
    )
    tag = required_string(
        source_row,
        "tag",
    )
    logical_shard = required_string(
        source_row,
        "logical_shard",
    )
    physical_part = required_string(
        source_row,
        "physical_part",
    )

    input_path = normalized_path(
        required_string(
            source_row,
            "input_path",
        )
    )
    output_dir = normalized_path(
        required_string(
            source_row,
            "output_dir",
        )
    )

    expected_input_events = required_nonnegative_int(
        source_row,
        "expected_input_events",
    )
    input_readable_events = required_nonnegative_int(
        source_row,
        "input_readable_events",
    )

    include = int(bool(source_row["include"]))
    exclusion_reason = optional_string(
        source_row,
        "exclusion_reason",
    )

    if include == 0 and not exclusion_reason:
        raise ValueError(
            f"Excluded job {job_key} has no exclusion_reason"
        )

    multipart = int(
        physical_part.lower() not in {
            "",
            "full",
            "0",
        }
    )

    event_namespace = "::".join(
        [
            required_string(source_row, "generator"),
            sample_key,
            polarization,
            job_key,
            physical_part,
        ]
    )

    # All physical parts of the same logical shard share this key.
    split_group = "::".join(
        [
            required_string(source_row, "source"),
            sample_key,
            polarization,
            logical_shard,
        ]
    )

    kinfit_paths = derive_kinfit_paths(
        output_dir,
        job_key,
    )

    return {
        "source_row": source_line,
        "job_key": job_key,
        "tag": tag,
        "event_namespace": event_namespace,
        "split_group": split_group,

        "sample_key": sample_key,
        "source_class_label": required_string(
            source_row,
            "class_label",
        ),
        "class_label": sample_cfg["class_label"],
        "event_category": int(
            sample_cfg["event_category"]
        ),
        "role": sample_cfg["role"],
        "use_for_training": int(
            bool(sample_cfg["use_for_training"])
        ),
        "source_process": required_string(
            source_row,
            "process",
        ),
        "process_mask": optional_string(
            source_row,
            "process_mask",
        ),
        "source": required_string(
            source_row,
            "source",
        ),
        "generator": required_string(
            source_row,
            "generator",
        ),
        "channel": required_string(
            source_row,
            "channel",
        ),
        "stage": required_string(
            source_row,
            "stage",
        ),

        "polarization": polarization,
        "helicity": helicity,

        "logical_shard": logical_shard,
        "physical_part": physical_part,
        "multipart": multipart,

        "production_branch": required_string(
            source_row,
            "production_branch",
        ),
        "truejet_available": int(
            bool(source_row["truejet_available"])
        ),
        "partial": int(
            bool(source_row["partial"])
        ),
        "probe_status": required_string(
            source_row,
            "probe_status",
        ),
        "processor_lib": required_string(
            source_row,
            "processor_lib",
        ),
        "processor_lib_sha256": required_string(
            source_row,
            "processor_lib_sha256",
        ),

        "input_path": input_path,
        "output_dir": output_dir,
        **kinfit_paths,

        "expected_input_events": expected_input_events,
        "input_readable_events": input_readable_events,

        # Canonical MVA manifest readable-event count.
        "readable_events": input_readable_events,
        "readable_events_source": (
            "job_plan.input_readable_events"
        ),

        # Optional source bookkeeping; null remains empty.
        "source_expected_readable_events": optional_string(
            source_row,
            "expected_readable_events",
        ),
        "source_n_iso1_events": optional_string(
            source_row,
            "n_iso1_events",
        ),
        "source_readable_events": optional_string(
            source_row,
            "readable_events",
        ),

        "denominator_stage": sample_cfg[
            "denominator_stage"
        ],

        "include": include,
        "exclusion_reason": exclusion_reason,

        # Physical normalization is enriched later.
        "generator_events": "",
        "sgv_events": "",
        "xsec_fb": "",
        "normalization_denominator": "",
        "luminosity_fb_inv": "",
        "weight_phys": "",
        "normalization_status": cfg[
            "normalization"
        ]["status"],
    }


def duplicate_values(
    rows: list[dict[str, Any]],
    field: str,
) -> list[str]:
    """Return duplicated non-empty values of one manifest field."""
    counts = Counter(
        str(row[field])
        for row in rows
        if str(row[field])
    )

    return sorted(
        value
        for value, count in counts.items()
        if count > 1
    )


def validate_uniqueness(
    rows: list[dict[str, Any]],
    cfg: dict,
) -> list[str]:
    """Validate identities whose duplication would cause double counting."""
    problems: list[str] = []
    checks = cfg["checks"]

    fields = []

    if checks.get("require_unique_job_key", True):
        fields.append("job_key")

    if checks.get("require_unique_input_path", True):
        fields.append("input_path")

    if checks.get(
        "require_unique_kinfit_root_path",
        True,
    ):
        fields.append("kinfit_root_path")

    for field in fields:
        duplicates = duplicate_values(
            rows,
            field,
        )

        if duplicates:
            problems.append(
                f"Duplicated {field}: {duplicates[:10]}"
            )

    if checks.get(
        "require_unique_physical_identity",
        True,
    ):
        counts = Counter(
            (
                row["source"],
                row["sample_key"],
                row["polarization"],
                row["logical_shard"],
                row["physical_part"],
            )
            for row in rows
        )

        duplicates = sorted(
            identity
            for identity, count in counts.items()
            if count > 1
        )

        if duplicates:
            problems.append(
                "Duplicated physical identities "
                "(source, sample_key, polarization, "
                "logical_shard, physical_part): "
                f"{duplicates[:10]}"
            )

    return problems


def validate_input_counts(
    rows: list[dict[str, Any]],
    cfg: dict,
) -> list[str]:
    """Compare the two populated KinFit-input count fields."""
    if not cfg["checks"].get(
        "validate_input_count_consistency",
        True,
    ):
        return []

    problems = []

    for row in rows:
        if int(row["include"]) != 1:
            continue

        expected = int(
            row["expected_input_events"]
        )
        readable = int(
            row["input_readable_events"]
        )

        if expected != readable:
            problems.append(
                f"{row['job_key']}: "
                f"expected_input_events={expected} != "
                f"input_readable_events={readable}"
            )

    return problems


def validate_expected_totals(
    rows: list[dict[str, Any]],
    cfg: dict,
) -> list[str]:
    """Detect a wrong, truncated, or unintended job plan."""
    if not cfg["checks"].get(
        "validate_expected_totals",
        True,
    ):
        return []

    problems = []

    included = [
        row
        for row in rows
        if int(row["include"]) == 1
    ]

    expected = cfg["meta"]["expected"]

    if len(rows) != int(expected["source_rows"]):
        problems.append(
            f"Source-row count mismatch: "
            f"observed={len(rows)}, "
            f"expected={expected['source_rows']}"
        )

    if len(included) != int(expected["included_rows"]):
        problems.append(
            f"Included-row count mismatch: "
            f"observed={len(included)}, "
            f"expected={expected['included_rows']}"
        )

    observed_total_events = sum(
        int(row["input_readable_events"])
        for row in included
    )
    expected_total_events = int(
        expected["input_readable_events"]
    )

    if observed_total_events != expected_total_events:
        problems.append(
            f"Total input-readable-event mismatch: "
            f"observed={observed_total_events}, "
            f"expected={expected_total_events}"
        )

    by_sample: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for row in included:
        by_sample[str(row["sample_key"])].append(
            row
        )

    for sample_key, sample_cfg in cfg["samples"].items():
        sample_rows = by_sample.get(
            sample_key,
            [],
        )

        expected_jobs = int(
            sample_cfg["expected_jobs"]
        )
        observed_jobs = len(sample_rows)

        if observed_jobs != expected_jobs:
            problems.append(
                f"{sample_key}: job-count mismatch: "
                f"observed={observed_jobs}, "
                f"expected={expected_jobs}"
            )

        observed_events = sum(
            int(row["input_readable_events"])
            for row in sample_rows
        )
        expected_events = int(
            sample_cfg[
                "expected_input_readable_events"
            ]
        )

        if observed_events != expected_events:
            problems.append(
                f"{sample_key}: input-readable-event mismatch: "
                f"observed={observed_events}, "
                f"expected={expected_events}"
            )

    unexpected_samples = sorted(
        set(by_sample) - set(cfg["samples"])
    )

    if unexpected_samples:
        problems.append(
            f"Unexpected sample keys: {unexpected_samples}"
        )

    return problems


def validate_files(
    rows: list[dict[str, Any]],
    cfg: dict,
) -> list[str]:
    """Check only files required by the configured manifest contract."""
    checks = cfg["checks"]
    fields = []

    if checks.get("require_input_file", True):
        fields.append("input_path")

    if checks.get(
        "require_kinfit_root_file",
        True,
    ):
        fields.append("kinfit_root_path")

    if checks.get(
        "require_companion_files",
        False,
    ):
        fields.extend(
            [
                "kinfit_xml_path",
                "kinfit_log_path",
                "validation_json_path",
                "provenance_json_path",
            ]
        )

    problems = []

    for row in rows:
        if int(row["include"]) != 1:
            continue

        for field in fields:
            path = Path(str(row[field]))

            if not path.is_file():
                problems.append(
                    f"{row['job_key']}: "
                    f"missing {field}: {path}"
                )

                # Avoid flooding the terminal when a mount is unavailable.
                if len(problems) >= 30:
                    problems.append(
                        "Further missing-file messages suppressed."
                    )
                    return problems

    return problems


def validate_manifest(
    rows: list[dict[str, Any]],
    cfg: dict,
    *,
    check_files: bool,
) -> dict[str, Any]:
    """Run the minimal fail-closed manifest checks."""
    problems = []

    problems.extend(
        validate_uniqueness(
            rows,
            cfg,
        )
    )
    problems.extend(
        validate_input_counts(
            rows,
            cfg,
        )
    )
    problems.extend(
        validate_expected_totals(
            rows,
            cfg,
        )
    )

    if check_files:
        problems.extend(
            validate_files(
                rows,
                cfg,
            )
        )

    included = [
        row
        for row in rows
        if int(row["include"]) == 1
    ]

    return {
        "ok": not problems,
        "problems": problems,
        "source_rows": len(rows),
        "included_rows": len(included),
        "training_rows": sum(
            int(row["include"]) == 1
            and int(row["use_for_training"]) == 1
            for row in rows
        ),
        "cp_validation_rows": sum(
            int(row["include"]) == 1
            and row["role"] == "cp_validation"
            for row in rows
        ),
        "input_readable_events": sum(
            int(row["input_readable_events"])
            for row in included
        ),
        "logical_split_groups": len(
            {
                row["split_group"]
                for row in included
            }
        ),
    }


def make_group_summary(
    rows: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Summarize included rows without imposing extra physics checks."""
    summary: dict[str, dict[str, Any]] = {}

    sample_keys = sorted(
        {
            str(row["sample_key"])
            for row in rows
        }
    )

    for sample_key in sample_keys:
        selected = [
            row
            for row in rows
            if row["sample_key"] == sample_key
            and int(row["include"]) == 1
        ]

        summary[sample_key] = {
            "jobs": len(selected),
            "input_readable_events": sum(
                int(row["input_readable_events"])
                for row in selected
            ),
            "polarizations": dict(
                sorted(
                    Counter(
                        str(row["polarization"])
                        for row in selected
                    ).items()
                )
            ),
            "production_branches": dict(
                sorted(
                    Counter(
                        str(row["production_branch"])
                        for row in selected
                    ).items()
                )
            ),
            "physical_parts": dict(
                sorted(
                    Counter(
                        str(row["physical_part"])
                        for row in selected
                    ).items()
                )
            ),
            "logical_split_groups": len(
                {
                    row["split_group"]
                    for row in selected
                }
            ),
        }

    return summary


def write_manifest_csv(
    output_path: Path,
    rows: list[dict[str, Any]],
) -> None:
    """Write the canonical MVA input manifest."""
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=MANIFEST_COLUMNS,
            extrasaction="raise",
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()

    config_path = resolve_repo_path(
        args.config
    )
    cfg = load_yaml(config_path)

    job_plan_path = Path(
        cfg["meta"]["official_job_plan"]
    )

    source_rows = read_jsonl(
        job_plan_path
    )

    if args.inspect_source:
        inspect_source(source_rows)
        return

    manifest_rows = []

    for line_number, source_row in source_rows:
        try:
            manifest_rows.append(
                build_manifest_row(
                    line_number,
                    source_row,
                    cfg,
                )
            )
        except Exception as exc:
            raise RuntimeError(
                f"Failed to process job-plan row "
                f"{line_number}: {exc}"
            ) from exc

    manifest_rows.sort(
        key=lambda row: (
            row["sample_key"],
            row["polarization"],
            row["logical_shard"],
            row["physical_part"],
            row["job_key"],
        )
    )

    report = validate_manifest(
        manifest_rows,
        cfg,
        check_files=not args.no_file_checks,
    )

    if not report["ok"]:
        formatted = "\n".join(
            f"  - {problem}"
            for problem in report["problems"]
        )

        raise SystemExit(
            "MVA manifest validation failed:\n"
            + formatted
        )

    output_path = (
        resolve_repo_path(args.output)
        if args.output is not None
        else resolve_repo_path(
            cfg["meta"]["output_manifest"]
        )
    )

    write_manifest_csv(
        output_path,
        manifest_rows,
    )

    metadata = {
        "schema_version": cfg["meta"]["schema_version"],
        "analysis_name": cfg["meta"]["analysis_name"],
        "created_utc": dt.datetime.now(
            dt.timezone.utc
        ).isoformat(),
        "source_job_plan": str(job_plan_path),
        "source_job_plan_sha256": sha256_file(
            job_plan_path
        ),
        "configuration": str(config_path),
        "configuration_sha256": sha256_file(
            config_path
        ),
        "filesystem_checks_enabled": (
            not args.no_file_checks
        ),
        "validation": report,
        "groups": make_group_summary(
            manifest_rows
        ),
        "normalization_status": cfg[
            "normalization"
        ]["status"],
    }

    metadata_path = output_path.with_suffix(
        ".meta.json"
    )

    with metadata_path.open("w") as stream:
        json.dump(
            metadata,
            stream,
            indent=2,
            sort_keys=True,
        )

    print(f"[manifest] source: {job_plan_path}")
    print(f"[manifest] CSV:    {output_path}")
    print(f"[manifest] meta:   {metadata_path}")
    print(
        "[manifest] "
        f"source_rows={report['source_rows']}, "
        f"included={report['included_rows']}, "
        f"input_events={report['input_readable_events']}, "
        f"split_groups={report['logical_split_groups']}"
    )


if __name__ == "__main__":
    main()