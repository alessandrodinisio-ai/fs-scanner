"""Detection of leftover files from uninstalled applications."""

from __future__ import annotations

import logging
import os
import plistlib
import subprocess
from pathlib import Path

from ..catalog.models import RiskLevel, Suggestion

logger = logging.getLogger("fs_scanner")
_MIN_REPORT_SIZE = 50 * 1024 * 1024  # 50 MB


def find_suggestions(scan_root: Path) -> list[Suggestion]:
    """Detect leftover files from uninstalled applications."""
    home = Path.home()
    installed_apps = _detect_installed_apps()
    suggestions: list[Suggestion] = []

    app_support = home / "Library" / "Application Support"
    if app_support.is_dir():
        suggestions.extend(_check_app_support(app_support, installed_apps))

    launch_agents = home / "Library" / "LaunchAgents"
    if launch_agents.is_dir():
        suggestions.extend(_check_launch_agents(launch_agents))

    return sorted(suggestions, key=lambda s: s.size, reverse=True)


def _detect_installed_apps() -> set[str]:
    """Glob /Applications and ~/Applications for .app bundle names."""
    apps: set[str] = set()
    for app_dir in [Path("/Applications"), Path.home() / "Applications"]:
        if not app_dir.is_dir():
            continue
        try:
            for entry in app_dir.iterdir():
                if entry.suffix == ".app":
                    apps.add(entry.stem.lower())
                    bid = _read_bundle_id(entry / "Contents" / "Info.plist")
                    if bid:
                        apps.add(bid.lower())
                        parts = bid.split(".")
                        if len(parts) > 2:
                            apps.add(parts[-1].lower())
        except (PermissionError, OSError):
            continue
    return apps


def _read_bundle_id(plist_path: Path) -> str | None:
    """Read CFBundleIdentifier from Info.plist."""
    try:
        with open(plist_path, "rb") as f:
            return plistlib.load(f).get("CFBundleIdentifier")
    except (OSError, plistlib.InvalidFileException, KeyError):
        return None


def _check_app_support(app_support: Path, installed_apps: set[str]) -> list[Suggestion]:
    """Find Application Support dirs not matching installed apps."""
    suggestions: list[Suggestion] = []
    system_dirs = {
        "apple", "com.apple", "addressbook", "cloudkit", "crashreporter",
        "dock", "fileprovider", "knowledge", "mobiledevice", "syncservices",
        "webkit", "icdd",
    }

    try:
        for entry in app_support.iterdir():
            if not entry.is_dir() or entry.is_symlink():
                continue
            name_lower = entry.name.lower()
            if name_lower in installed_apps:
                continue
            if name_lower in system_dirs or name_lower.startswith("com.apple"):
                continue
            if any(app in name_lower or name_lower in app for app in installed_apps):
                continue

            size = _safe_dir_size(entry)
            if size >= _MIN_REPORT_SIZE:
                suggestions.append(Suggestion(
                    path=str(entry),
                    size=size,
                    category="App Leftover",
                    reason=f"'{entry.name}' doesn't match any installed app. May be residual.",
                    risk_level=RiskLevel.SAFE,
                ))
    except (PermissionError, OSError):
        pass
    return suggestions


def _check_launch_agents(launch_agents: Path) -> list[Suggestion]:
    """Find LaunchAgents referencing executables that no longer exist."""
    dead: list[Suggestion] = []
    try:
        for plist_file in launch_agents.glob("*.plist"):
            try:
                with open(plist_file, "rb") as f:
                    data = plistlib.load(f)
                prog_args = data.get("ProgramArguments", [])
                executable = prog_args[0] if prog_args else data.get("Program", "")
                if executable and not Path(executable).exists():
                    dead.append(Suggestion(
                        path=str(plist_file),
                        size=plist_file.stat().st_size,
                        category="Dead LaunchAgent",
                        reason=f"References missing executable: {executable}",
                        risk_level=RiskLevel.SAFE,
                    ))
            except (plistlib.InvalidFileException, OSError, IndexError, KeyError,
                    Exception):
                continue
    except (PermissionError, OSError):
        pass
    return dead


def _safe_dir_size(path: Path) -> int:
    """Get dir size via du subprocess (macOS safe)."""
    try:
        result = subprocess.run(
            ["/usr/bin/du", "-sk", str(path)],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, timeout=15,
        )
        if result.stdout.strip():
            return int(result.stdout.strip().split("\t")[0]) * 1024
    except (subprocess.TimeoutExpired, OSError, ValueError, IndexError):
        pass
    return 0
