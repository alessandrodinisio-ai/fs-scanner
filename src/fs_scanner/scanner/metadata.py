"""Spotlight metadata integration via mdls.

Queries kMDItemLastUsedDate for files to determine when they were
last actually opened (not just modified).
"""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("fs_scanner")

_BATCH_SIZE = 50
_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")


@dataclass(frozen=True)
class SpotlightMetadata:
    """Metadata from Spotlight for a single file."""
    last_used_date: datetime | None
    kind: str | None


def batch_mdls(paths: list[Path], batch_size: int = _BATCH_SIZE) -> dict[Path, SpotlightMetadata]:
    """Query Spotlight metadata for files in batches.

    Calls: mdls -name kMDItemLastUsedDate -name kMDItemKind <paths...>
    Max batch_size files per invocation to avoid excessive process spawning.

    Returns empty metadata if mdls is unavailable.
    """
    results: dict[Path, SpotlightMetadata] = {}

    for i in range(0, len(paths), batch_size):
        batch = paths[i:i + batch_size]
        batch_results = _query_batch(batch)
        results.update(batch_results)

    return results


def _query_batch(paths: list[Path]) -> dict[Path, SpotlightMetadata]:
    """Query mdls for a single batch of files."""
    if not paths:
        return {}

    cmd = ["mdls", "-name", "kMDItemLastUsedDate", "-name", "kMDItemKind"]
    cmd.extend(str(p) for p in paths)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            return {}
        return _parse_mdls_output(result.stdout, paths)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return {}


def _parse_mdls_output(output: str, paths: list[Path]) -> dict[Path, SpotlightMetadata]:
    """Parse mdls multi-file output into metadata dict.

    mdls output format (per file):
    kMDItemLastUsedDate = 2024-01-15 10:30:00 +0000
    kMDItemKind         = "Python Script"
    (null) for missing values
    """
    results: dict[Path, SpotlightMetadata] = {}
    lines = output.strip().splitlines()

    # Each file produces exactly 2 lines of output
    file_idx = 0
    i = 0
    while i < len(lines) and file_idx < len(paths):
        last_used = None
        kind = None

        # Parse kMDItemLastUsedDate
        if i < len(lines):
            line = lines[i].strip()
            if "kMDItemLastUsedDate" in line and "(null)" not in line:
                match = _DATE_RE.search(line)
                if match:
                    try:
                        last_used = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        pass
            i += 1

        # Parse kMDItemKind
        if i < len(lines):
            line = lines[i].strip()
            if "kMDItemKind" in line and "(null)" not in line:
                # Extract quoted value
                if '"' in line:
                    kind = line.split('"')[1]
            i += 1

        results[paths[file_idx]] = SpotlightMetadata(
            last_used_date=last_used,
            kind=kind,
        )
        file_idx += 1

    return results


def is_unused(metadata: SpotlightMetadata, days_threshold: int = 180) -> bool:
    """Check if a file is unused based on Spotlight last-used date.

    Returns True if last_used_date is available and older than threshold.
    """
    if metadata.last_used_date is None:
        return False
    age = datetime.now() - metadata.last_used_date
    return age.days > days_threshold
