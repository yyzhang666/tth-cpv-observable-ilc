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
    """Orient selected W slots as q/qbar using signed light-flavor scores.

    Opposite q/qbar preferences are used directly. If both jets are q-like,
    the one with larger P(q) is q. If both are qbar-like, the one with larger
    P(qbar) is qbar. Exact decision-score ties keep W1 as q and are explicitly
    labelled.
    """
    first = light_charge_scores(w1_scores)
    second = light_charge_scores(w2_scores)
    first_q_like = first["signed_score"] >= 0.0
    second_q_like = second["signed_score"] >= 0.0
    if first_q_like != second_q_like:
        quark_slot, antiquark_slot = ((0, 1) if first_q_like else (1, 0))
        status = "opposite_preferences"
        margin = min(abs(first["signed_score"]), abs(second["signed_score"]))
    elif first_q_like:
        delta = first["p_quark"] - second["p_quark"]
        if abs(delta) <= tie_tolerance:
            quark_slot, antiquark_slot = 0, 1
            status = "tie_slot_order"
        else:
            quark_slot, antiquark_slot = ((0, 1) if delta > 0.0 else (1, 0))
            status = "both_q_like"
        margin = abs(delta)
    else:
        delta = first["p_antiquark"] - second["p_antiquark"]
        if abs(delta) <= tie_tolerance:
            quark_slot, antiquark_slot = 0, 1
            status = "tie_slot_order"
        else:
            antiquark_slot, quark_slot = ((0, 1) if delta > 0.0 else (1, 0))
            status = "both_qbar_like"
        margin = abs(delta)
    return {
        "quark_slot": quark_slot,
        "antiquark_slot": antiquark_slot,
        "margin": margin,
        "status": status,
        "w1": first,
        "w2": second,
    }
