#!/usr/bin/env bash
# Verify the environment and (optionally) the registered input data.
#
# Usage:
#   bash env/check_environment.sh          # software checks only
#   bash env/check_environment.sh --data   # also check registered sample paths

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHECK_DATA=0
[[ "${1:-}" == "--data" ]] && CHECK_DATA=1

PASS=0
FAIL=0

check() {
  local name="$1"; shift
  if "$@" >/dev/null 2>&1; then
    echo "  OK   $name"
    PASS=$((PASS + 1))
  else
    echo "  FAIL $name"
    FAIL=$((FAIL + 1))
  fi
}

echo "== software"
check "python3"            command -v python3
check "python3 >= 3.8"     python3 -c 'import sys; assert sys.version_info >= (3, 8)'
check "ilc_tth_cpv import" python3 -c "import sys; sys.path.insert(0, '$REPO_ROOT/src'); import ilc_tth_cpv"
check "pyyaml"             python3 -c 'import yaml'
check "numpy"              python3 -c 'import numpy'
check "matplotlib"         python3 -c 'import matplotlib'
check "xgboost (baseline)" python3 -c 'import xgboost'
check "sklearn"            python3 -c 'import sklearn'
check "pyLCIO"             python3 -c 'import pyLCIO'
check "ROOT"               python3 -c 'import ROOT'
check "Marlin"             command -v Marlin

echo "== repo"
check "configs/samples.yaml parses" python3 -c "
import sys; sys.path.insert(0, '$REPO_ROOT/src')
from ilc_tth_cpv.io import load_yaml
load_yaml('$REPO_ROOT/configs/samples.yaml')
"
check "analysis config parses" python3 -c "
import sys; sys.path.insert(0, '$REPO_ROOT/src')
from ilc_tth_cpv.io import load_analysis_config
load_analysis_config('$REPO_ROOT/configs/analysis_ow_lr.yaml')
"
check "model profiles parse" python3 -c "
import sys; sys.path.insert(0, '$REPO_ROOT/src')
from ilc_tth_cpv.io import load_yaml
load_yaml('$REPO_ROOT/configs/model_profiles.yaml')
"
check "default model profile check" python3 "$REPO_ROOT/scripts/check_model_profile.py"
check "outputs/ writable" bash -c "touch '$REPO_ROOT/outputs/.write_test' && rm '$REPO_ROOT/outputs/.write_test'"

if [[ "$CHECK_DATA" == "1" ]]; then
  echo "== registered data paths"
  python3 - "$REPO_ROOT" <<'PY'
import sys
from pathlib import Path

repo = Path(sys.argv[1])
sys.path.insert(0, str(repo / "src"))
from ilc_tth_cpv.io import load_yaml

manifest = load_yaml(repo / "configs" / "samples.yaml")
for section in ("signals",):
    for key, sample in manifest[section].items():
        status = sample.get("status") or []
        path = sample.get("path")
        if path is None:
            continue
        exists = Path(path).exists()
        pattern = sample.get("file_pattern")
        file_ok = True
        if exists and pattern:
            file_ok = bool(list(Path(path).glob(pattern)))
        flag = "OK  " if exists and file_ok else ("MISS" if not exists else "NOFI")
        expected = "config-only" in status and " (expected: config-only)" or ""
        print(f"  {flag} {key}: {path}{expected}")
PY
fi

echo
echo "passed=$PASS failed=$FAIL"
echo "(most checks need the software stack: run 'source env/setup.sh' first)"
[[ "$FAIL" == "0" ]]
