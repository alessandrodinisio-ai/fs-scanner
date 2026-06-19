"""Detection of old Xcode archives, simulators, and DerivedData."""

from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path

from ..catalog.models import RiskLevel, Suggestion

logger = logging.getLogger("fs_scanner")
_90_DAYS = 90 * 24 * 3600
_MIN_SIZE = 50 * 1024 * 1024  # 50 MB


def find_suggestions(scan_root: Path) -> list[Suggestion]:
    """Detect old Xcode artifacts."""
    home = Path.home()
    suggestions: list[Suggestion] = []

    derived = home / "Library" / "Developer" / "Xcode" / "DerivedData"
    if derived.is_dir():
        s = _check_derived_data(derived)
        if s:
            suggestions.append(s)

    archives = home / "Library" / "Developer" / "Xcode" / "Archives"
    if archives.is_dir():
        s = _check_archives(archives)
        if s:
            suggestions.append(s)

    simulators = home / "Library" / "Developer" / "CoreSimulator" / "Devices"
    if simulators.is_dir():
        size = _safe_dir_size(simulators)
        if size >= _MIN_SIZE:
            suggestions.append(Suggestion(
                path=str(simulators),
                size=size,
                category="iOS Simulators",
                reason="iOS simulator runtimes and data. Run: xcrun simctl delete unavailable",
                risk_level=RiskLevel.CAUTION,
            ))

    return sorted(suggestions, key=lambda s: s.size, reverse=True)


def _check_derived_data(derived: Path) -> Suggestion | None:
    size = _safe_dir_size(derived)
    if size < _MIN_SIZE:
        return None
    projects = []
    try:
        for entry in derived.iterdir():
            if entry.is_dir() and entry.name != "ModuleCache.noindex":
                projects.append(entry.name.split("-")[0])
    except (PermissionError, OSError):
        pass
    return Suggestion(
        path=str(derived),
        size=size,
        category="Xcode DerivedData",
        reason=f"Build artifacts ({len(projects)} projects). Run: rm -rf ~/Library/Developer/Xcode/DerivedData",
        risk_level=RiskLevel.SAFE,
    )


def _check_archives(archives: Path) -> Suggestion | None:
    now = time.time()
    old_size = 0
    old_count = 0
    try:
        for date_dir in archives.iterdir():
            if not date_dir.is_dir():
                continue
            for archive in date_dir.iterdir():
                if archive.suffix != ".xcarchive":
                    continue
                try:
                    if now - archive.stat().st_mtime > _90_DAYS:
                        old_size += _safe_dir_size(archive)
                        old_count += 1
                except OSError:
                    continue
    except (PermissionError, OSError):
        pass
    if old_size < _MIN_SIZE:
        return None
    return Suggestion(
        path=str(archives),
        size=old_size,
        category="Xcode Old Archives",
        reason=f"{old_count} archives older than 90 days.",
        risk_level=RiskLevel.SAFE,
    )


def _safe_dir_size(path: Path) -> int:
    try:
        result = subprocess.run(
            ["/usr/bin/du", "-sk", str(path)],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, timeout=30,
        )
        if result.stdout.strip():
            return int(result.stdout.strip().split("\t")[0]) * 1024
    except (subprocess.TimeoutExpired, OSError, ValueError, IndexError):
        pass
    return 0
