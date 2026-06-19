"""Test Git orphan repo detection on the real filesystem."""
from pathlib import Path
from fs_scanner.suggestions.git_repos import find_suggestions


def main():
    results = find_suggestions(Path.home(), max_repos=10)
    if not results:
        print("No bloated Git repos found.")
        return

    print(f"Found {len(results)} suggestion(s):\n")
    for s in results:
        print(f"  [{s.risk_level.value.upper()}] {s.category}")
        print(f"  Path: {s.path}")
        print(f"  Reclaimable: {s.size / 1024**3:.2f} GB")
        print(f"  {s.reason}")
        print()


if __name__ == "__main__":
    main()
