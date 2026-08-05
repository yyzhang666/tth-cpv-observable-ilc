"""Tests for truth-topology and down-type-daughter tests."""

### === Still work in progress (Aug 3rd)!!! Not exactly sure how to implement this === ###

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest
from ilc_tth_cpv.slcio import pdg

from ilc_tth_cpv.objects import identify_semileptonic_truth


def test_topology_w_bosons_from_correct_top(mc_list):
    """Verify that "W+ comes from top, W- comes from antitop."""
    truth = identify_semileptonic_truth(mc_list)

    assert pdg(truth.w_plus) == 24
    assert pdg(truth.w_minus) == -24


def charge_sign(pdg_id: int) -> int:
    """+1 or -1, matching electric-charge sign for leptons and down-type quarks
    (positive PDG id = particle = negative charge, for both cases)."""
    return -1 if pdg_id > 0 else 1

def test_lepton_downtype_quark_charge_pairing(mc_list):
    """Isolated lepton and hadronic-W down-type quark must have opposite
    electric charge, per SM ttbar decay kinematics
    (W+ -> l+ nu paired with W- -> d qbar', and vice versa)."""

    truth = identify_semileptonic_truth(mc_list)

    assert truth.lepton is not None, "No leptonic W found in this event"
    assert truth.down_type_daughter is not None, "No down-type daughter found"

    lepton_pdg = pdg(truth.lepton)
    down_pdg   = pdg(truth.down_type_daughter)

    lepton_charge_sign    = charge_sign(lepton_pdg)
    down_type_charge_sign = charge_sign(down_pdg)

    assert lepton_charge_sign != down_type_charge_sign
