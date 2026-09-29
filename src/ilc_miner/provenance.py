"""Small, deterministic provenance helpers for analysis workflows.

The functions in this module deliberately avoid analysis-specific defaults.
They record what was actually consumed and produced without changing physics
objects, selections, weights, or binning.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    """Return the full SHA-256 digest of one regular file."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def file_record(path: Path) -> dict[str, Any]:
    """Describe one file with a content hash and stable metadata."""
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": sha256_file(path),
    }


def file_records(paths: Iterable[Path]) -> list[dict[str, Any]]:
    """Describe files in caller-provided order."""
    return [file_record(Path(path)) for path in paths]


def git_state(repo_root: Path) -> dict[str, Any]:
    """Return commit/branch/dirty state, or an explicit unavailable status."""
    root = Path(repo_root).resolve()

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout.strip()

    try:
        status = git("status", "--porcelain")
        return {
            "root": str(root),
            "commit": git("rev-parse", "HEAD"),
            "branch": git("branch", "--show-current"),
            "dirty": bool(status),
            "status_porcelain": status.splitlines(),
        }
    except (OSError, subprocess.CalledProcessError) as exc:
        return {"root": str(root), "available": False, "error": str(exc)}


def runtime_state(packages: Iterable[str] = ()) -> dict[str, Any]:
    """Record Python/platform information and requested package versions."""
    versions: dict[str, Optional[str]] = {}
    try:
        from importlib.metadata import PackageNotFoundError, version

        for package in packages:
            try:
                versions[package] = version(package)
            except PackageNotFoundError:
                versions[package] = None
    except ImportError:
        versions = {package: None for package in packages}
    return {
        "python": sys.version,
        "executable": sys.executable,
        "platform": platform.platform(),
        "packages": versions,
    }


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Write JSON completely before replacing the destination path."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=str(destination.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
        temporary.replace(destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
