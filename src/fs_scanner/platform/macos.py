"""macOS-specific platform configuration."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .base import BasePlatform


class MacOSPlatform(BasePlatform):
    """macOS-specific paths, exclusions, and cache locations."""

    def system_exclusion_paths(self) -> tuple[str, ...]:
        return (
            "/System",
            "/Library",
            "/usr",
            "/bin",
            "/sbin",
            "/private",
            "/var",
            "/cores",
        )

    def excluded_dir_names(self) -> tuple[str, ...]:
        return (".Spotlight-V100", ".fseventsd", ".Trashes")

    def excluded_file_names(self) -> tuple[str, ...]:
        return (".DS_Store",)

    def sensitive_dirs(self) -> tuple[str, ...]:
        home = str(Path.home())
        return (
            f"{home}/.ssh/",
            f"{home}/.gnupg/",
            f"{home}/.aws/credentials",
        )

    def cache_rules(self, home: Path) -> list[dict]:
        """macOS-specific cache paths + cross-platform ones."""
        lib = home / "Library"

        macos_rules = [
            # macOS Caches
            {
                "path": lib / "Caches" / "JetBrains",
                "category": "JetBrains Cache",
                "reason": "JetBrains IDE caches. Regenerate on next start. Safe to remove.",
                "risk": "safe",
            },
            {
                "path": lib / "Caches" / "pip",
                "category": "pip Cache",
                "reason": "Python pip download cache. Run: pip cache purge",
                "risk": "safe",
            },
            {
                "path": lib / "Caches" / "Google",
                "category": "Chrome/Google Cache",
                "reason": "Google Chrome browser cache. Regenerates automatically.",
                "risk": "safe",
            },
            {
                "path": lib / "Caches" / "Homebrew",
                "category": "Homebrew Cache",
                "reason": "Homebrew download cache. Run: brew cleanup --prune=all",
                "risk": "safe",
            },
            {
                "path": lib / "Caches" / "pnpm",
                "category": "pnpm Cache",
                "reason": "pnpm download cache. Run: pnpm store prune",
                "risk": "safe",
            },
            {
                "path": lib / "Logs",
                "category": "macOS Logs",
                "reason": "System and application logs. Run: rm -rf ~/Library/Logs/*",
                "risk": "safe",
            },
            # Containers (Podman) — handled in dedicated check, too large for du
            # Email (skip du — too large, use dedicated module)
            # Thunderbird handled separately in mail.py / direct suggestion
        ]

        # Merge with cross-platform rules
        return macos_rules + super().cache_rules(home)

    def dir_size(self, path: Path, timeout: int = 30) -> int:
        """macOS: use /usr/bin/du to avoid TCC process termination."""
        try:
            result = subprocess.run(
                ["/usr/bin/du", "-sk", str(path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=timeout,
            )
            if result.returncode in (0, 1) and result.stdout.strip():
                last_line = result.stdout.strip().split("\n")[-1]
                size_kb = int(last_line.split("\t")[0])
                return size_kb * 1024
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError, ValueError, IndexError):
            pass
        return 0
