"""Pipeline runner — execute a modem test case end-to-end.

Wires together: HAR mock server -> auth -> resource loader ->
coordinator -> golden file comparison.

Result format distinguishes **errors** (pipeline failures that prevent
the test from running) from **failures** (golden file diffs where the
pipeline ran but output differs from expected).

See ONBOARDING_SPEC.md Test Execution Flow section.
"""

from __future__ import annotations

import importlib.util
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from ..auth.base import AuthResult
from ..auth.factory import create_auth_manager
from ..config_loader import load_modem_config, load_parser_config
from ..loaders.fetch_list import collect_fetch_targets
from ..loaders.hnap import HNAPLoader
from ..loaders.http import HTTPResourceLoader
from ..parsers.coordinator import ModemParserCoordinator, filter_restart_window
from .discovery import ModemTestCase
from .golden_file import ComparisonResult, compare_golden_file
from .har_mock_server import HARMockServer

_logger = logging.getLogger(__name__)

# Fixed class name for parser.py post-processors.
_POST_PROCESSOR_CLASS = "PostProcessor"


@dataclass
class TestResult:
    """Result of running a single modem test case.

    Attributes:
        test_name: Human-readable test ID from ``ModemTestCase.name``.
        passed: ``True`` only if pipeline succeeded AND golden file
            matches.
        error: Pipeline error message if the test could not run
            (auth failure, resource 404, import error). Empty string
            when the pipeline completed.
        comparison: Golden file comparison result. ``None`` if the
            pipeline errored before reaching comparison.
    """

    test_name: str
    passed: bool
    error: str = ""
    comparison: ComparisonResult | None = None


def run_modem_test(test_case: ModemTestCase) -> TestResult:
    """Run the full pipeline for a single test case.

    Builds a mock server from the HAR, authenticates, fetches
    resources, parses, and compares against the golden file.

    Args:
        test_case: Discovered test case with all file paths resolved.

    Returns:
        ``TestResult`` with pass/fail, error detail, or golden file diff.
        Never raises — all pipeline errors are captured in the result.
    """
    name = test_case.name

    # Check golden file existence
    if not test_case.golden_path.is_file():
        return TestResult(
            test_name=name,
            passed=False,
            error=f"Golden file not found: {test_case.golden_path}",
        )

    # Load HAR
    try:
        har_data = json.loads(
            test_case.har_path.read_text(encoding="utf-8"),
        )
        entries = har_data["log"]["entries"]
    except Exception as e:
        return TestResult(
            test_name=name,
            passed=False,
            error=f"Failed to load HAR: {e}",
        )

    # Load golden file
    try:
        expected = json.loads(
            test_case.golden_path.read_text(encoding="utf-8"),
        )
    except Exception as e:
        return TestResult(
            test_name=name,
            passed=False,
            error=f"Failed to load golden file: {e}",
        )

    # Load modem config
    try:
        modem_config = load_modem_config(test_case.modem_config_path)
    except Exception as e:
        return TestResult(
            test_name=name,
            passed=False,
            error=f"Failed to load modem config: {e}",
        )

    # Load parser config (optional — parser.py-only is valid)
    parser_config = None
    if test_case.parser_config_path is not None:
        try:
            parser_config = load_parser_config(test_case.parser_config_path)
        except Exception as e:
            return TestResult(
                test_name=name,
                passed=False,
                error=f"Failed to load parser config: {e}",
            )

    # Load post-processor (optional)
    post_processor = None
    if test_case.parser_py_path is not None:
        try:
            post_processor = load_post_processor(test_case.parser_py_path)
        except Exception as e:
            return TestResult(
                test_name=name,
                passed=False,
                error=f"Failed to load parser.py: {e}",
            )

    # Run pipeline against mock server
    try:
        actual = _run_pipeline(
            entries=entries,
            modem_config=modem_config,
            parser_config=parser_config,
            post_processor=post_processor,
        )
    except Exception as e:
        return TestResult(
            test_name=name,
            passed=False,
            error=f"Pipeline error: {e}",
        )

    return _compare_and_record(test_case, actual, expected)


def _compare_and_record(
    test_case: ModemTestCase,
    actual: dict[str, Any],
    expected: dict[str, Any],
) -> TestResult:
    """Write actual output, compare against golden file, clean up on pass."""
    actual_path = test_case.har_path.with_suffix(".actual.json")
    actual_path.write_text(
        json.dumps(actual, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    comparison = compare_golden_file(actual, expected)

    # Only keep actual file when there's drift
    if comparison.passed and actual_path.exists():
        actual_path.unlink()

    return TestResult(
        test_name=test_case.name,
        passed=comparison.passed,
        comparison=comparison,
    )


def _run_pipeline(
    *,
    entries: list[dict[str, Any]],
    modem_config: Any,
    parser_config: Any,
    post_processor: Any,
) -> dict[str, Any]:
    """Run the full extraction pipeline against a mock server.

    Args:
        entries: HAR log entries for the mock server.
        modem_config: Validated ``ModemConfig`` instance.
        parser_config: Validated ``ParserConfig`` instance (or ``None``).
        post_processor: ``PostProcessor`` instance (or ``None``).

    Returns:
        Extracted ``ModemData`` dict.

    Raises:
        Exception: On any pipeline failure (auth, fetch, parse).
    """
    with HARMockServer(entries, modem_config=modem_config) as server:
        base_url = server.base_url
        session = requests.Session()

        # Configure session
        auth_manager = create_auth_manager(modem_config)
        session_headers: dict[str, str] = {}
        if modem_config.session and modem_config.session.headers:
            session_headers = dict(modem_config.session.headers)
        auth_manager.configure_session(
            session,
            session_headers,
        )

        # Authenticate
        auth_result: AuthResult = auth_manager.authenticate(
            session,
            base_url,
            username="admin",
            password="pw",
            timeout=modem_config.timeout,
        )
        if not auth_result.success:
            raise RuntimeError(f"Auth failed: {auth_result.error}")

        # Fetch resources
        if parser_config is None:
            raise RuntimeError(
                "Modem requires custom parser.py — " "parser.yaml alone insufficient for resource loading",
            )

        if modem_config.transport == "hnap":
            # HNAP: batched SOAP request, no per-page fetching
            hmac_algorithm = "md5"
            if hasattr(modem_config.auth, "hmac_algorithm"):
                hmac_algorithm = modem_config.auth.hmac_algorithm
            hnap_loader = HNAPLoader(
                session=session,
                base_url=base_url,
                private_key=auth_result.auth_context.private_key,
                hmac_algorithm=hmac_algorithm,
                timeout=modem_config.timeout,
            )
            resources = hnap_loader.fetch(parser_config)
        else:
            # HTTP: per-page fetching
            targets = collect_fetch_targets(parser_config)
            url_token = ""
            token_prefix = ""
            if modem_config.session:
                token_prefix = modem_config.session.token_prefix
                # Extract URL token from session cookies only when
                # both cookie_name and token_prefix are configured
                # (url_token strategy).  Other strategies may set
                # cookie_name for session tracking without URL tokens.
                if modem_config.session.cookie_name and token_prefix:
                    url_token = (
                        session.cookies.get(
                            modem_config.session.cookie_name,
                            "",
                        )
                        or ""
                    )

            loader = HTTPResourceLoader(
                session=session,
                base_url=base_url,
                timeout=modem_config.timeout,
                url_token=url_token,
                token_prefix=token_prefix,
            )
            resources = loader.fetch(targets, auth_result)

        # Parse
        coordinator = ModemParserCoordinator(parser_config, post_processor)
        data = coordinator.parse(resources)

        # Post-parse: filter zero-power channels during restart window
        if modem_config.behaviors and modem_config.behaviors.zero_power_reported and modem_config.behaviors.restart:
            data = filter_restart_window(
                data,
                modem_config.behaviors.restart.window_seconds,
            )

        return data


def load_post_processor(parser_py_path: Path) -> Any:
    """Dynamically import a PostProcessor from a parser.py file.

    Loads the module from *parser_py_path* and returns an instance
    of the ``PostProcessor`` class. The class name is a fixed
    convention — all parser.py files use ``PostProcessor``.

    Args:
        parser_py_path: Absolute path to the ``parser.py`` file.

    Returns:
        An instance of ``PostProcessor``, or ``None`` if the class
        is not defined in the module.
    """
    spec = importlib.util.spec_from_file_location(
        f"parser_py_{parser_py_path.parent.name}",
        parser_py_path,
    )
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]

    cls = getattr(module, _POST_PROCESSOR_CLASS, None)
    if cls is None:
        return None

    return cls()
