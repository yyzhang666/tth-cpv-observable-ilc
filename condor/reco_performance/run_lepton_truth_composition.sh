#!/bin/bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "usage: $0 REPO_ROOT RUN_ROOT COUNTS_JSON" >&2
  exit 2
fi

repo_root=$1
run_root=$2
counts_json=$3
input_root=/data/dust/user/zhangyuy/analysis/tth/events_physsim/production/sm_tth/eL.pR/I01234_0/complete_reco
arguments=()
for chunk in {1..10}; do
  arguments+=(
    --complete
    "$input_root/complete_reco_kinfit_ready_E550-Test.Ptth.Gphyssim.eL.pR.I01234_0.${chunk}_sgv.slcio"
  )
done

source /data/dust/user/zhangyuy/analysis/tth/ZHH/setup.sh >/dev/null 2>&1
exec python3 "$repo_root/scripts/reco_performance/report_lepton_selection_truth_composition.py" \
  "${arguments[@]}" \
  --counts-json "$counts_json" \
  --legacy "$repo_root/reco_performance_study/legacy/count_hbb_ttbar_had_iso_pass.py" \
  --output-dir "$run_root/result"
