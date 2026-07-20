#!/usr/bin/env python3
"""TEMPLATE — minimal feature export loop.

The real exporter is scripts/export_features.py (config-driven). This
template strips it to the essentials so the data flow is visible:

    sidecar weights -> truth objects -> frame -> RAW features -> CSV row

Key contract points (docs/DATA_SCHEMA.md):
- FEATURES ARE RAW VARIABLES: E, theta, phi (+ mass) per object.
  No log/sin/cos or other transformations (frozen supervisor decision).
- every weight column exists (NaN when unavailable, never silent zeros);
- deterministic split from event_id + seed (same split at gen and reco);
- <obj>_valid flags missing objects instead of fake zeros.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ilc_tth_cpv.features import deterministic_split, raw_object_features
from ilc_tth_cpv.io import write_table

NAN = float("nan")


def build_row(event_id: int, w_signed: float, objects: dict, seed: int) -> dict:
    """objects: {name: (E, theta, phi) or None} evaluated in ONE frame."""
    row = {
        "event_id": event_id,
        "sample_name": "template_demo",
        "process": "ttH_CPVint",
        "level": "gen",
        "helicity": "LR",
        "split": deterministic_split(
            event_id, seed, {"train": 0.6, "validation": 0.2, "test": 0.2}
        ),
        # weight block — training and template weights are SEPARATE
        "weight_sm": NAN,                          # from SM sample bookkeeping
        "weight_interference_signed": w_signed,    # physics templates
        "weight_interference_abs": abs(w_signed),
        "weight_quadratic": NAN,
        "weight_training": abs(w_signed),          # |w|, balancing later
        "weight_polarization": NAN,
        "weight_luminosity": NAN,
        "weight_template": w_signed,
        "label": 1 if w_signed > 0 else -1,
    }
    for name, triple in objects.items():
        if triple is None:
            row.update(raw_object_features(name, None, None, None))
        else:
            energy, theta, phi = triple
            row.update(raw_object_features(name, energy, theta, phi))
    return row


def main() -> int:
    # Fake three events to show the mechanics without pyLCIO.
    rows = [
        build_row(1, +0.004, {"wjet_quark": (95.0, 1.2, 1.2), "wjet_antiquark": (80.0, 1.7, -0.7)}, 20260720),
        build_row(2, -0.004, {"wjet_quark": (120.0, 2.1, 2.9), "wjet_antiquark": (60.0, 1.4, 0.4)}, 20260720),
        build_row(3, +0.004, {"wjet_quark": None, "wjet_antiquark": (70.0, 1.6, 0.0)}, 20260720),
    ]
    out = Path("/tmp/ilc_tth_cpv_template_features.csv")
    write_table(out, rows, metadata={"note": "template demo, not physics"})
    print(f"wrote {out}")
    for row in rows:
        print(f"event {row['event_id']}: split={row['split']} "
              f"valid_quark={row['wjet_quark_valid']} label={row['label']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
