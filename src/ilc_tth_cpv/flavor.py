"""Reco flavor-score helpers for signed object ordering."""

from __future__ import annotations

import math
from typing import Mapping


LIGHT_QUARK_KEYS = ("mc_u", "mc_d", "mc_s", "mc_c")
LIGHT_ANTIQUARK_KEYS = ("mc_ubar", "mc_dbar", "mc_sbar", "mc_cbar")
DOWN_QUARK_KEYS={"mc_d","mc_dbar","mc_s","mc_sbar"}
UP_QUARK_KEYS={"mc_u","mc_ubar","mc_c","mc_cbar"}


def light_charge_scores(scores: Mapping[str, float]) -> dict[str, float]:
    """Return summed q/qbar probabilities and their signed discriminator."""

    required = LIGHT_QUARK_KEYS + LIGHT_ANTIQUARK_KEYS
    missing = [key for key in required if key not in scores]

    if missing:
        raise ValueError(f"missing Weaver light-flavor scores: {', '.join(missing)}")

    values = {key: float(scores[key]) for key in required}
    nonfinite = [key for key, value in values.items() if not math.isfinite(value)]

    if nonfinite:
        raise ValueError(f"non-finite Weaver light-flavor scores: {', '.join(nonfinite)}")

    p_quark = sum(values[key] for key in LIGHT_QUARK_KEYS)
    p_antiquark = sum(values[key] for key in LIGHT_ANTIQUARK_KEYS)

    return {
        "p_quark": p_quark,
        "p_antiquark": p_antiquark,
        "signed_score": p_quark - p_antiquark,
    }

def down_type_scores(
    scores: Mapping[str, float],
) -> dict[str, float]:
    """Return summed down/up-type probabilities."""

    required = DOWN_TYPE_KEYS + UP_TYPE_KEYS

    missing = [key for key in required if key not in scores]
    if missing:
        raise ValueError(
            f"missing Weaver light-flavor scores: {', '.join(missing)}"
        )

    values = {key: float(scores[key]) for key in required}

    nonfinite = [
        key
        for key, value in values.items()
        if not math.isfinite(value)
    ]

    if nonfinite:
        raise ValueError(
            f"non-finite Weaver light-flavor scores: "
            f"{', '.join(nonfinite)}"
        )

    p_down = sum(values[key] for key in DOWN_TYPE_KEYS)
    p_up = sum(values[key] for key in UP_TYPE_KEYS)

    return {
        "p_down": p_down,
        "p_up": p_up,
        "signed_score": p_down - p_up,
    }


def orient_w_pair(
    w1_scores: Mapping[str, float],
    w2_scores: Mapping[str, float],
    tie_tolerance: float = 1.0e-12,
    ) -> dict:
    """Orient selected W slots as q/qbar using joint likelihood (L12 vs L21)
    **Details are in docs/W_DAUGHTER_ORDERING.md

    Computes L12 = P_q(w1) * P_qbar(w2) and L21 = P_q(w2) * P_qbar(w1).
    Assigns (0, 1) if L12 > L21, and (1, 0) if L21 > L12.
    """
    first = light_charge_scores(w1_scores)
    second = light_charge_scores(w2_scores)

    # Probability of jet being quark or antiquark
    prob_q_jet1 = first["p_quark"] 
    prob_q_jet2 = second["p_quark"]

    prob_qbar_jet1 = first["p_antiquark"] 
    prob_qbar_jet2 = second["p_antiquark"]

    # Calculate L12 and L21
    L12 = prob_q_jet1 * prob_qbar_jet2
    L21 = prob_q_jet2 * prob_qbar_jet1

    eps=1e-12
    delta_L = math.log(L12+eps) - math.log(L21+eps)
    L_ratio = L12 / L21
    margin = abs(delta_L)

    # Determine the assignment of jets based on L12 and L21
    if abs(L_ratio - 1) <= tie_tolerance: 
        # Case 1: the difference between L12 and L21 are smaller than or equal to 'tie_tolerance'
        quark_slot, antiquark_slot = 0, 1
        status = "tie_slot_order"
    elif abs(L_ratio) > 1:
        # Case 2: L12 > L21
        quark_slot, antiquark_slot = 0, 1
        status = "L12_preferred"
    else:
        # Case 3: L12 < L21
        quark_slot, antiquark_slot = 1, 0
        status = "L21_preferred"

    return {
        "quark_slot": quark_slot,
        "antiquark_slot": antiquark_slot,
        "margin": margin,
        "status": status,
        "L12": L12,
        "L21": L21,
        "w1": first,
        "w2": second,
    }

def orient_w_pair_v2(
    w1_scores: Mapping[str, float],
    w2_scores: Mapping[str, float],
    tie_tolerance: float = 1.0e-3,
) -> dict:
    """
    Orient the two selected W jets as down-like / up-like.

    Primary ordering uses up/down-type Weaver information.

    Charge information is retained as an auxiliary discriminator,
    but does not affect the hard down/up assignment.
    """

    eps = 1.0e-12

    first_type = down_type_scores(w1_scores)
    second_type = down_type_scores(w2_scores)

    first_charge = light_charge_scores(w1_scores)
    second_charge = light_charge_scores(w2_scores)

    # Hypothesis H12:
    #   W1 = down-type, W2 = up-type
    L12_type = (first_type["p_down"]* second_type["p_up"] )

    # Hypothesis H21:
    #   W2 = down-type, W1 = up-type
    L21_type = (second_type["p_down"]* first_type["p_up"])

    delta_type = ( math.log(L12_type + eps)- math.log(L21_type + eps))

    margin = abs(delta_type)

    # Auxiliary q/qbar information.
    #
    # Positive delta_charge:
    #   W1 prefers q, W2 prefers qbar.
    #
    # Negative delta_charge:
    #   W1 prefers qbar, W2 prefers q.
    L12_charge = (first_charge["p_quark"]* second_charge["p_antiquark"])

    L21_charge = (second_charge["p_quark"]* first_charge["p_antiquark"])

    delta_charge = (math.log(L12_charge + eps)- math.log(L21_charge + eps))

    # Hard assignment uses TYPE ONLY.
    if margin <= tie_tolerance:
        down_slot, up_slot = 0, 1
        status = "tie_slot_order"

    elif delta_type > 0.0:
        down_slot, up_slot = 0, 1
        status = "L12_type_preferred"

    else:
        down_slot, up_slot = 1, 0
        status = "L21_type_preferred"

    return {
        "down_slot": down_slot,
        "up_slot": up_slot,

        "margin": margin,
        "status": status,

        "L12_type": L12_type,
        "L21_type": L21_type,
        "type_delta_logL": delta_type,

        "L12_charge": L12_charge,
        "L21_charge": L21_charge,
        "charge_delta_logL": delta_charge,

        "w1_type": first_type,
        "w2_type": second_type,

        "w1_charge": first_charge,
        "w2_charge": second_charge,
    }

def quark_antiquark_slots_from_type(
    lepton_charge: float,
    down_slot: int,
    up_slot: int,
) -> tuple[int, int]:
    """
    Convert down/up-type ordering into q/qbar ordering
    using the semileptonic lepton charge.
    """

    if not math.isfinite(lepton_charge) or lepton_charge == 0.0:
        raise ValueError("lepton_charge must be finite and non-zero")

    if lepton_charge > 0.0:
        # leptonic side: W+
        # hadronic side: W- -> D + Ubar
        quark_slot = down_slot
        antiquark_slot = up_slot

    else:
        # leptonic side: W-
        # hadronic side: W+ -> U + Dbar
        quark_slot = up_slot
        antiquark_slot = down_slot

    return quark_slot, antiquark_slot

    
def semileptonic_down_type_order(
    lepton_charge: float | None,
    ) -> tuple[str, str] | None:
    """Return the top-side and antitop-side analyzer object names."""

    if lepton_charge is None:
        return None

    if lepton_charge > 0.0:
        return "lepton", "wjet_quark"

    if lepton_charge < 0.0:
        return "wjet_antiquark", "lepton"

    return None