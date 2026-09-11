#!/usr/bin/env python3
"""Run one whole Whizard file through a job-local current-SGV variant."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path


SGV_HOME = Path("/data/dust/user/zhangyuy/ZHH/mysgv_new")
SETUP = Path("/data/dust/user/zhangyuy/ZHH/setup.sh")
UPDATER = Path("/data/dust/user/zhangyuy/analysis/AI_PIPELINES/update_sgv_steering.py")
SAMPLE_PATTERN = re.compile(r"E550-Test\.Ptth\.Gwhizard-3_1_5\.eL\.pR\.I410213_([0-3])\.0\.slcio$")
VARIANT_LABEL = "current-SGV controlled variant"


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sample_index(path):
    match = SAMPLE_PATTERN.fullmatch(Path(path).name)
    if not match:
        raise ValueError(f"input is not one of the four frozen Whizard physical files: {path}")
    return int(match.group(1))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--lock-file", type=Path, required=True)
    parser.add_argument("--event-count", type=int, required=True)
    parser.add_argument("--allow-long-run", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    index = sample_index(args.input)
    if args.event_count <= 0:
        raise ValueError("event-count must be the positive actual count")
    if args.event_count > 20 and not args.allow_long_run:
        raise RuntimeError("SGV above 20 events requires the recorded long-run gate")
    input_path = args.input.resolve(strict=True)
    output_path = args.output.resolve(strict=False)
    run_dir = args.run_dir.resolve(strict=False)
    if output_path.exists() or output_path.is_symlink():
        raise RuntimeError(f"refusing to overwrite SGV output: {output_path}")
    if run_dir.exists() or run_dir.is_symlink():
        raise RuntimeError(f"refusing to reuse SGV run directory: {run_dir}")
    run_dir.mkdir(parents=True)
    local_steer = run_dir / "sgv.steer"
    shutil.copy2(SGV_HOME / "sgv.steer", local_steer)
    (run_dir / "fort.17").symlink_to("sgv.steer")
    for source in SGV_HOME.iterdir():
        if source.name in {"sgv.steer", "fort.17"} or source.suffix == ".slcio":
            continue
        (run_dir / source.name).symlink_to(source)
    temporary_output = run_dir / "sgvout.slcio"
    subprocess.run(
        ["python3", str(UPDATER), str(local_steer), str(input_path), temporary_output.name, "0", str(args.event_count), "LCIO"],
        check=True,
    )
    executable = run_dir / "usesgvlcio.exe"
    command = [str(executable)]
    runtime = {
        "variant_label": VARIANT_LABEL,
        "historical_sgv_exactly_reproduced": False,
        "sample_index": index,
        "input": str(input_path),
        "output": str(output_path),
        "event_count": args.event_count,
        "n_skip": 0,
        "command": command,
        "cwd": str(run_dir),
        "files": {
            "executable": {"path": str(SGV_HOME / "usesgvlcio.exe"), "sha256": sha256(SGV_HOME / "usesgvlcio.exe")},
            "source_steer": {"path": str(SGV_HOME / "sgv.steer"), "sha256": sha256(SGV_HOME / "sgv.steer")},
            "local_steer": {"path": str(local_steer), "sha256": sha256(local_steer)},
            "setup": {"path": str(SETUP), "sha256": sha256(SETUP)},
            "updater": {"path": str(UPDATER), "sha256": sha256(UPDATER)},
            "fort17_target": os.readlink(run_dir / "fort.17"),
        },
    }
    (run_dir / "runtime_manifest.json").write_text(json.dumps(runtime, indent=2, sort_keys=True) + "\n")
    if args.prepare_only:
        return
    args.lock_file.parent.mkdir(parents=True, exist_ok=True)
    with args.lock_file.open("a+") as lock_stream:
        fcntl.flock(lock_stream, fcntl.LOCK_EX)
        shell = 'source "$1" >/dev/null 2>&1; exec "$2"'
        with (run_dir / "sgv.log").open("xb") as log_stream:
            subprocess.run(
                ["bash", "-lc", shell, "bash", str(SETUP), str(executable)],
                check=True,
                cwd=run_dir,
                stdout=log_stream,
                stderr=subprocess.STDOUT,
            )
    if not temporary_output.is_file() or temporary_output.is_symlink():
        raise RuntimeError("SGV did not create a regular non-empty job-local output")
    if temporary_output.stat().st_size <= 0:
        raise RuntimeError("SGV created an empty job-local output")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    os.replace(temporary_output, output_path)


if __name__ == "__main__":
    main()
