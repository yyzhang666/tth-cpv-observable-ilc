#!/usr/bin/env python3
"""Write arguments.txt for the condor kinfit example: one line per chunk.

Usage:
    python3 make_arguments.py --config ../../configs/analysis_ow_lr.yaml
    python3 make_arguments.py --config ../../configs/analysis_ow_lr.yaml --component sm
    python3 make_arguments.py --config ... --chunks 0-9        # subset
"""

from __future__ import annotations

import argparse
import glob
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ilc_tth_cpv.io import load_analysis_config, load_yaml, repo_root  # noqa: E402


def parse_chunk_selection(spec: str | None, available: list) -> list:
    if not spec:
        return available
    out = []
    for part in spec.split(","):
        if "-" in part:
            lo, hi = part.split("-")
            out.extend(str(i) for i in range(int(lo), int(hi) + 1))
        else:
            out.append(part.strip())
    return [c for c in out if c in set(available)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--chunks", default=None, help="e.g. 0-9 or 0,5,7 (default: all found)")
    parser.add_argument("--component", choices=("interference", "sm"),
                        default="interference")
    parser.add_argument("--out", default="arguments.txt")
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    cfg = load_analysis_config(config_path)
    manifest = load_yaml(repo_root() / cfg["samples"]["manifest"])
    sample_config_key = (
        "sm_reco_sample" if args.component == "sm" else "reco_sample"
    )
    sample = manifest["signals"][cfg["samples"][sample_config_key]]

    # discover chunk ids from the files on disk
    pattern = str(Path(sample["path"]) / sample["file_pattern"])
    chunk_re = re.compile(
        re.escape(sample["file_pattern"]).replace(r"\*", r"(\d+)")
    )
    chunks = []
    for path in sorted(glob.glob(pattern)):
        match = chunk_re.search(Path(path).name)
        if match:
            chunks.append(match.group(1))
    chunks = sorted(set(chunks), key=int)
    selected = parse_chunk_selection(args.chunks, chunks)
    if not selected:
        raise SystemExit(f"No chunks found matching {pattern}")

    config_rel = config_path.relative_to(repo_root())
    lines = [f"{config_rel}, {chunk}, {args.component}" for chunk in selected]
    Path(args.out).write_text("\n".join(lines) + "\n")
    print(f"wrote {args.out}: {len(lines)} jobs "
          f"(chunks {selected[0]}..{selected[-1]} of {len(chunks)} available)")
    print("smoke-test first:  head -1 arguments.txt > arguments_smoke.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
