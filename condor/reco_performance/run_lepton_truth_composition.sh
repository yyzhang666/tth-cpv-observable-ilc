#!/bin/bash
set -eo pipefail

if [[ $# -ne 4 ]]; then
  echo "usage: $0 REPO_ROOT RUN_ROOT COUNTS_JSON MAX_EVENTS" >&2
  exit 2
fi

repo_root=$1
run_root=$2
counts_json=$3
max_events=$4
input_root=/data/dust/user/zhangyuy/analysis/tth/events_physsim/production/sm_tth/eL.pR/I01234_0/complete_reco
arguments=()
for chunk in {1..10}; do
  arguments+=(
    --complete
    "$input_root/complete_reco_kinfit_ready_E550-Test.Ptth.Gphyssim.eL.pR.I01234_0.${chunk}_sgv.slcio"
  )
done

setup_log="$run_root/condor/setup.log"
set +e
source /data/dust/user/zhangyuy/analysis/tth/ZHH/setup.sh >"$setup_log" 2>&1
setup_rc=$?
set -e
if [[ $setup_rc -ne 0 ]]; then
  echo "ZHH setup failed with exit code $setup_rc; see $setup_log" >&2
  exit "$setup_rc"
fi

python_executable=$(command -v python3 || true)
printf 'python3=%s\n' "$python_executable" >>"$setup_log"
if [[ -z "$python_executable" ]]; then
  echo "python3 is unavailable after ZHH setup; see $setup_log" >&2
  exit 1
fi
if ! "$python_executable" -c 'import pyLCIO' >>"$setup_log" 2>&1; then
  echo "pyLCIO import failed with $python_executable; see $setup_log" >&2
  exit 1
fi

exec "$python_executable" "$repo_root/scripts/reco_performance/report_lepton_selection_truth_composition.py" \
  "${arguments[@]}" \
  --counts-json "$counts_json" \
  --legacy "$repo_root/reco_performance_study/legacy/count_hbb_ttbar_had_iso_pass.py" \
  --output-dir "$run_root/result" \
  --max-events "$max_events"
