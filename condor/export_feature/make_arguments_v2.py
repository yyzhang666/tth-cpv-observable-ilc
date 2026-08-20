#!/usr/bin/env python3
"""Write arguments.txt for the feature-export HTCondor workflow.

One line corresponds to one production chunk.

Examples:
    python3 make_arguments.py --config ../../configs/analysis_ml_superdataset_lr.yaml
    python3 make_arguments.py --config ../../configs/analysis_ml_superdataset_lr.yaml --chunks 0
    python3 make_arguments.py --config ../../configs/analysis_ml_superdataset_lr.yaml --chunks 0-9
    python3 make_arguments.py --config ../../configs/analysis_ml_superdataset_lr.yaml --component sm
    python3 make_arguments.py --config ../../configs/analysis_ml_superdataset_lr.yaml --level gen

This script only discovers chunks from the configured production sample and
writes Condor arguments. Input resolution and feature-export logic remain in
scripts/export_features.py and the analysis YAML.
"""

from __future__ import annotations

import argparse
import glob
import re
import sys
from pathlib import Path

WORKFLOW_DIR = Path(__file__).resolve().parent
REPO_ROOT = WORKFLOW_DIR.parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ilc_tth_cpv.io import load_analysis_config, load_yaml, repo_root  # noqa: E402


def parse_chunk_selection(spec: str | None, available: list[str]) -> list[str]:
    if not spec:
        return available

    requested = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            requested.extend(str(i) for i in range(int(lo), int(hi) + 1))
        else:
            requested.append(part)

    available_set = set(available)
    missing = [chunk for chunk in requested if chunk not in available_set]
    if missing:
        raise SystemExit(
            "Requested chunks are not present in the configured sample: "
            + ", ".join(missing)
        )
    return requested


def configured_sample(cfg: dict, manifest: dict, level: str, component: str) -> dict:
    prefix = "sm_" if component == "sm" else ""
    config_key = f"{prefix}{level}_sample"
    if config_key not in cfg["samples"]:
        raise SystemExit(f"Config has no samples.{config_key}")

    sample_key = cfg["samples"][config_key]
    try:
        return manifest["signals"][sample_key]
    except KeyError as exc:
        raise SystemExit(f"Sample '{sample_key}' is missing from samples manifest") from exc


def discover_chunks(sample: dict) -> list[str]:
    file_pattern = sample["file_pattern"]
    base = Path(sample["path"])

    if "*" not in file_pattern:
        path = base / file_pattern
        return ["0"] if path.exists() else []

    glob_pattern = str(base / file_pattern)
    chunk_re = re.compile(
        "^" + re.escape(file_pattern).replace(r"\*", r"([0-9]+)") + "$"
    )

    chunks = []
    for path_str in glob.glob(glob_pattern):
        match = chunk_re.match(Path(path_str).name)
        if match:
            chunks.append(match.group(1))

    return sorted(set(chunks), key=int)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True,
                        help="analysis YAML used by scripts/export_features.py")
    parser.add_argument("--chunks", default=None,
                        help="subset such as 0, 0-9, or 0,5,7 (default: all found)")
    parser.add_argument("--component", choices=("interference", "sm"),
                        default="interference")
    parser.add_argument("--level", choices=("gen", "reco"), default="reco")
    parser.add_argument("--out", default=str(WORKFLOW_DIR / "arguments_v2.txt"))
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    cfg = load_analysis_config(config_path)
    manifest = load_yaml(repo_root() / cfg["samples"]["manifest"])
    sample = configured_sample(cfg, manifest, args.level, args.component)

    chunks = discover_chunks(sample)
    if not chunks:
        raise SystemExit(
            "No chunks found for configured sample: "
            f"{sample['path']}/{sample['file_pattern']}"
        )

    selected = parse_chunk_selection(args.chunks, chunks)
    config_rel = config_path.relative_to(repo_root())

    model_tag = "cpv" if args.component == "interference" else "sm"
    out_dir = f"outputs/ml_superdataset/features_v2/{args.level}_{model_tag}"

    lines = [
        f"{config_rel}, {chunk}, {args.component}, {args.level}"
        for chunk in selected
    ]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n")

    for name in ("log", "out", "err"):
        (WORKFLOW_DIR / name).mkdir(parents=True, exist_ok=True)

    print(f"wrote {out_path}: {len(lines)} jobs")
    print(
        f"level={args.level} component={args.component} "
        f"chunks={selected[0]}..{selected[-1]}"
    )
    print("smoke test first with --chunks 0 before submitting all chunks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
