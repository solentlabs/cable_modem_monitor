#!/usr/bin/env python3
"""Clean up test artifacts from the workspace."""
import shutil
from pathlib import Path

# Root of the workspace (go up 2 levels: dev/ -> scripts/ -> project root)
ROOT = Path(__file__).resolve().parents[2]

# Common test artifacts to clean
CLEANUP_PATHS = [
    ".coverage",  # Coverage data file
    "htmlcov",  # HTML coverage report
    ".pytest_cache",  # Pytest cache
    "__pycache__",  # Python bytecode cache
]


def main():
    """Clean up test artifacts."""
    for name in CLEANUP_PATHS:
        path = ROOT / name
        if path.is_file():
            print(f"Removing file: {path}")
            path.unlink(missing_ok=True)
        elif path.is_dir():
            print(f"Removing directory: {path}")
            shutil.rmtree(path, ignore_errors=True)

    # Clean up all __pycache__ directories recursively
    for pycache in ROOT.rglob("__pycache__"):
        print(f"Removing directory: {pycache}")
        shutil.rmtree(pycache, ignore_errors=True)

    print("\nCleanup complete!")


if __name__ == "__main__":
    main()
