import math

import pytest

from ilc_tth_cpv.ml_features import (
    feature_columns_from_config,
    resolve_feature_value,
)


def test_feature_set_expansion_preserves_object_then_auxiliary_order():
    config = {
        "features": {
            "sets": {
                "chosen": {
                    "objects": {"lepton": ["E", "phi"], "top": ["mass"]},
                    "auxiliary": ["fit_chi2"],
                }
            }
        }
    }
    assert feature_columns_from_config(config, "chosen") == [
        "lepton_E",
        "lepton_phi",
        "top_mass",
        "fit_chi2",
    ]


def test_selected_w_likelihood_uses_orientation_decision():
    assert resolve_feature_value(
        {"w_orientation_status": "L12_preferred", "L12": "0.8", "L21": "0.2"},
        "w_assignment_likelihood_selected",
    ) == pytest.approx(0.8)
    assert resolve_feature_value(
        {"w_orientation_status": "L21_preferred", "L12": "0.8", "L21": "0.2"},
        "w_assignment_likelihood_selected",
    ) == pytest.approx(0.2)


def test_invalid_minus_one_down_type_indices_do_not_resolve_a_fake_feature():
    value = resolve_feature_value(
        {
            "idx_W_down_candidate": "-1",
            "idx_W_quark": "-1",
            "idx_W_antiquark": "5",
            "wjet_quark_phi": "0.7",
        },
        "down_type_daughter_phi",
    )
    assert math.isnan(value)


def test_second_w_daughter_and_neutrino_pt_fallbacks_match_frozen_formulae():
    row = {
        "idx_W_down_candidate": "4",
        "idx_W_quark": "4",
        "idx_W_antiquark": "5",
        "wjet_antiquark_E": "5",
        "wjet_antiquark_mass": "3",
        "wjet_antiquark_theta": str(math.pi / 2),
        "neutrino_E": "4",
        "neutrino_theta": str(math.pi / 6),
    }
    assert resolve_feature_value(row, "second_w_daughter_pt") == pytest.approx(4.0)
    assert resolve_feature_value(row, "neutrino_pt") == pytest.approx(2.0)
