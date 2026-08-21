import json
from types import SimpleNamespace
from pathlib import Path

import pytest

from scripts.mva.build_mva_group_materials import (
    build_record,
    catalog_strata,
    category_cutflow,
    coverage_closed_projection,
    exact_rows,
    exact_score_digest,
    missing_strata_details,
    parse_cutflow_source,
    projection_finalization,
    verify_production_summary,
    normalization_inventory,
    projection_rows,
    refuse_overwrite,
    roc_curve_rows,
    validate_stratified_coverage,
    weighted_threshold_scan,
)


def test_category_cutflow_arithmetic() -> None:
    evaluation = {
        "strata": {"test": {"analysis_category": {
            "tth-hbb": {"events": 10}, "tth-nonbb": {"events": 5},
        }}},
        "test_selected_yields": {"analysis_category": {
            "tth-hbb": {"events": 6, "expected_yield": 12.0},
            "tth-nonbb": {"events": 1, "expected_yield": 0.5},
        }},
    }
    rows = category_cutflow(evaluation)
    hbb = next(row for row in rows if row["category"] == "tth-hbb")
    assert hbb["events_before_threshold"] == 10
    assert hbb["events_pass"] == 6
    assert hbb["efficiency"] == pytest.approx(.6)
    assert hbb["test_yield"] == 12.0


def test_exact_mode_missing_stratum_fails() -> None:
    with pytest.raises(RuntimeError, match="MISSING_NORMALIZATION_CATEGORY_COVERAGE"):
        validate_stratified_coverage(
            [{"normalization_key": "eL.pR", "category": "tth-hbb"}],
            {("eL.pR", "tth-hbb"), ("eR.pL", "tth-hbb")},
        )


def test_output_directory_never_overwritten(tmp_path: Path) -> None:
    output = tmp_path / "material"
    output.mkdir()
    (output / "sentinel").write_text("keep")
    with pytest.raises(RuntimeError, match="Refusing to overwrite"):
        refuse_overwrite(output)
    assert (output / "sentinel").read_text() == "keep"


def test_reported_efficiency_arithmetic() -> None:
    assert (49688 / 84672) == pytest.approx(0.5868291761)


def test_test_s_b_z_reproduces_baseline(tmp_path: Path) -> None:
    evaluation = {
        "analysis_name": "baseline", "threshold": 0.954,
        "test_selected_yields": {"analysis_category": {
            "tth-hbb": {"expected_yield": 275.53}, "tth-nonbb": {"expected_yield": 10.0},
            "ttz": {"expected_yield": 50.0}, "ttbb": {"expected_yield": 40.0},
            "6q": {"expected_yield": 20.0}, "4f2l": {"expected_yield": 49.55},
        }},
    }
    evaluation_path = tmp_path / "evaluation.json"; evaluation_path.write_text(json.dumps(evaluation))
    config = tmp_path / "config.yaml"; config.write_text("model: {library: xgboost}\n")
    record = build_record(config, evaluation_path, tmp_path, [])
    assert record["test_S"] == pytest.approx(275.53)
    assert record["test_B"] == pytest.approx(169.55)
    assert record["test_Z"] == pytest.approx(13.06, abs=0.01)


def test_naive_projection_arithmetic() -> None:
    authority = SimpleNamespace(catalog_jobs={
        "s": {"sample_key": "tth-sm", "normalization_key": "eL.pR", "weight_phys": 2.0,
              "analysis_category_counts": {"tth-hbb": 100}},
        "b": {"sample_key": "ttz", "normalization_key": "eL.pR", "weight_phys": 1.0,
              "analysis_category_counts": {"ttz": 100}},
    })
    rows = ([{"sample_key": "tth-sm", "category": "tth-hbb", "normalization_key": "eL.pR", "score": 0.9}] * 6
            + [{"sample_key": "tth-sm", "category": "tth-hbb", "normalization_key": "eL.pR", "score": 0.1}] * 4
            + [{"sample_key": "ttz", "category": "ttz", "normalization_key": "eL.pR", "score": 0.9}] * 2
            + [{"sample_key": "ttz", "category": "ttz", "normalization_key": "eL.pR", "score": 0.1}] * 8)
    naive, _, missing = projection_rows(authority, rows, 0.5)
    assert next(row for row in naive if row["category"] == "tth-hbb")["projected_yield"] == pytest.approx(120.0)
    assert missing == []


def test_projection_excludes_cpv_control_rows() -> None:
    authority = SimpleNamespace(catalog_jobs={
        "sm": {"sample_key": "tth-sm", "normalization_key": "sm", "weight_phys": 1.0,
               "analysis_category_counts": {"tth-hbb": 100}},
    })
    rows = [
        {"sample_key": "tth-sm", "category": "tth-hbb", "normalization_key": "sm", "score": 0.9},
        {"sample_key": "tth-sm", "category": "tth-hbb", "normalization_key": "sm", "score": 0.1},
        {"sample_key": "tth-cpv", "category": "tth-hbb", "normalization_key": "cpv", "score": 0.9},
    ]
    naive, stratified, missing = projection_rows(authority, rows, 0.5)
    hbb = next(row for row in naive if row["category"] == "tth-hbb")
    assert hbb["test_efficiency"] == pytest.approx(0.5)
    assert hbb["projected_yield"] == pytest.approx(50.0)
    assert len(stratified) == 1
    assert missing == []


def test_inventory_uses_physical_field_names(tmp_path: Path) -> None:
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps({"normalizations": [{
        "sample_key": "tth-sm", "normalization_key": "sm::LR",
        "generator_events": 10, "cross_section_fb": 2.5,
        "effective_luminosity_fb_inv": 2576.0, "weight_phys": 644.0,
    }]}))
    row = normalization_inventory(path)[0]
    assert row["cross_section_fb"] == 2.5
    assert row["effective_luminosity_fb_inv"] == 2576.0


def test_exact_score_hdf5_join_checks_event_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import h5py
    import scripts.mva.build_mva_group_materials as builder
    source = tmp_path / "source.h5"; shard_dir = tmp_path / "scores"; shard_dir.mkdir()
    with h5py.File(source, "w") as target:
        target.create_dataset("event_index", data=[11, 12]); target.create_dataset("analysis_category", data=[b"tth-hbb", b"tth-hbb"])
    shard = shard_dir / "job.scores.h5"
    with h5py.File(shard, "w") as target:
        target.create_dataset("event_index", data=[11, 12]); target.create_dataset("score", data=[.9, .1])
        for key, value in {"complete": True, "job_key": "job", "sample_key": "tth-sm", "polarization": "eL.pR",
                           "n_events": 2, "source_hdf5": str(source), "source_hdf5_sha256": "h", "weights_catalog_hash": "c"}.items(): target.attrs[key] = value
    authority = SimpleNamespace(catalog_jobs={"job": {"sample_key": "tth-sm", "polarization": "eL.pR", "split": "test", "n_events": 2,
                                                       "hdf5_sha256": "h", "normalization_key": "eL.pR", "weight_phys": 1.0}}, catalog_hash="c")
    monkeypatch.setattr(builder, "selected_job_keys", lambda *args, **kwargs: ["job"])
    monkeypatch.setattr(builder, "validate_job_hdf5", lambda *args, **kwargs: (source, authority.catalog_jobs["job"], {}))
    rows = exact_rows(authority, shard_dir, include_cpv=False)
    assert [row["event_index"] for row in rows] == [11, 12]


def test_cutflow_source_and_production_summary_fail_closed(tmp_path: Path) -> None:
    source = tmp_path / "cutflow.md"
    rows = ["| group | files | input | accepted | fit_success |", "|---|---:|---:|---:|---:|"]
    for sample in ("tth-sm", "tth-cpv", "ttz", "ttbb", "6q", "4f2l"):
        rows.append(f"| {sample} | 1 | 1 | 2 | 3 |")
    source.write_text("\n".join(rows))
    assert parse_cutflow_source(source)["tth-sm"] == (1, 2, 3)
    source.write_text(source.read_text().replace("| 6q | 1 | 1 | 2 | 3 |", "| 6q | 1 | 1 | 2 | 9 |"))
    assert parse_cutflow_source(source)["6q"] == (1, 2, 9)
    authority = SimpleNamespace(catalog_jobs={"j": {"n_events": 2}})
    summary = tmp_path / "production.json"
    summary.write_text(json.dumps({"total_exported_events": 2, "jobs": [{"job_key": "j", "exported_events": 2}]}))
    audit = verify_production_summary(summary, authority)
    assert audit["jobs"] == 1
    assert audit["total_exported_events"] == 2
    assert len(audit["sha256"]) == 64
    summary.write_text(json.dumps({"total_exported_events": 3, "jobs": [{"job_key": "j", "exported_events": 3}]}))
    with pytest.raises(RuntimeError, match="production summary"):
        verify_production_summary(summary, authority)


def test_cutflow_source_accepts_backtick_4q2l_alias(tmp_path: Path) -> None:
    source = tmp_path / "handoff.md"
    lines = ["| group | files | input | accepted | fit_success |", "|---|---:|---:|---:|---:|"]
    for sample in ("tth-sm", "tth-cpv", "ttz", "ttbb", "6q"):
        lines.append(f"| `{sample}`（Physsim all-channel） | 1 | 1,974,649 | 734,477 | 734,443 |")
    lines.append("| `4q2l`（Whizard nIso=1） | 1 | 2,429,494 | 2,429,490 | 2,427,720 |")
    source.write_text("\n".join(lines))
    assert parse_cutflow_source(source)["4f2l"] == (2429494, 2429490, 2427720)


def test_projection_status_blocks_partial_stratified_publish() -> None:
    stratified = [{"projection_status": "complete_stratified"}]
    assert projection_finalization([{"full_pre_mva_yield": 4.0}], stratified) == "blocked_missing_strata"
    assert stratified[0]["projection_status"] == "partial_not_publishable"
    complete = [{"projection_status": "complete_stratified"}]
    assert projection_finalization([], complete) == "complete_stratified"


def test_exact_score_digest_binds_event_index_and_score() -> None:
    rows = [{"job_key": "j", "event_index": 1, "score": .1}, {"job_key": "j", "event_index": 2, "score": .9}]
    swapped = [{"job_key": "j", "event_index": 1, "score": .9}, {"job_key": "j", "event_index": 2, "score": .1}]
    assert exact_score_digest(rows) != exact_score_digest(swapped)


def test_weighted_threshold_scan_uses_physical_signal_efficiency() -> None:
    rows = [
        {"sample_key": "tth-sm", "category": "tth-hbb", "score": .8, "weight_phys": 2.0},
        {"sample_key": "tth-sm", "category": "tth-hbb", "score": .2, "weight_phys": 1.0},
        {"sample_key": "ttz", "category": "ttz", "score": .7, "weight_phys": 3.0},
        {"sample_key": "ttz", "category": "ttz", "score": .1, "weight_phys": 1.0},
    ]
    scan = weighted_threshold_scan(rows)
    at_half = scan[500]
    assert at_half["threshold"] == pytest.approx(.5)
    assert at_half["signal"] == pytest.approx(2.0)
    assert at_half["background"] == pytest.approx(3.0)
    assert at_half["signal_efficiency"] == pytest.approx(2 / 3)
    assert at_half["significance"] == pytest.approx(2 / (5 ** .5))


def test_roc_curve_matches_unweighted_auc_and_working_point() -> None:
    rows = [
        {"sample_key": "tth-sm", "category": "tth-hbb", "score": .9},
        {"sample_key": "tth-sm", "category": "tth-hbb", "score": .6},
        {"sample_key": "ttz", "category": "ttz", "score": .8},
        {"sample_key": "ttbb", "category": "ttbb", "score": .6},
        {"sample_key": "6q", "category": "6q", "score": .2},
        {"sample_key": "tth-cpv", "category": "tth-hbb", "score": .99},
    ]
    curve, summary = roc_curve_rows(rows, .7)
    assert curve[0]["false_positive_rate"] == 0.0
    assert curve[-1]["true_positive_rate"] == 1.0
    assert summary["auc"] == pytest.approx(.75)
    assert summary["true_positive_rate"] == pytest.approx(.5)
    assert summary["false_positive_rate"] == pytest.approx(1 / 3)
    assert summary["background_rejection"] == pytest.approx(2 / 3)
    assert summary["weighting"] == "unweighted_raw_test_events"


def test_missing_strata_table_and_coverage_bounds() -> None:
    authority = SimpleNamespace(catalog_jobs={
        "signal_test": {
            "sample_key": "tth-sm", "normalization_key": "sm", "process_mask": None,
            "polarization": "eL.pR", "split": "test", "weight_phys": 2.0,
            "analysis_category_counts": {"tth-hbb": 2},
        },
        "background_validation": {
            "sample_key": "4f2l", "normalization_key": "val", "process_mask": "v",
            "polarization": "eL.pR", "split": "validation", "weight_phys": 3.0,
            "analysis_category_counts": {"4f2l": 2},
        },
        "background_train": {
            "sample_key": "6q", "normalization_key": "train", "process_mask": "t",
            "polarization": "eR.pL", "split": "train", "weight_phys": 4.0,
            "analysis_category_counts": {"6q": 1},
        },
    })
    strata = catalog_strata(authority)
    fallback = [
        {"sample_key": "4f2l", "normalization_key": "val", "category": "4f2l", "split": "validation", "score": .9},
        {"sample_key": "4f2l", "normalization_key": "val", "category": "4f2l", "split": "validation", "score": .1},
        {"sample_key": "6q", "normalization_key": "train", "category": "6q", "split": "train", "score": .1},
    ]
    details = missing_strata_details(strata, fallback, .5)
    assert [row["coverage_class"] for row in details] == ["train_only", "validation_only"]
    assert sum(row["full_pre_mva_expected_yield_8ab"] for row in details) == pytest.approx(10.0)
    test_rows = [
        {"sample_key": "tth-sm", "normalization_key": "sm", "category": "tth-hbb", "split": "test", "score": .9},
        {"sample_key": "tth-sm", "normalization_key": "sm", "category": "tth-hbb", "split": "test", "score": .1},
    ]
    projection, summary = coverage_closed_projection(strata, test_rows, details, .5)
    central = next(row for row in summary if row["projection"] == "coverage_closed_central")
    all_pass = next(row for row in summary if row["projection"] == "train_only_all_pass")
    assert len(projection) == 3
    assert central["signal_Hbb"] == pytest.approx(2.0)
    assert central["background"] == pytest.approx(3.0)
    assert all_pass["background"] == pytest.approx(7.0)


def test_builder_hash_is_available() -> None:
    import scripts.mva.build_mva_group_materials as builder
    digest = builder.sha256_file(Path(builder.__file__).resolve())
    assert len(digest) == 64
