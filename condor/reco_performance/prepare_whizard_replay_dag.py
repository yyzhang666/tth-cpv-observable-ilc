#!/usr/bin/env python3
"""Create one immutable four-file Whizard SGV -> complete-reco DAG."""

from __future__ import annotations

import argparse
from pathlib import Path


INPUT_TEMPLATE = (
    "/pnfs/desy.de/ilc/prod/ilc/mc-2025/generated/550-TDR_ws/8f/"
    "E550-Test.Ptth.Gwhizard-3_1_5.eL.pR.I410213_{index}.0.slcio"
)


def dag_quote(value):
    value = str(value)
    if '"' in value or "\n" in value:
        raise ValueError(f"unsupported DAG value: {value!r}")
    return value


def render_dag(repo_root, run_root):
    sgv_submit = repo_root / "condor/reco_performance/whizard_sgv.sub"
    reco_submit = repo_root / "condor/reco_performance/whizard_reco.sub"
    lines = []
    for index in range(4):
        common = (
            f'repo_root="{dag_quote(repo_root)}" '
            f'run_root="{dag_quote(run_root)}" index="{index}"'
        )
        lines.extend(
            (
                f"JOB SGV{index} {sgv_submit}",
                f'VARS SGV{index} {common} input="{INPUT_TEMPLATE.format(index=index)}"',
                f"JOB RECO{index} {reco_submit}",
                f"VARS RECO{index} {common}",
                f"PARENT SGV{index} CHILD RECO{index}",
            )
        )
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    args = parser.parse_args()
    repo_root = args.repo_root.resolve(strict=True)
    run_root = args.run_root.resolve(strict=False)
    if run_root.exists() or run_root.is_symlink():
        raise RuntimeError(f"refusing to reuse run root: {run_root}")
    for relative in ("condor", "sgv", "reco"):
        (run_root / relative).mkdir(parents=True)
    dag_path = run_root / "whizard_sgv_reco.dag"
    dag_path.write_text(render_dag(repo_root, run_root), encoding="utf-8")
    print(dag_path)


if __name__ == "__main__":
    main()
