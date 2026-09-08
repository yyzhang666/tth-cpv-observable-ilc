import importlib.util
import os
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/maintenance/verify_account_snapshot.py"
SPEC = importlib.util.spec_from_file_location("verify_account_snapshot", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_snapshot_manifest_detects_content_and_symlinks(tmp_path: Path):
    source = tmp_path / "source"
    snapshot = tmp_path / "snapshot"
    source.mkdir()
    snapshot.mkdir()
    (source / "data.txt").write_text("same\n")
    (snapshot / "data.txt").write_text("same\n")
    os.symlink("data.txt", source / "link")
    os.symlink("data.txt", snapshot / "link")
    result = MODULE.compare(MODULE.scan_tree(source, set()), MODULE.scan_tree(snapshot, set()))
    assert result["status"] == "COMPLETE"

    (snapshot / "data.txt").write_text("changed\n")
    result = MODULE.compare(MODULE.scan_tree(source, set()), MODULE.scan_tree(snapshot, set()))
    assert result["status"] == "PARTIAL"
    assert result["mismatched_paths"] == ["data.txt"]


def test_snapshot_manifest_records_explicit_exclusion(tmp_path: Path):
    source = tmp_path / "source"
    snapshot = tmp_path / "snapshot"
    source.mkdir()
    snapshot.mkdir()
    (source / ".quota-usage.csv").write_text("private\n")
    result = MODULE.compare(
        MODULE.scan_tree(source, {".quota-usage.csv"}),
        MODULE.scan_tree(snapshot, {".quota-usage.csv"}),
    )
    assert result["status"] == "COMPLETE"
    assert result["excluded_paths"] == [".quota-usage.csv"]
