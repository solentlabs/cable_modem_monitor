"""
This script updates the version number in manifest.json and hacs.json
to match the VERSION constant specified in const.py.

This ensures that the version number is consistent across the project.
"""
import json
import os
from pathlib import Path

def get_version_from_const() -> str:
    """Reads the VERSION constant from const.py without importing the file."""
    script_dir = os.path.dirname(os.path.realpath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, '..'))
    const_file_path = os.path.join(project_root, 'custom_components', 'cable_modem_monitor', 'const.py')

    with open(const_file_path, 'r') as f:
        for line in f:
            if line.startswith("VERSION"):
                ***REMOVED*** Extracts the version number from a line like: VERSION = "2.4.1"
                return line.split('=')[1].strip().strip('"')
    
    raise ValueError("VERSION constant not found in const.py")

def update_json_file(file_path: str, version: str) -> None:
    """Reads a JSON file, updates the version, and writes it back."""
    if not os.path.exists(file_path):
        print(f"Skipping {file_path}: File not found.")
        return

    with open(file_path, 'r') as f:
        data = json.load(f)

    data['version'] = version

    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)
        f.write('\n')  ***REMOVED*** Add a newline at the end of the file

    print(f"Updated version in {file_path} to {version}")

def main() -> None:
    """Main function to update version numbers."""
    version = get_version_from_const()
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

    print(f"Syncing to version {version} from const.py...")

    ***REMOVED*** Update manifest.json
    manifest_path = os.path.join(project_root, 'custom_components', 'cable_modem_monitor', 'manifest.json')
    update_json_file(manifest_path, version)

    ***REMOVED*** Update hacs.json
    hacs_path = os.path.join(project_root, 'hacs.json')
    update_json_file(hacs_path, version)

    print("\nVersion sync complete.")

if __name__ == "__main__":
    main()