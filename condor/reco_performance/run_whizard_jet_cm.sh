#!/bin/bash
set -eo pipefail

if [[ $# -ne 3 ]]; then
  echo "usage: $0 REPO_ROOT RUN_ROOT SOURCES_JSON" >&2
  exit 2
fi

repo_root=$1
run_root=$2
sources_json=$3
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

exec "$python_executable" \
  "$repo_root/scripts/reco_performance/report_whizard_jet_cm.py" \
  --sources-json "$sources_json" \
  --legacy "$repo_root/reco_performance_study/legacy/plot_tth_truejet_weaver_cm10.py" \
  --output-dir "$run_root/result" \
  --expected-events 12500
