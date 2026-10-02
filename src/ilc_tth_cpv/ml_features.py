"""Compatibility exports for the authoritative input-feature registry."""

from ilc_tth_cpv.input_features import (
    feature_columns_from_config,
    resolve_feature_value,
    to_float,
)

__all__ = [
    "feature_columns_from_config",
    "resolve_feature_value",
    "to_float",
]
