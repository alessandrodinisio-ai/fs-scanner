"""Detection of old Time Machine local snapshots."""

from __future__ import annotations

import subprocess

from ..catalog.models import RiskLevel, Suggestion


def find_suggestions(scan_root=None) -> list[Suggestion]:
    """Detect old Time Machine local snapshots."""
    snapshots = _list_snapshots()
    if not snapshots:
        return []

    total_size = _get_snapshot_size()
    if total_size == 0 and len(snapshots) < 3:
        return []

    return [Suggestion(
        path="/",
        size=total_size,
        category="Time Machine Snapshots",
        reason=(
            f"{len(snapshots)} local snapshot(s) (oldest: {snapshots[0]}). "
            f"Run: tmutil thinlocalsnapshots / 10000000000 4"
        ),
        risk_level=RiskLevel.CAUTION,
    )]


def _list_snapshots() -> list[str]:
    """Call tmutil and parse output."""
    try:
        result = subprocess.run(
            ["tmutil", "listlocalsnapshots", "/"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return []
        snapshots = []
        for line in result.stdout.strip().splitlines():
            line = line.strip()
            if "TimeMachine" in line or line.startswith("com.apple"):
                snapshots.append(line)
        return sorted(snapshots)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []


def _get_snapshot_size() -> int:
    """Estimate total snapshot disk usage via diskutil."""
    try:
        result = subprocess.run(
            ["diskutil", "apfs", "list"],
            capture_output=True, text=True, timeout=10,
        )
        for line in result.stdout.splitlines():
            if "Snapshot" in line and "B (" in line:
                parts = line.split("(")
                if len(parts) >= 2:
                    try:
                        return int(parts[1].split()[0])
                    except (ValueError, IndexError):
                        pass
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return 0
