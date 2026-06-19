"""Detection of large cached mail attachments."""

from __future__ import annotations

import subprocess
from pathlib import Path

from ..catalog.models import RiskLevel, Suggestion

_MIN_SIZE = 100 * 1024 * 1024  # 100 MB


def find_suggestions(scan_root: Path) -> list[Suggestion]:
    """Detect large Mail.app attachment cache."""
    mail_dir = Path.home() / "Library" / "Mail"
    size = _safe_dir_size(mail_dir)
    if size < _MIN_SIZE:
        return []
    return [Suggestion(
        path=str(mail_dir),
        size=size,
        category="Mail Attachments",
        reason="Apple Mail cached data and attachments. Remove old/large emails or rebuild mailbox.",
        risk_level=RiskLevel.CAUTION,
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
