#!/usr/bin/env python3
"""Score one v3 feature table with the fixed electron/muon CPV models."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ilc_tth_cpv.model_scoring import COMPONENTS, score_feature_table  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    score = subparsers.add_parser("score", help="score and merge probabilities into test rows")
    score.add_argument("--input", required=True)
    score.add_argument("--component", choices=COMPONENTS, required=True)
    score.add_argument("--model-root", required=True)
    score.add_argument("--model-tag", required=True)
    score.add_argument("--output", required=True)
    score.add_argument("--score-column", default="q_CPV_wtype_v0")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output = score_feature_table(
        input_csv=Path(args.input),
        component=args.component,
        model_root=Path(args.model_root),
        model_tag=args.model_tag,
        output=Path(args.output),
        score_column=args.score_column,
    )
    metadata = json.loads(output.with_suffix(".meta.json").read_text())
    print(
        f"scored {metadata['n_output_rows']} test rows; "
        f"dropped {metadata['n_dropped_nonfinite']} nonfinite -> {output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
