import math

import pytest

from ilc_tth_cpv import angles, frames, input_features
from ilc_tth_cpv.input_features import (
    FeatureContext,
    materialize_v2_canonical_fields,
    resolve_feature_value,
    resolve_feature_values,
)
from ilc_tth_cpv.reco_baseline import WEAVER_SCORE_KEYS


def _scores(q: float, qbar: float) -> dict[str, float]:
    values = {key: 0.0 for key in WEAVER_SCORE_KEYS}
    for key in ("mc_u", "mc_d", "mc_s", "mc_c"):
        values[key] = q / 4.0
    for key in ("mc_ubar", "mc_dbar", "mc_sbar", "mc_cbar"):
        values[key] = qbar / 4.0
    return values


def _baseline_row(charge: int = -1, *, swap_orientation: bool = False, tie: bool = False):
    row = {
        "idx_W1": 0,
        "idx_W2": 1,
        "idx_bhad": 2,
        "idx_blep": 3,
        "idx_H1": 4,
        "idx_H2": 5,
        "lepton_charge": charge,
        "lepton_lab_E": 35.0,
        "lepton_lab_px": 10.0,
        "lepton_lab_py": 5.0,
        "lepton_lab_pz": 20.0,
        "nu_fit_E": 30.0,
        "nu_fit_px": -8.0,
        "nu_fit_py": 6.0,
        "nu_fit_pz": -15.0,
        "fitchi2": 12.0,
        "ndof": 4.0,
        "mW_had_postfit": 80.1,
        "mt_had_postfit": 173.2,
        "mt_lep_postfit": 171.8,
        "mH_postfit": 124.25,
    }
    p4s = (
        (45.0, 20.0, 5.0, 30.0),
        (38.0, -15.0, 9.0, -20.0),
        (55.0, 12.0, -18.0, 40.0),
        (50.0, -10.0, -15.0, -35.0),
        (70.0, 18.0, 8.0, 25.0),
        (65.0, -12.0, 4.0, -20.0),
    )
    for slot, p4 in enumerate(p4s):
        for suffix, value in zip(("E", "px", "py", "pz"), p4):
            row[f"jet{slot}_{suffix}"] = value
    if tie:
        pair = (_scores(0.4, 0.3), _scores(0.4, 0.3))
    elif swap_orientation:
        pair = (_scores(0.1, 0.7), _scores(0.8, 0.1))
    else:
        pair = (_scores(0.8, 0.1), _scores(0.1, 0.7))
    all_scores = pair + tuple(_scores(0.2, 0.2) for _ in range(4))
    for slot, scores in enumerate(all_scores):
        for key, value in scores.items():
            row[f"jet{slot}_weaver_{key}"] = value
    return row


@pytest.mark.parametrize(
    ("swap", "expected_status", "expected_quark", "expected_antiquark"),
    ((False, "L12_preferred", 0, 1), (True, "L21_preferred", 1, 0)),
)
def test_w_orientation_and_selected_likelihood(swap, expected_status, expected_quark, expected_antiquark):
    derived = materialize_v2_canonical_fields(_baseline_row(swap_orientation=swap))
    assert derived["w_orientation_status"] == expected_status
    assert derived["idx_W_quark"] == expected_quark
    assert derived["idx_W_antiquark"] == expected_antiquark
    assert derived["w_assignment_likelihood_selected"] == pytest.approx(
        derived["L12"] if expected_status == "L12_preferred" else derived["L21"]
    )


def test_tie_orientation_is_slot_order_and_has_no_selected_likelihood():
    derived = materialize_v2_canonical_fields(_baseline_row(tie=True))
    assert derived["w_orientation_status"] == "tie_slot_order"
    assert derived["idx_W_quark"] == 0
    assert derived["idx_W_antiquark"] == 1
    assert math.isnan(resolve_feature_value(_baseline_row(tie=True), "w_assignment_likelihood_selected"))


@pytest.mark.parametrize(
    ("charge", "top_b_index", "down_index", "expected_lnu_order"),
    ((-1, 2, 1, ("lepton_phi", "neutrino_phi")), (1, 3, 0, ("neutrino_phi", "lepton_phi"))),
)
def test_charge_mapping_higgs_rest_objects_aliases_and_angles(charge, top_b_index, down_index, expected_lnu_order):
    row = _baseline_row(charge)
    derived = materialize_v2_canonical_fields(row)
    assert derived["idx_W_down_candidate"] == down_index
    assert derived["top_b_mass"] == pytest.approx(frames.invariant_mass(tuple(row[f"jet{top_b_index}_{x}"] for x in ("E", "px", "py", "pz"))))
    assert derived["higgs_pt"] == pytest.approx(0.0, abs=1e-12)
    assert derived["m_H"] == pytest.approx(124.25)
    assert derived["higgs_mass"] != pytest.approx(derived["m_H"])
    assert derived["O_jj"] == pytest.approx(angles.delta_phi(derived["wjet_quark_phi"], derived["wjet_antiquark_phi"]))
    assert derived["O_lD"] == pytest.approx(angles.delta_phi(derived["top_side_fermion_phi"], derived["anti_top_side_fermion_phi"]))
    assert derived["O_b"] == pytest.approx(angles.delta_phi(derived["top_b_phi"], derived["antitop_bbar_phi"]))
    assert derived["O_top"] == pytest.approx(angles.delta_phi(derived["top_phi"], derived["antitop_phi"]))
    assert derived["O_lnu"] == pytest.approx(angles.delta_phi(derived[expected_lnu_order[0]], derived[expected_lnu_order[1]]))


EXPECTED_ANGLE_OPERANDS = {
    -1: {
        "O_lnu": ("lepton_phi", "neutrino_phi"),
        "O_jj": ("wjet_quark_phi", "wjet_antiquark_phi"),
        "O_lD": ("wjet_antiquark_phi", "lepton_phi"),
        "O_lU": ("lepton_phi", "wjet_quark_phi"),
        "O_nuD": ("wjet_antiquark_phi", "neutrino_phi"),
        "O_nuU": ("wjet_quark_phi", "neutrino_phi"),
        "O_b": ("top_b_phi", "antitop_bbar_phi"),
        "O_lb": ("lepton_phi", "top_b_phi"),
        "O_lbbar": ("lepton_phi", "antitop_bbar_phi"),
        "O_nub": ("top_b_phi", "neutrino_phi"),
        "O_nubbar": ("antitop_bbar_phi", "neutrino_phi"),
        "O_Db": ("top_b_phi", "wjet_antiquark_phi"),
        "O_Dbbar": ("antitop_bbar_phi", "wjet_antiquark_phi"),
        "O_Ub": ("wjet_quark_phi", "top_b_phi"),
        "O_Ubbar": ("wjet_quark_phi", "antitop_bbar_phi"),
    },
    1: {
        "O_lnu": ("neutrino_phi", "lepton_phi"),
        "O_jj": ("wjet_quark_phi", "wjet_antiquark_phi"),
        "O_lD": ("lepton_phi", "wjet_quark_phi"),
        "O_lU": ("wjet_antiquark_phi", "lepton_phi"),
        "O_nuD": ("neutrino_phi", "wjet_quark_phi"),
        "O_nuU": ("neutrino_phi", "wjet_antiquark_phi"),
        "O_b": ("top_b_phi", "antitop_bbar_phi"),
        "O_lb": ("top_b_phi", "lepton_phi"),
        "O_lbbar": ("antitop_bbar_phi", "lepton_phi"),
        "O_nub": ("neutrino_phi", "top_b_phi"),
        "O_nubbar": ("neutrino_phi", "antitop_bbar_phi"),
        "O_Db": ("wjet_quark_phi", "top_b_phi"),
        "O_Dbbar": ("wjet_quark_phi", "antitop_bbar_phi"),
        "O_Ub": ("top_b_phi", "wjet_antiquark_phi"),
        "O_Ubbar": ("antitop_bbar_phi", "wjet_antiquark_phi"),
    },
}


@pytest.mark.parametrize("charge", (-1, 1))
def test_all_15_angles_use_exact_charge_ordered_operands(monkeypatch, charge):
    context = FeatureContext(_baseline_row(charge))
    expected_values = {
        name: tuple(context.resolve(feature) for feature in pair)
        for name, pair in EXPECTED_ANGLE_OPERANDS[charge].items()
    }
    for name, pair in expected_values.items():
        assert context.resolve(name) == pytest.approx(angles.delta_phi(*pair))

    context = FeatureContext(_baseline_row(charge))
    observed = []

    def record_delta(first, second):
        observed.append((first, second))
        return float(len(observed))

    monkeypatch.setattr(input_features.angles, "delta_phi", record_delta)
    for index, name in enumerate(EXPECTED_ANGLE_OPERANDS[charge], start=1):
        assert context.resolve(name) == float(index)
        assert observed[-1] == pytest.approx(expected_values[name])


@pytest.mark.parametrize("charge", (-1, 1))
def test_O_lD_preserves_historical_top_minus_antitop_sign(charge):
    context = FeatureContext(_baseline_row(charge))
    assert context.resolve("O_lD") == pytest.approx(
        angles.delta_phi(
            context.resolve("top_side_fermion_phi"),
            context.resolve("anti_top_side_fermion_phi"),
        )
    )


@pytest.mark.parametrize("charge", (0, float("nan"), None))
def test_invalid_charge_only_allows_O_jj(charge):
    row = _baseline_row()
    if charge is None:
        row.pop("lepton_charge")
    else:
        row["lepton_charge"] = charge
    context = FeatureContext(row)
    assert context.resolve("O_jj") == pytest.approx(
        angles.delta_phi(
            context.resolve("wjet_quark_phi"),
            context.resolve("wjet_antiquark_phi"),
        )
    )
    charge_dependent = tuple(
        name for name in EXPECTED_ANGLE_OPERANDS[-1] if name != "O_jj"
    )
    assert all(math.isnan(context.resolve(name)) for name in charge_dependent)


def test_O_jj_replaces_base_O_W_but_direct_and_v2_paths_remain():
    row = _baseline_row()
    derived = materialize_v2_canonical_fields(row)
    assert "O_jj" in derived
    assert "O_W" not in derived
    assert "O_jj" in input_features._EXACT_REGISTRY
    assert "O_W" not in input_features._EXACT_REGISTRY
    assert math.isnan(resolve_feature_value(row, "O_W"))
    row["O_W"] = 0.123456789
    row["O_jj"] = -0.25
    assert resolve_feature_value(row, "O_W") == pytest.approx(0.123456789)
    assert resolve_feature_value(row, "O_jj") == pytest.approx(-0.25)
    assert math.isfinite(resolve_feature_value(row, "O_W_v2"))
    assert math.isfinite(resolve_feature_value(row, "O_lD_v2"))


@pytest.mark.parametrize(
    ("charge", "expected_fermion", "expected_antifermion"),
    ((-1, "lepton", "neutrino"), (1, "neutrino", "lepton")),
)
def test_lnu_fermion_and_lnu_antifermion_follow_charge_mapping(
    charge, expected_fermion, expected_antifermion
):
    context = FeatureContext(_baseline_row(charge))
    for variable in ("E", "pt", "theta", "phi"):
        assert context.resolve(f"lnu_fermion_{variable}") == pytest.approx(
            context.resolve(f"{expected_fermion}_{variable}")
        )
        assert context.resolve(f"lnu_antifermion_{variable}") == pytest.approx(
            context.resolve(f"{expected_antifermion}_{variable}")
        )


@pytest.mark.parametrize("charge", (0, float("nan")))
def test_lnu_fermion_and_lnu_antifermion_invalid_charge_is_nan(charge):
    names = tuple(
        f"{alias}_{variable}"
        for alias in ("lnu_fermion", "lnu_antifermion")
        for variable in ("E", "pt", "theta", "phi")
    )
    values = resolve_feature_values(_baseline_row(charge), names)
    assert all(math.isnan(value) for value in values.values())


def test_direct_first_batch_and_context_cache_semantics(monkeypatch):
    row = _baseline_row()
    context = FeatureContext(row)
    monkeypatch.setattr(
        "ilc_tth_cpv.input_features.flavor.orient_w_pair",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("orientation must stay lazy")
        ),
    )
    monkeypatch.setattr(
        "ilc_tth_cpv.input_features.frames.boost_to_rest",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("boost must stay lazy")
        ),
    )
    assert resolve_feature_values(context, ("m_H", "chi2_over_ndof")) == {
        "m_H": 124.25,
        "chi2_over_ndof": 3.0,
    }
    assert set(context._resolved) == {"m_H", "chi2_over_ndof"}
    assert context._intermediate == {}

    assert context.resolve("m_top_had") == pytest.approx(173.2)
    assert set(context._resolved) == {"m_H", "chi2_over_ndof", "m_top_had"}
    assert context._intermediate == {}
    row["mt_had_postfit"] = 180.0
    assert context.resolve("m_top_had") == pytest.approx(173.2)
    assert FeatureContext(row).resolve("m_top_had") == pytest.approx(180.0)


def test_invalid_selected_index_yields_invalid_canonical_object():
    row = _baseline_row()
    row["idx_W1"] = 9
    derived = materialize_v2_canonical_fields(row)
    assert derived["wjet_quark_valid"] == 0
    assert math.isnan(derived["O_jj"])
