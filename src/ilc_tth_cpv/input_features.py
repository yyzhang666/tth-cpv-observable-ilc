"""Authoritative, lazy row-level ML input-feature resolution.

Finite materialized CSV columns always win. Derived values are dispatched
through an explicit registry and share only event-local intermediate caches;
requesting one feature never materializes the full canonical feature table.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ilc_tth_cpv import angles, flavor, frames

NAN = float("nan")

CANONICAL_OBJECTS = (
    "wjet_quark", "wjet_antiquark", "top_side_fermion",
    "anti_top_side_fermion", "top_b", "antitop_bbar", "lepton",
    "neutrino", "top", "antitop", "higgs",
)
OBJECT_VARIABLES = ("E", "pt", "theta", "phi", "mass", "valid")
WEAVER_SCORE_KEYS = (
    "mc_u", "mc_d", "mc_s", "mc_c", "mc_b",
    "mc_ubar", "mc_dbar", "mc_sbar", "mc_cbar", "mc_bbar",
)
WEAVER_SUMMARY_KEYS = ("mc_b", "mc_bbar", "mc_c", "mc_cbar")
ORIENTED_WEAVER_OBJECTS = (
    "wjet_quark", "wjet_antiquark", "top_b", "antitop_bbar",
)

ORIENTATION_FIELDS = (
    "idx_W_quark", "idx_W_antiquark", "w_orientation_status",
    "w_orientation_margin", "W1_weaver_pq", "W1_weaver_pqbar",
    "W1_weaver_qminusqbar", "W2_weaver_pq", "W2_weaver_pqbar",
    "W2_weaver_qminusqbar", "L12", "L21",
    "w_assignment_likelihood_selected",
)
CHARGE_FIELDS = (
    "hadronic_W_charge", "idx_W_down_candidate", "down_candidate_source",
    "down_type_slot",
)
KINEMATIC_FIELDS = tuple(
    f"{name}_{variable}"
    for name in CANONICAL_OBJECTS
    for variable in OBJECT_VARIABLES
)
V2_CANONICAL_FIELDS = (
    ORIENTATION_FIELDS
    + CHARGE_FIELDS
    + KINEMATIC_FIELDS
    + ("lepton_px", "lepton_py", "lepton_pz")
    + ("nu_fit_pt", "nu_fit_theta", "nu_fit_phi")
    + (
        "m_ttbar", "m_W_had", "m_top_had", "m_top_lep", "m_H",
        "down_jet_mass", "top_side_fermion_down_jet_mass",
        "anti_top_side_fermion_down_jet_mass",
    )
    + ("O_W", "O_lD", "O_b", "O_top", "O_lnu", "chi2_over_ndof")
    + tuple(f"max_weaver_{key}" for key in WEAVER_SUMMARY_KEYS)
    + tuple(
        f"{name}_weaver_{key}"
        for name in ORIENTED_WEAVER_OBJECTS
        for key in WEAVER_SUMMARY_KEYS
    )
)

STRING_FEATURES = {"w_orientation_status", "down_candidate_source"}


def to_float(value: object) -> float:
    """Convert a value to float, returning NaN when conversion fails."""
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return NAN


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


def _add_p4(*items: tuple[float, float, float, float] | None):
    if any(item is None for item in items):
        return None
    return tuple(
        sum(item[index] for item in items if item is not None)
        for index in range(4)
    )


@dataclass(frozen=True)
class FeatureSpec:
    """One exact feature calculator in the lazy registry."""

    calculator: Callable[["FeatureContext", str], object]


class FeatureContext:
    """One immutable-row view with lazy, event-local intermediate caches."""

    def __init__(self, row: Mapping[str, object]):
        self.row = row
        self._resolved: dict[str, object] = {}
        self._intermediate: dict[str, object] = {}

    def _p4(self, prefix: str):
        key = f"p4:{prefix}"
        if key not in self._intermediate:
            values = tuple(
                to_float(self.row.get(f"{prefix}_{suffix}"))
                for suffix in ("E", "px", "py", "pz")
            )
            self._intermediate[key] = (
                values if all(math.isfinite(value) for value in values) else None
            )
        return self._intermediate[key]

    @staticmethod
    def _slot(index_value: object) -> int | None:
        value = to_float(index_value)
        if not math.isfinite(value) or int(value) != value or not 0 <= int(value) < 6:
            return None
        return int(value)

    def _slot_p4(self, index_value: object):
        slot = self._slot(index_value)
        return self._p4(f"jet{slot}") if slot is not None else None

    def _weaver(self, index_value: object) -> dict[str, float] | None:
        slot = self._slot(index_value)
        if slot is None:
            return None
        key = f"weaver:{slot}"
        if key not in self._intermediate:
            self._intermediate[key] = {
                score: to_float(self.row.get(f"jet{slot}_weaver_{score}"))
                for score in WEAVER_SCORE_KEYS
            }
        return self._intermediate[key]  # type: ignore[return-value]

    def _orientation(self) -> dict | None:
        key = "orientation"
        if key not in self._intermediate:
            first = self._weaver(self.row.get("idx_W1"))
            second = self._weaver(self.row.get("idx_W2"))
            if first is None or second is None:
                result = None
            else:
                try:
                    result = flavor.orient_w_pair(first, second)
                except (ValueError, ZeroDivisionError):
                    result = None
            self._intermediate[key] = result
        return self._intermediate[key]  # type: ignore[return-value]

    def _oriented_w_slots(self) -> tuple[int | None, int | None]:
        key = "oriented_w_slots"
        if key not in self._intermediate:
            orientation = self._orientation()
            selected = (
                self._slot(self.row.get("idx_W1")),
                self._slot(self.row.get("idx_W2")),
            )
            if orientation is None or None in selected:
                result = (None, None)
            else:
                result = (
                    selected[orientation["quark_slot"]],
                    selected[orientation["antiquark_slot"]],
                )
            self._intermediate[key] = result
        return self._intermediate[key]  # type: ignore[return-value]

    def _charge_assignment(self) -> dict[str, object]:
        key = "charge_assignment"
        if key not in self._intermediate:
            wq_slot, wqbar_slot = self._oriented_w_slots()
            w1 = self._slot_p4(self.row.get("idx_W1"))
            w2 = self._slot_p4(self.row.get("idx_W2"))
            bhad = self._slot_p4(self.row.get("idx_bhad"))
            blep = self._slot_p4(self.row.get("idx_blep"))
            lepton = self._p4("lepton_lab")
            neutrino = self._p4("nu_fit")
            wq = self._slot_p4(wq_slot)
            wqbar = self._slot_p4(wqbar_slot)
            hadronic_top = _add_p4(w1, w2, bhad)
            leptonic_top = _add_p4(lepton, neutrino, blep)
            charge = to_float(self.row.get("lepton_charge"))
            result: dict[str, object] = {
                "charge": charge,
                "wq": wq,
                "wqbar": wqbar,
                "wq_slot": wq_slot,
                "wqbar_slot": wqbar_slot,
            }
            if math.isfinite(charge) and charge < 0.0:
                result.update({
                    "top": hadronic_top, "antitop": leptonic_top,
                    "top_side": wqbar, "anti_side": lepton,
                    "top_b": bhad, "antitop_bbar": blep,
                    "top_b_slot": self._slot(self.row.get("idx_bhad")),
                    "antitop_bbar_slot": self._slot(self.row.get("idx_blep")),
                    "down": wqbar, "down_slot": wqbar_slot,
                    "hadronic_W_charge": 1,
                })
            elif math.isfinite(charge) and charge > 0.0:
                result.update({
                    "top": leptonic_top, "antitop": hadronic_top,
                    "top_side": lepton, "anti_side": wq,
                    "top_b": blep, "antitop_bbar": bhad,
                    "top_b_slot": self._slot(self.row.get("idx_blep")),
                    "antitop_bbar_slot": self._slot(self.row.get("idx_bhad")),
                    "down": wq, "down_slot": wq_slot,
                    "hadronic_W_charge": -1,
                })
            self._intermediate[key] = result
        return self._intermediate[key]  # type: ignore[return-value]

    def _canonical_p4(self, object_name: str):
        key = f"canonical_p4:{object_name}"
        if key not in self._intermediate:
            if object_name == "lepton":
                value = self._p4("lepton_lab")
            elif object_name == "neutrino":
                value = self._p4("nu_fit")
            elif object_name == "higgs":
                value = _add_p4(
                    self._slot_p4(self.row.get("idx_H1")),
                    self._slot_p4(self.row.get("idx_H2")),
                )
            else:
                assignment = self._charge_assignment()
                value = {
                    "wjet_quark": assignment.get("wq"),
                    "wjet_antiquark": assignment.get("wqbar"),
                    "top_side_fermion": assignment.get("top_side"),
                    "anti_top_side_fermion": assignment.get("anti_side"),
                    "top_b": assignment.get("top_b"),
                    "antitop_bbar": assignment.get("antitop_bbar"),
                    "top": assignment.get("top"),
                    "antitop": assignment.get("antitop"),
                }.get(object_name)
            self._intermediate[key] = value
        return self._intermediate[key]

    def _rest_p4(self):
        key = "higgs_rest_p4"
        if key not in self._intermediate:
            self._intermediate[key] = self._canonical_p4("higgs")
        return self._intermediate[key]

    def _object_kinematics(self, object_name: str) -> dict[str, float]:
        key = f"kinematics:{object_name}"
        if key not in self._intermediate:
            p4 = self._canonical_p4(object_name)
            rest_p4 = self._rest_p4()
            boosted = (
                frames.boost_to_rest(p4, rest_p4)
                if p4 is not None and rest_p4 is not None
                else None
            )
            boosted_angles = (
                frames.boost_only_angles(p4, rest_p4)
                if p4 is not None and rest_p4 is not None
                else None
            )
            if boosted is None:
                values = {
                    "E": NAN, "pt": NAN, "theta": NAN, "phi": NAN,
                    "mass": NAN, "valid": 0.0,
                }
            else:
                energy, px, py, _ = boosted
                values = {
                    "E": energy,
                    "pt": math.hypot(px, py),
                    "mass": frames.invariant_mass(p4),
                    "valid": 0.0 if boosted_angles is None else 1.0,
                    "theta": NAN,
                    "phi": NAN,
                }
                if boosted_angles is not None:
                    _, cos_theta, phi = boosted_angles
                    values["theta"] = math.acos(max(-1.0, min(1.0, cos_theta)))
                    values["phi"] = phi
            self._intermediate[key] = values
        return self._intermediate[key]  # type: ignore[return-value]

    def _value(self, feature_name: str) -> object:
        if feature_name in self._resolved:
            return self._resolved[feature_name]

        direct = to_float(self.row.get(feature_name))
        if math.isfinite(direct):
            self._resolved[feature_name] = direct
            return direct
        if feature_name in STRING_FEATURES:
            direct_string = self.row.get(feature_name)
            if isinstance(direct_string, str) and direct_string:
                self._resolved[feature_name] = direct_string
                return direct_string

        spec = _EXACT_REGISTRY.get(feature_name)
        if spec is not None:
            value = spec.calculator(self, feature_name)
        else:
            value = NAN
            for prefix, calculator in _PREFIX_REGISTRY:
                if feature_name.startswith(prefix):
                    value = calculator(self, feature_name)
                    break
        self._resolved[feature_name] = value
        return value

    def resolve(self, feature_name: str) -> float:
        """Resolve one numeric feature and cache only its dependency path."""
        return to_float(self._value(feature_name))


def _calc_orientation(context: FeatureContext, name: str) -> object:
    orientation = context._orientation()
    if orientation is None:
        return NAN
    wq_slot, wqbar_slot = context._oriented_w_slots()
    mapping: dict[str, object] = {
        "idx_W_quark": wq_slot,
        "idx_W_antiquark": wqbar_slot,
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
    }
    return mapping.get(name, NAN)


def _calc_selected_likelihood(context: FeatureContext, _name: str) -> float:
    raw_status = context.row.get("w_orientation_status")
    if raw_status == "L12_preferred":
        return to_float(context.row.get("L12"))
    if raw_status == "L21_preferred":
        return to_float(context.row.get("L21"))
    orientation = context._orientation()
    if orientation is None:
        return NAN
    if orientation["status"] == "L12_preferred":
        return float(orientation["L12"])
    if orientation["status"] == "L21_preferred":
        return float(orientation["L21"])
    return NAN


def _calc_selected_type_likelihood(
    context: FeatureContext,
    _name: str,
) -> float:

    assignment = context._charge_assignment()

    down_slot = assignment.get("down_slot")
    wq_slot = assignment.get("wq_slot")
    wqbar_slot = assignment.get("wqbar_slot")

    if down_slot is None or wq_slot is None or wqbar_slot is None:
        return NAN

    if down_slot == wq_slot:
        up_slot = wqbar_slot
    elif down_slot == wqbar_slot:
        up_slot = wq_slot
    else:
        return NAN

    down_scores = context._weaver(down_slot)
    up_scores = context._weaver(up_slot)

    if down_scores is None or up_scores is None:
        return NAN

    try:
        return flavor.w_type_assignment_likelihood(
            down_scores,
            up_scores,
        )
    except ValueError:
        return NAN


def _calc_charge(context: FeatureContext, name: str) -> object:
    assignment = context._charge_assignment()
    charge = to_float(assignment.get("charge"))
    if not math.isfinite(charge) or charge == 0.0:
        return NAN
    if name == "hadronic_W_charge":
        return assignment.get("hadronic_W_charge", NAN)
    if name == "idx_W_down_candidate":
        slot = assignment.get("down_slot")
        return slot if slot is not None else -1
    if name == "down_candidate_source":
        return "qqbar_orientation_plus_lepton_charge"
    down_slot = assignment.get("down_slot")
    w1_slot = context._slot(context.row.get("idx_W1"))
    w2_slot = context._slot(context.row.get("idx_W2"))
    return 1 if down_slot == w1_slot else 2 if down_slot == w2_slot else 0


def _parse_object_feature(name: str) -> tuple[str, str] | None:
    for object_name in CANONICAL_OBJECTS:
        prefix = f"{object_name}_"
        if name.startswith(prefix):
            variable = name.removeprefix(prefix)
            if variable in OBJECT_VARIABLES:
                return object_name, variable
    return None


def _calc_object_feature(context: FeatureContext, name: str) -> float:
    parsed = _parse_object_feature(name)
    if parsed is None:
        return NAN
    object_name, variable = parsed
    value = context._object_kinematics(object_name)[variable]
    if object_name == "neutrino" and variable == "pt" and not math.isfinite(value):
        energy = to_float(context.row.get("neutrino_E"))
        theta = to_float(context.row.get("neutrino_theta"))
        if math.isfinite(energy) and math.isfinite(theta):
            return energy * math.sin(theta)
    return value


def _calc_lepton_component(context: FeatureContext, name: str) -> float:
    p4 = context._canonical_p4("lepton")
    rest = context._rest_p4()
    key = "boosted:lepton"
    if key not in context._intermediate:
        context._intermediate[key] = (
            frames.boost_to_rest(p4, rest)
            if p4 is not None and rest is not None
            else None
        )
    boosted = context._intermediate[key]
    if boosted is None:
        return NAN
    return float(boosted[{"lepton_px": 1, "lepton_py": 2, "lepton_pz": 3}[name]])


def _calc_nu_fit(context: FeatureContext, name: str) -> float:
    p4 = context._p4("nu_fit")
    if p4 is None:
        return NAN
    _, px, py, pz = p4
    if name == "nu_fit_pt":
        return math.hypot(px, py)
    if name == "nu_fit_phi":
        return math.atan2(py, px)
    momentum = math.sqrt(px * px + py * py + pz * pz)
    return math.acos(max(-1.0, min(1.0, pz / momentum))) if momentum > 0.0 else NAN


def _calc_mass_or_alias(context: FeatureContext, name: str) -> float:
    aliases = {
        "m_W_had": "mW_had_postfit",
        "m_top_had": "mt_had_postfit",
        "m_top_lep": "mt_lep_postfit",
        "m_H": "mH_postfit",
    }
    if name in aliases:
        return to_float(context.row.get(aliases[name]))
    if name == "chi2_over_ndof":
        chi2 = to_float(context.row.get("fitchi2"))
        ndof = to_float(context.row.get("ndof"))
        return chi2 / ndof if math.isfinite(chi2) and math.isfinite(ndof) and ndof > 0.0 else NAN
    if name == "m_ttbar":
        ttbar = _add_p4(context._canonical_p4("top"), context._canonical_p4("antitop"))
        return frames.invariant_mass(ttbar) if ttbar is not None else NAN
    assignment = context._charge_assignment()
    object_key = {
        "down_jet_mass": "down",
        "top_side_fermion_down_jet_mass": "top_side",
        "anti_top_side_fermion_down_jet_mass": "anti_side",
    }[name]
    p4 = assignment.get(object_key)
    return frames.invariant_mass(p4) if p4 is not None else NAN


def _calc_angle(context: FeatureContext, name: str) -> float:
    pairs = {
        "O_W": ("wjet_quark_phi", "wjet_antiquark_phi"),
        "O_lD": ("top_side_fermion_phi", "anti_top_side_fermion_phi"),
        "O_b": ("top_b_phi", "antitop_bbar_phi"),
        "O_top": ("top_phi", "antitop_phi"),
    }
    if name == "O_lnu":
        charge = to_float(context.row.get("lepton_charge"))
        if charge < 0.0:
            pair = ("lepton_phi", "neutrino_phi")
        elif charge > 0.0:
            pair = ("neutrino_phi", "lepton_phi")
        else:
            return NAN
    else:
        pair = pairs[name]
    first = context.resolve(pair[0])
    second = context.resolve(pair[1])
    return angles.delta_phi(first, second) if math.isfinite(first) and math.isfinite(second) else NAN


def _calc_max_weaver(context: FeatureContext, name: str) -> float:
    score = name.removeprefix("max_weaver_")
    values = []
    for slot in range(6):
        scores = context._weaver(slot)
        if scores is not None and math.isfinite(scores[score]):
            values.append(scores[score])
    return max(values) if values else NAN


def _calc_oriented_weaver(context: FeatureContext, name: str) -> float:
    for object_name in ORIENTED_WEAVER_OBJECTS:
        prefix = f"{object_name}_weaver_"
        if name.startswith(prefix):
            score = name.removeprefix(prefix)
            assignment = context._charge_assignment()
            slot = {
                "wjet_quark": assignment.get("wq_slot"),
                "wjet_antiquark": assignment.get("wqbar_slot"),
                "top_b": assignment.get("top_b_slot"),
                "antitop_bbar": assignment.get("antitop_bbar_slot"),
            }[object_name]
            scores = context._weaver(slot)
            return scores[score] if scores is not None else NAN
    return NAN


def _calc_down_type_daughter(context: FeatureContext, name: str) -> float:
    variable = name.removeprefix("down_type_daughter_")
    down = context.resolve("idx_W_down_candidate")
    quark = context.resolve("idx_W_quark")
    antiquark = context.resolve("idx_W_antiquark")
    if not math.isfinite(down) or down == -1.0:
        return NAN
    prefix = "wjet_quark" if down == quark else "wjet_antiquark" if down == antiquark else None
    return context.resolve(f"{prefix}_{variable}") if prefix else NAN


def _calc_second_w_daughter(context: FeatureContext, name: str) -> float:
    variable = name.removeprefix("second_w_daughter_")
    down = context.resolve("idx_W_down_candidate")
    quark = context.resolve("idx_W_quark")
    antiquark = context.resolve("idx_W_antiquark")
    if not all(math.isfinite(value) for value in (down, quark, antiquark)):
        return NAN
    prefix = "wjet_antiquark" if down == quark else "wjet_quark" if down == antiquark else None
    if prefix is None:
        return NAN
    if variable == "pt":
        energy = context.resolve(f"{prefix}_E")
        theta = context.resolve(f"{prefix}_theta")
        mass = context.resolve(f"{prefix}_mass")
        if not (math.isfinite(energy) and math.isfinite(theta)):
            return NAN
        mass_value = mass if math.isfinite(mass) else 0.0
        return math.sqrt(max(0.0, energy**2 - mass_value**2)) * math.sin(theta)
    return context.resolve(f"{prefix}_{variable}")

def _orientation_v2(self) -> dict | None:
    key = "orientation_v2"

    if key not in self._intermediate:
        first = self._weaver(self.row.get("idx_W1"))
        second = self._weaver(self.row.get("idx_W2"))

        if first is None or second is None:
            result = None
        else:
            try:
                result = flavor.orient_w_pair_v2(first, second)
            except (ValueError, ZeroDivisionError):
                result = None

        self._intermediate[key] = result

    return self._intermediate[key]  # type: ignore[return-value]


def _w_slots_v2(self) -> dict[str, int | None]:
    """
    Resolve global jet slots for:
      down-type, up-type, quark, antiquark

    Hard D/U ordering comes only from orient_w_pair_v2.
    q/qbar interpretation additionally uses lepton charge.
    """

    key = "w_slots_v2"

    if key not in self._intermediate:
        orientation = self._orientation_v2()

        selected = (
            self._slot(self.row.get("idx_W1")),
            self._slot(self.row.get("idx_W2")),
        )

        charge = to_float(self.row.get("lepton_charge"))

        if (
            orientation is None
            or None in selected
            or not math.isfinite(charge)
            or charge == 0.0
        ):
            result = {
                "down": None,
                "up": None,
                "quark": None,
                "antiquark": None,
            }

        else:
            down_local = orientation["down_slot"]
            up_local = orientation["up_slot"]

            quark_local, antiquark_local = (
                flavor.quark_antiquark_slots_from_type(
                    charge,
                    down_local,
                    up_local,
                )
            )

            result = {
                "down": selected[down_local],
                "up": selected[up_local],
                "quark": selected[quark_local],
                "antiquark": selected[antiquark_local],
            }

        self._intermediate[key] = result

    return self._intermediate[key]  # type: ignore[return-value]

def _slot_phi_higgs_rest(
    context: FeatureContext,
    slot: int | None,
) -> float:
    if slot is None:
        return NAN

    p4 = context._slot_p4(slot)
    rest_p4 = context._rest_p4()

    if p4 is None or rest_p4 is None:
        return NAN

    triple = frames.boost_only_angles(p4, rest_p4)

    if triple is None:
        return NAN

    return float(triple[2])


def _calc_angle_v2(
    context: FeatureContext,
    name: str,
) -> float:

    slots = context._w_slots_v2()

    if name == "O_W_v2":
        phi_q = _slot_phi_higgs_rest(
            context,
            slots["quark"],
        )
        phi_qbar = _slot_phi_higgs_rest(
            context,
            slots["antiquark"],
        )

        if not (
            math.isfinite(phi_q)
            and math.isfinite(phi_qbar)
        ):
            return NAN

        return angles.delta_phi(phi_q, phi_qbar)

    if name == "O_lD_v2":
        phi_down = _slot_phi_higgs_rest(
            context,
            slots["down"],
        )

        phi_lepton = context.resolve("lepton_phi")

        charge = to_float(
            context.row.get("lepton_charge")
        )

        if not (
            math.isfinite(phi_down)
            and math.isfinite(phi_lepton)
            and math.isfinite(charge)
        ):
            return NAN

        # q_l > 0:
        # top side     = l+
        # antitop side = D from W-
        if charge > 0.0:
            return angles.delta_phi(
                phi_lepton,
                phi_down,
            )

        # q_l < 0:
        # top side     = anti-D from W+
        # antitop side = l-
        if charge < 0.0:
            return angles.delta_phi(
                phi_down,
                phi_lepton,
            )

    return NAN

_EXACT_REGISTRY: dict[str, FeatureSpec] = {}
for _name in ORIENTATION_FIELDS[:-1]:
    _EXACT_REGISTRY[_name] = FeatureSpec(_calc_orientation)
_EXACT_REGISTRY["w_assignment_likelihood_selected"] = FeatureSpec(_calc_selected_likelihood)
_EXACT_REGISTRY["w_type_assignment_likelihood_selected"] = FeatureSpec(_calc_selected_type_likelihood)
for _name in CHARGE_FIELDS:
    _EXACT_REGISTRY[_name] = FeatureSpec(_calc_charge)
for _name in ("lepton_px", "lepton_py", "lepton_pz"):
    _EXACT_REGISTRY[_name] = FeatureSpec(_calc_lepton_component)
for _name in ("nu_fit_pt", "nu_fit_theta", "nu_fit_phi"):
    _EXACT_REGISTRY[_name] = FeatureSpec(_calc_nu_fit)
for _name in (
    "m_ttbar", "m_W_had", "m_top_had", "m_top_lep", "m_H",
    "down_jet_mass", "top_side_fermion_down_jet_mass",
    "anti_top_side_fermion_down_jet_mass", "chi2_over_ndof",
):
    _EXACT_REGISTRY[_name] = FeatureSpec(_calc_mass_or_alias)
for _name in ("O_W", "O_lD", "O_b", "O_top", "O_lnu"):
    _EXACT_REGISTRY[_name] = FeatureSpec(_calc_angle)
for _name in tuple(f"max_weaver_{key}" for key in WEAVER_SUMMARY_KEYS):
    _EXACT_REGISTRY[_name] = FeatureSpec(_calc_max_weaver)
for _name in tuple(
    f"{obj}_weaver_{key}"
    for obj in ORIENTED_WEAVER_OBJECTS
    for key in WEAVER_SUMMARY_KEYS
):
    _EXACT_REGISTRY[_name] = FeatureSpec(_calc_oriented_weaver)

for _name in ("O_W_v2", "O_lD_v2"):
    _EXACT_REGISTRY[_name] = FeatureSpec(_calc_angle_v2)
_PREFIX_REGISTRY: tuple[tuple[str, Callable[[FeatureContext, str], object]], ...] = (
    tuple((f"{name}_", _calc_object_feature) for name in CANONICAL_OBJECTS)
    + (
        ("down_type_daughter_", _calc_down_type_daughter),
        ("second_w_daughter_", _calc_second_w_daughter),
    )
)



def resolve_feature_value(
    row: Mapping[str, object] | FeatureContext, feature_name: str
) -> float:
    """Resolve one numeric feature with finite materialized values first."""
    context = row if isinstance(row, FeatureContext) else FeatureContext(row)
    return context.resolve(feature_name)


def resolve_feature_values(
    row: Mapping[str, object] | FeatureContext, names: Sequence[str]
) -> dict[str, float]:
    """Resolve only the requested names through one shared event context."""
    context = row if isinstance(row, FeatureContext) else FeatureContext(row)
    return {name: context.resolve(name) for name in names}


def materialize_v2_canonical_fields(
    row_or_context: Mapping[str, object] | FeatureContext,
) -> dict[str, object]:
    """Compatibility helper: explicitly resolve the frozen v2 field list."""
    context = (
        row_or_context
        if isinstance(row_or_context, FeatureContext)
        else FeatureContext(row_or_context)
    )
    return {name: context._value(name) for name in V2_CANONICAL_FIELDS}
