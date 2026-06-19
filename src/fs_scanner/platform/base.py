"""Base platform — cross-platform defaults only."""

from __future__ import annotations

from pathlib import Path


class BasePlatform:
    """Cross-platform defaults. No OS-specific logic."""

    def system_exclusion_paths(self) -> tuple[str, ...]:
        return ()

    def excluded_dir_names(self) -> tuple[str, ...]:
        return ()

    def excluded_file_names(self) -> tuple[str, ...]:
        return ()

    def sensitive_patterns(self) -> tuple[str, ...]:
        return (".env", "*.pem", "*.key", "credentials*", "*.kdbx")

    def sensitive_dirs(self) -> tuple[str, ...]:
        home = str(Path.home())
        return (
            f"{home}/.ssh/",
            f"{home}/.gnupg/",
        )

    def cache_rules(self, home: Path) -> list[dict]:
        """Cross-platform cache paths (work on any OS)."""
        return [
            {
                "path": home / ".m2" / "repository",
                "category": "Maven Cache",
                "reason": "Maven local repository. Re-downloads on next build. Run: rm -rf ~/.m2/repository",
                "risk": "safe",
            },
            {
                "path": home / ".gradle" / "caches",
                "category": "Gradle Cache",
                "reason": "Gradle build cache. Regenerates on next build. Run: rm -rf ~/.gradle/caches",
                "risk": "safe",
            },
            {
                "path": home / ".npm" / "_cacache",
                "category": "npm Cache",
                "reason": "npm download cache. Run: npm cache clean --force",
                "risk": "safe",
            },
        ]

    def dir_size(self, path: Path, timeout: int = 30) -> int:
        """Cross-platform directory size using os.walk."""
        import os
        total = 0
        try:
            for dirpath, _, filenames in os.walk(path):
                for f in filenames:
                    try:
                        total += os.path.getsize(os.path.join(dirpath, f))
                    except (PermissionError, OSError):
                        pass
        except (PermissionError, OSError):
            pass
        return total
