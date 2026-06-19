"""Verify JSON serialization is deterministic."""
from fs_scanner.catalog.models import Category, CategoryStats, FileEntry, ScanResult
from fs_scanner.reporters.json_report import serialize


def main():
    # Build a fixed ScanResult
    files = [
        FileEntry(path="/z/b.py", size=200, mtime=1000.0, extension="py", category=Category.CODE),
        FileEntry(path="/a/a.txt", size=100, mtime=2000.0, extension="txt", category=Category.DOCUMENTS),
        FileEntry(path="/m/c.log", size=50, mtime=500.0, extension="log", category=Category.APP_TEMP),
    ]
    categories = {
        Category.CODE: CategoryStats(total_size=200, file_count=1, percentage=57.14),
        Category.DOCUMENTS: CategoryStats(total_size=100, file_count=1, percentage=28.57),
        Category.APP_TEMP: CategoryStats(total_size=50, file_count=1, percentage=14.29),
    }
    result = ScanResult(
        root="/test",
        timestamp="2024-01-01T00:00:00Z",
        total_size=350,
        total_files=3,
        files=files,
        dirs=[],
        categories=categories,
        suggestions=[],
    )

    # Serialize multiple times - must be byte-identical
    out1 = serialize(result)
    out2 = serialize(result)
    out3 = serialize(result)

    assert out1 == out2 == out3, "JSON output is not deterministic!"
    assert '"sort_keys"' not in out1  # Sanity check

    # Verify files are sorted by category then path in output
    import json
    data = json.loads(out1)
    file_entries = data["files"]
    assert file_entries[0]["category"] == "App Temp"  # A before C before D
    assert file_entries[1]["category"] == "Code"
    assert file_entries[2]["category"] == "Documents"

    # Verify keys are sorted
    keys = list(data.keys())
    assert keys == sorted(keys), f"Top-level keys not sorted: {keys}"

    print("Determinism verified: 3 serializations are byte-identical")
    print(f"Output length: {len(out1)} bytes")


if __name__ == "__main__":
    main()
