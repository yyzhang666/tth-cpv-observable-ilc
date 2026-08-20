#!/usr/bin/env python3
"""Create an immutable HTCondor DAG for one full selection-MVA run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .selection_mva_common import (
        atomic_json,
        implementation_identity,
        load_authority,
        selected_job_keys,
    )
except ImportError:
    from selection_mva_common import (
        atomic_json,
        implementation_identity,
        load_authority,
        selected_job_keys,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/mva_training.yaml"))
    parser.add_argument("--run-id", required=True)
    return parser.parse_args()


def dag_value(value: str | Path) -> str:
    text = str(value)
    if '"' in text or "\n" in text:
        raise RuntimeError(f"Unsafe DAG value: {text!r}")
    return text


def main() -> None:
    args = parse_args()
    authority = load_authority(args.config)
    root = authority.root
    implementation = implementation_identity(root)
    config_path = authority.config_path
    run_id = args.run_id
    workflow_dir = root / "outputs/mva/condor" / run_id
    model_dir = root / "outputs/mva/training" / run_id
    scores_dir = root / "outputs/mva/scores" / run_id
    evaluation_path = root / "outputs/mva/evaluation" / f"{run_id}.json"
    for path in (workflow_dir, model_dir, scores_dir, evaluation_path):
        if path.exists():
            raise RuntimeError(f"Refusing existing workflow output: {path}")
    (workflow_dir / "logs").mkdir(parents=True)
    (workflow_dir / "job_lists").mkdir()

    keys = selected_job_keys(authority, include_cpv=True)
    batch_size = int(authority.config["condor"]["apply"]["jobs_per_process"])
    batches = [keys[index:index + batch_size] for index in range(0, len(keys), batch_size)]
    dag_lines = []
    train_submit = root / "condor/mva/train.sub"
    apply_submit = root / "condor/mva/apply.sub"
    evaluate_submit = root / "condor/mva/evaluate.sub"
    log_dir = workflow_dir / "logs"
    model_path = model_dir / "model.json"

    dag_lines.extend([
        f"JOB TRAIN {dag_value(train_submit)}",
        "VARS TRAIN "
        f'repo_root="{dag_value(root)}" config="{dag_value(config_path)}" '
        f'run_id="{dag_value(run_id)}" log_dir="{dag_value(log_dir)}"',
    ])
    apply_nodes = []
    manifest_batches = []
    for index, keys_in_batch in enumerate(batches):
        batch_id = f"{index:04d}"
        node = f"APPLY{index:04d}"
        apply_nodes.append(node)
        job_list = workflow_dir / "job_lists" / f"batch-{batch_id}.txt"
        job_list.write_text("\n".join(keys_in_batch) + "\n")
        manifest_batches.append({"batch_id": batch_id, "jobs": keys_in_batch})
        dag_lines.extend([
            f"JOB {node} {dag_value(apply_submit)}",
            f"VARS {node} "
            f'repo_root="{dag_value(root)}" config="{dag_value(config_path)}" '
            f'model="{dag_value(model_path)}" scores_dir="{dag_value(scores_dir)}" '
            f'job_list="{dag_value(job_list)}" batch_id="{batch_id}" '
            f'log_dir="{dag_value(log_dir)}"',
            f"PARENT TRAIN CHILD {node}",
        ])
    dag_lines.extend([
        f"JOB EVALUATE {dag_value(evaluate_submit)}",
        "VARS EVALUATE "
        f'repo_root="{dag_value(root)}" config="{dag_value(config_path)}" '
        f'model="{dag_value(model_path)}" scores_dir="{dag_value(scores_dir)}" '
        f'evaluation="{dag_value(evaluation_path)}" log_dir="{dag_value(log_dir)}"',
        f"PARENT {' '.join(apply_nodes)} CHILD EVALUATE",
    ])
    dag_path = workflow_dir / "workflow.dag"
    dag_path.write_text("\n".join(dag_lines) + "\n")
    atomic_json(workflow_dir / "workflow_manifest.json", {
        "schema_version": 1,
        "run_id": run_id,
        "config": str(config_path),
        "weights_catalog_hash": authority.catalog_hash,
        "implementation": implementation,
        "model": str(model_path),
        "scores_dir": str(scores_dir),
        "evaluation": str(evaluation_path),
        "jobs": len(keys),
        "apply_batches": manifest_batches,
        "dag": str(dag_path),
        "submitted": False,
    })
    print(json.dumps({
        "dag": str(dag_path),
        "jobs": len(keys),
        "apply_batches": len(batches),
        "submit": f"condor_submit_dag {dag_path}",
    }, indent=2))


if __name__ == "__main__":
    main()
