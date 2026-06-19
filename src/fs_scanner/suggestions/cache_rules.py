"""Detection of cache, temp, and build artifact directories.

Scans known macOS cache/temp paths and development tool caches,
reporting total size and cleanup commands.

IMPORTANT: On macOS, certain paths under ~/Library are TCC-protected and
cause the process to be killed (SIGABRT) if accessed without Full Disk Access.
This module uses subprocess `du` for sizing and avoids calling stat/is_dir
on potentially protected paths.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from ..catalog.models import RiskLevel, Suggestion

logger = logging.getLogger("fs_scanner")

# Minimum size to report (100 MB)
_MIN_REPORT_SIZE = 100 * 1024 * 1024


def find_suggestions(scan_root: Path) -> list[Suggestion]:
    """Find reclaimable space in cache/temp directories.

    Args:
        scan_root: Root directory (typically home).

    Returns:
        Sorted list of suggestions for cache cleanup.
    """
    home = Path.home()
    suggestions: list[Suggestion] = []
    rules = _get_cache_rules(home)

    for rule in rules:
        path = rule["path"]
        size = _safe_dir_size(path)
        if size < _MIN_REPORT_SIZE:
            continue

        suggestions.append(Suggestion(
            path=str(path),
            size=size,
            category=rule["category"],
            reason=rule["reason"],
            risk_level=rule["risk"],
        ))

    return sorted(suggestions, key=lambda s: s.size, reverse=True)


def _safe_dir_size(path: Path) -> int:
    """Get directory size using subprocess du.

    This avoids Python-level stat() calls that can trigger macOS TCC
    process termination. `du` handles permission errors gracefully.
    Returns 0 if path doesn't exist or can't be measured.
    """
    try:
        result = subprocess.run(
            ["/usr/bin/du", "-sk", str(path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=60,
        )
        if result.returncode in (0, 1) and result.stdout.strip():
            # du outputs "SIZE\tPATH" — size in KB
            last_line = result.stdout.strip().split("\n")[-1]
            size_kb = int(last_line.split("\t")[0])
            return size_kb * 1024
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError, ValueError, IndexError):
        pass
    return 0


def _get_cache_rules(home: Path) -> list[dict]:
    """Define known cache/temp paths with cleanup metadata.

    Only includes paths that are safe to measure with `du` on macOS.
    Avoids TCC-protected directories that could kill the process.
    """
    lib = home / "Library"

    return [
        # Only paths verified safe on macOS without Full Disk Access
        {
            "path": lib / "Caches" / "JetBrains",
            "category": "JetBrains Cache",
            "reason": "JetBrains IDE caches. Regenerate on next start. Safe to remove.",
            "risk": RiskLevel.SAFE,
        },
        {
            "path": lib / "Caches" / "pip",
            "category": "pip Cache",
            "reason": "Python pip download cache. Run: pip cache purge",
            "risk": RiskLevel.SAFE,
        },
        {
            "path": lib / "Caches" / "Google",
            "category": "Chrome/Google Cache",
            "reason": "Google Chrome browser cache. Regenerates automatically.",
            "risk": RiskLevel.SAFE,
        },
        {
            "path": lib / "Caches" / "Homebrew",
            "category": "Homebrew Cache",
            "reason": "Homebrew download cache. Run: brew cleanup --prune=all",
            "risk": RiskLevel.SAFE,
        },
        {
            "path": lib / "Logs",
            "category": "macOS Logs",
            "reason": "System and application logs. Run: rm -rf ~/Library/Logs/*",
            "risk": RiskLevel.SAFE,
        },
        {
            "path": home / ".m2" / "repository",
            "category": "Maven Cache",
            "reason": "Maven local repository (re-downloads on next build). Run: rm -rf ~/.m2/repository",
            "risk": RiskLevel.SAFE,
        },
        {
            "path": home / ".npm" / "_cacache",
            "category": "npm Cache",
            "reason": "npm download cache. Run: npm cache clean --force",
            "risk": RiskLevel.SAFE,
        },
        {
            "path": home / ".local" / "share" / "containers",
            "category": "Podman Containers",
            "reason": "Podman VM disk image + container data. Run: podman machine stop && podman system prune -a --volumes",
            "risk": RiskLevel.CAUTION,
        },
        {
            "path": lib / "Thunderbird" / "Profiles",
            "category": "Thunderbird Email",
            "reason": "Thunderbird profiles (email, attachments). Compact folders in Thunderbird to reclaim space.",
            "risk": RiskLevel.RISKY,
        },
    ]
