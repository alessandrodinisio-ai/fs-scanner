"""Detection of large cached mail attachments."""

from __future__ import annotations

import subprocess
from pathlib import Path

from ..catalog.models import RiskLevel, Suggestion

_MIN_SIZE = 100 * 1024 * 1024  # 100 MB


def find_suggestions(scan_root: Path) -> list[Suggestion]:
    """Detect large Mail.app and Thunderbird data."""
    home = Path.home()
    suggestions = []

    # Apple Mail
    mail_dir = home / "Library" / "Mail"
    size = _safe_dir_size(mail_dir)
    if size >= _MIN_SIZE:
        suggestions.append(Suggestion(
            path=str(mail_dir), size=size,
            category="Mail Attachments",
            reason="Apple Mail cached data and attachments. Remove old/large emails or rebuild mailbox.",
            risk_level=RiskLevel.CAUTION,
        ))

    # Thunderbird (use longer timeout — can be very large)
    tb_dir = home / "Library" / "Thunderbird" / "Profiles"
    size = _safe_dir_size(tb_dir, timeout=120)
    if size >= _MIN_SIZE:
        suggestions.append(Suggestion(
            path=str(tb_dir), size=size,
            category="Thunderbird Email",
            reason="Thunderbird profiles (email, attachments). Compact folders in Thunderbird to reclaim space.",
            risk_level=RiskLevel.RISKY,
        ))

    return suggestions


def _safe_dir_size(path: Path, timeout: int = 30) -> int:
    try:
        result = subprocess.run(
            ["/usr/bin/du", "-sk", str(path)],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, timeout=timeout,
        )
        if result.stdout.strip():
            return int(result.stdout.strip().split("\t")[0]) * 1024
    except (subprocess.TimeoutExpired, OSError, ValueError, IndexError):
        pass
    return 0
