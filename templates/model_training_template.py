#!/usr/bin/env python3
"""TEMPLATE — model training conventions (no real data needed).

Demonstrates on toy data the four rules every training must satisfy:
1. deterministic split, no leakage between train/validation/test;
2. labels = sign of the interference weight; class order frozen and stored;
3. training weight = |w_int| (balancing allowed) — template weight stays signed;
4. model metadata JSON records everything needed to reproduce and to
   interpret the score (O_ML = P(+) - P(-)).

The production trainer is scripts/train_cpv_model.py.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ilc_tth_cpv.features import deterministic_split


def toy_events(n: int, seed: int):
    rng = random.Random(seed)
    events = []
    for event_id in range(1, n + 1):
        # toy: one feature carries the CP information
        label = 1 if rng.random() < 0.5 else -1
        x = rng.gauss(0.3 * label, 1.0)
        w_signed = label * abs(rng.gauss(0.004, 0.001))
        events.append({"event_id": event_id, "x": [x], "label": label,
                       "w_signed": w_signed})
    return events


def main() -> int:
    seed = 20260720
    events = toy_events(2000, seed)
    fractions = {"train": 0.6, "validation": 0.2, "test": 0.2}

    # Rule 1: deterministic split — recomputable from event_id alone.
    pools = {"train": [], "validation": [], "test": []}
    for evt in events:
        pools[deterministic_split(evt["event_id"], seed, fractions)].append(evt)
    assert not (set(e["event_id"] for e in pools["train"])
                & set(e["event_id"] for e in pools["test"]))

    # Rule 3: training weights |w|, balanced; signed weights kept aside.
    for pool in pools.values():
        for evt in pool:
            evt["w_train"] = abs(evt["w_signed"])
    pos = sum(e["w_train"] for e in pools["train"] if e["label"] > 0)
    neg = sum(e["w_train"] for e in pools["train"] if e["label"] < 0)
    for evt in pools["train"]:
        if evt["label"] < 0:
            evt["w_train"] *= pos / neg
    print(f"balanced class sums: +{pos:.4f} / -{neg * pos / neg:.4f}")

    try:
        from catboost import CatBoostClassifier
    except ImportError:
        print("catboost not installed — template stops before fitting, "
              "conventions above still apply.")
        return 0

    model = CatBoostClassifier(iterations=50, depth=3, random_seed=seed, verbose=0)
    model.fit(
        [e["x"] for e in pools["train"]],
        [e["label"] for e in pools["train"]],
        sample_weight=[e["w_train"] for e in pools["train"]],
        eval_set=(
            [e["x"] for e in pools["validation"]],
            [e["label"] for e in pools["validation"]],
        ),
    )

    # Rule 2: resolve class columns BY LABEL VALUE, never by position.
    classes = [int(c) for c in model.classes_]
    plus_idx, minus_idx = classes.index(1), classes.index(-1)

    # Score on the independent test split only.
    proba = model.predict_proba([e["x"] for e in pools["test"]])
    scores = [p[plus_idx] - p[minus_idx] for p in proba]
    print(f"test events: {len(scores)}; first scores: "
          + ", ".join(f"{s:+.3f}" for s in scores[:5]))

    # Rule 4: metadata.
    metadata = {
        "model_type": "catboost",
        "class_order_model": classes,
        "score_definition": "P(+) - P(-)",
        "seed": seed,
        "split_fractions": fractions,
        "weight_convention": "training=|w_int| balanced; templates=signed w_int",
    }
    out = Path("/tmp/ilc_tth_cpv_template_model_metadata.json")
    out.write_text(json.dumps(metadata, indent=2))
    print(f"metadata -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
