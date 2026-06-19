"""Core data models for fs-scanner."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Category(Enum):
    """File category based on extension."""

    CODE = "Code"
    DOCUMENTS = "Documents"
    MEDIA = "Media"
    IMAGES = "Images"
    ARCHIVES = "Archives"
    DATA = "Data"
    CACHE_BUILD = "Cache/Build"
    APP_TEMP = "App Temp"
    OTHER = "Other"


class RiskLevel(Enum):
    """Risk level for deletion suggestions."""

    SAFE = "safe"
    CAUTION = "caution"
    RISKY = "risky"


@dataclass(slots=True)
class FileEntry:
    """A single file discovered during scanning."""

    path: str
    size: int
    mtime: float
    extension: str
    category: Category


@dataclass(slots=True)
class DirEntry:
    """A directory with aggregated size from its subtree."""

    path: str
    total_size: int
    file_count: int
    children: list[DirEntry] = field(default_factory=list)


@dataclass(slots=True)
class Suggestion:
    """A deletion suggestion for reclaimable space."""

    path: str
    size: int
    category: str
    reason: str
    risk_level: RiskLevel
    last_used: datetime | None = None


@dataclass(frozen=True)
class CategoryStats:
    """Aggregated statistics for a single category."""

    total_size: int
    file_count: int
    percentage: float  # 0.0 - 100.0


@dataclass(frozen=True)
class ScanResult:
    """Complete result of a filesystem scan."""

    root: str
    timestamp: str  # ISO 8601
    total_size: int
    total_files: int
    files: list[FileEntry]
    dirs: list[DirEntry]
    categories: dict[Category, CategoryStats]
    suggestions: list[Suggestion]
