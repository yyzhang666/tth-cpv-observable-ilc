"""Shared feature-list expansion and row-level feature resolution.

The dynamic fallbacks are the frozen behavior previously implemented inside
``scripts/train_cpv_model.py``.  Both binary and three-class training import
this module so derived features cannot drift between workflows.
"""

from __future__ import annotations

import math
from typing import Any, Mapping


def to_float(value: object) -> float:
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


def resolve_feature_value(row: Mapping[str, object], feature_name: str) -> float:
    """Read a feature, including the frozen derived-feature fallbacks."""
    direct = to_float(row.get(feature_name))
    if math.isfinite(direct):
        return direct

    if feature_name.startswith("down_type_daughter_"):
        variable = feature_name.removeprefix("down_type_daughter_")
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

    if feature_name.startswith("second_w_daughter_"):
        variable = feature_name.removeprefix("second_w_daughter_")
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

    if feature_name.startswith("neutrino"):
        direct = to_float(row.get(feature_name))
        if math.isfinite(direct):
            return direct
        if feature_name == "neutrino_pt":
            energy = to_float(row.get("neutrino_E"))
            theta = to_float(row.get("neutrino_theta"))
            if math.isfinite(energy) and math.isfinite(theta):
                return energy * math.sin(theta)
        return float("nan")

    if feature_name == "w_assignment_likelihood_selected":
        preference = row.get("w_orientation_status")
        if preference == "L12_preferred":
            selected = row.get("L12")
        elif preference == "L21_preferred":
            selected = row.get("L21")
        else:
            selected = None
        return to_float(selected)

    return float("nan")
