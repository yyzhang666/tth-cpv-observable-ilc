"""Authoritative row-level ML input-feature resolution.

CSV columns are always preferred when they contain a finite numeric value.
The small resolver registry below only supplies the frozen calculations needed
by existing ML superdatasets when a materialized column is absent or invalid.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from ilc_tth_cpv import angles, flavor, frames

NAN = float("nan")

CANONICAL_OBJECTS = (
    "wjet_quark",
    "wjet_antiquark",
    "top_side_fermion",
    "anti_top_side_fermion",
    "top_b",
    "antitop_bbar",
    "lepton",
    "neutrino",
    "top",
    "antitop",
    "higgs",
)

WEAVER_SUMMARY_KEYS = ("mc_b", "mc_bbar", "mc_c", "mc_cbar")


def to_float(value: object) -> float:
    """Convert a value to float, returning NaN when conversion fails."""
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return float("nan")


def feature_columns_from_config(
    config: Mapping[str, Any], feature_set_name: str
) -> list[str]:
    """Expand one ordered feature set from an analysis configuration."""
    feature_sets = config["features"]["sets"]
    if feature_set_name not in feature_sets:
        raise ValueError(
            f"unknown feature set {feature_set_name!r}; available: {list(feature_sets)}"
        )
    feature_config = feature_sets[feature_set_name]
    columns: list[str] = []
    for object_name, variables in feature_config.get("objects", {}).items():
        columns.extend(f"{object_name}_{variable}" for variable in variables)
    columns.extend(feature_config.get("auxiliary", []))
    return columns


def _selected_w_likelihood(row: Mapping[str, object]) -> float:
    preference = row.get("w_orientation_status")
    if preference == "L12_preferred":
        return to_float(row.get("L12"))
    if preference == "L21_preferred":
        return to_float(row.get("L21"))
    return float("nan")


def _down_type_daughter(row: Mapping[str, object], variable: str) -> float:
    down = to_float(row.get("idx_W_down_candidate"))
    quark = to_float(row.get("idx_W_quark"))
    antiquark = to_float(row.get("idx_W_antiquark"))
    if not math.isfinite(down) or down == -1.0:
        return float("nan")
    if down == quark:
        prefix = "wjet_quark"
    elif down == antiquark:
        prefix = "wjet_antiquark"
    else:
        return float("nan")
    return to_float(row.get(f"{prefix}_{variable}"))


def _second_w_daughter(row: Mapping[str, object], variable: str) -> float:
    down = to_float(row.get("idx_W_down_candidate"))
    quark = to_float(row.get("idx_W_quark"))
    antiquark = to_float(row.get("idx_W_antiquark"))
    if not all(math.isfinite(value) for value in (down, quark, antiquark)):
        return float("nan")
    if down == quark:
        prefix = "wjet_antiquark"
    elif down == antiquark:
        prefix = "wjet_quark"
    else:
        return float("nan")

    if variable == "pt":
        energy = to_float(row.get(f"{prefix}_E"))
        theta = to_float(row.get(f"{prefix}_theta"))
        mass = to_float(row.get(f"{prefix}_mass"))
        if not (math.isfinite(energy) and math.isfinite(theta)):
            return float("nan")
        mass_value = mass if math.isfinite(mass) else 0.0
        momentum = math.sqrt(max(0.0, energy**2 - mass_value**2))
        return momentum * math.sin(theta)
    return to_float(row.get(f"{prefix}_{variable}"))


def _neutrino(row: Mapping[str, object], variable: str) -> float:
    if variable == "pt":
        energy = to_float(row.get("neutrino_E"))
        theta = to_float(row.get("neutrino_theta"))
        if math.isfinite(energy) and math.isfinite(theta):
            return energy * math.sin(theta)
    return float("nan")


def _add_p4(*items: tuple[float, float, float, float] | None):
    if any(item is None for item in items):
        return None
    return tuple(sum(item[i] for item in items if item is not None) for i in range(4))


class FeatureContext:
    """One-row derived-feature context with event-local memoization.

    The underlying row is treated as immutable for the lifetime of a context.
    Values already resolved by this context remain cached even if the caller
    mutates the mapping; construct a new context to observe changed inputs.
    """

    def __init__(self, row: Mapping[str, object]):
        self.row = row
        self._resolved: dict[str, float] = {}
        self._derived: dict[str, object] | None = None

    def _p4(self, prefix: str):
        values = tuple(to_float(self.row.get(f"{prefix}_{suffix}")) for suffix in ("E", "px", "py", "pz"))
        return values if all(math.isfinite(value) for value in values) else None

    def _jet_p4(self, index_value: object):
        index = to_float(index_value)
        if not math.isfinite(index) or int(index) != index or not 0 <= int(index) < 6:
            return None
        return self._p4(f"jet{int(index)}")

    def _weaver(self, index_value: object) -> dict[str, float] | None:
        index = to_float(index_value)
        if not math.isfinite(index) or int(index) != index or not 0 <= int(index) < 6:
            return None
        scores = {
            key: to_float(self.row.get(f"jet{int(index)}_weaver_{key}"))
            for key in (
                "mc_u", "mc_d", "mc_s", "mc_c", "mc_b",
                "mc_ubar", "mc_dbar", "mc_sbar", "mc_cbar", "mc_bbar",
            )
        }
        return scores

    def _build_derived(self) -> dict[str, object]:
        if self._derived is not None:
            return self._derived

        out: dict[str, object] = {}
        idx_w1 = self.row.get("idx_W1")
        idx_w2 = self.row.get("idx_W2")
        w1 = self._jet_p4(idx_w1)
        w2 = self._jet_p4(idx_w2)
        bhad = self._jet_p4(self.row.get("idx_bhad"))
        blep = self._jet_p4(self.row.get("idx_blep"))
        h1 = self._jet_p4(self.row.get("idx_H1"))
        h2 = self._jet_p4(self.row.get("idx_H2"))
        lepton = self._p4("lepton_lab")
        neutrino = self._p4("nu_fit")
        higgs = _add_p4(h1, h2)

        orientation = None
        w1_scores = self._weaver(idx_w1)
        w2_scores = self._weaver(idx_w2)
        if w1_scores is not None and w2_scores is not None:
            try:
                orientation = flavor.orient_w_pair(w1_scores, w2_scores)
            except (ValueError, ZeroDivisionError):
                orientation = None

        wq = wqbar = None
        wq_index = wqbar_index = None
        if orientation is not None:
            selected = (idx_w1, idx_w2)
            wq_index = int(to_float(selected[orientation["quark_slot"]]))
            wqbar_index = int(to_float(selected[orientation["antiquark_slot"]]))
            wq = self._jet_p4(wq_index)
            wqbar = self._jet_p4(wqbar_index)
            out.update({
                "idx_W_quark": wq_index,
                "idx_W_antiquark": wqbar_index,
                "w_orientation_status": orientation["status"],
                "w_orientation_margin": orientation["margin"],
                "W1_weaver_pq": orientation["w1"]["p_quark"],
                "W1_weaver_pqbar": orientation["w1"]["p_antiquark"],
                "W1_weaver_qminusqbar": orientation["w1"]["signed_score"],
                "W2_weaver_pq": orientation["w2"]["p_quark"],
                "W2_weaver_pqbar": orientation["w2"]["p_antiquark"],
                "W2_weaver_qminusqbar": orientation["w2"]["signed_score"],
                "L12": orientation["L12"],
                "L21": orientation["L21"],
            })
            if orientation["status"] == "L12_preferred":
                out["w_assignment_likelihood_selected"] = orientation["L12"]
            elif orientation["status"] == "L21_preferred":
                out["w_assignment_likelihood_selected"] = orientation["L21"]

        hadronic_top = _add_p4(w1, w2, bhad)
        leptonic_top = _add_p4(lepton, neutrino, blep)
        charge = to_float(self.row.get("lepton_charge"))
        top = antitop = top_side = anti_side = top_b = antitop_bbar = down = None
        down_index = -1
        if math.isfinite(charge) and charge < 0.0:
            top, antitop = hadronic_top, leptonic_top
            top_side, anti_side = wqbar, lepton
            top_b, antitop_bbar = bhad, blep
            down, down_index = wqbar, wqbar_index if wqbar_index is not None else -1
            out["hadronic_W_charge"] = 1
        elif math.isfinite(charge) and charge > 0.0:
            top, antitop = leptonic_top, hadronic_top
            top_side, anti_side = lepton, wq
            top_b, antitop_bbar = blep, bhad
            down, down_index = wq, wq_index if wq_index is not None else -1
            out["hadronic_W_charge"] = -1

        if math.isfinite(charge) and charge != 0.0:
            w1_number = to_float(idx_w1)
            w2_number = to_float(idx_w2)
            out.update({
                "idx_W_down_candidate": down_index,
                "down_candidate_source": "qqbar_orientation_plus_lepton_charge",
                "down_type_slot": (
                    1 if math.isfinite(w1_number) and down_index == int(w1_number)
                    else 2 if math.isfinite(w2_number) and down_index == int(w2_number)
                    else 0
                ),
            })

        objects = {
            "wjet_quark": wq,
            "wjet_antiquark": wqbar,
            "top_side_fermion": top_side,
            "anti_top_side_fermion": anti_side,
            "top_b": top_b,
            "antitop_bbar": antitop_bbar,
            "lepton": lepton,
            "neutrino": neutrino,
            "top": top,
            "antitop": antitop,
            "higgs": higgs,
        }
        rest_p4 = higgs
        phis: dict[str, float] = {}
        for name in CANONICAL_OBJECTS:
            p4 = objects[name]
            boosted = frames.boost_to_rest(p4, rest_p4) if p4 is not None and rest_p4 is not None else None
            boosted_angles = frames.boost_only_angles(p4, rest_p4) if p4 is not None and rest_p4 is not None else None
            if boosted is None:
                out.update({
                    f"{name}_E": NAN, f"{name}_pt": NAN,
                    f"{name}_theta": NAN, f"{name}_phi": NAN,
                    f"{name}_mass": NAN, f"{name}_valid": 0,
                })
                continue
            energy, px, py, pz = boosted
            if boosted_angles is None:
                out.update({
                    f"{name}_E": energy,
                    f"{name}_pt": math.hypot(px, py),
                    f"{name}_theta": NAN,
                    f"{name}_phi": NAN,
                    f"{name}_mass": frames.invariant_mass(p4),
                    f"{name}_valid": 0,
                })
                continue
            _, cos_theta, phi = boosted_angles
            out.update({
                f"{name}_E": energy,
                f"{name}_pt": math.hypot(px, py),
                f"{name}_theta": math.acos(max(-1.0, min(1.0, cos_theta))),
                f"{name}_phi": phi,
                f"{name}_mass": frames.invariant_mass(p4),
                f"{name}_valid": 1,
            })
            phis[name] = phi

        if lepton is not None and rest_p4 is not None:
            boosted_lepton = frames.boost_to_rest(lepton, rest_p4)
            if boosted_lepton is not None:
                out.update({
                    "lepton_px": boosted_lepton[1],
                    "lepton_py": boosted_lepton[2],
                    "lepton_pz": boosted_lepton[3],
                })

        if neutrino is not None:
            _, px, py, pz = neutrino
            momentum = math.sqrt(px * px + py * py + pz * pz)
            out.update({
                "nu_fit_pt": math.hypot(px, py),
                "nu_fit_theta": math.acos(max(-1.0, min(1.0, pz / momentum))) if momentum > 0.0 else NAN,
                "nu_fit_phi": math.atan2(py, px),
            })

        ttbar = _add_p4(top, antitop)
        out["m_ttbar"] = frames.invariant_mass(ttbar) if ttbar is not None else NAN
        out.update({
            "m_W_had": to_float(self.row.get("mW_had_postfit")),
            "m_top_had": to_float(self.row.get("mt_had_postfit")),
            "m_top_lep": to_float(self.row.get("mt_lep_postfit")),
            "m_H": to_float(self.row.get("mH_postfit")),
            "down_jet_mass": frames.invariant_mass(down) if down is not None else NAN,
            "top_side_fermion_down_jet_mass": frames.invariant_mass(top_side) if top_side is not None else NAN,
            "anti_top_side_fermion_down_jet_mass": frames.invariant_mass(anti_side) if anti_side is not None else NAN,
        })

        def dphi(first: str, second: str) -> float:
            if first not in phis or second not in phis:
                return NAN
            return angles.delta_phi(phis[first], phis[second])

        out.update({
            "O_W": dphi("wjet_quark", "wjet_antiquark"),
            "O_lD": dphi("top_side_fermion", "anti_top_side_fermion"),
            "O_b": dphi("top_b", "antitop_bbar"),
            "O_top": dphi("top", "antitop"),
            "O_lnu": dphi("lepton", "neutrino") if charge < 0.0 else dphi("neutrino", "lepton") if charge > 0.0 else NAN,
        })

        ndof = to_float(self.row.get("ndof"))
        fitchi2 = to_float(self.row.get("fitchi2"))
        out["chi2_over_ndof"] = fitchi2 / ndof if math.isfinite(fitchi2) and math.isfinite(ndof) and ndof > 0.0 else NAN

        all_scores = [self._weaver(index) for index in range(6)]
        for key in WEAVER_SUMMARY_KEYS:
            values = [scores[key] for scores in all_scores if scores is not None and math.isfinite(scores[key])]
            out[f"max_weaver_{key}"] = max(values) if values else NAN
        oriented_indices = {
            "wjet_quark": wq_index,
            "wjet_antiquark": wqbar_index,
            "top_b": self.row.get("idx_bhad") if charge < 0.0 else self.row.get("idx_blep") if charge > 0.0 else None,
            "antitop_bbar": self.row.get("idx_blep") if charge < 0.0 else self.row.get("idx_bhad") if charge > 0.0 else None,
        }
        for name, index in oriented_indices.items():
            scores = self._weaver(index)
            for key in WEAVER_SUMMARY_KEYS:
                out[f"{name}_weaver_{key}"] = scores[key] if scores is not None else NAN

        self._derived = out
        return out

    def resolve(self, feature_name: str) -> float:
        if feature_name in self._resolved:
            return self._resolved[feature_name]

        direct = to_float(self.row.get(feature_name))
        if math.isfinite(direct):
            self._resolved[feature_name] = direct
            return direct

        derived = self._build_derived()
        value = to_float(derived.get(feature_name))
        if not math.isfinite(value):
            if feature_name == "w_assignment_likelihood_selected":
                value = _selected_w_likelihood(self.row)
            elif feature_name.startswith("down_type_daughter_"):
                value = _down_type_daughter({**derived, **self.row}, feature_name.removeprefix("down_type_daughter_"))
            elif feature_name.startswith("second_w_daughter_"):
                value = _second_w_daughter({**derived, **self.row}, feature_name.removeprefix("second_w_daughter_"))
            elif feature_name.startswith("neutrino_"):
                value = _neutrino(self.row, feature_name.removeprefix("neutrino_"))

        self._resolved[feature_name] = value
        return value

    def materialize(self) -> dict[str, object]:
        return dict(self._build_derived())


def resolve_feature_value(
    row: Mapping[str, object] | FeatureContext, feature_name: str
) -> float:
    """Resolve one numeric feature with finite materialized values first."""
    context = row if isinstance(row, FeatureContext) else FeatureContext(row)
    return context.resolve(feature_name)


def resolve_feature_values(
    row: Mapping[str, object] | FeatureContext, names: list[str] | tuple[str, ...]
) -> dict[str, float]:
    """Resolve several features through one shared event-local context."""
    context = row if isinstance(row, FeatureContext) else FeatureContext(row)
    return {name: context.resolve(name) for name in names}


def materialize_v2_canonical_fields(
    row_or_context: Mapping[str, object] | FeatureContext,
) -> dict[str, object]:
    """Build the v2 canonical/diagnostic fields from one v3 baseline row."""
    context = (
        row_or_context
        if isinstance(row_or_context, FeatureContext)
        else FeatureContext(row_or_context)
    )
    return context.materialize()
