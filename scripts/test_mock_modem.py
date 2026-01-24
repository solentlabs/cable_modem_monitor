#!/usr/bin/env python3
"""Test script to exercise mock modem server with the full scraper flow.

This script tests the complete data fetch cycle against the mock server:
1. Authentication (form, basic, etc.)
2. Page fetching
3. Data parsing

Usage:
    # Start mock server first:
    python scripts/mock_modem.py technicolor/cga2121 --port 9080

    # Then run this test script:
    python scripts/test_mock_modem.py technicolor/cga2121 --port 9080

    # Or test with different credentials:
    python scripts/test_mock_modem.py technicolor/cga2121 --port 9080 -u admin -p wrongpw
"""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from custom_components.cable_modem_monitor.core.data_orchestrator import DataOrchestrator  # noqa: E402
from custom_components.cable_modem_monitor.core.parser_registry import get_parser_by_name  # noqa: E402
from custom_components.cable_modem_monitor.core.setup import setup_modem  # noqa: E402
from custom_components.cable_modem_monitor.modem_config import load_modem_config  # noqa: E402
from custom_components.cable_modem_monitor.modem_config.adapter import ModemConfigAuthAdapter  # noqa: E402

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
_LOGGER = logging.getLogger(__name__)


def test_known_modem_setup(host: str, modem_path: str, username: str, password: str) -> bool:
    """Test the known modem setup against mock server.

    This tests the path users take when they select their modem model
    and we use modem.yaml as the source of truth for auth configuration.

    Returns:
        True if successful, False otherwise.
    """
    print(f"\n{'='*60}")
    print("TEST: Known Modem Setup (modem.yaml as source of truth)")
    print(f"{'='*60}")

    # Load modem config
    modem_dir = PROJECT_ROOT / "modems" / modem_path
    config = load_modem_config(modem_dir)
    adapter = ModemConfigAuthAdapter(config)

    # Get parser class
    parser_name = f"{config.manufacturer} {config.model}"
    parser_class = get_parser_by_name(parser_name)
    if not parser_class:
        print(f"ERROR: Parser not found for {parser_name}")
        return False

    parser = parser_class()  # Instance for name display
    print(f"Parser: {parser.name}")

    # Get static auth config (same format as load_static_auth_config)
    static_auth_config = adapter.get_static_auth_config()
    print(f"Auth strategy: {static_auth_config.get('auth_strategy')}")

    # Run known modem setup (pass class, not instance)
    print(f"\nRunning known modem setup against {host}...")
    result = setup_modem(
        host=host,
        parser_class=parser_class,
        static_auth_config=static_auth_config,
        username=username,
        password=password,
    )

    if result.success:
        print("\nSUCCESS!")
        print(f"  Working URL: {result.working_url}")
        print(f"  Auth strategy: {result.auth_strategy}")
        print(f"  Parser: {result.parser_name}")
        if result.modem_data:
            ds = result.modem_data.get("downstream_channels", [])
            us = result.modem_data.get("upstream_channels", [])
            print(f"  Downstream channels: {len(ds)}")
            print(f"  Upstream channels: {len(us)}")
            if ds:
                print(f"  First DS channel: {ds[0]}")
        return True
    else:
        print(f"\nFAILED at step: {result.failed_step}")
        print(f"  Error: {result.error}")
        return False


def test_scraper_polling(host: str, modem_path: str, username: str, password: str) -> bool:
    """Test the scraper polling flow (simulates what HA does during updates).

    Returns:
        True if successful, False otherwise.
    """
    print(f"\n{'='*60}")
    print("TEST: Scraper Polling (simulates HA coordinator updates)")
    print(f"{'='*60}")

    # Load modem config
    modem_dir = PROJECT_ROOT / "modems" / modem_path
    config = load_modem_config(modem_dir)
    adapter = ModemConfigAuthAdapter(config)

    # Get parser
    parser_name = f"{config.manufacturer} {config.model}"
    parser_class = get_parser_by_name(parser_name)
    if not parser_class:
        print(f"ERROR: Parser not found for {parser_name}")
        return False

    parser = parser_class()

    # Get auth config (simulating what's stored in config entry)
    static_config = adapter.get_static_auth_config()
    auth_strategy = static_config.get("auth_strategy")
    auth_form_config = static_config.get("auth_form_config")
    auth_hnap_config = static_config.get("auth_hnap_config")
    auth_url_token_config = static_config.get("auth_url_token_config")

    print("Creating scraper with stored auth config...")
    print(f"  Auth strategy: {auth_strategy}")
    print(f"  Form config: {auth_form_config is not None}")
    print(f"  HNAP config: {auth_hnap_config is not None}")

    # Create scraper (simulating what __init__.py does)
    try:
        scraper = DataOrchestrator(
            host=host,
            username=username,
            password=password,
            parser=parser,
            cached_url=f"http://{host}",
            verify_ssl=False,
            legacy_ssl=False,
            auth_strategy=auth_strategy,
            auth_form_config=auth_form_config,
            auth_hnap_config=auth_hnap_config,
            auth_url_token_config=auth_url_token_config,
        )
    except Exception as e:
        print(f"\nFAILED to create scraper: {e}")
        return False

    # Fetch data (simulating coordinator update)
    print("\nFetching modem data (poll #1)...")
    try:
        data = scraper.get_modem_data()
    except Exception as e:
        print(f"\nFAILED with exception: {e}")
        return False

    if data:
        # Scraper uses cable_modem_* keys, discovery uses downstream/upstream
        ds = data.get("cable_modem_downstream", [])
        us = data.get("cable_modem_upstream", [])
        print("\nSUCCESS!")
        print(f"  Downstream channels: {len(ds)}")
        print(f"  Upstream channels: {len(us)}")
        if ds:
            print(f"  First DS channel: {ds[0]}")

        # Test second poll (session should still be valid)
        print("\nFetching modem data (poll #2 - session reuse)...")
        try:
            data2 = scraper.get_modem_data()
            if data2:
                ds2 = data2.get("cable_modem_downstream", [])
                print(f"  Poll #2 downstream channels: {len(ds2)}")
                return True
            else:
                print("  Poll #2 FAILED - no data")
                return False
        except Exception as e:
            print(f"  Poll #2 FAILED with exception: {e}")
            return False
    else:
        print("\nFAILED to get modem data")
        return False


def test_auth_failure(host: str, modem_path: str) -> bool:
    """Test that auth failure is handled correctly.

    Returns:
        True if failure is handled correctly, False otherwise.
    """
    print(f"\n{'='*60}")
    print("TEST: Auth Failure Handling (wrong credentials)")
    print(f"{'='*60}")

    # Load modem config
    modem_dir = PROJECT_ROOT / "modems" / modem_path
    config = load_modem_config(modem_dir)
    adapter = ModemConfigAuthAdapter(config)

    # Get parser
    parser_name = f"{config.manufacturer} {config.model}"
    parser_class = get_parser_by_name(parser_name)
    if not parser_class:
        print(f"ERROR: Parser not found for {parser_name}")
        return False

    # Get static auth config (same format as load_static_auth_config)
    static_auth_config = adapter.get_static_auth_config()

    print("Running setup with WRONG credentials...")
    result = setup_modem(
        host=host,
        parser_class=parser_class,
        static_auth_config=static_auth_config,
        username="wrong_user",
        password="wrong_pass",
    )

    if not result.success:
        print("\nCORRECT: Auth failed as expected")
        print(f"  Failed step: {result.failed_step}")
        print(f"  Error: {result.error}")
        return True
    else:
        print("\nWRONG: Auth should have failed but succeeded!")
        return False


def main():
    parser = argparse.ArgumentParser(description="Test mock modem server with scraper")
    parser.add_argument("modem", help="Modem path (e.g., technicolor/cga2121)")
    parser.add_argument("--host", default="localhost", help="Mock server host")
    parser.add_argument("--port", type=int, default=9080, help="Mock server port")
    parser.add_argument("-u", "--username", default="admin", help="Username")
    parser.add_argument("-p", "--password", default="pw", help="Password")
    parser.add_argument("--skip-auth-failure", action="store_true", help="Skip auth failure test")

    args = parser.parse_args()

    host = f"{args.host}:{args.port}"
    print(f"Testing mock modem at {host}")
    print(f"Modem: {args.modem}")
    print(f"Credentials: {args.username} / {'*' * len(args.password)}")

    results = []

    # Test 1: Known modem setup (modem.yaml as source of truth)
    results.append(("Known Modem Setup", test_known_modem_setup(host, args.modem, args.username, args.password)))

    # Test 2: Scraper polling
    results.append(("Scraper Polling", test_scraper_polling(host, args.modem, args.username, args.password)))

    # Test 3: Auth failure handling
    if not args.skip_auth_failure:
        results.append(("Auth Failure Handling", test_auth_failure(host, args.modem)))

    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("All tests PASSED!")
        return 0
    else:
        print("Some tests FAILED!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
