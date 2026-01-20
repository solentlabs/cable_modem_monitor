"""Test fixture utilities.

Provides consistent access to modem fixtures stored in modems/{manufacturer}/{model}/fixtures/.
All parser tests should use these helpers instead of relative path construction.
"""

from __future__ import annotations

from pathlib import Path

# Root of the modems directory
MODEMS_ROOT = Path(__file__).parent.parent / "modems"


def get_fixture_path(manufacturer: str, model: str, filename: str) -> Path:
    """Get path to a fixture file.

    Args:
        manufacturer: Modem manufacturer (e.g., "arris", "motorola")
        model: Modem model (e.g., "sb8200", "mb7621")
        filename: Fixture filename (e.g., "status.html", "extended/login.html")

    Returns:
        Path to the fixture file.

    Raises:
        FileNotFoundError: If fixture doesn't exist.

    Example:
        path = get_fixture_path("arris", "sb8200", "cmconnectionstatus.html")
    """
    path = MODEMS_ROOT / manufacturer / model / "fixtures" / filename
    if not path.exists():
        raise FileNotFoundError(f"Fixture not found: {path}")
    return path


def get_fixture_dir(manufacturer: str, model: str) -> Path:
    """Get path to a modem's fixture directory.

    Args:
        manufacturer: Modem manufacturer
        model: Modem model

    Returns:
        Path to the fixtures directory.
    """
    return MODEMS_ROOT / manufacturer / model / "fixtures"


def load_fixture(manufacturer: str, model: str, filename: str, encoding: str = "utf-8") -> str:
    """Load fixture file contents as string.

    Args:
        manufacturer: Modem manufacturer
        model: Modem model
        filename: Fixture filename
        encoding: File encoding (default utf-8)

    Returns:
        File contents as string.
    """
    path = get_fixture_path(manufacturer, model, filename)
    return path.read_text(encoding=encoding)


def load_fixture_bytes(manufacturer: str, model: str, filename: str) -> bytes:
    """Load fixture file contents as bytes.

    Args:
        manufacturer: Modem manufacturer
        model: Modem model
        filename: Fixture filename

    Returns:
        File contents as bytes.
    """
    path = get_fixture_path(manufacturer, model, filename)
    return path.read_bytes()


def fixture_exists(manufacturer: str, model: str, filename: str) -> bool:
    """Check if a fixture file exists.

    Args:
        manufacturer: Modem manufacturer
        model: Modem model
        filename: Fixture filename

    Returns:
        True if fixture exists.
    """
    path = MODEMS_ROOT / manufacturer / model / "fixtures" / filename
    return path.exists()
