#!/bin/bash
set -euo pipefail

if [[ $# -ne 4 ]]; then
  echo "usage: $0 REPO_ROOT RUN_ROOT INDEX INPUT" >&2
  exit 2
fi

repo_root=$1
run_root=$2
index=$3
input=$4

case "$index" in
  0|1|2|3) ;;
  *) echo "invalid Whizard sample index: $index" >&2; exit 2 ;;
esac

python3 "$repo_root/scripts/reco_performance/run_whizard_sgv.py" \
  --input "$input" \
  --output "$run_root/sgv/whizard_I410213_${index}_sgv.slcio" \
  --run-dir "$run_root/sgv/run_${index}" \
  --lock-file "$run_root/sgv/sgv.lock" \
  --event-count 12500 \
  --allow-long-run

python3 "$repo_root/scripts/reco_performance/run_whizard_marlin.py" reco \
  --authority "$repo_root/reco_performance_study/steering/reference/whizard_complete_reco_20260616.xml" \
  --input "$run_root/sgv/whizard_I410213_${index}_sgv.slcio" \
  --output "$run_root/reco/whizard_I410213_${index}_complete_reco.slcio" \
  --run-dir "$run_root/reco/run_${index}" \
  --event-count 12500 \
  --allow-long-run \
  --accept-validated-reco-tail-segv
