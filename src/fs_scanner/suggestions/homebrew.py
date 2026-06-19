"""Detection of old Homebrew formula versions and cached downloads.

Identifies:
- Unlinked (old) formula versions in the Cellar
- Cached .tar.gz/.bottle downloads in ~/Library/Caches/Homebrew
- Suggests `brew cleanup --prune=all` to reclaim space
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from ..catalog.models import RiskLevel, Suggestion

logger = logging.getLogger("fs_scanner")

_MIN_REPORT_SIZE = 50 * 1024 * 1024  # 50 MB


def find_suggestions(scan_root: Path) -> list[Suggestion]:
    """Detect old Homebrew versions and cached downloads.

    Args:
        scan_root: Root path (typically home directory).

    Returns:
        List of suggestions for Homebrew cleanup.
    """
    suggestions: list[Suggestion] = []

    # Detect Homebrew installation
    homebrew_prefix = _find_homebrew_prefix()
    if not homebrew_prefix:
        return suggestions

    # Check for old (unlinked) formula versions
    old_versions = _find_old_versions(homebrew_prefix)
    if old_versions:
        suggestions.append(old_versions)

    # Check cached downloads
    cache_suggestion = _check_download_cache()
    if cache_suggestion:
        suggestions.append(cache_suggestion)

    return sorted(suggestions, key=lambda s: s.size, reverse=True)


def _find_homebrew_prefix() -> Path | None:
    """Detect Homebrew installation path."""
    candidates = [
        Path("/opt/homebrew"),          # Apple Silicon
        Path("/usr/local/Homebrew"),    # Intel Mac
        Path("/usr/local"),             # Older Intel installs
    ]
    for prefix in candidates:
        cellar = prefix / "Cellar"
        if cellar.is_dir():
            return prefix
    return None


def _find_old_versions(homebrew_prefix: Path) -> Suggestion | None:
    """Find unlinked formula versions (old versions kept after upgrade).

    Logic:
    - List all formulas in Cellar/
    - For each formula, check which version is linked in opt/
    - Any version NOT linked is an old version
    """
    cellar = homebrew_prefix / "Cellar"
    opt = homebrew_prefix / "opt"

    if not cellar.is_dir():
        return None

    # Get linked versions from opt/ symlinks
    linked_versions = _get_linked_versions(opt, cellar)

    # Find old (unlinked) versions
    total_old_size = 0
    old_count = 0
    old_formulas: list[str] = []

    try:
        for formula_dir in cellar.iterdir():
            if not formula_dir.is_dir():
                continue
            formula_name = formula_dir.name
            linked_ver = linked_versions.get(formula_name)

            try:
                versions = [v for v in formula_dir.iterdir() if v.is_dir()]
            except (PermissionError, OSError):
                continue

            if len(versions) <= 1:
                continue  # Only one version, nothing to clean

            for version_dir in versions:
                if version_dir.name == linked_ver:
                    continue  # This is the active version
                # This is an old version
                size = _dir_size(version_dir)
                total_old_size += size
                old_count += 1
                if len(old_formulas) < 10:
                    old_formulas.append(f"{formula_name}@{version_dir.name}")
    except (PermissionError, OSError):
        pass

    if total_old_size < _MIN_REPORT_SIZE:
        return None

    formulas_str = ", ".join(old_formulas[:5])
    if old_count > 5:
        formulas_str += f" ... and {old_count - 5} more"

    return Suggestion(
        path=str(cellar),
        size=total_old_size,
        category="Homebrew Old Versions",
        reason=(
            f"{old_count} old formula versions not currently linked. "
            f"Examples: {formulas_str}. "
            f"Run: brew cleanup --prune=all"
        ),
        risk_level=RiskLevel.SAFE,
    )


def _get_linked_versions(opt: Path, cellar: Path) -> dict[str, str]:
    """Read symlinks in opt/ to determine currently linked versions.

    Returns dict mapping formula_name -> linked_version_string.
    """
    linked: dict[str, str] = {}

    if not opt.is_dir():
        return linked

    try:
        for entry in opt.iterdir():
            if not entry.is_symlink():
                continue
            try:
                target = entry.resolve()
                # Target should be like /opt/homebrew/Cellar/formula/version
                if str(cellar) in str(target):
                    parts = target.parts
                    cellar_parts = cellar.parts
                    # Find the version part after Cellar/formula/
                    idx = len(cellar_parts)
                    if len(parts) > idx + 1:
                        formula = parts[idx]
                        version = parts[idx + 1]
                        linked[formula] = version
            except (OSError, ValueError):
                continue
    except (PermissionError, OSError):
        pass

    return linked


def _check_download_cache() -> Suggestion | None:
    """Check Homebrew download cache for old cached files."""
    home = Path.home()
    cache_paths = [
        home / "Library" / "Caches" / "Homebrew" / "downloads",
        home / "Library" / "Caches" / "Homebrew",
    ]

    total_size = 0
    file_count = 0

    for cache_path in cache_paths:
        if not cache_path.is_dir():
            continue
        try:
            for dirpath, _, filenames in os.walk(cache_path):
                for f in filenames:
                    try:
                        total_size += os.lstat(os.path.join(dirpath, f)).st_size
                        file_count += 1
                    except (OSError, PermissionError):
                        pass
        except (OSError, PermissionError):
            pass

    if total_size < _MIN_REPORT_SIZE:
        return None

    return Suggestion(
        path=str(cache_paths[0].parent),
        size=total_size,
        category="Homebrew Download Cache",
        reason=(
            f"{file_count} cached download files. "
            f"Run: brew cleanup --prune=all"
        ),
        risk_level=RiskLevel.SAFE,
    )


def _dir_size(path: Path) -> int:
    """Calculate total size of a directory."""
    total = 0
    try:
        for dirpath, _, filenames in os.walk(path):
            for f in filenames:
                try:
                    total += os.lstat(os.path.join(dirpath, f)).st_size
                except (OSError, PermissionError):
                    pass
    except (OSError, PermissionError):
        pass
    return total
