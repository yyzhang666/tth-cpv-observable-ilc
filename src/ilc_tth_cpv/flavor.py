"""Reco flavor-score helpers for signed object ordering."""

from __future__ import annotations

import math
from typing import Mapping


LIGHT_QUARK_KEYS = ("mc_u", "mc_d", "mc_s", "mc_c")
LIGHT_ANTIQUARK_KEYS = ("mc_ubar", "mc_dbar", "mc_sbar", "mc_cbar")


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

    delta_L = math.log(L12)-math.log(L21)
    L_ratio = L12 / L21
    margin = abs(L_ratio - 1.0)

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
        "w1": first,
        "w2": second,
    }
    
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