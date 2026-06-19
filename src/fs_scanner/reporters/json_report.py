"""Deterministic JSON report output."""

from __future__ import annotations

import json
import os
from pathlib import Path

from ..catalog.models import Category, ScanResult


def render_json(result: ScanResult, output_path: Path) -> None:
    """Write deterministic JSON report to file with 0o600 permissions.

    Args:
        result: The scan result to serialize.
        output_path: Path where the JSON file will be written.
    """
    content = serialize(result)
    output_path.write_text(content, encoding="utf-8")
    os.chmod(output_path, 0o600)


def serialize(result: ScanResult) -> str:
    """Serialize ScanResult to a deterministic JSON string.

    Guarantees:
    - sort_keys=True for key ordering
    - indent=2 for readability
    - Collections sorted (files by category+path, dirs by size desc)
    - Same input always produces byte-identical output
    """
    return json.dumps(_to_dict(result), sort_keys=True, indent=2, ensure_ascii=False)


def _to_dict(result: ScanResult) -> dict:
    """Convert ScanResult to a JSON-serializable dictionary."""
    return {
        "root": result.root,
        "timestamp": result.timestamp,
        "total_size": result.total_size,
        "total_files": result.total_files,
        "categories": {
            cat.value: {
                "total_size": stats.total_size,
                "file_count": stats.file_count,
                "percentage": stats.percentage,
            }
            for cat, stats in sorted(result.categories.items(), key=lambda x: x[0].value)
        },
        "top_directories": [
            {
                "path": d.path,
                "total_size": d.total_size,
                "file_count": d.file_count,
            }
            for d in result.dirs
        ],
        "suggestions": [
            {
                "path": s.path,
                "size": s.size,
                "category": s.category,
                "reason": s.reason,
                "risk_level": s.risk_level.value,
                "last_used": s.last_used.isoformat() if s.last_used else None,
            }
            for s in result.suggestions
        ],
        "files": [
            {
                "path": f.path,
                "size": f.size,
                "mtime": f.mtime,
                "extension": f.extension,
                "category": f.category.value,
            }
            for f in sorted(result.files, key=lambda x: (x.category.value, x.path))
        ],
    }
