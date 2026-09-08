#!/usr/bin/env python3
"""Build and compare content manifests for a preserved account tree.

Symlinks are recorded but never followed.  Unreadable files/directories are
reported explicitly, so a partial snapshot cannot be mislabeled complete.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import stat
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Optional


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ilc_tth_cpv.provenance import atomic_write_json, sha256_file  # noqa: E402


FIELDS = (
    "relative_path",
    "type",
    "size",
    "mtime_ns",
    "mode",
    "sha256",
    "symlink_target",
    "target_exists",
    "read_status",
    "error",
)


def normalized_excludes(values: Iterable[str]) -> set[str]:
    return {value.strip("/") for value in values if value.strip("/")}


def is_excluded(relative: str, excludes: set[str]) -> bool:
    return any(relative == item or relative.startswith(item + "/") for item in excludes)


def record_entry(path: Path, relative: str) -> dict[str, Any]:
    row: dict[str, Any] = {field: "" for field in FIELDS}
    row["relative_path"] = relative
    try:
        metadata = path.lstat()
    except OSError as exc:
        row.update(type="unreadable", read_status="error", error=str(exc))
        return row
    row.update(
        size=metadata.st_size,
        mtime_ns=metadata.st_mtime_ns,
        mode=oct(stat.S_IMODE(metadata.st_mode)),
        read_status="ok",
    )
    if stat.S_ISLNK(metadata.st_mode):
        row["type"] = "symlink"
        try:
            row["symlink_target"] = os.readlink(path)
            row["target_exists"] = path.exists()
        except OSError as exc:
            row.update(read_status="error", error=str(exc))
    elif stat.S_ISDIR(metadata.st_mode):
        row["type"] = "directory"
    elif stat.S_ISREG(metadata.st_mode):
        row["type"] = "file"
        try:
            row["sha256"] = sha256_file(path)
        except OSError as exc:
            row.update(read_status="error", error=str(exc))
    else:
        row["type"] = "other"
    return row


def scan_tree(root: Path, excludes: set[str]) -> list[dict[str, Any]]:
    root = root.resolve()
    rows: list[dict[str, Any]] = []

    def visit(directory: Path, prefix: str) -> None:
        try:
            entries = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError as exc:
            rows.append(
                {
                    **{field: "" for field in FIELDS},
                    "relative_path": prefix or ".",
                    "type": "directory",
                    "read_status": "error",
                    "error": str(exc),
                }
            )
            return
        for entry in entries:
            relative = f"{prefix}/{entry.name}" if prefix else entry.name
            if is_excluded(relative, excludes):
                rows.append(
                    {
                        **{field: "" for field in FIELDS},
                        "relative_path": relative,
                        "type": "excluded",
                        "read_status": "excluded",
                    }
                )
                continue
            path = Path(entry.path)
            row = record_entry(path, relative)
            rows.append(row)
            if row["type"] == "directory" and row["read_status"] == "ok":
                visit(path, relative)

    visit(root, "")
    return rows


def write_manifest(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def comparable(row: dict[str, Any]) -> tuple[Any, ...]:
    kind = row["type"]
    common = (kind, row["mode"])
    if kind == "file":
        return common + (row["size"], row["sha256"])
    if kind == "symlink":
        return common + (row["symlink_target"],)
    return common


def compare(
    source_rows: list[dict[str, Any]], snapshot_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    source = {row["relative_path"]: row for row in source_rows}
    snapshot = {row["relative_path"]: row for row in snapshot_rows}
    excluded = sorted(path for path, row in source.items() if row["type"] == "excluded")
    unreadable = sorted(
        path for path, row in source.items() if row["read_status"] == "error"
    )
    source_paths = set(source) - set(excluded)
    snapshot_paths = set(snapshot) - set(excluded)
    missing = sorted(source_paths - snapshot_paths)
    extra = sorted(snapshot_paths - source_paths)
    mismatched = sorted(
        path
        for path in source_paths & snapshot_paths
        if source[path]["read_status"] == "ok"
        and snapshot[path]["read_status"] == "ok"
        and comparable(source[path]) != comparable(snapshot[path])
    )
    snapshot_unreadable = sorted(
        path for path, row in snapshot.items() if row["read_status"] == "error"
    )
    status = (
        "COMPLETE"
        if not unreadable and not snapshot_unreadable and not missing and not extra and not mismatched
        else "PARTIAL"
    )
    return {
        "status": status,
        "source_counts": dict(Counter(row["type"] for row in source_rows)),
        "snapshot_counts": dict(Counter(row["type"] for row in snapshot_rows)),
        "excluded_paths": excluded,
        "source_unreadable": unreadable,
        "snapshot_unreadable": snapshot_unreadable,
        "missing_paths": missing,
        "extra_paths": extra,
        "mismatched_paths": mismatched,
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--source", type=Path, required=True)
    result.add_argument("--snapshot", type=Path, required=True)
    result.add_argument("--output-dir", type=Path, required=True)
    result.add_argument("--exclude", action="append", default=[])
    return result


def main(argv: Optional[list[str]] = None) -> int:
    args = parser().parse_args(argv)
    excludes = normalized_excludes(args.exclude)
    source_rows = scan_tree(args.source, excludes)
    snapshot_rows = scan_tree(args.snapshot, excludes)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_manifest(args.output_dir / "source_manifest.csv", source_rows)
    write_manifest(args.output_dir / "snapshot_manifest.csv", snapshot_rows)
    summary = compare(source_rows, snapshot_rows)
    summary.update(
        source=str(args.source.resolve()),
        snapshot=str(args.snapshot.resolve()),
        comparison=(
            "regular files: size+SHA256+mode; symlinks: target+mode; "
            "directories/other: type+mode; symlinks not followed"
        ),
    )
    atomic_write_json(args.output_dir / "comparison_summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
