"""HTML dashboard report output (placeholder - full implementation in Tasks 21-26)."""

from __future__ import annotations

import os
from pathlib import Path

from ..catalog.models import ScanResult


def render_html(result: ScanResult, output_path: Path, history: list[ScanResult] | None = None) -> None:
    """Generate a self-contained HTML dashboard and write with 0o600 permissions.

    Full implementation in Tasks 21-26. This is a minimal working version.
    """
    from ..dashboard.generator import generate_dashboard

    html_content = generate_dashboard(result, history)
    output_path.write_text(html_content, encoding="utf-8")
    os.chmod(output_path, 0o600)
