"""Configuration loading and merging for fs-scanner."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class ScanConfig:
    """Immutable configuration for a scan run."""

    root: Path
    max_depth: int | None
    min_size_bytes: int | None
    top_n: int
    output_format: str  # "terminal" | "json" | "html"
    exclude_patterns: tuple[str, ...]
    suggestions_enabled: bool
    compare_path: Path | None
    dry_run: bool
    verbose: bool


_SIZE_PATTERN = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(B|KB|MB|GB|TB)?\s*$", re.IGNORECASE)

_SIZE_MULTIPLIERS: dict[str, int] = {
    "b": 1,
    "kb": 1024,
    "mb": 1024**2,
    "gb": 1024**3,
    "tb": 1024**4,
}


def parse_size(size_str: str) -> int:
    """Parse a human-readable size string into bytes.

    Supports: '100B', '1KB', '50MB', '2GB', '1.5GB'.
    If no suffix is given, bytes are assumed.

    Raises:
        ValueError: If the string cannot be parsed.
    """
    match = _SIZE_PATTERN.match(size_str)
    if not match:
        raise ValueError(
            f"Invalid size format: '{size_str}'. "
            "Expected format like '100B', '1KB', '50MB', '2GB'."
        )
    value = float(match.group(1))
    unit = (match.group(2) or "B").lower()
    return int(value * _SIZE_MULTIPLIERS[unit])


def _load_yaml_config(config_path: Path) -> dict:
    """Load configuration from a YAML file, returning empty dict on failure."""
    if not config_path.is_file():
        return {}
    try:
        with open(config_path) as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}
    except (yaml.YAMLError, OSError):
        return {}


def _load_scannerignore(root: Path) -> list[str]:
    """Load exclusion patterns from .scannerignore in the scan root."""
    ignore_file = root / ".scannerignore"
    if not ignore_file.is_file():
        return []
    patterns = []
    try:
        for line in ignore_file.read_text().splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                patterns.append(stripped)
    except OSError:
        pass
    return patterns


def load_config(cli_args: dict) -> ScanConfig:
    """Build ScanConfig by merging: defaults → config.yaml → .scannerignore → CLI flags.

    Args:
        cli_args: Dictionary of CLI arguments from Click.
    """
    # Resolve root path
    raw_path = cli_args.get("path", "~")
    root = Path(raw_path).expanduser().resolve()

    # Load user-global YAML config
    global_config_path = Path("~/.fs-scanner/config.yaml").expanduser()
    yaml_cfg = _load_yaml_config(global_config_path)

    # Load .scannerignore from scan root
    ignore_patterns = _load_scannerignore(root)

    # Merge: yaml defaults < .scannerignore < CLI flags
    # CLI flags take highest priority (None means "not specified")
    exclude_from_yaml = tuple(yaml_cfg.get("exclude", []))
    exclude_from_cli = tuple(cli_args.get("exclude", ()))
    all_excludes = exclude_from_yaml + tuple(ignore_patterns) + exclude_from_cli

    # Parse min-size
    min_size_str = cli_args.get("min_size")
    min_size_bytes = None
    if min_size_str:
        min_size_bytes = parse_size(min_size_str)

    # Parse compare path
    compare_raw = cli_args.get("compare")
    compare_path = Path(compare_raw).resolve() if compare_raw else None

    return ScanConfig(
        root=root,
        max_depth=cli_args.get("depth") or yaml_cfg.get("depth"),
        min_size_bytes=min_size_bytes,
        top_n=cli_args.get("top", yaml_cfg.get("top", 20)),
        output_format=cli_args.get("output_format", yaml_cfg.get("format", "terminal")),
        exclude_patterns=all_excludes,
        suggestions_enabled=not cli_args.get("no_suggestions", False),
        compare_path=compare_path,
        dry_run=cli_args.get("dry_run", False),
        verbose=cli_args.get("verbose", False),
    )
