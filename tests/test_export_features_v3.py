from pathlib import Path

import pytest

from ilc_tth_cpv.reco_baseline import (
    RECO_BASELINE_COLUMNS,
    _project_row,
    baseline_output_path,
    export_reco_baseline,
)


def test_reco_baseline_schema_is_exactly_148_columns_in_frozen_order():
    expected = (
        (
            "event_id", "sample_name", "chunk", "process", "level", "helicity", "split",
            "weight_sm", "weight_sm_shape", "weight_interference_signed",
            "weight_interference_abs", "weight_quadratic", "weight_training",
            "weight_polarization", "weight_luminosity", "weight_template", "label",
            "run_number", "event_number", "event_index", "accepted", "fit_success",
            "fit_status", "best_combo_id", "idx_W1", "idx_W2", "idx_bhad", "idx_blep",
            "idx_H1", "idx_H2", "fitprob", "fitchi2", "ndof", "final_selection_mode",
            "flavor_weight", "final_selection_score", "final_fit_score",
            "final_flavor_score", "lepton_charge", "lepton_flavor",
            "best_preselect_score", "preselect_score_W", "preselect_score_top",
            "preselect_score_H", "constraint_mode", "mW_had_prefit", "mt_had_prefit",
            "mt_lep_prefit", "mH_prefit", "mW_had_postfit", "mt_had_postfit",
            "mt_lep_postfit", "mH_postfit",
        )
        + tuple(
            f"jet{slot}_{component}"
            for slot in range(6)
            for component in ("E", "px", "py", "pz")
        )
        + (
            "lepton_lab_E", "lepton_lab_px", "lepton_lab_py", "lepton_lab_pz",
            "nu_fit_E", "nu_fit_px", "nu_fit_py", "nu_fit_pz",
        )
        + tuple(
            f"jet{slot}_weaver_{key}"
            for slot in range(6)
            for key in (
                "mc_u", "mc_d", "mc_s", "mc_c", "mc_b",
                "mc_ubar", "mc_dbar", "mc_sbar", "mc_cbar", "mc_bbar",
            )
        )
        + ("truth_higgs_decay", "truth_ttbar_decay", "pass_truth_hbb")
    )
    assert RECO_BASELINE_COLUMNS == expected
    assert len(RECO_BASELINE_COLUMNS) == 148


def test_full_and_debug_output_names_are_distinct():
    out_dir = Path("somewhere")
    assert baseline_output_path(out_dir, "interference", "1", 0).name == (
        "features_reco_baseline_v3_interference_chunk1.csv"
    )
    assert baseline_output_path(out_dir, "interference", "1", 64).name == (
        "features_reco_baseline_v3_interference_chunk1_max64.csv"
    )


def test_projection_has_stable_schema_and_drops_extra_keys():
    projected = _project_row({"event_id": 7, "unexpected": 9})
    assert tuple(projected) == RECO_BASELINE_COLUMNS
    assert len(projected) == 148
    assert projected["event_id"] == 7
    assert "unexpected" not in projected


def test_default_refuses_existing_target_before_reading_inputs(tmp_path):
    target = baseline_output_path(tmp_path, "interference", "1", 64)
    target.write_text("already here\n")
    with pytest.raises(FileExistsError):
        export_reco_baseline(
            {},
            component="interference",
            chunk_id="1",
            out_dir=tmp_path,
            max_events=64,
        )
