#!/usr/bin/env python3
"""Join the supervisor's event-selection MVA scores onto a feature table.

Interface: docs/MVA_INTERFACE.md. Reports unmatched/duplicated ids.

Usage:
    python3 scripts/join_selection_mva.py \
        --features outputs/ow_lr/features/features_gen_higgs_rest.csv \
        --scores outputs/mva/scores.csv
"""

from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ilc_tth_cpv.io import read_table, write_table  # noqa: E402

REQUIRED_SCORE_COLUMNS = ("event_id", "mva_score", "pass_nominal_mva", "model_version")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", required=True)
    parser.add_argument("--scores", required=True)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    scores = read_table(Path(args.scores))
    if not scores:
        raise SystemExit("Empty score file")
    missing = [c for c in REQUIRED_SCORE_COLUMNS if c not in scores[0]]
    if missing:
        raise SystemExit(f"Score file missing columns {missing} (docs/MVA_INTERFACE.md)")

    by_id = {}
    duplicates = 0
    for row in scores:
        key = row["event_id"]
        if key in by_id:
            duplicates += 1
        by_id[key] = row
    if duplicates:
        raise SystemExit(f"{duplicates} duplicated event_id in score file")

    rows = read_table(Path(args.features))
    n_matched = 0
    for row in rows:
        score_row = by_id.get(row["event_id"])
        if score_row is None:
            row["mva_score"] = float("nan")
            row["pass_nominal_mva"] = ""
            row["mva_model_version"] = ""
        else:
            row["mva_score"] = score_row["mva_score"]
            row["pass_nominal_mva"] = score_row["pass_nominal_mva"]
            row["mva_model_version"] = score_row["model_version"]
            n_matched += 1

    unmatched_features = len(rows) - n_matched
    unmatched_scores = len(by_id) - n_matched
    print(f"feature rows={len(rows)} matched={n_matched} "
          f"unmatched_features={unmatched_features} unmatched_scores={unmatched_scores}")
    if unmatched_features:
        print("NOTE: unmatched feature events must be justified before physics use.")

    out_path = Path(args.out) if args.out else Path(
        str(args.features).replace(".csv", ".mva.csv")
    )
    write_table(out_path, rows, metadata={
        "features": str(args.features),
        "scores": str(args.scores),
        "n_matched": n_matched,
        "unmatched_features": unmatched_features,
        "unmatched_scores": unmatched_scores,
        "created": datetime.datetime.now().isoformat(),
    })
    print(f"wrote -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
