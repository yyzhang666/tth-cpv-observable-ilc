import csv
import json
from pathlib import Path

import pytest

from ilc_tth_cpv import model_scoring
from ilc_tth_cpv.model_scoring import WEIGHT_8AB_FACTOR, score_feature_table


class FakeModel:
    classes_ = [-1, 1]

    def __init__(self, flavor):
        self.flavor = flavor

    def predict_proba(self, rows):
        probability = [0.8, 0.2] if self.flavor == "electron" else [0.3, 0.7]
        return [probability for _row in rows]


def _models(tmp_path: Path, *, features=None, muon_features=None, classes=None) -> Path:
    root = tmp_path / "models"
    tag = "iter1000_d7_lr005_es50"
    features = features or ["f1", "f2"]
    for flavor in ("electron", "muon"):
        directory = root / flavor / tag
        directory.mkdir(parents=True)
        (directory / "cpv_catboost.cbm").write_bytes(f"{flavor}-model".encode())
        metadata = {
            "feature_list": muon_features if flavor == "muon" and muon_features else features,
            "class_order_model": classes if classes is not None else [-1, 1],
            "lepton_flavor": flavor,
        }
        (directory / "model_metadata.json").write_text(json.dumps(metadata))
    return root


def _input_table(
    tmp_path: Path,
    rows,
    *,
    component="interference",
    include_weight_8ab=False,
) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    columns = [
        "sample_name", "level", "event_id", "split", "lepton_flavor",
        "weight_template", "f1", "f2",
    ]
    if include_weight_8ab:
        columns.append("weight_8ab")
    table = tmp_path / f"{component}.csv"
    with table.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    metadata = {
        "component": component,
        "table": table.name,
        "columns": columns,
        "feature_list": ["f1", "f2"],
        "n_output_rows": len(rows),
    }
    table.with_suffix(".meta.json").write_text(json.dumps(metadata))
    return table


def _patch_models(monkeypatch):
    monkeypatch.setattr(
        model_scoring,
        "_load_catboost_model",
        lambda path: FakeModel(path.parents[1].name),
    )


def test_score_maps_classes_drops_nonfinite_derives_weight_and_preserves_order(
    tmp_path, monkeypatch
):
    _patch_models(monkeypatch)
    root = _models(tmp_path)
    rows = [
        {"sample_name": "s", "level": "reco", "event_id": "1", "split": "train", "lepton_flavor": "electron", "weight_template": "0.1", "f1": "1", "f2": "2"},
        {"sample_name": "s", "level": "reco", "event_id": "2", "split": "test", "lepton_flavor": "electron", "weight_template": "0.1", "f1": "3", "f2": "4"},
        {"sample_name": "s", "level": "reco", "event_id": "3", "split": "test", "lepton_flavor": "muon", "weight_template": "0.2", "f1": "5", "f2": "6"},
        {"sample_name": "s", "level": "reco", "event_id": "4", "split": "test", "lepton_flavor": "electron", "weight_template": "0.3", "f1": "nan", "f2": "7"},
    ]
    source = _input_table(tmp_path, rows)
    output = tmp_path / "scored.csv"
    score_feature_table(
        input_csv=source,
        component="interference",
        model_root=root,
        model_tag="iter1000_d7_lr005_es50",
        output=output,
    )

    with output.open(newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == [
            "sample_name", "level", "event_id", "split", "lepton_flavor",
            "weight_template", "f1", "f2", "p_plus", "p_minus",
            "q_CPV_wtype_v0", "weight_8ab",
        ]
        scored = list(reader)
    assert [row["event_id"] for row in scored] == ["2", "3"]
    assert float(scored[0]["p_minus"]) == pytest.approx(0.8)
    assert float(scored[0]["p_plus"]) == pytest.approx(0.2)
    assert float(scored[0]["q_CPV_wtype_v0"]) == pytest.approx(-0.6)
    assert float(scored[1]["q_CPV_wtype_v0"]) == pytest.approx(0.4)
    assert float(scored[0]["weight_8ab"]) == pytest.approx(0.1 * WEIGHT_8AB_FACTOR)
    assert float(scored[1]["weight_8ab"]) == pytest.approx(0.2 * WEIGHT_8AB_FACTOR)

    metadata = json.loads(output.with_suffix(".meta.json").read_text())
    assert metadata["feature_list"] == ["f1", "f2"]
    assert metadata["class_order_model"] == [-1, 1]
    assert metadata["probability_columns"] == {"p_minus": -1, "p_plus": 1}
    assert metadata["n_input_rows"] == 4
    assert metadata["n_test_rows"] == 3
    assert metadata["n_skipped_non_test"] == 1
    assert metadata["n_dropped_nonfinite"] == 1
    assert metadata["n_output_rows"] == 2
    assert metadata["feature_nonfinite_counts"] == {"f1": 1, "f2": 0}
    assert metadata["dropped_event_keys"][0]["event_id"] == "4"
    assert metadata["scored_flavor_counts"] == {"electron": 1, "muon": 1}
    assert metadata["weight_8ab"]["mode"] == "derived"


def test_existing_signal_weight_is_validated_and_preserved(tmp_path, monkeypatch):
    _patch_models(monkeypatch)
    root = _models(tmp_path)
    expected = 0.25 * WEIGHT_8AB_FACTOR
    rows = [{
        "sample_name": "sm", "level": "reco", "event_id": "1", "split": "test",
        "lepton_flavor": "electron", "weight_template": "0.25", "f1": "1", "f2": "2",
        "weight_8ab": repr(expected),
    }]
    source = _input_table(tmp_path, rows, component="sm", include_weight_8ab=True)
    output = tmp_path / "sm_scored.csv"
    score_feature_table(
        input_csv=source, component="sm", model_root=root,
        model_tag="iter1000_d7_lr005_es50", output=output,
    )
    with output.open(newline="") as handle:
        row = next(csv.DictReader(handle))
    assert row["weight_8ab"] == repr(expected)
    metadata = json.loads(output.with_suffix(".meta.json").read_text())
    assert metadata["weight_8ab"]["mode"] == "validated_existing"


def test_background_requires_finite_existing_weight(tmp_path, monkeypatch):
    _patch_models(monkeypatch)
    root = _models(tmp_path)
    row = {
        "sample_name": "bg", "level": "reco", "event_id": "1", "split": "test",
        "lepton_flavor": "muon", "weight_template": "nan", "f1": "1", "f2": "2",
    }
    missing = _input_table(tmp_path, [row], component="background")
    with pytest.raises(ValueError, match="requires an existing weight_8ab"):
        score_feature_table(
            input_csv=missing, component="background", model_root=root,
            model_tag="iter1000_d7_lr005_es50", output=tmp_path / "missing.csv",
        )

    row["weight_8ab"] = "12.5"
    existing = _input_table(
        tmp_path / "weighted", [row], component="background", include_weight_8ab=True
    )
    output = tmp_path / "background_scored.csv"
    score_feature_table(
        input_csv=existing, component="background", model_root=root,
        model_tag="iter1000_d7_lr005_es50", output=output,
    )
    with output.open(newline="") as handle:
        assert next(csv.DictReader(handle))["weight_8ab"] == "12.5"


def test_duplicate_component_mismatch_and_no_overwrite_are_fatal(tmp_path, monkeypatch):
    _patch_models(monkeypatch)
    root = _models(tmp_path)
    row = {"sample_name": "s", "level": "reco", "event_id": "1", "split": "test", "lepton_flavor": "electron", "weight_template": "0.1", "f1": "1", "f2": "2"}
    source = _input_table(tmp_path, [row, dict(row)])
    output = tmp_path / "duplicate.csv"
    with pytest.raises(ValueError, match="duplicate event key"):
        score_feature_table(
            input_csv=source, component="interference", model_root=root,
            model_tag="iter1000_d7_lr005_es50", output=output,
        )
    assert not output.exists()
    assert not output.with_suffix(".meta.json").exists()

    source = _input_table(tmp_path / "mismatch", [row], component="sm")
    with pytest.raises(ValueError, match="does not match requested"):
        score_feature_table(
            input_csv=source, component="interference", model_root=root,
            model_tag="iter1000_d7_lr005_es50", output=tmp_path / "mismatch.csv",
        )

    existing = tmp_path / "owned.csv"
    existing.write_text("owned\n")
    with pytest.raises(FileExistsError):
        score_feature_table(
            input_csv=tmp_path / "does_not_exist.csv", component="interference",
            model_root=root, model_tag="iter1000_d7_lr005_es50", output=existing,
        )
    assert existing.read_text() == "owned\n"


def test_model_metadata_and_runtime_class_contracts(tmp_path, monkeypatch):
    root = _models(tmp_path, muon_features=["f1", "different"])
    _patch_models(monkeypatch)
    with pytest.raises(ValueError, match="feature_list values differ"):
        model_scoring._load_models(root, "iter1000_d7_lr005_es50")

    root = _models(tmp_path / "classes")

    class ReversedModel(FakeModel):
        classes_ = [1, -1]

    monkeypatch.setattr(
        model_scoring, "_load_catboost_model",
        lambda path: ReversedModel(path.parents[1].name),
    )
    with pytest.raises(ValueError, match=r"classes must be \[-1, 1\]"):
        model_scoring._load_models(root, "iter1000_d7_lr005_es50")
