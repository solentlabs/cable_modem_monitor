#!/usr/bin/env python3
"""
Fresh Start Script - Reset VS Code state to test new developer experience

This is ONLY needed to test what a brand new developer sees.
Normal development doesn't require this script.

Usage:
    python scripts/dev/fresh_start.py
    # OR
    python3 scripts/dev/fresh_start.py
"""

import os
import platform
import shutil
import subprocess
from pathlib import Path


def print_header(text: str) -> None:
    """Print a formatted header."""
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80 + "\n")


def print_step(text: str) -> None:
    """Print a step message."""
    print(f"▶ {text}")


def print_success(text: str) -> None:
    """Print a success message."""
    print(f"✅ {text}")


def print_warning(text: str) -> None:
    """Print a warning message."""
    print(f"⚠️  {text}")


def print_info(text: str) -> None:
    """Print an info message."""
    print(f"→ {text}")


def is_vscode_running() -> bool:
    """Check if VS Code is running."""
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq Code.exe"],
                capture_output=True,
                text=True,
                check=False,
            )
            return "Code.exe" in result.stdout
        else:
            result = subprocess.run(
                ["pgrep", "-f", "code"],
                capture_output=True,
                text=True,
                check=False,
            )
            return bool(result.stdout.strip())
    except Exception:
        return False


def get_vscode_cache_path() -> Path:
    """Get VS Code workspace cache path based on OS."""
    system = platform.system()

    if system == "Windows":
        cache_path = Path(os.environ.get("APPDATA", "")) / "Code" / "User" / "workspaceStorage"
    elif system == "Darwin":  # macOS
        cache_path = Path.home() / "Library" / "Application Support" / "Code" / "User" / "workspaceStorage"
    else:  # Linux
        cache_path = Path.home() / ".config" / "Code" / "User" / "workspaceStorage"

    return cache_path


def clear_workspace_cache() -> int:
    """Clear VS Code workspace cache for this project."""
    cache_path = get_vscode_cache_path()

    if not cache_path.exists():
        print_info("Workspace cache directory not found")
        print_info("This is normal on first install")
        return 0

    found = 0
    for workspace_dir in cache_path.iterdir():
        if not workspace_dir.is_dir():
            continue

        workspace_json = workspace_dir / "workspace.json"
        if not workspace_json.exists():
            continue

        try:
            content = workspace_json.read_text()
            if "cable_modem_monitor" in content:
                print_info(f"Removing: {workspace_dir.name}")
                shutil.rmtree(workspace_dir)
                found += 1
        except Exception as e:
            print_warning(f"Could not process {workspace_dir.name}: {e}")

    return found


def main() -> None:
    """Main entry point."""
    print_header("🔄 Fresh Start - Reset VS Code State")

    print("This script resets VS Code's memory of this project.")
    print("Use this to test the new developer onboarding experience.")
    print()
    print_warning("Note: This is ONLY for testing. Normal development doesn't need this.")
    print()

    # Step 1: Check if VS Code is running
    if is_vscode_running():
        print_warning("VS Code appears to be running")
        print()
        input("Close all VS Code windows and press Enter to continue (or Ctrl+C to cancel)... ")
        print()

    # Step 2: Detect OS
    system_name = platform.system()
    display_name = {"Windows": "Windows", "Darwin": "macOS", "Linux": "Linux"}.get(
        system_name, system_name
    )
    print(f"🖥️  Detected: {display_name}")
    print()

    # Step 3: Clear workspace cache
    print_step("Clearing VS Code workspace cache for this project...")
    found = clear_workspace_cache()

    if found > 0:
        print_success(f"Cleared {found} workspace cache folder(s)")
    else:
        print_info("No cached workspace found (already clean)")

    # Step 4: Optional - Remove .venv
    print()
    print_header("Optional: Test Setup From Scratch")
    print()
    print("Remove .venv to test the complete setup process?")
    print("(This simulates a brand new clone)")
    print()
    response = input("Remove .venv? (y/N): ").strip().lower()

    if response in ("y", "yes"):
        venv_path = Path(".venv")
        if venv_path.exists():
            print_info("Removing .venv...")
            shutil.rmtree(venv_path)
            print_success("Removed .venv")
        else:
            print_info("No .venv found")
    else:
        print_info("Keeping .venv (faster testing)")

    # Step 5: Summary
    print()
    print_header("✅ Fresh start ready!")
    print()
    print("Now open VS Code to see the new developer experience:")
    print()
    print("   code .")
    print()
    print_header("What You Should See:")
    print()
    print("Notifications (in order):")
    print("  1. 'Dev Container configuration available...'")
    print("     → Your choice: Use it OR dismiss")
    print()
    print("  2. 'Install recommended extensions?'")
    print("     → Click 'Install' (6 essential extensions)")
    print()
    print("What You Should NOT See:")
    print("  ❌ GitLens notification (removed - optional)")
    print("  ❌ CodeQL error notifications (removed - optional)")
    print()
    print_header("Next Steps:")
    print()
    print("If you dismissed Dev Container:")
    if system_name == "Windows":
        print("   bash scripts/setup.sh  (in Git Bash)")
        print("   OR")
        print("   python scripts/setup.py  (if available)")
    else:
        print("   ./scripts/setup.sh")
    print()
    print("Then validate everything works:")
    print("   make validate")
    print()
    print("Or use VS Code task:")
    print("   Ctrl+Shift+P → Tasks: Run Task → Quick Validation")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user")
        exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        exit(1)
