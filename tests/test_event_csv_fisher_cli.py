import importlib.util
import csv
import json
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


def test_scored_background_event_id_is_a_valid_event_key():
    assert MODULE.event_key(
        {"event_id": "background:job-7:42"}, "background"
    ) == ("background:job-7:42",)


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


def fisher_rows(role: str, include_q_sel: bool = True) -> list[dict[str, str]]:
    rows = []
    for flavor in ("electron", "muon"):
        role_weights = ("2.0", "-1.0") if role == "cpv" else ("1.0",)
        for index, weight in enumerate(role_weights):
            row = {
                "event_id": f"{role}:{flavor}:{index}",
                "lepton_flavor": flavor,
                "weight_8ab": weight,
                "score": "0.2",
            }
            if include_q_sel:
                row["q_sel"] = "0.99"
            rows.append(row)
    return rows


def test_signal_only_cli_needs_no_background_or_q_sel(tmp_path: Path):
    sm_path = tmp_path / "sm.csv"
    cpv_path = tmp_path / "cpv.csv"
    output_dir = tmp_path / "signal-only"
    write_rows(sm_path, fisher_rows("sm", include_q_sel=False))
    write_rows(cpv_path, fisher_rows("cpv", include_q_sel=False))

    assert MODULE.main(
        [
            "--signal-only",
            "--sm-csv",
            str(sm_path),
            "--cpv-csv",
            str(cpv_path),
            "--ml-score-column",
            "score",
            "--bins",
            "2",
            "--output-dir",
            str(output_dir),
        ]
    ) == 0

    payload = json.loads((output_dir / "fisher_summary.json").read_text())
    assert payload["selection"]["expression"] == "none (signal-only)"
    assert "background" not in payload["inputs"]
    assert payload["summary"]["electron"]["fisher"] == pytest.approx(1.0)
    assert payload["summary"]["muon"]["fisher"] == pytest.approx(1.0)
    assert payload["summary"]["combined_likelihood"]["fisher"] == pytest.approx(2.0)


def test_background_cli_still_uses_q_sel_and_background(tmp_path: Path):
    background_path = tmp_path / "background.csv"
    sm_path = tmp_path / "sm.csv"
    cpv_path = tmp_path / "cpv.csv"
    output_dir = tmp_path / "with-background"
    write_rows(background_path, fisher_rows("background"))
    write_rows(sm_path, fisher_rows("sm"))
    write_rows(cpv_path, fisher_rows("cpv"))

    assert MODULE.main(
        [
            "--background-csv",
            str(background_path),
            "--sm-csv",
            str(sm_path),
            "--cpv-csv",
            str(cpv_path),
            "--ml-score-column",
            "score",
            "--bins",
            "2",
            "--output-dir",
            str(output_dir),
        ]
    ) == 0

    payload = json.loads((output_dir / "fisher_summary.json").read_text())
    assert payload["selection"]["expression"] == "q_sel > 0.954"
    assert payload["summary"]["electron"]["fisher"] == pytest.approx(0.5)
    assert payload["summary"]["muon"]["fisher"] == pytest.approx(0.5)
    assert payload["summary"]["combined_likelihood"]["fisher"] == pytest.approx(1.0)
