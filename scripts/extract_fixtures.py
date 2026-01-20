#!/usr/bin/env python3
"""Extract fixtures from HAR files and create $fixture references.

Takes a HAR file and:
1. Extracts HTML/JSON responses to modems/{mfr}/{model}/fixtures/
2. Replaces HAR content with $fixture references
3. Creates metadata.yaml with capture info
4. Outputs the modified HAR to modems/{mfr}/{model}/har/modem.har

Usage:
    python scripts/extract_fixtures.py RAW_DATA/modem.har --modem mb7621
    python scripts/extract_fixtures.py RAW_DATA/modem.har --modem sb8200 --variant noauth
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

# File extensions to extract as fixtures
EXTRACTABLE_TYPES = {
    "text/html": ".html",
    "text/plain": ".html",  # Some modems serve HTML as text/plain
    "application/json": ".json",
    "application/xml": ".xml",
    "text/xml": ".xml",
}

# Minimum content size to extract (skip tiny responses)
MIN_CONTENT_SIZE = 100


def get_fixture_name(url: str, mime_type: str) -> str | None:
    """Generate fixture filename from URL and MIME type.

    Args:
        url: Request URL
        mime_type: Response MIME type

    Returns:
        Filename for fixture, or None if not extractable
    """
    # Get extension from MIME type
    ext = EXTRACTABLE_TYPES.get(mime_type)
    if not ext:
        return None

    # Parse URL path
    parsed = urlparse(url)
    path = parsed.path.strip("/")

    if not path or path == "/":
        return f"index{ext}"

    # Use the filename from the path
    filename = path.split("/")[-1]

    # If no extension, add one
    if "." not in filename:
        filename = f"{filename}{ext}"

    # Clean up the filename
    filename = re.sub(r"[^\w.\-]", "_", filename)

    return filename


def load_har(har_path: Path) -> dict[str, Any]:
    """Load HAR file (supports .gz)."""
    if har_path.suffix == ".gz":
        with gzip.open(har_path, "rt", encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)
            return data
    with open(har_path, encoding="utf-8") as f:
        data = json.load(f)
        return data


def save_har(har_data: dict, har_path: Path) -> None:
    """Save HAR file."""
    with open(har_path, "w", encoding="utf-8") as f:
        json.dump(har_data, f, indent=2)


def extract_fixtures(  # noqa: C901
    har_path: Path,
    modem_key: str,
    variant: str | None = None,
    dry_run: bool = False,
) -> tuple[Path, dict[str, str]]:
    """Extract fixtures from HAR file.

    Args:
        har_path: Path to source HAR file
        modem_key: Modem identifier (e.g., "mb7621", "sb8200")
        variant: Optional variant name (e.g., "noauth", "https")
        dry_run: If True, don't write files

    Returns:
        Tuple of (output_har_path, extracted_files_map)
    """
    # Find modem directory
    repo_root = Path(__file__).parent.parent
    modem_dir = None

    for mfr_dir in (repo_root / "modems").iterdir():
        if not mfr_dir.is_dir():
            continue
        model_dir = mfr_dir / modem_key
        if model_dir.exists():
            modem_dir = model_dir
            break

    if not modem_dir:
        raise ValueError(f"Modem directory not found for '{modem_key}'")

    fixtures_dir = modem_dir / "fixtures"
    har_dir = modem_dir / "har"

    # Create directories
    if not dry_run:
        fixtures_dir.mkdir(exist_ok=True)
        har_dir.mkdir(exist_ok=True)

    # Load HAR
    har_data = load_har(har_path)
    entries = har_data.get("log", {}).get("entries", [])

    extracted: dict[str, str] = {}  # fixture_name -> url
    seen_names: set[str] = set()

    for entry in entries:
        request = entry.get("request", {})
        response = entry.get("response", {})
        content = response.get("content", {})

        url = request.get("url", "")
        mime_type = content.get("mimeType", "").split(";")[0].strip()
        text = content.get("text", "")

        # Skip if already a $fixture reference
        if "$fixture" in content:
            continue

        # Skip small responses
        if len(text) < MIN_CONTENT_SIZE:
            continue

        # Get fixture filename
        fixture_name = get_fixture_name(url, mime_type)
        if not fixture_name:
            continue

        # Handle duplicates
        base_name = fixture_name
        counter = 1
        while fixture_name in seen_names:
            name, ext = base_name.rsplit(".", 1)
            fixture_name = f"{name}_{counter}.{ext}"
            counter += 1
        seen_names.add(fixture_name)

        # Decode base64 if needed
        if content.get("encoding") == "base64":
            import base64

            try:
                text = base64.b64decode(text).decode("utf-8", errors="replace")
            except Exception as e:
                print(f"Warning: Failed to decode base64 for {url}: {e}")
                continue

        # Write fixture file
        fixture_path = fixtures_dir / fixture_name
        if not dry_run:
            fixture_path.write_text(text, encoding="utf-8")
            print(f"  Extracted: {fixture_name} ({len(text)} bytes)")

        extracted[fixture_name] = url

        # Replace content with $fixture reference
        content.clear()
        content["$fixture"] = fixture_name
        content["mimeType"] = mime_type

    # Add metadata to HAR
    har_data.setdefault("log", {})["_solentlabs"] = {
        "tool": "cable_modem_monitor/extract_fixtures.py",
        "extracted_date": datetime.now().isoformat(),
        "fixture_refs": True,
        "source_har": har_path.name,
    }

    # Determine output HAR filename
    if variant:
        har_filename = f"modem-{variant}.har"
    else:
        har_filename = "modem.har"

    output_har = har_dir / har_filename

    if not dry_run:
        save_har(har_data, output_har)
        print(f"  Saved HAR: {output_har}")

    # Create/update metadata.yaml
    metadata_path = fixtures_dir / "metadata.yaml"
    metadata: dict = {}

    if metadata_path.exists():
        with open(metadata_path) as f:
            metadata = yaml.safe_load(f) or {}

    metadata.update(
        {
            "captured_date": datetime.now().strftime("%Y-%m-%d"),
            "source_har": har_path.name,
        }
    )

    if not dry_run:
        with open(metadata_path, "w") as f:
            yaml.dump(metadata, f, default_flow_style=False, sort_keys=False)
        print(f"  Updated: {metadata_path}")

    return output_har, extracted


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract fixtures from HAR files")
    parser.add_argument(
        "har_file",
        type=Path,
        help="HAR file to process",
    )
    parser.add_argument(
        "--modem",
        "-m",
        required=True,
        help="Modem key (e.g., 'mb7621', 'sb8200')",
    )
    parser.add_argument(
        "--variant",
        "-v",
        help="Variant name (e.g., 'noauth', 'https')",
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Show what would be done without writing files",
    )

    args = parser.parse_args()

    if not args.har_file.exists():
        print(f"Error: HAR file not found: {args.har_file}")
        return 1

    print(f"Extracting fixtures from {args.har_file}")
    print(f"  Modem: {args.modem}")
    if args.variant:
        print(f"  Variant: {args.variant}")
    if args.dry_run:
        print("  (dry run - no files will be written)")

    try:
        output_har, extracted = extract_fixtures(
            args.har_file,
            args.modem,
            args.variant,
            args.dry_run,
        )
    except ValueError as e:
        print(f"Error: {e}")
        return 1

    print(f"\nExtracted {len(extracted)} fixtures:")
    for name, url in extracted.items():
        print(f"  {name} <- {url}")

    if not args.dry_run:
        print(f"\nOutput HAR: {output_har}")
        print("\nNext steps:")
        print("  1. Review extracted fixtures in modems/*/fixtures/")
        print(f"  2. Validate HAR: python scripts/validate_har_secrets.py {output_har}")
        print("  3. Update metadata.yaml with firmware_version, contributor, etc.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
