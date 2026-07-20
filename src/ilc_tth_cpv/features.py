"""ML feature conventions (docs/DATA_SCHEMA.md).

FROZEN POLICY (supervisor decision 2026-07-20): ML inputs are the RAW
variables — object E, theta, phi (plus masses and scores where configured).
Do NOT introduce derived encodings (log E, cos theta, sin/cos phi, ...) at
this stage; if that study is ever wanted it needs a supervisor-approved
config change, not an ad-hoc transformation.

Four-vectors are kept upstream for boosts and invariant masses; this module
only assembles already-frame-evaluated raw values.
"""

from __future__ import annotations

from typing import Dict, Optional

RAW_SUFFIXES = ("E", "theta", "phi")


def raw_object_features(
    name: str,
    energy: Optional[float],
    theta: Optional[float],
    phi: Optional[float],
) -> Dict[str, float]:
    """Raw features for one object; NaN + valid=0 when missing."""
    nan = float("nan")
    if energy is None or theta is None or phi is None or energy <= 0.0:
        return {
            f"{name}_E": nan,
            f"{name}_theta": nan,
            f"{name}_phi": nan,
            f"{name}_valid": 0,
        }
    return {
        f"{name}_E": energy,
        f"{name}_theta": theta,
        f"{name}_phi": phi,
        f"{name}_valid": 1,
    }


def minimal_feature_columns(object_names: list) -> list:
    """Ordered raw-feature column list (frozen order)."""
    cols = []
    for name in object_names:
        cols.extend(f"{name}_{suffix}" for suffix in RAW_SUFFIXES)
    return cols


def deterministic_split(
    event_id: int, seed: int, fractions: Dict[str, float]
) -> str:
    """Deterministic split from a hash of (event_id, seed).

    Same event_id + seed always lands in the same split, independent of
    processing order — required for identical gen/reco splits.
    """
    import hashlib

    digest = hashlib.sha256(f"{seed}:{event_id}".encode()).hexdigest()
    u = int(digest[:12], 16) / float(16**12)
    acc = 0.0
    items = list(fractions.items())
    for name, frac in items:
        acc += float(frac)
        if u < acc:
            return name
    return items[-1][0]
