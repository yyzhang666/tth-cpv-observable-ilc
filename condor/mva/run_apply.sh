#!/bin/bash
set -euo pipefail

repo_root=$1
config=$2
model=$3
scores_dir=$4
job_list=$5
batch_id=$6

cd "$repo_root"
source env/setup.sh
export OMP_NUM_THREADS=1
python3 scripts/mva/apply_selection.py \
  --config "$config" \
  --model "$model" \
  --output-dir "$scores_dir" \
  --job-list "$job_list" \
  --batch-id "$batch_id" \
  --include-cpv
