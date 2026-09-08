#!/usr/bin/env python3
"""Canonical event-level angle/ML score -> selection -> Fisher workflow."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ilc_tth_cpv.event_workflow import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
