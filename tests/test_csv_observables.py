import math

import pytest

from ilc_tth_cpv.csv_observables import CsvObservableError, compute_csv_angle


def test_o_lnu_charge_ordering():
    negative = {"lepton_charge": -1, "lepton_phi": 0.8, "neutrino_phi": -0.2}
    positive = {"lepton_charge": 1, "lepton_phi": 0.8, "neutrino_phi": -0.2}
    assert compute_csv_angle("O_lnu", negative) == pytest.approx(1.0)
    assert compute_csv_angle("O_lnu", positive) == pytest.approx(-1.0)


def test_registered_pair_orderings():
    row = {
        "top_side_fermion_phi": 0.9,
        "anti_top_side_fermion_phi": -0.4,
        "wjet_quark_phi": 0.7,
        "wjet_antiquark_phi": -0.6,
        "top_b_phi": 0.5,
        "antitop_bbar_phi": -0.8,
        "top_phi": 0.3,
        "antitop_phi": -1.0,
    }
    for name in ("O_lD", "O_W", "O_jj_W", "O_b", "O_top"):
        assert compute_csv_angle(name, row) == pytest.approx(1.3)


def test_wrap_and_missing_column_fail_closed():
    row = {"top_b_phi": math.pi - 0.1, "antitop_bbar_phi": -math.pi + 0.1}
    assert compute_csv_angle("O_b", row) == pytest.approx(-0.2)
    with pytest.raises(CsvObservableError):
        compute_csv_angle("O_top", row)
