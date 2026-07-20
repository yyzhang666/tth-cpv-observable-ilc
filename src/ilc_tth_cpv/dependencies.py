"""Dependency checks for optional student-analysis profiles."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class DependencyStatus:
    package: str
    import_name: str
    available: bool


def dependency_report(requirements: Iterable[dict]) -> list[DependencyStatus]:
    """Return availability for profile entries from configs/model_profiles.yaml."""
    report = []
    for item in requirements:
        package = str(item.get("package", ""))
        import_name = str(item.get("import", package))
        report.append(
            DependencyStatus(
                package=package,
                import_name=import_name,
                available=importlib.util.find_spec(import_name) is not None,
            )
        )
    return report
