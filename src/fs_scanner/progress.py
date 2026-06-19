"""Progress tracking during filesystem scanning."""

from __future__ import annotations

import threading

from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from .catalog.models import FileEntry
from .config import ScanConfig
from .scanner.exclusions import ExclusionEngine
from .scanner.walker import parallel_walk


def scan_with_progress(config: ScanConfig, exclusions: ExclusionEngine) -> list[FileEntry]:
    """Run the scanner with a progress bar (terminal) or silently (json/html).

    Args:
        config: Scan configuration.
        exclusions: Exclusion engine.

    Returns:
        List of discovered FileEntry objects.
    """
    if config.output_format != "terminal":
        # No progress bar for non-terminal output
        return parallel_walk(
            root=config.root,
            exclusions=exclusions,
            max_depth=config.max_depth,
            min_size=config.min_size_bytes,
            verbose=config.verbose,
        )

    # Terminal mode: show progress
    dir_count = 0
    lock = threading.Lock()

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]Scanning..."),
        TextColumn("{task.description}"),
        TimeElapsedColumn(),
        transient=True,
    ) as progress:
        task = progress.add_task("", total=None)

        def on_dir(dir_path: str) -> None:
            nonlocal dir_count
            with lock:
                dir_count += 1
                # Show abbreviated path
                display = dir_path
                if len(display) > 60:
                    display = "..." + display[-57:]
                progress.update(task, description=f"[dim]{display}[/dim] ({dir_count} dirs)")

        files = parallel_walk(
            root=config.root,
            exclusions=exclusions,
            max_depth=config.max_depth,
            min_size=config.min_size_bytes,
            verbose=config.verbose,
            progress_callback=on_dir,
        )

    return files
