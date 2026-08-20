import csv
from pathlib import Path

import pytest

from scripts.mva.build_physical_normalization_inventory import (
    validate_interference_sidecar,
)
from tests.mva_test_helpers import write_cpv_sidecar


def test_full_cpv_sidecar_validation(tmp_path: Path) -> None:
    path = tmp_path / "sample.1.tthcpv_me.csv"
    write_cpv_sidecar(path)
    result = validate_interference_sidecar(path, 0.4, 0.01)
    assert result["n_generated"] == result["rows"] == 4
    assert result["shard_id"] == "sample.1"


def test_truncated_cpv_sidecar_fails(tmp_path: Path) -> None:
    path = tmp_path / "truncated.tthcpv_me.csv"
    write_cpv_sidecar(path, n=4)
    lines = path.read_text().splitlines()
    path.write_text("\n".join(lines[:-1]) + "\n")
    with pytest.raises(RuntimeError, match="sidecar rows"):
        validate_interference_sidecar(path, 0.4, 0.01)


def test_duplicate_or_reordered_event_fails(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.tthcpv_me.csv"
    write_cpv_sidecar(path, n=4)
    rows = list(csv.DictReader(path.open()))
    rows[2]["event"] = "2"
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(RuntimeError, match="event sequence mismatch"):
        validate_interference_sidecar(path, 0.4, 0.01)


def test_non_first_row_corruption_fails(tmp_path: Path) -> None:
    path = tmp_path / "bad-sign.tthcpv_me.csv"
    write_cpv_sidecar(path, n=4, bad_row=3)
    with pytest.raises(RuntimeError, match="invalid interference sign"):
        validate_interference_sidecar(path, 0.4, 0.01)
