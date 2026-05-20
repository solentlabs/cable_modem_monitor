"""Failed-server auth-detail log coverage — every modem in the catalog.

Auto-parametrized by ``conftest.py``: every ``modem*.yaml`` in the
catalog runs through the collector against a server that 401s every
request. We assert two invariants per modem:

1. **WARNING fires.** At least one ``WARNING`` record on the
   ``solentlabs.cable_modem_monitor_core.orchestration.collector``
   logger. Catches a strategy that bypasses the auth-failure log
   path entirely.
2. **No credential leak.** A distinctive fixture password is
   checked against the captured WARNING text in raw, base64
   ``user:password``, and URL-encoded forms. Catches scrubber
   regressions across all strategies.

Adding a new modem = the test runs against it automatically. The
failure-detail log is the single diagnostic surface for stuck-setup
users — this test is the regression guard for that surface.
"""

from __future__ import annotations

import base64
import logging
import threading
import urllib.parse
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from solentlabs.cable_modem_monitor_core.config_loader import (
    load_modem_config,
    load_parser_config,
)
from solentlabs.cable_modem_monitor_core.orchestration import create_collector
from solentlabs.cable_modem_monitor_core.post_processor import (
    load_post_processor,
)

_COLLECTOR_LOGGER = "solentlabs.cable_modem_monitor_core.orchestration.collector"

# Distinctive fixture credentials. Any encoding a strategy might put
# on the wire is easy to grep for.
_FIXTURE_USER = "admin"
_FIXTURE_PASSWORD = "ZqL4PaSsW0RdBeEf9X"


class _FailHandler(BaseHTTPRequestHandler):
    """HTTP handler that returns 401 to every request, regardless of path."""

    def do_GET(self) -> None:  # noqa: N802 — stdlib dispatch convention
        self._reject()

    def do_POST(self) -> None:  # noqa: N802
        self._reject()

    def do_HEAD(self) -> None:  # noqa: N802
        self._reject()

    def _reject(self) -> None:
        body = b"unauthorized"
        self.send_response(401)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: ARG002, A002
        """Silence stdlib's per-request stderr noise during tests."""


@contextmanager
def _fail_server() -> Iterator[str]:
    """Spin up a 401-everything HTTP server on a random port."""
    server = HTTPServer(("127.0.0.1", 0), _FailHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        # ``server_address`` is typed as IPv4 (host, port) | IPv6
        # (host, port, flowinfo, scopeid). We bind to 127.0.0.1 so
        # it's always the 2-tuple — slice to make that explicit to
        # the type checker.
        host, port = server.server_address[:2]
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2.0)


def _forbidden_password_forms() -> list[str]:
    """Encodings of the fixture credential that must NOT appear in any WARNING."""
    creds = f"{_FIXTURE_USER}:{_FIXTURE_PASSWORD}".encode()
    return [
        _FIXTURE_PASSWORD,
        base64.b64encode(creds).decode(),
        urllib.parse.quote(_FIXTURE_PASSWORD),
    ]


def test_failed_server_capture(
    modem_yaml_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Run the collector against a 401-everything server and check the log.

    Asserts the failure-detail invariants for every modem in the
    catalog.
    """
    modem_config = load_modem_config(modem_yaml_path)

    # Modems with no auth block at all (placeholder/unsupported entries
    # awaiting HAR data) skip — there's nothing to validate.
    if modem_config.auth is None:
        pytest.skip("no auth block configured")

    modem_dir = modem_yaml_path.parent
    parser_yaml = modem_dir / "parser.yaml"
    parser_py = modem_dir / "parser.py"
    parser_config = load_parser_config(parser_yaml) if parser_yaml.exists() else None
    post_processor = load_post_processor(parser_py) if parser_py.exists() else None

    with caplog.at_level(logging.WARNING, logger=_COLLECTOR_LOGGER), _fail_server() as base_url:
        collector = create_collector(
            modem_config=modem_config,
            parser_config=parser_config,
            post_processor=post_processor,
            base_url=base_url,
            username=_FIXTURE_USER,
            password=_FIXTURE_PASSWORD,
        )
        result = collector.execute()

    model = modem_config.model

    # A 401-everything server cannot succeed.
    assert result.success is False, f"{model}: validation succeeded against a 401-everything server"

    # The collector emitted at least one WARNING with the failure detail.
    warning_records = [r for r in caplog.records if r.name == _COLLECTOR_LOGGER and r.levelno == logging.WARNING]
    assert warning_records, (
        f"{model} ({modem_config.auth.strategy}): no WARNING from the collector — "
        f"the strategy may be bypassing the auth-failure log path"
    )

    # No credential string of any encoding appears in any WARNING.
    captured_text = "\n".join(r.getMessage() for r in warning_records)
    for forbidden in _forbidden_password_forms():
        assert forbidden not in captured_text, (
            f"{model} ({modem_config.auth.strategy}): credential leaked in WARNING — "
            f"found {forbidden!r} in:\n{captured_text}"
        )
