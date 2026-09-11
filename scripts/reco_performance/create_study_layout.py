#!/usr/bin/env python3
"""Create the fixed reco-performance directory layout and repository links."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


OUTPUT_GROUPS = (
    "generator_mtt",
    "physsim_leptons",
    "whizard_jet_flavor",
    "whizard_jet_assignment",
)
STEERING_GROUPS = ("generator", "sgv", "reco", "kinfit")
RECORD_GROUPS = (
    "contract",
    "input_manifest",
    "runtime_manifest",
    "xml_diff",
    "validation",
    "handoff",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--study-root", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo_root.resolve(strict=True)
    study = args.study_root.resolve(strict=False)

    for group in OUTPUT_GROUPS:
        (study / "outputs" / group).mkdir(parents=True, exist_ok=True)
    for group in STEERING_GROUPS:
        (study / "steering" / group).mkdir(parents=True, exist_ok=True)
    for group in RECORD_GROUPS:
        (study / "records" / group).mkdir(parents=True, exist_ok=True)
    (study / "scripts").mkdir(parents=True, exist_ok=True)
    (study / "functions").mkdir(parents=True, exist_ok=True)

    links = {
        study / "scripts" / "repo": repo / "scripts" / "reco_performance",
        study / "functions" / "reco_performance.py": repo / "src" / "ilc_tth_cpv" / "reco_performance.py",
    }
    records = []
    for link, target in links.items():
        target = target.resolve(strict=True)
        if link.is_symlink():
            if link.resolve(strict=True) != target:
                raise RuntimeError(f"existing link has a different target: {link}")
        elif link.exists():
            raise RuntimeError(f"refusing to replace existing path: {link}")
        else:
            link.symlink_to(target)
        records.append({"link": str(link), "target": str(target)})

    manifest_source = repo / "reco_performance_study" / "study_inputs.json"
    manifest_target = study / "records" / "input_manifest" / "study_inputs.json"
    if not manifest_target.exists():
        manifest_target.symlink_to(manifest_source.resolve(strict=True))
    elif not manifest_target.is_symlink() or manifest_target.resolve(strict=True) != manifest_source.resolve(strict=True):
        raise RuntimeError(f"refusing to replace existing manifest path: {manifest_target}")

    payload = {
        "repo_root": str(repo),
        "git_commit": subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "links": records,
        "linked_file_sha256": {
            "functions/reco_performance.py": sha256(repo / "src" / "ilc_tth_cpv" / "reco_performance.py"),
            "records/input_manifest/study_inputs.json": sha256(manifest_source),
        },
    }
    output = study / "records" / "runtime_manifest" / "repository_links.json"
    if output.exists():
        existing = json.loads(output.read_text(encoding="utf-8"))
        if existing != payload:
            raise RuntimeError(f"refusing to overwrite changed link manifest: {output}")
    else:
        output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
