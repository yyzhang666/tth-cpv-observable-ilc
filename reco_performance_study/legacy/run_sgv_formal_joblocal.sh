#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 5 ]]; then
  echo "Usage: $0 CHUNK TAG INPUT_STDHEP OUTPUT_ROOT MAX_EVENTS" >&2
  exit 2
fi

CHUNK="$1"
TAG="$2"
INPUT_STDHEP="$3"
OUTPUT_ROOT="$4"
MAX_EVENTS="$5"

ANALYSIS_ROOT=/data/dust/user/zhangyuy/analysis
ZHH_ROOT=/data/dust/user/zhangyuy/ZHH
LATEST_SGV_DIR="$ZHH_ROOT/mysgv_new"
UPDATE_STEERING="$ANALYSIS_ROOT/AI_PIPELINES/update_sgv_steering.py"
LINEAGE_CSV="$ANALYSIS_ROOT/AI_PIPELINES/workflow_lineage.csv"
LINEAGE_LOCK="$ANALYSIS_ROOT/AI_PIPELINES/workflow_lineage.lock"

SGV_DIR="$OUTPUT_ROOT/sgv"
LOG_DIR="$OUTPUT_ROOT/logs_and_dumps"
WORK_ROOT="$OUTPUT_ROOT/work_sgv"
LOCK_DIR="$OUTPUT_ROOT/locks"
JOB_WORKDIR="$WORK_ROOT/$TAG"

FINAL_SGV="$SGV_DIR/${TAG}_sgv.slcio"
TMP_SGV_NAME="sgvout.slcio"
TMP_SGV="$JOB_WORKDIR/$TMP_SGV_NAME"
LOG_FILE="$LOG_DIR/sgv_${TAG}.log"

if [[ ! -s "$INPUT_STDHEP" ]]; then
  echo "Missing or empty input stdhep: $INPUT_STDHEP" >&2
  exit 1
fi

for required in "$ZHH_ROOT/setup.sh" "$LATEST_SGV_DIR/sgv.steer" "$LATEST_SGV_DIR/usesgvlcio.exe" "$UPDATE_STEERING"; do
  if [[ ! -e "$required" ]]; then
    echo "Missing required file: $required" >&2
    exit 1
  fi
done

for output in "$FINAL_SGV" "$LOG_FILE"; do
  if [[ -e "$output" ]]; then
    echo "Refusing to overwrite existing file: $output" >&2
    exit 3
  fi
done

mkdir -p "$SGV_DIR" "$LOG_DIR" "$WORK_ROOT" "$LOCK_DIR" "$JOB_WORKDIR"

if [[ -e "$TMP_SGV" ]]; then
  echo "Refusing to overwrite existing temporary SGV output: $TMP_SGV" >&2
  exit 3
fi

cleanup_success() {
  if [[ "${KEEP_SGV_WORKDIR:-0}" == "1" ]]; then
    return 0
  fi
  case "$JOB_WORKDIR" in
    "$WORK_ROOT"/*) rm -rf "$JOB_WORKDIR" ;;
    *) echo "Refusing to remove unexpected workdir path: $JOB_WORKDIR" >&2; return 6 ;;
  esac
}

find "$LATEST_SGV_DIR" -maxdepth 1 \( -type f -o -type l \) ! -name "*.slcio" -exec ln -sf {} "$JOB_WORKDIR"/ \;
rm -f "$JOB_WORKDIR/sgv.steer" "$JOB_WORKDIR/fort.17"
cp -p "$LATEST_SGV_DIR/sgv.steer" "$JOB_WORKDIR/sgv.steer"
( cd "$JOB_WORKDIR" && ln -s sgv.steer fort.17 )

python3 "$UPDATE_STEERING" "$JOB_WORKDIR/sgv.steer" "$INPUT_STDHEP" "$TMP_SGV_NAME" 0 "$MAX_EVENTS" STDH

echo "[1/4] Run SGV chunk=$CHUNK tag=$TAG"
set +u
source "$ZHH_ROOT/setup.sh"
set -u
set +e
( cd "$JOB_WORKDIR" && ./usesgvlcio.exe > "$LOG_FILE" 2>&1 )
SGV_STATUS=$?
set -e
echo "SGV exit code: $SGV_STATUS"
tail -n 60 "$LOG_FILE" || true

if [[ "$SGV_STATUS" -ne 0 ]]; then
  echo "SGV failed; workdir kept for diagnostics: $JOB_WORKDIR" >&2
  exit "$SGV_STATUS"
fi

if [[ ! -s "$TMP_SGV" ]]; then
  echo "SGV did not produce a non-empty file: $TMP_SGV" >&2
  exit 1
fi

if [[ -L "$TMP_SGV" ]]; then
  echo "Refusing to promote symlinked SGV output: $TMP_SGV -> $(readlink "$TMP_SGV")" >&2
  exit 1
fi

mv "$TMP_SGV" "$FINAL_SGV"

echo "[2/4] Append workflow record"
flock "$LINEAGE_LOCK" python3 - "$LINEAGE_CSV" "$INPUT_STDHEP" "$FINAL_SGV" "$LOG_FILE" "$MAX_EVENTS" <<'PY'
import csv
import datetime as dt
import sys
from pathlib import Path

lineage = Path(sys.argv[1])
input_path, output_path, log_path, max_events = sys.argv[2:6]
fieldnames = ["date", "branch", "stage", "input_path", "output_path", "producer_or_script", "notes"]
row = {
    "date": dt.date.today().isoformat(),
    "branch": "physsim",
    "stage": "sgv_latest_common_baseline",
    "input_path": input_path,
    "output_path": f"{output_path}; {log_path}",
    "producer_or_script": "/afs/desy.de/user/z/zhangyuy/condorworkflow_tth_physsim/run_sgv.sh",
    "notes": f"Job-local SGV steering; GENERATOR_INPUT_TYPE=STDH; MAXEV={max_events}; N_SKIP=0",
}
exists = lineage.is_file()
with lineage.open("a", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fieldnames)
    if not exists:
        writer.writeheader()
    writer.writerow(row)
print(f"record_appended output={output_path}")
PY

echo "[3/4] Summary"
ls -lh "$FINAL_SGV" "$LOG_FILE"

echo "[4/4] Cleanup"
cleanup_success
echo "Done."
