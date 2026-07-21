"""Tests for reco signed-flavor object ordering."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from ilc_tth_cpv.flavor import orient_w_pair


def scores(q, qbar, b=0.0):
    return {
        "mc_u": q,
        "mc_d": 0.0,
        "mc_s": 0.0,
        "mc_c": 0.0,
        "mc_ubar": qbar,
        "mc_dbar": 0.0,
        "mc_sbar": 0.0,
        "mc_cbar": 0.0,
        "mc_b": b,
    }


def test_orient_opposite_preferences():
    result = orient_w_pair(scores(0.7, 0.1), scores(0.1, 0.6))
    assert (result["quark_slot"], result["antiquark_slot"]) == (0, 1)
    assert result["status"] == "opposite_preferences"


def test_orient_two_q_like_jets_uses_stronger_quark_score():
    result = orient_w_pair(scores(0.4, 0.1), scores(0.8, 0.2))
    assert (result["quark_slot"], result["antiquark_slot"]) == (1, 0)
    assert result["status"] == "both_q_like"


def test_orient_two_qbar_like_jets_uses_stronger_antiquark_score():
    result = orient_w_pair(scores(0.2, 0.5), scores(0.1, 0.8))
    assert (result["quark_slot"], result["antiquark_slot"]) == (0, 1)
    assert result["status"] == "both_qbar_like"


def test_two_q_like_jets_compare_pq_not_signed_difference():
    result = orient_w_pair(scores(0.60, 0.59), scores(0.30, 0.10))
    assert (result["quark_slot"], result["antiquark_slot"]) == (0, 1)


def test_two_qbar_like_jets_compare_pqbar_not_signed_difference():
    result = orient_w_pair(scores(0.59, 0.60), scores(0.10, 0.30))
    assert (result["quark_slot"], result["antiquark_slot"]) == (1, 0)


def test_orient_ignores_high_b_probability():
    result = orient_w_pair(scores(0.2, 0.1, b=0.69), scores(0.1, 0.3, b=0.59))
    assert (result["quark_slot"], result["antiquark_slot"]) == (0, 1)


def test_orient_tie_is_deterministic_and_labelled():
    result = orient_w_pair(scores(0.2, 0.1), scores(0.2, 0.1))
    assert (result["quark_slot"], result["antiquark_slot"]) == (0, 1)
    assert result["status"] == "tie_slot_order"


def test_orient_rejects_missing_light_scores():
    with pytest.raises(ValueError, match="missing Weaver"):
        orient_w_pair({"mc_u": 0.5}, scores(0.1, 0.4))
