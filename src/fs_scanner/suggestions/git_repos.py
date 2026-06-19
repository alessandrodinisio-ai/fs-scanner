"""Detection of bloated/orphan Git repositories.

Identifies .git directories that contain large amounts of unreachable objects
(orphan blobs/trees/commits not referenced by any branch or tag), which waste
disk space and can be reclaimed with `git prune` or `git gc`.

Also detects Git repositories initialized in unusual locations (like the home
directory) which are often accidental.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from ..catalog.models import RiskLevel, Suggestion

logger = logging.getLogger("fs_scanner")

# Threshold: report if loose objects exceed this size
_MIN_REPORT_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB


def find_suggestions(scan_root: Path, max_repos: int = 50) -> list[Suggestion]:
    """Scan for .git directories and check for orphan/bloated objects.

    Args:
        scan_root: Root path to search for .git directories.
        max_repos: Maximum number of repos to analyze (avoid slowdown).

    Returns:
        List of suggestions for repos with reclaimable space.
    """
    suggestions: list[Suggestion] = []
    git_dirs = _find_git_dirs(scan_root, max_repos)

    for git_dir in git_dirs:
        suggestion = _analyze_git_repo(git_dir)
        if suggestion:
            suggestions.append(suggestion)

    return sorted(suggestions, key=lambda s: s.size, reverse=True)


def _find_git_dirs(root: Path, max_count: int) -> list[Path]:
    """Find .git directories under root (breadth-first, limited)."""
    git_dirs: list[Path] = []

    # Check if root itself has a .git
    if (root / ".git").is_dir():
        git_dirs.append(root / ".git")

    try:
        for dirpath, dirnames, _ in os.walk(root):
            if len(git_dirs) >= max_count:
                break

            # Don't descend into .git directories themselves
            if ".git" in dirnames:
                git_path = Path(dirpath) / ".git"
                if git_path not in git_dirs:
                    git_dirs.append(git_path)
                dirnames.remove(".git")

            # Skip known heavy directories to speed up search
            for skip in ("node_modules", ".venv", "venv", "__pycache__", "Library"):
                if skip in dirnames:
                    dirnames.remove(skip)
    except (PermissionError, OSError):
        pass

    return git_dirs


def _analyze_git_repo(git_dir: Path) -> Suggestion | None:
    """Analyze a .git directory for orphan objects and bloat.

    Returns a Suggestion if significant reclaimable space is found.
    """
    try:
        result = subprocess.run(
            ["git", "--git-dir", str(git_dir), "count-objects", "-v"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None

    # Parse count-objects output
    stats = _parse_count_objects(result.stdout)
    loose_size = stats.get("size", 0) * 1024  # "size" is in KB
    pack_size = stats.get("size-pack", 0) * 1024
    loose_count = stats.get("count", 0)

    # Fallback: if count-objects reports 0 but directory is large, measure directly
    if loose_size == 0 and pack_size == 0:
        actual_size = _measure_git_objects_dir(git_dir)
        if actual_size > _MIN_REPORT_SIZE_BYTES:
            loose_size = actual_size
            loose_count = -1  # Unknown count

    # Check if there are reachable commits
    has_commits = _has_reachable_commits(git_dir)

    # Determine if this is reportable
    total_git_size = loose_size + pack_size

    if loose_size < _MIN_REPORT_SIZE_BYTES and not _is_unusual_location(git_dir):
        return None

    # Determine reclaimable space
    # If no commits exist, everything is reclaimable (entire .git can go)
    # If commits exist but loose objects are large, loose objects are reclaimable
    if not has_commits:
        reclaimable = total_git_size
        reason = (
            f"Orphan Git repo with no reachable commits. "
            f"{loose_count:,} loose objects ({_fmt_size(loose_size)}). "
            f"Safe to remove entire .git directory or run `git prune`."
        )
        risk = RiskLevel.SAFE
        category = "Orphan Git Repository"
    else:
        # Has commits but large loose objects (unreachable after rebase/reset)
        reclaimable = loose_size
        reason = (
            f"Git repo with {loose_count:,} loose objects ({_fmt_size(loose_size)}) "
            f"not reachable from any branch. "
            f"Reclaim with: git --git-dir='{git_dir}' prune && git --git-dir='{git_dir}' gc"
        )
        risk = RiskLevel.CAUTION
        category = "Git Loose Objects"

    if reclaimable < _MIN_REPORT_SIZE_BYTES:
        return None

    # Flag unusual locations
    if _is_unusual_location(git_dir):
        category = "Git Repo in Unusual Location"
        reason = f"Git repo in home directory (likely accidental). " + reason

    return Suggestion(
        path=str(git_dir),
        size=reclaimable,
        category=category,
        reason=reason,
        risk_level=risk,
    )


def _has_reachable_commits(git_dir: Path) -> bool:
    """Check if the repo has any reachable commits."""
    try:
        result = subprocess.run(
            ["git", "--git-dir", str(git_dir), "rev-list", "--all", "--count"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            count = int(result.stdout.strip())
            return count > 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError, ValueError):
        pass
    return False


def _is_unusual_location(git_dir: Path) -> bool:
    """Check if .git is in an unusual location (home dir root, /tmp, etc)."""
    parent = git_dir.parent
    home = Path.home()

    # .git directly in home directory
    if parent == home:
        return True

    # .git in /tmp or similar
    if str(parent).startswith("/tmp"):
        return True

    return False


def _parse_count_objects(output: str) -> dict[str, int]:
    """Parse `git count-objects -v` output into a dict."""
    stats: dict[str, int] = {}
    for line in output.strip().splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            try:
                stats[key.strip()] = int(value.strip())
            except ValueError:
                pass
    return stats


def _measure_git_objects_dir(git_dir: Path) -> int:
    """Measure total size of .git/objects/ directory by walking it."""
    objects_dir = git_dir / "objects"
    if not objects_dir.is_dir():
        return 0
    total = 0
    try:
        for dirpath, _, filenames in os.walk(objects_dir):
            for f in filenames:
                try:
                    total += os.path.getsize(os.path.join(dirpath, f))
                except OSError:
                    pass
    except (PermissionError, OSError):
        pass
    return total


def _fmt_size(size_bytes: int) -> str:
    """Quick human-readable size format."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024**2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024**3:
        return f"{size_bytes / 1024**2:.1f} MB"
    else:
        return f"{size_bytes / 1024**3:.1f} GB"
