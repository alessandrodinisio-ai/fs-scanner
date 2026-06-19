"""Detection of cache, temp, and build artifact directories.

Uses the platform abstraction layer for OS-specific cache paths.
Cross-platform rules (Maven, Gradle, npm, Docker, etc.) work on any OS.
macOS-specific rules (~/Library/Caches, Podman, Thunderbird) only on macOS.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ..catalog.models import RiskLevel, Suggestion

logger = logging.getLogger("fs_scanner")

# Minimum size to report (100 MB)
_MIN_REPORT_SIZE = 100 * 1024 * 1024

_RISK_MAP = {"safe": RiskLevel.SAFE, "caution": RiskLevel.CAUTION, "risky": RiskLevel.RISKY}


def find_suggestions(scan_root: Path) -> list[Suggestion]:
    """Find reclaimable space in cache/temp directories."""
    from ..platform import current as plat

    home = Path.home()
    suggestions: list[Suggestion] = []
    rules = plat.cache_rules(home)

    for rule in rules:
        path = rule["path"]
        timeout = rule.get("_timeout", 30)
        try:
            size = plat.dir_size(path, timeout=timeout)
        except (OSError, Exception):
            continue
        if size < _MIN_REPORT_SIZE:
            continue

        suggestions.append(Suggestion(
            path=str(path),
            size=size,
            category=rule["category"],
            reason=rule["reason"],
            risk_level=_RISK_MAP.get(rule["risk"], RiskLevel.CAUTION),
        ))

    return sorted(suggestions, key=lambda s: s.size, reverse=True)
