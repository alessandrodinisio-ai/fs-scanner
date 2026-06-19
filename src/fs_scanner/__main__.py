"""Allow running fs-scanner as `python -m fs_scanner`."""

from fs_scanner.cli import scan

if __name__ == "__main__":
    scan()
