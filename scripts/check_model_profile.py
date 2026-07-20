#!/usr/bin/env python3
"""Check whether dependencies for a configured model/profile are available."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ilc_tth_cpv.dependencies import dependency_report  # noqa: E402
from ilc_tth_cpv.io import load_yaml  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default=None)
    parser.add_argument("--profiles-config", default="configs/model_profiles.yaml")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    config = load_yaml(Path(args.profiles_config))
    profile_name = args.profile or config.get("default_profile", "xgboost_baseline")
    profiles = config.get("profiles", {})
    if profile_name not in profiles:
        raise SystemExit(f"Unknown profile: {profile_name}")

    profile = profiles[profile_name]
    report = dependency_report(profile.get("required_modules", []))
    missing = [item for item in report if not item.available]
    payload = {
        "profile": profile_name,
        "status": profile.get("status"),
        "tier": profile.get("tier"),
        "model_type": profile.get("model_type"),
        "available": [
            {"package": item.package, "import": item.import_name}
            for item in report
            if item.available
        ],
        "missing": [
            {"package": item.package, "import": item.import_name}
            for item in missing
        ],
        "ready": not missing,
    }

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"profile: {payload['profile']}")
        print(f"tier: {payload['tier']}")
        print(f"model_type: {payload['model_type']}")
        for item in report:
            state = "OK" if item.available else "MISSING"
            print(f"{item.package} ({item.import_name}): {state}")
        print(f"ready: {payload['ready']}")
    return 1 if args.strict and missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
