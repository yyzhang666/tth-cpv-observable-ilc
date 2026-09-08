#!/usr/bin/env python3
"""Compatibility entry point for the event-CSV Fisher workflow.

New commands should use ``scripts/workflows/run_event_fisher.py``.  This path
is retained so the published v0 commands and tests keep working unchanged.
"""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ilc_tth_cpv.event_workflow import (  # noqa: E402,F401
    ML_MODEL_COLUMNS,
    main,
    read_and_select,
    strict_q_sel_pass,
)


if __name__ == "__main__":
    raise SystemExit(main())
