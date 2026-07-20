#!/usr/bin/env bash
# Environment setup for the ilc-tth-cpv repository on the DESY NAF.
#
# Usage:  source env/setup.sh
#
# Sources the analysis-side ZHH environment (ILCSoft, LCIO, Marlin, ROOT,
# pyLCIO) and adds this repo's src/ to PYTHONPATH.

_REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- ZHH / ILCSoft stack (provides pyLCIO, Marlin, ROOT) --------------------
ZHH_SETUP_DEFAULT="/data/dust/user/zhangyuy/analysis/tth/ZHH/setup.sh"
ZHH_SETUP="${ZHH_SETUP:-$ZHH_SETUP_DEFAULT}"

if [[ -e "$ZHH_SETUP" ]]; then
  # the ZHH setup is not `set -u`-clean
  set +u 2>/dev/null || true
  source "$ZHH_SETUP"
else
  echo "[env] WARNING: ZHH setup not found at $ZHH_SETUP" >&2
  echo "[env]          pyLCIO/Marlin-dependent steps will not work." >&2
fi

# --- this repository ---------------------------------------------------------
export ILC_TTH_CPV_ROOT="$_REPO_ROOT"
export PYTHONPATH="$_REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

echo "[env] ILC_TTH_CPV_ROOT=$ILC_TTH_CPV_ROOT"
echo "[env] run 'bash env/check_environment.sh' to verify the stack."
