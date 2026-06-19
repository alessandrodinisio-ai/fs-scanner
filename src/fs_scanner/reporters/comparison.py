"""Scan comparison: diff between two scan results."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ..catalog.models import Category, ScanResult
from .terminal import format_size


@dataclass(frozen=True)
class ComparisonResult:
    """Diff between two scan results."""

    added_files: list[str]
    removed_files: list[str]
    size_changes: dict[str, int]  # category name → size delta (positive = growth)
    net_change: int
    current_total: int
    previous_total: int


def compare_scans(current: ScanResult, previous_path: Path) -> ComparisonResult:
    """Load a previous JSON scan result and compute a diff against the current scan.

    Args:
        current: The current scan result.
        previous_path: Path to a previously generated JSON report.

    Returns:
        ComparisonResult with added/removed files and size changes.

    Raises:
        ValueError: If the previous file cannot be parsed.
    """
    try:
        raw = previous_path.read_text(encoding="utf-8")
        prev_data = json.loads(raw)
    except (json.JSONDecodeError, OSError) as e:
        raise ValueError(f"Cannot read previous scan: {e}") from e

    # Extract file paths from previous scan
    prev_files: dict[str, int] = {}
    for f in prev_data.get("files", []):
        prev_files[f["path"]] = f["size"]

    # Current file paths
    curr_files: dict[str, int] = {f.path: f.size for f in current.files}

    # Compute added and removed
    prev_paths = set(prev_files.keys())
    curr_paths = set(curr_files.keys())

    added = sorted(curr_paths - prev_paths)
    removed = sorted(prev_paths - curr_paths)

    # Size changes per category
    prev_categories: dict[str, int] = {}
    for cat_name, cat_data in prev_data.get("categories", {}).items():
        prev_categories[cat_name] = cat_data.get("total_size", 0)

    size_changes: dict[str, int] = {}
    for cat in Category:
        curr_size = current.categories.get(cat, None)
        curr_val = curr_size.total_size if curr_size else 0
        prev_val = prev_categories.get(cat.value, 0)
        delta = curr_val - prev_val
        if delta != 0:
            size_changes[cat.value] = delta

    prev_total = prev_data.get("total_size", 0)
    net_change = current.total_size - prev_total

    return ComparisonResult(
        added_files=added,
        removed_files=removed,
        size_changes=size_changes,
        net_change=net_change,
        current_total=current.total_size,
        previous_total=prev_total,
    )


def format_comparison(result: ComparisonResult) -> str:
    """Format comparison result as human-readable text."""
    lines: list[str] = []
    lines.append("=== Scan Comparison ===")
    lines.append("")

    # Net change
    sign = "+" if result.net_change >= 0 else ""
    lines.append(f"Net disk usage change: {sign}{format_size(abs(result.net_change))}")
    lines.append(f"  Previous: {format_size(result.previous_total)}")
    lines.append(f"  Current:  {format_size(result.current_total)}")
    lines.append("")

    # Category changes
    if result.size_changes:
        lines.append("Changes by category:")
        for cat_name, delta in sorted(result.size_changes.items(), key=lambda x: abs(x[1]), reverse=True):
            sign = "+" if delta >= 0 else "-"
            lines.append(f"  {cat_name:12s} {sign}{format_size(abs(delta))}")
        lines.append("")

    # Added files
    if result.added_files:
        lines.append(f"New files: {len(result.added_files)}")
        for path in result.added_files[:20]:
            lines.append(f"  + {path}")
        if len(result.added_files) > 20:
            lines.append(f"  ... and {len(result.added_files) - 20} more")
        lines.append("")

    # Removed files
    if result.removed_files:
        lines.append(f"Removed files: {len(result.removed_files)}")
        for path in result.removed_files[:20]:
            lines.append(f"  - {path}")
        if len(result.removed_files) > 20:
            lines.append(f"  ... and {len(result.removed_files) - 20} more")
        lines.append("")

    return "\n".join(lines)
