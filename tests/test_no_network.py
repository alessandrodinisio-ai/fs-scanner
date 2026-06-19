"""Verify scanner makes no network calls."""
import socket
from pathlib import Path

# Monkey-patch socket to detect any network access
_orig_connect = socket.socket.connect


def _blocked_connect(self, *args, **kwargs):
    raise RuntimeError("Network call detected! Scanner must be offline-only.")


socket.socket.connect = _blocked_connect

try:
    from fs_scanner.scanner.exclusions import ExclusionEngine
    from fs_scanner.scanner.walker import parallel_walk
    from fs_scanner.catalog.categorizer import categorize_files, compute_stats

    files = parallel_walk(Path("src/fs_scanner"), ExclusionEngine(), max_depth=2)
    categorize_files(files)
    stats = compute_stats(files)
    print(f"Scan OK: {len(files)} files, no network calls made")
finally:
    socket.socket.connect = _orig_connect
