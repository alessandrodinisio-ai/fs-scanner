"""Exclusion engine for system, sensitive, and user-defined patterns."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ExclusionEngine:
    """Determines which files and directories to skip during scanning.

    Exclusion hierarchy:
    1. System paths (absolute macOS directories)
    2. Excluded directory names (anywhere in tree)
    3. Excluded file names (anywhere in tree)
    4. Sensitive file patterns (never recorded)
    5. Sensitive directories (never recorded)
    6. User glob patterns (from CLI --exclude or .scannerignore)
    """

    system_paths: tuple[str, ...] = (
        "/System",
        "/Library",
        "/usr",
        "/bin",
        "/sbin",
        "/private",
        "/var",
        "/cores",
    )

    excluded_dir_names: tuple[str, ...] = (
        ".Spotlight-V100",
        ".fseventsd",
        ".Trashes",
    )

    excluded_file_names: tuple[str, ...] = (".DS_Store",)

    sensitive_patterns: tuple[str, ...] = (
        ".env",
        "*.pem",
        "*.key",
        "credentials*",
        "*.kdbx",
    )

    sensitive_dirs: tuple[str, ...] = (
        "~/.aws/credentials",
        "~/.ssh/",
        "~/.gnupg/",
    )

    user_patterns: tuple[str, ...] = ()

    # Resolved sensitive directory paths (computed post-init)
    _resolved_sensitive_dirs: tuple[str, ...] = field(
        default=(), init=False, repr=False, compare=False, hash=False
    )

    def __post_init__(self) -> None:
        # Resolve ~ in sensitive dirs for fast prefix matching
        resolved = tuple(
            str(Path(d).expanduser().resolve()).rstrip("/")
            for d in self.sensitive_dirs
        )
        # Bypass frozen with object.__setattr__
        object.__setattr__(self, "_resolved_sensitive_dirs", resolved)

    def should_exclude_dir(self, path: Path) -> bool:
        """Check if a directory should be skipped entirely (subtree not traversed).

        Args:
            path: Absolute path to the directory.

        Returns:
            True if the directory should be excluded.
        """
        path_str = str(path)

        # Check system paths (exact prefix match)
        for sys_path in self.system_paths:
            if path_str == sys_path or path_str.startswith(sys_path + "/"):
                return True

        # Check excluded directory names
        dir_name = path.name
        if dir_name in self.excluded_dir_names:
            return True

        # Check sensitive directories
        for sensitive_dir in self._resolved_sensitive_dirs:
            if path_str == sensitive_dir or path_str.startswith(sensitive_dir + "/"):
                return True

        # Check user glob patterns against directory name and full path
        for pattern in self.user_patterns:
            if fnmatch.fnmatch(dir_name, pattern):
                return True
            if fnmatch.fnmatch(path_str, pattern):
                return True

        return False

    def should_exclude_file(self, path: Path) -> bool:
        """Check if a file should be excluded from results.

        Args:
            path: Absolute path to the file.

        Returns:
            True if the file should be excluded.
        """
        file_name = path.name

        # Check excluded file names
        if file_name in self.excluded_file_names:
            return True

        # Check if sensitive (sensitive files are always excluded)
        if self.is_sensitive(path):
            return True

        # Check user glob patterns
        path_str = str(path)
        for pattern in self.user_patterns:
            if fnmatch.fnmatch(file_name, pattern):
                return True
            if fnmatch.fnmatch(path_str, pattern):
                return True

        return False

    def is_sensitive(self, path: Path) -> bool:
        """Check if a file matches sensitivity rules.

        Sensitive files have no trace recorded — no path, name, metadata, or count.

        Args:
            path: Absolute path to the file.

        Returns:
            True if the file is sensitive.
        """
        path_str = str(path)
        file_name = path.name

        # Check sensitive file patterns
        for pattern in self.sensitive_patterns:
            if fnmatch.fnmatch(file_name, pattern):
                return True

        # Check if under a sensitive directory
        for sensitive_dir in self._resolved_sensitive_dirs:
            if path_str.startswith(sensitive_dir):
                return True

        return False
