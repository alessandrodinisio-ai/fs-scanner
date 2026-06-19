"""Terminal reporter using rich for colored output."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.tree import Tree
from rich.panel import Panel
from rich.text import Text

from ..catalog.models import Category, ScanResult


def format_size(size_bytes: int) -> str:
    """Format byte count as human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024**2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024**3:
        return f"{size_bytes / 1024**2:.1f} MB"
    elif size_bytes < 1024**4:
        return f"{size_bytes / 1024**3:.1f} GB"
    else:
        return f"{size_bytes / 1024**4:.1f} TB"


# Color mapping for categories
_CATEGORY_COLORS: dict[Category, str] = {
    Category.CODE: "green",
    Category.DOCUMENTS: "blue",
    Category.MEDIA: "magenta",
    Category.IMAGES: "cyan",
    Category.ARCHIVES: "yellow",
    Category.DATA: "white",
    Category.CACHE_BUILD: "red",
    Category.APP_TEMP: "bright_red",
    Category.OTHER: "dim",
}


def render_terminal(result: ScanResult, top_n: int = 20) -> None:
    """Render scan results with rich: summary, category table, tree view, suggestions."""
    console = Console()

    # Header
    console.print()
    console.print(Panel(
        f"[bold]Scanned:[/bold] {result.root}\n"
        f"[bold]Files:[/bold] {result.total_files:,}  "
        f"[bold]Total Size:[/bold] {format_size(result.total_size)}  "
        f"[bold]Time:[/bold] {result.timestamp}",
        title="[bold cyan]fs-scanner Report[/bold cyan]",
        border_style="cyan",
    ))

    # Category table
    _render_categories(console, result)

    # Directory tree
    _render_tree(console, result, top_n)

    # Suggestions
    if result.suggestions:
        _render_suggestions(console, result)

    console.print()


def _render_categories(console: Console, result: ScanResult) -> None:
    """Render per-category statistics table."""
    table = Table(title="File Categories", show_lines=False, border_style="dim")
    table.add_column("Category", style="bold", min_width=12)
    table.add_column("Size", justify="right", min_width=10)
    table.add_column("Files", justify="right", min_width=8)
    table.add_column("%", justify="right", min_width=6)
    table.add_column("Bar", min_width=20)

    # Sort categories by size descending
    sorted_cats = sorted(
        result.categories.items(),
        key=lambda x: x[1].total_size,
        reverse=True,
    )

    for cat, stats in sorted_cats:
        if stats.file_count == 0:
            continue
        color = _CATEGORY_COLORS.get(cat, "white")
        bar_len = int(stats.percentage / 5)  # Scale to max ~20 chars
        bar = Text("█" * bar_len, style=color)

        table.add_row(
            f"[{color}]{cat.value}[/{color}]",
            format_size(stats.total_size),
            f"{stats.file_count:,}",
            f"{stats.percentage:.1f}%",
            bar,
        )

    console.print()
    console.print(table)


def _render_tree(console: Console, result: ScanResult, top_n: int) -> None:
    """Render heavy directory tree view."""
    if not result.dirs:
        return

    console.print()
    tree = Tree(
        f"[bold]Top {min(top_n, len(result.dirs))} Heaviest Directories[/bold]",
        guide_style="dim",
    )

    for dir_entry in result.dirs[:top_n]:
        size_str = format_size(dir_entry.total_size)
        # Color based on relative size
        if result.total_size > 0:
            ratio = dir_entry.total_size / result.total_size
            if ratio > 0.3:
                color = "bold red"
            elif ratio > 0.1:
                color = "yellow"
            else:
                color = "green"
        else:
            color = "white"

        tree.add(
            f"[{color}]{size_str:>10}[/{color}]  "
            f"{dir_entry.path} "
            f"[dim]({dir_entry.file_count:,} files)[/dim]"
        )

    console.print(tree)


def _render_suggestions(console: Console, result: ScanResult) -> None:
    """Render deletion suggestions."""
    console.print()
    table = Table(title="Deletion Suggestions", show_lines=True, border_style="dim")
    table.add_column("Category", style="bold", min_width=20)
    table.add_column("Path", min_width=40)
    table.add_column("Size", justify="right", min_width=10)
    table.add_column("Risk", justify="center", min_width=8)

    risk_colors = {"safe": "green", "caution": "yellow", "risky": "red"}

    for suggestion in result.suggestions:
        risk_color = risk_colors.get(suggestion.risk_level.value, "white")
        table.add_row(
            suggestion.category,
            suggestion.path,
            format_size(suggestion.size),
            f"[{risk_color}]{suggestion.risk_level.value.upper()}[/{risk_color}]",
        )

    total_reclaimable = sum(s.size for s in result.suggestions)
    console.print(table)
    console.print(
        f"\n[bold]Total reclaimable:[/bold] [green]{format_size(total_reclaimable)}[/green]"
    )
