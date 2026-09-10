import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from ilc_tth_cpv.provenance import file_record
from ilc_tth_cpv.event_workflow import main as fisher_main


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/workflows/train_threeclass_model.py"
SPEC = importlib.util.spec_from_file_location("train_threeclass_model", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def row(label: int, weight: float, role: str = "cpv") -> dict[str, str]:
    return {
        "event_id": f"{role}-{label}-{weight}",
        "lepton_flavor": "electron",
        "split": "train",
        "training_include": "1",
        "target_label": str(label),
        "base_training_weight": str(weight),
        "source_role": role,
    }


def test_class_scales_equalize_targets_but_preserve_neutral_composition():
    rows = [
        row(-1, 2.0),
        row(1, 4.0),
        row(0, 3.0, "sm"),
        row(0, 1.0, "background"),
    ]
    scales = MODULE.class_scales(rows, "electron")
    balanced = {
        label: sum(
            float(item["base_training_weight"]) * scales[label]
            for item in rows
            if int(item["target_label"]) == label
        )
        for label in MODULE.CLASS_ORDER
    }
    assert balanced == {-1: 1.0, 0: 1.0, 1: 1.0}
    assert (3.0 * scales[0]) / (1.0 * scales[0]) == 3.0


def test_zero_weight_row_is_allowed_if_class_total_is_positive():
    rows = [row(-1, 1.0), row(0, 1.0, "sm"), row(0, 0.0, "background"), row(1, 1.0)]
    assert MODULE.class_scales(rows, "electron") == {-1: 1.0, 0: 1.0, 1: 1.0}


def test_threeclass_score_uses_model_class_mapping_not_column_position():
    score = MODULE.threeclass_score([0.6, 0.1, 0.3], [1, -1, 0])
    assert score == pytest.approx(0.5)


def test_threeclass_score_rejects_incomplete_probabilities():
    with pytest.raises(ValueError, match="model classes"):
        MODULE.threeclass_score([0.2, 0.8], [-1, 1])


def test_formal_cli_has_no_single_flavor_mode():
    with pytest.raises(SystemExit):
        MODULE.parser().parse_args(
            [
                "--dataset",
                "events.csv",
                "--out-dir",
                "model",
                "--lepton-flavor",
                "electron",
            ]
        )


UNITY_SCALES = {
    (role, flavor): 1.0
    for role in ("background", "sm", "cpv")
    for flavor in MODULE.FLAVORS
}
FIXTURE_SCALES = {
    ("background", "electron"): 2.0,
    ("sm", "electron"): 3.0,
    ("cpv", "electron"): 4.0,
    ("background", "muon"): 5.0,
    ("sm", "muon"): 6.0,
    ("cpv", "muon"): 7.0,
}


def contract_row(role: str, label: str, include: str, template: str) -> dict[str, str]:
    return {
        "event_id": f"{role}-1",
        "source_role": role,
        "lepton_flavor": "electron",
        "split": "test",
        "training_include": include,
        "target_label": label,
        "base_training_weight": "1.0",
        "source_template_weight": template,
        "test_weight_scale": "1.0",
        "template_weight": template,
        "q_sel": "0.99",
    }


def test_scheme_one_contract_keeps_background_inference_only():
    rows = [
        contract_row("cpv", "1", "1", "2.0"),
        contract_row("sm", "0", "1", "3.0"),
        contract_row("background", "", "0", "4.0"),
    ]
    MODULE.validate_contract(rows, "sm", 0.954, UNITY_SCALES)


def test_scheme_two_contract_requires_background_in_neutral_class():
    background = contract_row("background", "", "0", "4.0")
    with pytest.raises(ValueError, match="background inclusion"):
        MODULE.validate_contract(
            [background], "sm-plus-background", 0.954, UNITY_SCALES
        )


def test_cpv_target_must_match_signed_interference():
    cpv = contract_row("cpv", "-1", "1", "2.0")
    with pytest.raises(ValueError, match="CPV target/weight"):
        MODULE.validate_contract([cpv], "sm", 0.954, UNITY_SCALES)


def write_formal_fixture(path: Path, neutral_class: str) -> None:
    rows: list[dict[str, object]] = []
    for flavor_index, flavor in enumerate(("electron", "muon")):
        for split_index, split in enumerate(("train", "validation", "test")):
            for label in MODULE.CLASS_ORDER:
                role = "sm" if label == 0 else "cpv"
                for event_index in range(2):
                    source_template = 1.0 if label == 0 else float(label)
                    scale = FIXTURE_SCALES[(role, flavor)] if split == "test" else 1.0
                    template = source_template * scale
                    identity = f"{role}-{flavor}-{split}-{label}-{event_index}"
                    rows.append(
                        {
                            "event_id": identity,
                            "source_role": role,
                            "source_identity": identity,
                            "split_group": f"{role}-{flavor}-{split}-{event_index}",
                            "split": split,
                            "process": role,
                            "lepton_flavor": flavor,
                            "q_sel": 0.99,
                            "target_label": label,
                            "training_include": 1,
                            "base_training_weight": abs(template),
                            "source_template_weight": source_template,
                            "test_weight_scale": scale,
                            "template_weight": template,
                            "feature": label + 0.03 * event_index + 0.01 * flavor_index
                            + 0.001 * split_index,
                        }
                    )
            if neutral_class == "sm-plus-background" or split == "test":
                identity = f"background-{flavor}-{split}"
                include = int(neutral_class == "sm-plus-background")
                scale = (
                    FIXTURE_SCALES[("background", flavor)]
                    if split == "test"
                    else 1.0
                )
                rows.append(
                    {
                        "event_id": identity,
                        "source_role": "background",
                        "source_identity": identity,
                        "split_group": identity,
                        "split": split,
                        "process": "background",
                        "lepton_flavor": flavor,
                        "q_sel": 0.99,
                        "target_label": 0 if include else "",
                        "training_include": include,
                        "base_training_weight": 0.5 * scale,
                        "source_template_weight": 0.5,
                        "test_weight_scale": scale,
                        "template_weight": 0.5 * scale,
                        "feature": 0.2,
                    }
                )
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    manifest = {
        "formal_training_allowed": True,
        "missing_training_cells": [],
        "neutral_class": neutral_class,
        "class_order": [
            {"target": -1, "name": "cpv_negative"},
            {"target": 0, "name": "neutral"},
            {"target": 1, "name": "cpv_positive"},
        ],
        "feature_columns": ["feature"],
        "q_sel_threshold": 0.954,
        "test_weight_projection": {
            "status": "caller-asserted-already-projected-to-8ab",
            "target_exposure_fb": 8000,
            "scales": {
                f"{role}:{flavor}": FIXTURE_SCALES[(role, flavor)]
                for role in ("background", "sm", "cpv")
                for flavor in MODULE.FLAVORS
            },
        },
        "output": file_record(path),
    }
    path.with_suffix(path.suffix + ".manifest.json").write_text(json.dumps(manifest))


@pytest.mark.parametrize("neutral_class", ["sm", "sm-plus-background"])
def test_tiny_catboost_train_score_and_plot(tmp_path: Path, neutral_class: str):
    dataset = tmp_path / "events.csv"
    output = tmp_path / "model"
    write_formal_fixture(dataset, neutral_class)
    assert MODULE.main(
        [
            "--dataset",
            str(dataset),
            "--out-dir",
            str(output),
            "--iterations",
            "6",
            "--depth",
            "2",
            "--learning-rate",
            "0.1",
            "--thread-count",
            "1",
            "--plot",
        ]
    ) == 0
    assert (output / "electron/threeclass_catboost.cbm").is_file()
    assert (output / "muon/training_history.png").is_file()
    for role in ("background", "sm", "cpv"):
        score_path = output / "scores" / f"{role}_scores.csv"
        scored = list(csv.DictReader(score_path.open()))
        assert scored
        for item in scored:
            probabilities = sum(
                float(item[column])
                for column in ("p_minus", "p_neutral", "p_plus")
            )
            assert probabilities == pytest.approx(1.0)
            assert float(item["q_threeclass"]) == pytest.approx(
                float(item["p_plus"]) - float(item["p_minus"])
            )
        source_absolute_yield = {"background": 0.5, "sm": 2.0, "cpv": 4.0}[role]
        for flavor in MODULE.FLAVORS:
            projected = sum(
                abs(float(item["weight_8ab"]))
                for item in scored
                if item["lepton_flavor"] == flavor
            )
            assert projected == pytest.approx(
                source_absolute_yield * FIXTURE_SCALES[(role, flavor)]
            )
    fisher_output = tmp_path / "fisher"
    assert fisher_main(
        [
            "--background-csv",
            str(output / "scores/background_scores.csv"),
            "--sm-csv",
            str(output / "scores/sm_scores.csv"),
            "--cpv-csv",
            str(output / "scores/cpv_scores.csv"),
            "--ml-score-column",
            "q_threeclass",
            "--bins",
            "6",
            "--range",
            "-1",
            "1",
            "--q-sel-threshold",
            "0.954",
            "--plot",
            "--output-dir",
            str(fisher_output),
        ]
    ) == 0
    assert (fisher_output / "fisher_summary.json").is_file()
    assert (fisher_output / "event_templates.png").is_file()
