#!/bin/bash
set -euo pipefail

repo_root=$1
config=$2
model=$3
scores_dir=$4
evaluation=$5

cd "$repo_root"
source env/setup.sh
export OMP_NUM_THREADS=2
python3 scripts/mva/evaluate_selection.py \
  --config "$config" \
  --model "$model" \
  --scores-dir "$scores_dir" \
  --output "$evaluation"
