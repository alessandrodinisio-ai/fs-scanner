"""Detection of locally downloaded iCloud files."""

from __future__ import annotations

import subprocess
from pathlib import Path

from ..catalog.models import RiskLevel, Suggestion

_MIN_SIZE = 100 * 1024 * 1024  # 100 MB


def find_suggestions(scan_root: Path) -> list[Suggestion]:
    """Detect locally downloaded iCloud files."""
    mobile_docs = Path.home() / "Library" / "Mobile Documents"
    size = _safe_dir_size(mobile_docs)
    if size < _MIN_SIZE:
        return []
    return [Suggestion(
        path=str(mobile_docs),
        size=size,
        category="iCloud Local Copies",
        reason="Locally downloaded iCloud files. Remain in iCloud after eviction. Run: brctl evict <path>",
        risk_level=RiskLevel.SAFE,
    )]


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
