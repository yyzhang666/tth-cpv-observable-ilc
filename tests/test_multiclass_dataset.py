import csv
import importlib.util
import sys
from argparse import Namespace
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/workflows/prepare_multiclass_dataset.py"
SPEC = importlib.util.spec_from_file_location("prepare_multiclass_dataset", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def background_row(weight: str = "2.0") -> dict[str, str]:
    return {
        "event_id": "background-1",
        "job_key": "job-7",
        "split": "test",
        "q_sel": "0.99",
        "weight_8ab": weight,
        "lepton_flavor": "electron",
        "feature": "0.2",
    }


def read_background(
    path: Path,
    neutral_class: str,
    test_weight_scales: dict[tuple[str, str], float] | None = None,
) -> tuple[list[dict[str, object]], dict[str, int]]:
    return MODULE.read_role(
        path,
        "background",
        ["feature"],
        0.954,
        1,
        neutral_class,
        "abs_template",
        "template",
        None,
        test_weight_scales,
    )


def test_cpv_target_comes_from_signed_template_and_checks_existing_label():
    assert MODULE.cpv_target({"label": "1"}, 2.5) == 1
    assert MODULE.cpv_target({"label": "-1"}, -2.5) == -1
    with pytest.raises(ValueError, match="label/sign mismatch"):
        MODULE.cpv_target({"label": "1"}, -2.5)
    with pytest.raises(ValueError, match="finite and nonzero"):
        MODULE.cpv_target({}, 0.0)


def test_neutral_modes_change_only_background_training_membership(tmp_path: Path):
    path = tmp_path / "background.csv"
    write_rows(path, [background_row()])

    sm_only, _ = read_background(path, "sm")
    sm_plus_background, _ = read_background(path, "sm-plus-background")

    assert sm_only[0]["training_include"] == 0
    assert sm_only[0]["target_label"] == ""
    assert sm_plus_background[0]["training_include"] == 1
    assert sm_plus_background[0]["target_label"] == 0
    for column in (
        "event_id",
        "split_group",
        "split",
        "q_sel",
        "base_training_weight",
        "template_weight",
        "feature",
    ):
        assert sm_only[0][column] == sm_plus_background[0][column]
    assert sm_only[0]["split_group"] == "job-7"


def test_test_weight_projection_is_applied_and_auditable(tmp_path: Path):
    path = tmp_path / "background.csv"
    write_rows(path, [background_row("2.0")])
    rows, _ = read_background(
        path, "sm", {("background", "electron"): 3.5}
    )
    assert rows[0]["source_template_weight"] == 2.0
    assert rows[0]["test_weight_scale"] == 3.5
    assert rows[0]["template_weight"] == 7.0


def test_duplicate_identity_is_a_hard_failure(tmp_path: Path):
    path = tmp_path / "background.csv"
    row = background_row()
    write_rows(path, [row, row])
    with pytest.raises(ValueError, match="duplicate background event"):
        read_background(path, "sm")


def test_negative_background_template_weight_is_a_hard_failure(tmp_path: Path):
    path = tmp_path / "background.csv"
    write_rows(path, [background_row("-1.0")])
    with pytest.raises(ValueError, match="negative background weight_8ab"):
        read_background(path, "sm")


def test_zero_background_weight_is_preserved_for_inference(tmp_path: Path):
    path = tmp_path / "background.csv"
    write_rows(path, [background_row("0.0")])
    rows, _ = read_background(path, "sm")
    assert rows[0]["base_training_weight"] == 0.0
    assert rows[0]["template_weight"] == 0.0


def test_invalid_lepton_flavor_is_a_hard_failure(tmp_path: Path):
    path = tmp_path / "background.csv"
    row = background_row()
    row["lepton_flavor"] = "tau"
    write_rows(path, [row])
    with pytest.raises(ValueError, match="unexpected lepton_flavor"):
        read_background(path, "sm")


def test_split_is_deterministic_and_in_contract():
    first = MODULE.deterministic_split("chunk-17", 1234)
    assert first == MODULE.deterministic_split("chunk-17", 1234)
    assert first in {"train", "validation", "test"}


def test_dataset_level_test_split_overrides_hash_when_row_has_no_split():
    assert MODULE.resolved_split({}, "job-17", 1234, "test") == "test"


def test_explicit_inputs_require_a_declared_test_projection():
    args = Namespace(test_weights_already_8ab=False, test_weight_scale=None)
    with pytest.raises(SystemExit, match="require --test-weights-already-8ab"):
        MODULE.projection_contract(args, using_defaults=False)


def formal_rows(neutral_class: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for flavor in MODULE.FLAVORS:
        for split in ("train", "validation", "test"):
            for label in MODULE.CLASS_ORDER:
                rows.append(
                    {
                        "source_role": "sm" if label == 0 else "cpv",
                        "lepton_flavor": flavor,
                        "split": split,
                        "target_label": label,
                        "training_include": 1,
                        "base_training_weight": 1.0,
                        "template_weight": float(label) if label else 1.0,
                    }
                )
            if neutral_class == "sm-plus-background" or split == "test":
                rows.append(
                    {
                        "source_role": "background",
                        "lepton_flavor": flavor,
                        "split": split,
                        "target_label": (
                            0 if neutral_class == "sm-plus-background" else ""
                        ),
                        "training_include": int(
                            neutral_class == "sm-plus-background"
                        ),
                        "base_training_weight": 1.0,
                        "template_weight": 1.0,
                    }
                )
    return rows


@pytest.mark.parametrize("neutral_class", ["sm", "sm-plus-background"])
def test_formal_readiness_requires_background_test_coverage(neutral_class: str):
    rows = formal_rows(neutral_class)
    assert MODULE.formal_training_allowed(rows, neutral_class) == (True, [])
    for row in rows:
        if (
            row["source_role"] == "background"
            and row["lepton_flavor"] == "muon"
            and row["split"] == "test"
        ):
            row["template_weight"] = 0.0
    allowed, missing = MODULE.formal_training_allowed(rows, neutral_class)
    assert not allowed
    assert "background:muon:test:positive_weight" in missing


def test_scheme_two_requires_positive_background_train_and_validation_weight():
    rows = formal_rows("sm-plus-background")
    for row in rows:
        if row["source_role"] == "background" and row["split"] == "train":
            row["template_weight"] = 0.0
            row["base_training_weight"] = 0.0
    allowed, missing = MODULE.formal_training_allowed(rows, "sm-plus-background")
    assert not allowed
    assert "background:electron:train:positive_weight" in missing
    assert "background:muon:train:positive_weight" in missing


def test_scheme_two_requires_sm_separately_from_background():
    rows = formal_rows("sm-plus-background")
    for row in rows:
        if row["source_role"] == "sm" and row["split"] == "validation":
            row["template_weight"] = 0.0
            row["base_training_weight"] = 0.0
    allowed, missing = MODULE.formal_training_allowed(rows, "sm-plus-background")
    assert not allowed
    assert "sm:electron:validation:positive_weight" in missing
    assert "sm:muon:validation:positive_weight" in missing


def test_split_group_cannot_cross_splits():
    with pytest.raises(ValueError, match="appears in train and test"):
        MODULE.validate_groups(
            [
                {"split_group": "same-job", "split": "train"},
                {"split_group": "same-job", "split": "test"},
            ]
        )
