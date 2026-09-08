import importlib.util
import csv
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/evaluate_event_csv_fisher.py"
SPEC = importlib.util.spec_from_file_location("event_csv_fisher", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_q_sel_cut_is_strict():
    assert not MODULE.strict_q_sel_pass(0.954, 0.954)
    assert MODULE.strict_q_sel_pass(0.95400001, 0.954)


def test_baseline_model_alias_is_separate_from_q_sel():
    assert MODULE.ML_MODEL_COLUMNS["wbjets_lepton_v0"] == "q_CPV_wbjets_lepton"
    assert MODULE.ML_MODEL_COLUMNS["wbjets_lepton"] == "q_CPV_wbjets_lepton"
    assert MODULE.ML_MODEL_COLUMNS["wbjets_lepton_v0"] != "q_sel"


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def selected_row(weight: str) -> dict[str, str]:
    return {
        "event_id": "one",
        "q_sel": "0.99",
        "lepton_flavor": "electron",
        "weight_8ab": weight,
        "score": "0.2",
    }


def test_negative_sm_weight_is_a_hard_failure(tmp_path: Path):
    source = tmp_path / "sm.csv"
    write_rows(source, [selected_row("-1.0")])
    with pytest.raises(ValueError, match="negative sm weight_8ab"):
        MODULE.read_and_select(source, "sm", 0.954, None, "score")


def test_nonfinite_cpv_weight_is_a_hard_failure(tmp_path: Path):
    source = tmp_path / "cpv.csv"
    write_rows(source, [selected_row("nan")])
    with pytest.raises(ValueError, match="invalid cpv weight_8ab"):
        MODULE.read_and_select(source, "cpv", 0.954, None, "score")
