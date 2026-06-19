"""File categorization by extension."""

from __future__ import annotations

from .models import Category, CategoryStats, FileEntry

# Immutable mapping: extension (lowercase, no dot) → Category
EXTENSION_MAP: dict[str, Category] = {
    # Code
    "py": Category.CODE,
    "js": Category.CODE,
    "ts": Category.CODE,
    "java": Category.CODE,
    "scala": Category.CODE,
    "rs": Category.CODE,
    "go": Category.CODE,
    "c": Category.CODE,
    "cpp": Category.CODE,
    "h": Category.CODE,
    "rb": Category.CODE,
    "sh": Category.CODE,
    "sql": Category.CODE,
    "html": Category.CODE,
    "css": Category.CODE,
    "scss": Category.CODE,
    # Documents
    "pdf": Category.DOCUMENTS,
    "doc": Category.DOCUMENTS,
    "docx": Category.DOCUMENTS,
    "xls": Category.DOCUMENTS,
    "xlsx": Category.DOCUMENTS,
    "ppt": Category.DOCUMENTS,
    "pptx": Category.DOCUMENTS,
    "txt": Category.DOCUMENTS,
    "md": Category.DOCUMENTS,
    "rtf": Category.DOCUMENTS,
    "odt": Category.DOCUMENTS,
    "pages": Category.DOCUMENTS,
    "numbers": Category.DOCUMENTS,
    "keynote": Category.DOCUMENTS,
    # Media
    "mp4": Category.MEDIA,
    "mkv": Category.MEDIA,
    "avi": Category.MEDIA,
    "mov": Category.MEDIA,
    "mp3": Category.MEDIA,
    "wav": Category.MEDIA,
    "flac": Category.MEDIA,
    "aac": Category.MEDIA,
    "ogg": Category.MEDIA,
    "m4a": Category.MEDIA,
    "m4v": Category.MEDIA,
    # Images
    "jpg": Category.IMAGES,
    "jpeg": Category.IMAGES,
    "png": Category.IMAGES,
    "gif": Category.IMAGES,
    "svg": Category.IMAGES,
    "bmp": Category.IMAGES,
    "tiff": Category.IMAGES,
    "webp": Category.IMAGES,
    "ico": Category.IMAGES,
    "heic": Category.IMAGES,
    "raw": Category.IMAGES,
    "psd": Category.IMAGES,
    "ai": Category.IMAGES,
    # Archives
    "zip": Category.ARCHIVES,
    "tar": Category.ARCHIVES,
    "gz": Category.ARCHIVES,
    "bz2": Category.ARCHIVES,
    "xz": Category.ARCHIVES,
    "7z": Category.ARCHIVES,
    "rar": Category.ARCHIVES,
    "dmg": Category.ARCHIVES,
    "iso": Category.ARCHIVES,
    "pkg": Category.ARCHIVES,
    # Data
    "json": Category.DATA,
    "xml": Category.DATA,
    "yaml": Category.DATA,
    "yml": Category.DATA,
    "csv": Category.DATA,
    "tsv": Category.DATA,
    "parquet": Category.DATA,
    "avro": Category.DATA,
    "sqlite": Category.DATA,
    "db": Category.DATA,
    # Cache/Build
    "class": Category.CACHE_BUILD,
    "o": Category.CACHE_BUILD,
    "pyc": Category.CACHE_BUILD,
    "pyo": Category.CACHE_BUILD,
    "jar": Category.CACHE_BUILD,
    "war": Category.CACHE_BUILD,
    # App Temp
    "log": Category.APP_TEMP,
    "tmp": Category.APP_TEMP,
    "cache": Category.APP_TEMP,
    "swp": Category.APP_TEMP,
    "bak": Category.APP_TEMP,
}

# Directory names that indicate Cache/Build category
CACHE_BUILD_DIR_NAMES: frozenset[str] = frozenset({
    "node_modules",
    "__pycache__",
    ".gradle",
    ".m2",
    "build",
    "dist",
    "target",
})


def categorize(extension: str) -> Category:
    """Return the Category for a file extension.

    Args:
        extension: File extension, with or without leading dot, any case.

    Returns:
        The matching Category, or Category.OTHER if unknown.
    """
    return EXTENSION_MAP.get(extension.lower().lstrip("."), Category.OTHER)


def categorize_files(files: list[FileEntry]) -> list[FileEntry]:
    """Assign categories to all file entries in-place and return the list.

    Uses the extension-based categorizer. Files in cache/build directories
    are categorized as CACHE_BUILD regardless of extension.
    """
    for entry in files:
        # Check if file is under a known cache/build directory
        parts = entry.path.split("/")
        if any(part in CACHE_BUILD_DIR_NAMES for part in parts):
            entry.category = Category.CACHE_BUILD
        else:
            entry.category = categorize(entry.extension)
    return files


def compute_stats(files: list[FileEntry]) -> dict[Category, CategoryStats]:
    """Compute per-category size, count, and percentage.

    Args:
        files: List of categorized FileEntry objects.

    Returns:
        Dictionary mapping each Category to its statistics.
    """
    size_by_cat: dict[Category, int] = {}
    count_by_cat: dict[Category, int] = {}

    for entry in files:
        size_by_cat[entry.category] = size_by_cat.get(entry.category, 0) + entry.size
        count_by_cat[entry.category] = count_by_cat.get(entry.category, 0) + 1

    total_size = sum(size_by_cat.values())

    stats: dict[Category, CategoryStats] = {}
    for cat in Category:
        cat_size = size_by_cat.get(cat, 0)
        cat_count = count_by_cat.get(cat, 0)
        percentage = (cat_size / total_size * 100.0) if total_size > 0 else 0.0
        stats[cat] = CategoryStats(
            total_size=cat_size,
            file_count=cat_count,
            percentage=round(percentage, 2),
        )

    return stats
