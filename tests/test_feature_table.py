import csv
import json
import math
from pathlib import Path

import pytest

from ilc_tth_cpv import feature_table, flavor
from ilc_tth_cpv.feature_table import augment_feature_table, parse_chunk_spec
from ilc_tth_cpv.reco_baseline import (
    IDENTITY_COLUMNS,
    RECO_BASELINE_COLUMNS,
    WEAVER_SCORE_KEYS,
    WEIGHT_COLUMNS,
)


def _row(event_id: int, chunk: int) -> dict[str, object]:
    row = {column: "" for column in RECO_BASELINE_COLUMNS}
    row.update({
        "event_id": event_id,
        "sample_name": "tth_cpv_reco_elpr",
        "chunk": chunk,
        "process": "ttH_CPV_interference",
        "level": "reco",
        "helicity": "LR",
        "split": "test" if event_id % 2 else "train",
        "weight_sm": "nan",
        "weight_sm_shape": "nan",
        "weight_interference_signed": -0.5 if event_id % 2 else 0.5,
        "weight_interference_abs": 0.5,
        "weight_quadratic": "nan",
        "weight_training": 0.5,
        "weight_polarization": 1.0,
        "weight_luminosity": 1.0,
        "weight_template": 0.5,
        "label": -1 if event_id % 2 else 1,
        "lepton_flavor": "electron" if event_id % 2 else "muon",
        "lepton_charge": -1,
        "idx_W1": 0,
        "idx_W2": 1,
        "idx_bhad": 2,
        "idx_blep": 3,
        "idx_H1": 4,
        "idx_H2": 5,
        "fitchi2": 2.0,
        "ndof": 1.0,
        "final_selection_score": 0.9,
        "mH_postfit": 125.0,
        "mW_had_postfit": 80.0,
        "mt_had_postfit": 172.0,
        "mt_lep_postfit": 171.0,
        "lepton_lab_E": 20.0,
        "lepton_lab_px": 3.0,
        "lepton_lab_py": 4.0,
        "lepton_lab_pz": 10.0,
        "nu_fit_E": 18.0,
        "nu_fit_px": -2.0,
        "nu_fit_py": 3.0,
        "nu_fit_pz": -8.0,
        "pass_truth_hbb": 1,
    })
    p4s = (
        (45.0, 12.0, 3.0, 20.0),
        (40.0, -8.0, 6.0, -15.0),
        (55.0, 7.0, -5.0, 25.0),
        (50.0, -6.0, -4.0, -21.0),
        (70.0, 15.0, 8.0, 31.0),
        (65.0, -13.0, -7.0, -28.0),
    )
    for slot, values in enumerate(p4s):
        for name, value in zip(("E", "px", "py", "pz"), values):
            row[f"jet{slot}_{name}"] = value
        for score_index, key in enumerate(WEAVER_SCORE_KEYS):
            row[f"jet{slot}_weaver_{key}"] = 0.01 * (score_index + 1) + 0.001 * slot
    return row


def _write_source(
    directory: Path,
    chunk: int,
    rows: list[dict[str, object]],
    *,
    component: str = "interference",
) -> Path:
    table = directory / f"baseline_chunk{chunk}.csv"
    with table.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RECO_BASELINE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    metadata = {
        "schema_version": "reco_baseline_v3",
        "frame": "lab_raw",
        "level": "reco",
        "component": component,
        "status": "baseline_export",
        "max_events": 0,
        "n_columns": 148,
        "chunk": str(chunk),
        "table": table.name,
        "n_exported": len(rows),
        "missing_weaver_score_counts": {key: 0 for key in WEAVER_SCORE_KEYS},
        "n_event_number_mismatch": 0,
    }
    table.with_suffix(".meta.json").write_text(json.dumps(metadata))
    return table


def _config_file(tmp_path: Path) -> Path:
    path = tmp_path / "analysis.yaml"
    path.write_text("test: true\n")
    return path


def test_parse_chunk_spec_is_numeric_unique_and_sorted():
    assert parse_chunk_spec("3,1-2,2,7-8") == [1, 2, 3, 7, 8]
    for invalid in ("", "0", "2-1", "1,,2", "one", "1-2-3"):
        with pytest.raises(ValueError):
            parse_chunk_spec(invalid)


def test_streaming_output_order_columns_single_context_batch_and_nonfinite_counts(
    tmp_path, monkeypatch
):
    _write_source(tmp_path, 1, [_row(11, 1), _row(12, 1)])
    _write_source(tmp_path, 2, [_row(21, 2)])
    cfg = {
        "features": {"sets": {"tiny": {
            "objects": {"lepton": ["E"]},
            "auxiliary": ["final_selection_score"],
        }}}
    }
    calls = {"contexts": 0, "batches": 0}

    class CountingContext:
        def __init__(self, row):
            calls["contexts"] += 1
            self.row = row

    def resolve_once(context, names):
        calls["batches"] += 1
        assert isinstance(context, CountingContext)
        assert list(names) == ["lepton_E", "final_selection_score"]
        return {
            "lepton_E": float(context.row["event_id"]),
            "final_selection_score": (
                float("nan") if context.row["event_id"] == "12" else 0.9
            ),
        }

    monkeypatch.setattr(feature_table, "FeatureContext", CountingContext)
    monkeypatch.setattr(feature_table, "resolve_feature_values", resolve_once)
    output = tmp_path / "compact.csv"
    augment_feature_table(
        cfg,
        config_path=_config_file(tmp_path),
        feature_set="tiny",
        input_pattern=str(tmp_path / "baseline_chunk{chunk}.csv"),
        chunks=[2, 1],
        output=output,
    )

    with output.open(newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == (
            list(IDENTITY_COLUMNS) + list(WEIGHT_COLUMNS)
            + ["lepton_flavor", "lepton_E", "final_selection_score"]
        )
        rows = list(reader)
    assert [row["event_id"] for row in rows] == ["11", "12", "21"]
    assert calls == {"contexts": 3, "batches": 3}
    assert math.isnan(float(rows[1]["final_selection_score"]))
    metadata = json.loads(output.with_suffix(".meta.json").read_text())
    assert metadata["chunks"] == [1, 2]
    assert metadata["n_input_rows"] == metadata["n_output_rows"] == 3
    assert metadata["per_chunk_counts"] == {"1": 2, "2": 1}
    assert metadata["feature_nonfinite_counts"] == {
        "lepton_E": 0, "final_selection_score": 1,
    }
    assert metadata["compatibility"]["policy"] == "canonical"
    assert metadata["compatibility"]["total_changed_values"] == 0
    assert len(metadata["event_key_sha256"]) == 64
    assert len(metadata["sources"]) == 2
    assert set(metadata["provenance_sha256"]) == {
        str(path) for path in feature_table._provenance_paths(_config_file(tmp_path))
    }


def test_duplicate_aborts_without_publishing_pair(tmp_path):
    duplicate = _row(101, 1)
    _write_source(tmp_path, 1, [duplicate])
    duplicate_second = _row(101, 2)
    _write_source(tmp_path, 2, [duplicate_second])
    cfg = {"features": {"sets": {"tiny": {"auxiliary": ["m_H"]}}}}
    output = tmp_path / "duplicates.csv"
    with pytest.raises(ValueError, match="duplicate event key"):
        augment_feature_table(
            cfg,
            config_path=_config_file(tmp_path),
            feature_set="tiny",
            input_pattern=str(tmp_path / "baseline_chunk{chunk}.csv"),
            chunks=[1, 2],
            output=output,
        )
    assert not output.exists()
    assert not output.with_suffix(".meta.json").exists()
    assert not list(tmp_path.glob(".*duplicates*.tmp"))


def test_existing_output_refused_before_source_access(tmp_path):
    output = tmp_path / "exists.csv"
    output.write_text("owned\n")
    with pytest.raises(FileExistsError):
        augment_feature_table(
            {"features": {"sets": {"tiny": {"auxiliary": ["m_H"]}}}},
            config_path=_config_file(tmp_path),
            feature_set="tiny",
            input_pattern=str(tmp_path / "missing_chunk{chunk}.csv"),
            chunks=[1],
            output=output,
        )
    assert output.read_text() == "owned\n"
    assert not output.with_suffix(".meta.json").exists()


@pytest.mark.parametrize("compat_policy", ["canonical", "nana_v2_legacy"])
def test_original_38_feature_set_uses_no_v2_orientation(
    tmp_path, monkeypatch, compat_policy
):
    def forbidden(*args, **kwargs):
        raise AssertionError("orient_w_pair_v2 must not be called")

    monkeypatch.setattr(flavor, "orient_w_pair_v2", forbidden, raising=False)
    _write_source(tmp_path, 1, [_row(501, 1)])
    objects = {
        name: ["E", "pt", "theta", "phi"]
        for name in (
            "lepton", "neutrino", "top_side_fermion", "anti_top_side_fermion",
            "wjet_quark", "wjet_antiquark", "top_b", "antitop_bbar",
        )
    }
    cfg = {"features": {"sets": {"original": {
        "objects": objects,
        "auxiliary": [
            "lepton_charge", "w_assignment_likelihood_selected",
            "final_selection_score", "m_H", "m_ttbar", "down_jet_mass",
        ],
    }}}}
    output = tmp_path / f"original_{compat_policy}.csv"
    augment_feature_table(
        cfg,
        config_path=_config_file(tmp_path),
        feature_set="original",
        input_pattern=str(tmp_path / "baseline_chunk{chunk}.csv"),
        chunks=[1],
        output=output,
        compat_policy=compat_policy,
    )
    metadata = json.loads(output.with_suffix(".meta.json").read_text())
    assert len(metadata["feature_list"]) == 38
    assert metadata["n_columns"] == 56
    assert metadata["n_output_rows"] == 1
    assert metadata["compatibility"]["policy"] == compat_policy


def test_metadata_contract_failure_is_atomic(tmp_path):
    source = _write_source(tmp_path, 1, [_row(701, 1)])
    metadata_path = source.with_suffix(".meta.json")
    metadata = json.loads(metadata_path.read_text())
    metadata["component"] = "sm"
    metadata_path.write_text(json.dumps(metadata))
    output = tmp_path / "invalid.csv"
    with pytest.raises(ValueError, match="component"):
        augment_feature_table(
            {"features": {"sets": {"tiny": {"auxiliary": ["m_H"]}}}},
            config_path=_config_file(tmp_path),
            feature_set="tiny",
            input_pattern=str(tmp_path / "baseline_chunk{chunk}.csv"),
            chunks=[1],
            output=output,
        )
    assert not output.exists()
    assert not output.with_suffix(".meta.json").exists()


def test_sm_component_is_validated_and_recorded(tmp_path):
    _write_source(tmp_path, 1, [_row(711, 1)], component="sm")
    output = tmp_path / "sm.csv"
    augment_feature_table(
        {"features": {"sets": {"tiny": {"auxiliary": ["m_H"]}}}},
        config_path=_config_file(tmp_path),
        feature_set="tiny",
        input_pattern=str(tmp_path / "baseline_chunk{chunk}.csv"),
        chunks=[1],
        output=output,
        component="sm",
    )
    metadata = json.loads(output.with_suffix(".meta.json").read_text())
    assert metadata["component"] == "sm"


def test_legacy_policy_replaces_pt_invalidates_whole_block_and_preserves_aux(
    tmp_path, monkeypatch
):
    _write_source(tmp_path, 33, [_row(801, 33), _row(802, 33)])
    cfg = {"features": {"sets": {"legacy": {
        "objects": {"lepton": ["E", "pt", "theta", "phi", "mass", "valid"]},
        "auxiliary": ["final_selection_score"],
    }}}}
    calls = {"contexts": 0, "batches": 0}

    class CountingContext:
        def __init__(self, row):
            calls["contexts"] += 1
            self.row = row

    def resolve_once(context, names):
        calls["batches"] += 1
        assert isinstance(context, CountingContext)
        result = {name: 0.0 for name in names}
        for family in feature_table.LEGACY_FAMILIES:
            result[f"{family}_E"] = 5.0
            result[f"{family}_theta"] = math.pi / 2.0
            result[f"{family}_phi"] = 0.2
            result[f"{family}_mass"] = 3.0
            result[f"{family}_valid"] = 1.0
        result["lepton_pt"] = 99.0
        result["final_selection_score"] = (
            0.81 if context.row["event_id"] == "801" else 0.82
        )
        if context.row["event_id"] == "802":
            result["lepton_valid"] = 0.0
        return result

    def forbidden(*args, **kwargs):
        raise AssertionError("orient_w_pair_v2 must not be called")

    monkeypatch.setattr(feature_table, "FeatureContext", CountingContext)
    monkeypatch.setattr(feature_table, "resolve_feature_values", resolve_once)
    monkeypatch.setattr(flavor, "orient_w_pair_v2", forbidden, raising=False)
    output = tmp_path / "legacy.csv"
    augment_feature_table(
        cfg,
        config_path=_config_file(tmp_path),
        feature_set="legacy",
        input_pattern=str(tmp_path / "baseline_chunk{chunk}.csv"),
        chunks=[33],
        output=output,
        compat_policy="nana_v2_legacy",
    )

    with output.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert calls == {"contexts": 2, "batches": 2}
    assert float(rows[0]["lepton_pt"]) == pytest.approx(4.0)
    assert float(rows[0]["final_selection_score"]) == pytest.approx(0.81)
    for field in ("E", "pt", "theta", "phi", "mass"):
        assert math.isnan(float(rows[1][f"lepton_{field}"]))
    assert float(rows[1]["lepton_valid"]) == 0.0
    assert float(rows[1]["final_selection_score"]) == pytest.approx(0.82)

    metadata = json.loads(output.with_suffix(".meta.json").read_text())
    compat = metadata["compatibility"]
    assert compat["policy"] == "nana_v2_legacy"
    assert compat["version"] == "nana_v2_legacy_v2"
    assert compat["version_number"] == 2
    assert compat["legacy_pt_chunks"] == [33, 67]
    assert compat["invalidation_scope"] == "all_chunks"
    assert compat["per_family_counts"]["lepton"] == {
        "pt_replacements": 1, "invalidations": 1,
    }
    assert compat["per_feature_changed_counts"] == {
        "lepton_E": 1,
        "lepton_pt": 2,
        "lepton_theta": 1,
        "lepton_phi": 1,
        "lepton_mass": 1,
        "lepton_valid": 0,
        "final_selection_score": 0,
    }
    assert compat["total_changed_values"] == 6
    assert compat["per_chunk_transform_counts"]["33"] == {
        "rows": 2,
        "invalidated_objects": 1,
        "pt_applications": 1,
        "changed_cells": 6,
    }
    assert metadata["feature_nonfinite_counts"] == {
        "lepton_E": 1,
        "lepton_pt": 1,
        "lepton_theta": 1,
        "lepton_phi": 1,
        "lepton_mass": 1,
        "lepton_valid": 0,
        "final_selection_score": 0,
    }
    assert metadata["n_input_rows"] == metadata["n_output_rows"] == 2


def test_legacy_pt_is_heterogeneous_only_for_archived_chunks(tmp_path, monkeypatch):
    chunks = [1, 32, 33, 67, 68]
    for chunk in chunks:
        _write_source(tmp_path, chunk, [_row(9000 + chunk, chunk)])
    cfg = {"features": {"sets": {"legacy": {
        "objects": {"lepton": ["pt"]},
        "auxiliary": ["final_selection_score"],
    }}}}

    class Context:
        def __init__(self, row):
            self.row = row

    def resolved(context, names):
        result = {name: 0.0 for name in names}
        for family in feature_table.LEGACY_FAMILIES:
            result[f"{family}_E"] = 5.0
            result[f"{family}_theta"] = math.pi / 2.0
            result[f"{family}_phi"] = 0.2
            result[f"{family}_mass"] = 3.0
            result[f"{family}_valid"] = 1.0
        result["lepton_pt"] = 99.0
        result["final_selection_score"] = 0.75
        return result

    def forbidden(*args, **kwargs):
        raise AssertionError("orient_w_pair_v2 must not be called")

    monkeypatch.setattr(feature_table, "FeatureContext", Context)
    monkeypatch.setattr(feature_table, "resolve_feature_values", resolved)
    monkeypatch.setattr(flavor, "orient_w_pair_v2", forbidden, raising=False)
    output = tmp_path / "heterogeneous.csv"
    augment_feature_table(
        cfg,
        config_path=_config_file(tmp_path),
        feature_set="legacy",
        input_pattern=str(tmp_path / "baseline_chunk{chunk}.csv"),
        chunks=list(reversed(chunks)),
        output=output,
        compat_policy="nana_v2_legacy",
    )

    with output.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [int(row["chunk"]) for row in rows] == chunks
    by_chunk = {int(row["chunk"]): float(row["lepton_pt"]) for row in rows}
    assert by_chunk == {
        1: 99.0,
        32: 99.0,
        33: pytest.approx(4.0),
        67: pytest.approx(4.0),
        68: 99.0,
    }
    metadata = json.loads(output.with_suffix(".meta.json").read_text())
    compat = metadata["compatibility"]
    assert compat["total_changed_values"] == 2
    assert compat["per_chunk_transform_counts"]["1"]["changed_cells"] == 0
    assert compat["per_chunk_transform_counts"]["32"]["pt_applications"] == 0
    assert compat["per_chunk_transform_counts"]["33"]["pt_applications"] == 1
    assert compat["per_chunk_transform_counts"]["67"]["pt_applications"] == 1
    assert compat["per_chunk_transform_counts"]["68"]["pt_applications"] == 0


@pytest.mark.parametrize("row_chunk", [1, 33])
def test_legacy_invalid_object_is_invalidated_before_any_pt_formula(row_chunk):
    features = [
        "lepton_E", "lepton_pt", "lepton_theta", "lepton_phi",
        "lepton_mass", "lepton_valid",
    ]
    resolved = {}
    for family in feature_table.LEGACY_FAMILIES:
        resolved.update({
            f"{family}_E": 5.0,
            f"{family}_theta": math.pi / 2.0,
            f"{family}_phi": 0.2,
            f"{family}_mass": 3.0,
            f"{family}_valid": 1.0,
        })
    resolved["lepton_pt"] = 99.0
    resolved["lepton_valid"] = 0.0
    family_counts = {
        family: {"pt_replacements": 0, "invalidations": 0}
        for family in feature_table.LEGACY_FAMILIES
    }
    changed_counts = {feature: 0 for feature in features}
    transformed, changed, invalidated, pt_applications = (
        feature_table._apply_legacy_policy(
            resolved, features, row_chunk, family_counts, changed_counts
        )
    )
    for field in ("E", "pt", "theta", "phi", "mass"):
        assert math.isnan(transformed[f"lepton_{field}"])
    assert transformed["lepton_valid"] == 0.0
    assert changed == 5
    assert invalidated == 1
    assert pt_applications == 0
    assert family_counts["lepton"] == {
        "pt_replacements": 0, "invalidations": 1,
    }


@pytest.mark.parametrize(
    ("row_chunk", "message"),
    [("2", "does not match source chunk"), ("1.0", "canonical positive integer"), ("01", "canonical positive integer")],
)
def test_row_chunk_must_be_canonical_integer_and_match_source(
    tmp_path, row_chunk, message
):
    row = _row(9501, 1)
    row["chunk"] = row_chunk
    _write_source(tmp_path, 1, [row])
    output = tmp_path / "bad_chunk.csv"
    with pytest.raises(ValueError, match=message):
        augment_feature_table(
            {"features": {"sets": {"tiny": {"auxiliary": ["m_H"]}}}},
            config_path=_config_file(tmp_path),
            feature_set="tiny",
            input_pattern=str(tmp_path / "baseline_chunk{chunk}.csv"),
            chunks=[1],
            output=output,
        )
    assert not output.exists()
    assert not output.with_suffix(".meta.json").exists()
