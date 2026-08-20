#!/bin/bash
set -euo pipefail

repo_root=$1
config=$2
run_id=$3

cd "$repo_root"
source env/setup.sh
export OMP_NUM_THREADS=8
python3 scripts/mva/train_selection_mva.py \
  --config "$config" \
  --run-id "$run_id"
