import importlib.util
import csv
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/workflows/prepare_multiclass_dataset.py"
SPEC = importlib.util.spec_from_file_location("prepare_multiclass_dataset", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_cpv_training_weight_is_explicit_and_nonnegative():
    assert MODULE.cpv_training_weight(-2.5, "unit") == 1.0
    assert MODULE.cpv_training_weight(-2.5, "abs_template") == 2.5
    with pytest.raises(ValueError):
        MODULE.cpv_training_weight(-2.5, "signed")


def test_split_is_deterministic_and_in_contract():
    first = MODULE.deterministic_split("chunk-17", 1234)
    assert first == MODULE.deterministic_split("chunk-17", 1234)
    assert first in {"train", "validation", "test"}


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_duplicate_identity_is_a_hard_failure(tmp_path: Path):
    path = tmp_path / "sm.csv"
    row = {
        "event_id": "same",
        "q_sel": "0.99",
        "weight_8ab": "1.0",
        "feature": "0.2",
    }
    write_rows(path, [row, row])
    with pytest.raises(ValueError, match="duplicate event identity"):
        MODULE.read_role(path, "sm", ["feature"], 0.954, 1, "unit", "unit")


def test_negative_sm_template_weight_is_a_hard_failure(tmp_path: Path):
    path = tmp_path / "sm.csv"
    write_rows(
        path,
        [{
            "event_id": "one",
            "q_sel": "0.99",
            "weight_8ab": "-1.0",
            "feature": "0.2",
        }],
    )
    with pytest.raises(ValueError, match="must be nonnegative"):
        MODULE.read_role(path, "sm", ["feature"], 0.954, 1, "unit", "unit")
