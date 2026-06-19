"""Parallel filesystem walker using ThreadPoolExecutor."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from ..catalog.models import FileEntry, Category
from .exclusions import ExclusionEngine

logger = logging.getLogger("fs_scanner")


def parallel_walk(
    root: Path,
    exclusions: ExclusionEngine,
    max_depth: int | None = None,
    min_size: int | None = None,
    worker_count: int | None = None,
    verbose: bool = False,
    progress_callback: Callable[[str], None] | None = None,
) -> list[FileEntry]:
    """Walk filesystem in parallel threads, returning a flat list of FileEntry.

    Args:
        root: Root directory to scan.
        exclusions: ExclusionEngine determining what to skip.
        max_depth: Maximum depth (None = unlimited).
        min_size: Minimum file size in bytes (None = no filter).
        worker_count: Number of threads (None = auto).
        verbose: Log each directory as entered.
        progress_callback: Called with directory path for progress tracking.

    Returns:
        Flat list of FileEntry objects for all discovered files.
    """
    if worker_count is None:
        worker_count = min(32, (os.cpu_count() or 4) + 4)

    all_entries: list[FileEntry] = []

    # Use a work-stealing approach: start with root, fan out subdirectories
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {}
        # Submit root directory
        future = executor.submit(
            _scan_directory, root, 0, max_depth, exclusions, min_size, verbose, progress_callback
        )
        futures[future] = root

        while futures:
            done = []
            for f in as_completed(futures):
                done.append(f)
                break  # Process one at a time to submit subdirs promptly

            for f in done:
                del futures[f]
                try:
                    entries, subdirs = f.result()
                    all_entries.extend(entries)
                    # Submit discovered subdirectories for parallel processing
                    for subdir, depth in subdirs:
                        sub_future = executor.submit(
                            _scan_directory,
                            subdir,
                            depth,
                            max_depth,
                            exclusions,
                            min_size,
                            verbose,
                            progress_callback,
                        )
                        futures[sub_future] = subdir
                except Exception as e:
                    logger.warning(f"Error processing directory: {e}")

    return all_entries


def _scan_directory(
    dir_path: Path,
    current_depth: int,
    max_depth: int | None,
    exclusions: ExclusionEngine,
    min_size: int | None,
    verbose: bool,
    progress_callback: Callable[[str], None] | None,
) -> tuple[list[FileEntry], list[tuple[Path, int]]]:
    """Scan a single directory with os.scandir().

    Returns:
        Tuple of (file entries found, subdirectories to process with their depths).
    """
    entries: list[FileEntry] = []
    subdirs: list[tuple[Path, int]] = []

    if verbose:
        logger.debug(f"Scanning: {dir_path}")

    if progress_callback:
        progress_callback(str(dir_path))

    try:
        with os.scandir(dir_path) as it:
            for entry in it:
                try:
                    entry_path = Path(entry.path)

                    if entry.is_symlink():
                        # Record symlinks as zero-size entries but don't follow
                        if not exclusions.should_exclude_file(entry_path):
                            try:
                                # Use lstat to get the link's own info
                                stat = entry.stat(follow_symlinks=False)
                                ext = entry_path.suffix.lstrip(".").lower()
                                entries.append(FileEntry(
                                    path=entry.path,
                                    size=stat.st_size,
                                    mtime=stat.st_mtime,
                                    extension=ext,
                                    category=Category.OTHER,  # Categorized later
                                ))
                            except OSError:
                                pass
                        continue

                    if entry.is_dir(follow_symlinks=False):
                        if exclusions.should_exclude_dir(entry_path):
                            continue
                        # Queue for parallel processing if within depth
                        if max_depth is None or current_depth < max_depth:
                            subdirs.append((entry_path, current_depth + 1))
                        continue

                    if entry.is_file(follow_symlinks=False):
                        if exclusions.should_exclude_file(entry_path):
                            continue

                        stat = entry.stat(follow_symlinks=False)

                        # Apply min-size filter
                        if min_size is not None and stat.st_size < min_size:
                            continue

                        ext = entry_path.suffix.lstrip(".").lower()
                        entries.append(FileEntry(
                            path=entry.path,
                            size=stat.st_size,
                            mtime=stat.st_mtime,
                            extension=ext,
                            category=Category.OTHER,  # Categorized later
                        ))

                except PermissionError:
                    logger.warning(f"Permission denied: {entry.path}")
                except OSError as e:
                    logger.warning(f"I/O error on {entry.path}: {e}")

    except PermissionError:
        logger.warning(f"Cannot read directory: {dir_path}")
    except OSError as e:
        logger.warning(f"I/O error reading directory {dir_path}: {e}")

    return entries, subdirs
