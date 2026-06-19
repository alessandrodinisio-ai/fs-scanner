"""CLI interface for fs-scanner using Click."""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import click

from .config import ScanConfig, load_config, parse_size
from .catalog.categorizer import categorize_files, compute_stats
from .catalog.models import Category, DirEntry, ScanResult
from .scanner.exclusions import ExclusionEngine
from .scanner.walker import parallel_walk


logger = logging.getLogger("fs_scanner")


class SizeParamType(click.ParamType):
    """Click parameter type for human-readable size strings."""

    name = "size"

    def convert(self, value, param, ctx):
        if value is None:
            return None
        try:
            parse_size(value)
            return value
        except ValueError as e:
            self.fail(str(e), param, ctx)


SIZE_TYPE = SizeParamType()


@click.command()
@click.argument("path", default="~", type=click.Path())
@click.option("--depth", type=int, default=None, help="Max traversal depth below root.")
@click.option("--min-size", type=SIZE_TYPE, default=None, help="Min file size (e.g., 1MB, 500KB).")
@click.option("--top", type=int, default=20, help="Show top N heaviest directories.")
@click.option(
    "--format", "output_format",
    type=click.Choice(["terminal", "json", "html"], case_sensitive=False),
    default="terminal",
    help="Output format.",
)
@click.option("--exclude", multiple=True, help="Glob pattern to exclude (repeatable).")
@click.option("--no-suggestions", is_flag=True, help="Disable deletion suggestions.")
@click.option("--compare", type=click.Path(exists=True), default=None, help="Previous JSON scan for comparison.")
@click.option("--dry-run", is_flag=True, help="Show what would be scanned without scanning.")
@click.option("--verbose", is_flag=True, help="Show each directory as entered.")
def scan(
    path: str,
    depth: int | None,
    min_size: str | None,
    top: int,
    output_format: str,
    exclude: tuple[str, ...],
    no_suggestions: bool,
    compare: str | None,
    dry_run: bool,
    verbose: bool,
) -> None:
    """Scan filesystem and report disk usage.

    PATH is the root directory to scan (default: home directory).
    """
    # Setup logging
    log_level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s", stream=sys.stderr)

    # Build config
    cli_args = {
        "path": path,
        "depth": depth,
        "min_size": min_size,
        "top": top,
        "output_format": output_format,
        "exclude": exclude,
        "no_suggestions": no_suggestions,
        "compare": compare,
        "dry_run": dry_run,
        "verbose": verbose,
    }

    try:
        config = load_config(cli_args)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(2)

    # Validate root path exists
    if not config.root.exists():
        click.echo(f"Error: Path does not exist: {config.root}", err=True)
        sys.exit(2)

    if not config.root.is_dir():
        click.echo(f"Error: Path is not a directory: {config.root}", err=True)
        sys.exit(2)

    # Dry-run mode
    if config.dry_run:
        _show_dry_run(config)
        return

    # Build exclusion engine
    exclusions = ExclusionEngine(user_patterns=config.exclude_patterns)

    # Run scan with progress
    from .progress import scan_with_progress
    files = scan_with_progress(config, exclusions)

    # Categorize files
    categorize_files(files)

    # Compute statistics
    categories = compute_stats(files)
    total_size = sum(f.size for f in files)

    # Build directory tree
    dirs = _build_dir_tree(files, config.top_n)

    # Build scan result
    suggestions = []
    if config.suggestions_enabled:
        from .suggestions.git_repos import find_suggestions as find_git_suggestions
        from .suggestions.cache_rules import find_suggestions as find_cache_suggestions
        from .suggestions.homebrew import find_suggestions as find_homebrew_suggestions
        from .suggestions.app_leftovers import find_suggestions as find_leftover_suggestions
        from .suggestions.xcode import find_suggestions as find_xcode_suggestions
        from .suggestions.mail import find_suggestions as find_mail_suggestions
        from .suggestions.icloud import find_suggestions as find_icloud_suggestions
        from .suggestions.timemachine import find_suggestions as find_tm_suggestions

        suggestions.extend(find_git_suggestions(config.root))
        suggestions.extend(find_cache_suggestions(config.root))
        suggestions.extend(find_homebrew_suggestions(config.root))
        suggestions.extend(find_leftover_suggestions(config.root))
        suggestions.extend(find_xcode_suggestions(config.root))
        suggestions.extend(find_mail_suggestions(config.root))
        suggestions.extend(find_icloud_suggestions(config.root))
        suggestions.extend(find_tm_suggestions(config.root))
        suggestions.sort(key=lambda s: s.size, reverse=True)

    result = ScanResult(
        root=str(config.root),
        timestamp=datetime.now(timezone.utc).isoformat(),
        total_size=total_size,
        total_files=len(files),
        files=sorted(files, key=lambda f: (f.category.value, f.path)),
        dirs=dirs,
        categories=categories,
        suggestions=suggestions,
    )

    # Comparison mode
    if config.compare_path:
        from .reporters.comparison import compare_scans, format_comparison
        try:
            comp_result = compare_scans(result, config.compare_path)
            click.echo(format_comparison(comp_result))
        except (ValueError, OSError) as e:
            click.echo(f"Error loading comparison file: {e}", err=True)
            sys.exit(1)
        return

    # Output
    # Always save a JSON report with timestamp
    from .reporters.json_report import render_json
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_dir = Path("output")
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / f"scan_{timestamp_str}.json"
    render_json(result, json_path)
    click.echo(f"Report saved: {json_path.resolve()}", err=True)

    if config.output_format == "terminal":
        from .reporters.terminal import render_terminal
        render_terminal(result, top_n=config.top_n)
    elif config.output_format == "json":
        pass  # Already saved above
    elif config.output_format == "html":
        from .reporters.html_report import render_html
        html_path = report_dir / f"scan_{timestamp_str}.html"
        render_html(result, html_path)
        click.echo(f"HTML dashboard: {html_path.resolve()}", err=True)


def _show_dry_run(config: ScanConfig) -> None:
    """Display what would be scanned without actually scanning."""
    click.echo("=== DRY RUN ===")
    click.echo(f"Root path:       {config.root}")
    click.echo(f"Max depth:       {config.max_depth or 'unlimited'}")
    click.echo(f"Min file size:   {config.min_size_bytes or 'none'} bytes")
    click.echo(f"Output format:   {config.output_format}")
    click.echo(f"Top N dirs:      {config.top_n}")
    click.echo(f"Suggestions:     {'enabled' if config.suggestions_enabled else 'disabled'}")
    if config.exclude_patterns:
        click.echo(f"Exclude patterns: {', '.join(config.exclude_patterns)}")
    if config.compare_path:
        click.echo(f"Compare with:    {config.compare_path}")


def _build_dir_tree(files: list, top_n: int) -> list[DirEntry]:
    """Build a list of top directories sorted by cumulative size.

    Aggregates file sizes into their parent directories.
    """
    dir_sizes: dict[str, int] = {}
    dir_counts: dict[str, int] = {}

    for f in files:
        parent = str(Path(f.path).parent)
        dir_sizes[parent] = dir_sizes.get(parent, 0) + f.size
        dir_counts[parent] = dir_counts.get(parent, 0) + 1

    # Also propagate sizes up the tree
    all_dirs: dict[str, int] = {}
    all_counts: dict[str, int] = {}

    for f in files:
        parts = Path(f.path).parts
        # Accumulate size to each ancestor directory
        for i in range(1, len(parts)):
            dir_path = str(Path(*parts[:i]))
            all_dirs[dir_path] = all_dirs.get(dir_path, 0) + f.size
            all_counts[dir_path] = all_counts.get(dir_path, 0) + 1

    # Sort by size descending, take top N
    sorted_dirs = sorted(all_dirs.items(), key=lambda x: x[1], reverse=True)[:top_n]

    return [
        DirEntry(
            path=path,
            total_size=size,
            file_count=all_counts.get(path, 0),
        )
        for path, size in sorted_dirs
    ]
