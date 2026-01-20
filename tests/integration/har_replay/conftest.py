"""Pytest fixtures for HAR replay testing.

These fixtures enable testing auth strategies against real modem captures.
HAR files are auto-discovered from modems/<mfr>/<model>/har/ directories.
Tests skip gracefully when HAR files are missing.

Adding a new modem with HAR tests:
1. Place HAR file in modems/<mfr>/<model>/har/modem.har
2. Create modems/<mfr>/<model>/tests/test_har.py with modem-specific assertions
3. No changes needed to this file - auto-discovery handles it
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
import requests_mock as rm

from .har_parser import HarAuthFlow, HarExchange, HarParser

# Directory paths - default location, can be overridden
REPO_ROOT = Path(__file__).parent.parent.parent.parent
DEFAULT_MODEMS_DIR = REPO_ROOT / "modems"


def discover_modems(modems_root: Path | None = None) -> dict[str, tuple[str, str]]:
    """Auto-discover modems from modems/<mfr>/<model>/ directory structure.

    Args:
        modems_root: Root directory containing modem folders. Defaults to
                     the repository's modems/ directory. Pass a custom path
                     for testing or when modems are in a separate location.

    Returns:
        Dict mapping modem_key (model lowercase) to (manufacturer, model) tuple
    """
    modems_dir = modems_root or DEFAULT_MODEMS_DIR
    modems: dict[str, tuple[str, str]] = {}

    if not modems_dir.exists():
        return modems

    for mfr_dir in modems_dir.iterdir():
        if not mfr_dir.is_dir() or mfr_dir.name.startswith(("_", ".")):
            continue

        for model_dir in mfr_dir.iterdir():
            if not model_dir.is_dir() or model_dir.name.startswith(("_", ".")):
                continue

            # Skip if no modem.yaml (not a real modem directory)
            if not (model_dir / "modem.yaml").exists():
                continue

            modem_key = model_dir.name.lower()
            modems[modem_key] = (mfr_dir.name, model_dir.name)

    return modems


def get_har_path(modem_key: str, modems_root: Path | None = None) -> Path | None:
    """Get absolute path to HAR file for a modem.

    Args:
        modem_key: Modem key (model name lowercase, e.g., "mb7621")
        modems_root: Root directory containing modem folders. Defaults to
                     the repository's modems/ directory.

    Returns:
        Path to HAR file if it exists, None otherwise
    """
    modems_dir = modems_root or DEFAULT_MODEMS_DIR
    modems = discover_modems(modems_root)

    if modem_key not in modems:
        return None

    manufacturer, model = modems[modem_key]
    har_dir = modems_dir / manufacturer / model / "har"

    if not har_dir.exists():
        return None

    # Check for modem.har first
    modem_har = har_dir / "modem.har"
    if modem_har.exists():
        return modem_har

    # Check for gzipped version
    modem_har_gz = har_dir / "modem.har.gz"
    if modem_har_gz.exists():
        return modem_har_gz

    # Check for any .har file in the har directory
    har_files = list(har_dir.glob("*.har")) + list(har_dir.glob("*.har.gz"))
    if har_files:
        return har_files[0]

    return None


def get_available_har_modems(modems_root: Path | None = None) -> list[str]:
    """Get list of modem keys that have HAR files available.

    Args:
        modems_root: Root directory containing modem folders. Defaults to
                     the repository's modems/ directory.

    Returns:
        List of modem keys (lowercase model names) with available HARs
    """
    return sorted(
        modem_key for modem_key in discover_modems(modems_root) if get_har_path(modem_key, modems_root) is not None
    )


def har_available(modem_key: str, modems_root: Path | None = None) -> bool:
    """Check if HAR file exists for a modem.

    Args:
        modem_key: Modem key (model name lowercase)
        modems_root: Root directory containing modem folders.
    """
    return get_har_path(modem_key, modems_root) is not None


@pytest.fixture
def har_flow_factory() -> Any:
    """Factory fixture to load and parse HAR files.

    Returns:
        Function that takes modem_key and returns HarAuthFlow

    Example:
        def test_mb7621(har_flow_factory):
            flow = har_flow_factory("mb7621")
            assert flow.pattern == AuthPattern.FORM_BASE64
    """

    def _factory(modem_key: str) -> HarAuthFlow:
        path = get_har_path(modem_key)
        if path is None:
            pytest.skip(f"HAR file not available for {modem_key}")

        parser = HarParser(path)
        return parser.extract_auth_flow()

    return _factory


@pytest.fixture
def har_parser_factory() -> Any:
    """Factory fixture to get raw HarParser instances.

    Returns:
        Function that takes modem_key and returns HarParser

    Example:
        def test_exchanges(har_parser_factory):
            parser = har_parser_factory("mb7621")
            exchanges = parser.get_exchanges()
    """

    def _factory(modem_key: str) -> HarParser:
        path = get_har_path(modem_key)
        if path is None:
            pytest.skip(f"HAR file not available for {modem_key}")

        return HarParser(path)

    return _factory


@contextmanager
def mock_har_exchanges(
    exchanges: list[HarExchange],
) -> Generator[rm.Mocker, None, None]:
    """Context manager to register HAR exchanges as mock HTTP responses.

    Uses requests-mock to mock HTTP calls based on HAR data.

    Args:
        exchanges: List of HarExchange objects to register as mocks

    Yields:
        The requests_mock.Mocker instance

    Example:
        with mock_har_exchanges(parser.get_auth_exchanges()) as m:
            # Make HTTP calls - they'll use HAR responses
            session.get("http://192.168.100.1/login")
    """
    with rm.Mocker() as mocker:
        for exchange in exchanges:
            # Determine response body
            body = exchange.response.content
            if exchange.response.encoding == "base64":
                import base64

                body = base64.b64decode(body).decode("utf-8", errors="replace")

            # Build headers dict
            headers = dict(exchange.response.headers)
            if exchange.response.mime_type:
                headers["Content-Type"] = exchange.response.mime_type

            # Register the mock
            mocker.register_uri(
                exchange.method,
                exchange.url,
                text=body,
                status_code=exchange.status,
                headers=headers,
            )

        yield mocker


@pytest.fixture
def har_replay() -> Any:
    """Fixture providing har_replay context manager.

    Example:
        def test_auth(har_replay, har_parser_factory):
            parser = har_parser_factory("mb7621")
            with har_replay(parser.get_auth_exchanges()):
                # Run auth code against mocked responses
                handler.login()
    """
    return mock_har_exchanges


@pytest.fixture
def mock_har_for_modem(har_parser_factory: Any, har_replay: Any) -> Any:
    """Combined fixture to load HAR and set up mocks.

    Example:
        def test_mb7621_auth(mock_har_for_modem):
            with mock_har_for_modem("mb7621") as (flow, mocker):
                # HTTP calls are mocked, flow contains auth info
                assert flow.pattern == AuthPattern.FORM_BASE64
    """

    @contextmanager
    def _mock(modem_key: str) -> Generator[tuple[HarAuthFlow, rm.Mocker], None, None]:
        parser = har_parser_factory(modem_key)
        flow = parser.extract_auth_flow()

        with har_replay(parser.get_exchanges()) as mocker:
            yield flow, mocker

    return _mock


# Markers for selective test running
def pytest_configure(config: Any) -> None:
    """Register custom markers."""
    config.addinivalue_line("markers", "har_replay: marks tests using HAR replay")
    config.addinivalue_line("markers", "gate1: FORM_BASE64 auth pattern tests")
    config.addinivalue_line("markers", "gate2: URL_TOKEN_SESSION auth pattern tests")
    config.addinivalue_line("markers", "gate3: HNAP_SESSION auth pattern tests")
    config.addinivalue_line("markers", "gate4: FORM_PLAIN auth pattern tests")


# Skip decorator for HAR availability
def requires_har(modem_key: str) -> Any:
    """Decorator to skip test if HAR file not available.

    Example:
        @requires_har("mb7621")
        def test_mb7621_auth():
            ...
    """
    return pytest.mark.skipif(
        not har_available(modem_key),
        reason=f"HAR file for {modem_key} not available",
    )
