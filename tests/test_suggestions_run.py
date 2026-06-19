"""Test suggestion modules directly."""
import traceback
from pathlib import Path

print("Testing cache_rules...")
try:
    from fs_scanner.suggestions.cache_rules import find_suggestions
    results = find_suggestions(Path.home())
    print(f"  Found {len(results)} cache suggestions")
    for s in results[:8]:
        print(f"  [{s.risk_level.value:7s}] {s.category:25s} {s.size / 1024**2:8.0f} MB")
except Exception as e:
    traceback.print_exc()

print("\nTesting homebrew...")
try:
    from fs_scanner.suggestions.homebrew import find_suggestions as hb
    results = hb(Path.home())
    print(f"  Found {len(results)} homebrew suggestions")
    for s in results:
        print(f"  [{s.risk_level.value:7s}] {s.category:25s} {s.size / 1024**2:8.0f} MB")
except Exception as e:
    traceback.print_exc()

print("\nDone.")
