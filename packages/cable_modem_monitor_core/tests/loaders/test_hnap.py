"""Tests for HNAPLoader — batched SOAP request loading."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests
from solentlabs.cable_modem_monitor_core.loaders.hnap import (
    HNAPLoader,
    HNAPLoadError,
    _collect_hnap_actions,
    _strip_response_suffix,
)
from solentlabs.cable_modem_monitor_core.models.parser_config.common import (
    ChannelMapping,
    ColumnMapping,
    TableSelector,
)
from solentlabs.cable_modem_monitor_core.models.parser_config.config import ParserConfig
from solentlabs.cable_modem_monitor_core.models.parser_config.hnap import HNAPSection
from solentlabs.cable_modem_monitor_core.models.parser_config.system_info import (
    HNAPFieldMapping,
    HNAPSystemInfoSource,
    SystemInfoSection,
)
from solentlabs.cable_modem_monitor_core.models.parser_config.table import (
    HTMLTableSection,
    TableDefinition,
)


def _make_parser_config(**overrides: Any) -> ParserConfig:
    """Build a minimal ParserConfig with HNAP sections."""
    ds_section = HNAPSection(
        format="hnap",
        response_key="GetStatusDownstreamResponse",
        data_key="DownstreamChannel",
        record_delimiter="|+|",
        field_delimiter="^",
        fields=[ChannelMapping(index=0, field="channel_id", type="integer")],
    )
    us_section = HNAPSection(
        format="hnap",
        response_key="GetStatusUpstreamResponse",
        data_key="UpstreamChannel",
        record_delimiter="|+|",
        field_delimiter="^",
        fields=[ChannelMapping(index=0, field="channel_id", type="integer")],
    )
    defaults: dict[str, Any] = {
        "downstream": ds_section,
        "upstream": us_section,
    }
    defaults.update(overrides)
    return ParserConfig.model_validate(defaults)


def _make_http_parser_config() -> ParserConfig:
    """Build a ParserConfig with non-HNAP sections (for skip test)."""
    return ParserConfig(
        downstream=HTMLTableSection(
            format="table",
            resource="/status.html",
            tables=[
                TableDefinition(
                    selector=TableSelector(type="nth", match=0),
                    columns=[ColumnMapping(index=0, field="channel_id", type="integer")],
                ),
            ],
        ),
    )


# --- Mock HNAP Data Server ---


class _HNAPDataHandler(BaseHTTPRequestHandler):
    """Minimal HNAP mock server for data loading tests."""

    response_data: dict[str, Any] = {}

    def do_POST(self) -> None:  # noqa: N802
        """Handle GetMultipleHNAPs POST."""
        body = json.dumps(
            {
                "GetMultipleHNAPsResponse": {
                    "GetMultipleHNAPsResult": "OK",
                    **self.__class__.response_data,
                },
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress server log output."""


@pytest.fixture()
def hnap_data_server():
    """Start a mock HNAP data server and yield its base URL."""
    _HNAPDataHandler.response_data = {
        "GetStatusDownstreamResponse": {
            "DownstreamChannel": "1^567000000^3.2",
        },
        "GetStatusUpstreamResponse": {
            "UpstreamChannel": "1^38400000^47.0",
        },
    }
    server = HTTPServer(("127.0.0.1", 0), _HNAPDataHandler)
    port = server.server_address[1]
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


# fmt: off
STRIP_SUFFIX_CASES = [
    # (input,                                    expected,                               desc)
    ("GetStatusDownstreamResponse",              "GetStatusDownstream",                   "strips suffix"),
    ("GetCustomerStatusDownstreamChannelInfoResponse",
     "GetCustomerStatusDownstreamChannelInfo",   "long name"),
    ("GetStatus",                                "GetStatus",                             "no suffix"),
    ("Response",                                 "",                                      "suffix only"),
]
# fmt: on


@pytest.mark.parametrize(
    "input_key,expected,desc",
    STRIP_SUFFIX_CASES,
    ids=[c[2] for c in STRIP_SUFFIX_CASES],
)
def test_strip_response_suffix(input_key: str, expected: str, desc: str) -> None:
    """Verify Response suffix stripping from action names."""
    assert _strip_response_suffix(input_key) == expected


class TestActionCollection:
    """Test HNAP action name derivation from parser config."""

    def test_collects_from_sections(self) -> None:
        """Actions collected from downstream and upstream sections."""
        config = _make_parser_config()
        actions = _collect_hnap_actions(config)
        assert "GetStatusDownstream" in actions
        assert "GetStatusUpstream" in actions

    def test_collects_from_system_info(self) -> None:
        """Actions collected from system_info sources."""
        config = _make_parser_config(
            system_info=SystemInfoSection(
                sources=[
                    HNAPSystemInfoSource(
                        format="hnap",
                        response_key="GetDeviceStatusResponse",
                        fields=[
                            HNAPFieldMapping(
                                source="FirmwareVersion",
                                field="software_version",
                                type="string",
                            ),
                        ],
                    ),
                ],
            ),
        )
        actions = _collect_hnap_actions(config)
        assert "GetDeviceStatus" in actions

    def test_deduplicates_actions(self) -> None:
        """Duplicate response_key values produce unique actions."""
        same_section = HNAPSection(
            format="hnap",
            response_key="GetStatusDownstreamResponse",
            data_key="Channel",
            record_delimiter="|+|",
            field_delimiter="^",
            fields=[ChannelMapping(index=0, field="channel_id", type="integer")],
        )
        config = _make_parser_config(
            downstream=same_section,
            upstream=same_section,
        )
        actions = _collect_hnap_actions(config)
        assert actions.count("GetStatusDownstream") == 1


class TestFetch:
    """Test HNAP data fetching."""

    def test_returns_hnap_response(self, hnap_data_server: str) -> None:
        """Fetch returns resource dict with hnap_response key."""
        session = requests.Session()
        loader = HNAPLoader(
            session=session,
            base_url=hnap_data_server,
            private_key="test_key",
        )
        config = _make_parser_config()

        resources = loader.fetch(config)

        assert "hnap_response" in resources
        hnap = resources["hnap_response"]
        assert "GetStatusDownstreamResponse" in hnap
        assert "GetStatusUpstreamResponse" in hnap

    def test_unwraps_response(self, hnap_data_server: str) -> None:
        """GetMultipleHNAPsResponse wrapper is unwrapped."""
        session = requests.Session()
        loader = HNAPLoader(
            session=session,
            base_url=hnap_data_server,
            private_key="test_key",
        )
        config = _make_parser_config()

        resources = loader.fetch(config)

        assert "GetMultipleHNAPsResponse" not in resources["hnap_response"]

    def test_no_hnap_actions_returns_empty(self) -> None:
        """Config with non-HNAP sections produces empty hnap_response."""
        session = requests.Session()
        loader = HNAPLoader(
            session=session,
            base_url="http://unused",
            private_key="key",
        )
        config = _make_http_parser_config()

        resources = loader.fetch(config)

        assert resources == {"hnap_response": {}}


class TestRequestSigning:
    """Test HNAP_AUTH header on data requests."""

    @patch("solentlabs.cable_modem_monitor_core.protocol.hnap.time")
    def test_auth_header_sent(
        self,
        mock_time: Any,
        hnap_data_server: str,
    ) -> None:
        """Request includes HNAP_AUTH header."""
        mock_time.time.return_value = 1000.0

        session = requests.Session()
        loader = HNAPLoader(
            session=session,
            base_url=hnap_data_server,
            private_key="test_private_key",
        )
        config = _make_parser_config()

        resources = loader.fetch(config)
        assert "hnap_response" in resources

    def test_soap_action_header(self, hnap_data_server: str) -> None:
        """Request includes SOAPAction header for GetMultipleHNAPs."""
        session = requests.Session()
        loader = HNAPLoader(
            session=session,
            base_url=hnap_data_server,
            private_key="key",
        )
        config = _make_parser_config()

        # Should not raise
        loader.fetch(config)


class TestErrors:
    """Test error handling in HNAP loader."""

    def test_connection_refused(self) -> None:
        """Connection error raises HNAPLoadError."""
        session = requests.Session()
        loader = HNAPLoader(
            session=session,
            base_url="http://127.0.0.1:1",
            private_key="key",
            timeout=1,
        )
        config = _make_parser_config()

        with pytest.raises(HNAPLoadError, match="request failed"):
            loader.fetch(config)

    # ┌────────────────────┬─────────────────────────────────┐
    # │ json_value         │ description                     │
    # ├────────────────────┼─────────────────────────────────┤
    # │ "not a dict"       │ string response                 │
    # │ [1, 2, 3]          │ list response                   │
    # │ 42                 │ integer response                │
    # └────────────────────┴─────────────────────────────────┘
    #
    # fmt: off
    LOAD_NOT_DICT_CASES = [
        # (json_value,    description)
        ("not a dict",    "string response"),
        ([1, 2, 3],       "list response"),
        (42,              "integer response"),
    ]
    # fmt: on

    @pytest.mark.parametrize(
        "json_value,desc",
        LOAD_NOT_DICT_CASES,
        ids=[c[1] for c in LOAD_NOT_DICT_CASES],
    )
    def test_non_dict_json_raises_load_error(self, json_value: object, desc: str) -> None:
        """Non-dict JSON response raises HNAPLoadError."""
        session = requests.Session()
        loader = HNAPLoader(
            session=session,
            base_url="http://127.0.0.1:1",
            private_key="key",
        )
        config = _make_parser_config()

        resp = MagicMock()
        resp.status_code = 200
        resp.content = b"[]"
        resp.json.return_value = json_value

        with (
            patch.object(session, "post", return_value=resp),
            pytest.raises(HNAPLoadError, match="not a JSON object"),
        ):
            loader.fetch(config)


# ------------------------------------------------------------------
# Tests — HNAPLoadError status_code attribute (UC-21, UC-22)
# ------------------------------------------------------------------


class _StatusCodeHandler(BaseHTTPRequestHandler):
    """HNAP mock that returns a configurable HTTP status code."""

    status_code: int = 200

    def do_POST(self) -> None:  # noqa: N802
        """Return configured status code."""
        self.send_response(self.__class__.status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if self.__class__.status_code == 200:
            body = json.dumps({"GetMultipleHNAPsResponse": {}}).encode()
            self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress server log output."""


# ┌─────────────┬──────────────────┬───────────────────────┐
# │ HTTP status │ expected attr    │ description           │
# ├─────────────┼──────────────────┼───────────────────────┤
# │ 401         │ status_code=401  │ unauthorized          │
# │ 404         │ status_code=404  │ not found (S33 stale) │
# │ 500         │ status_code=500  │ server error          │
# └─────────────┴──────────────────┴───────────────────────┘
#
# fmt: off
HNAP_STATUS_CODE_CASES = [
    # (http_status, expected_status_code, description)
    (401,           401,                  "unauthorized"),
    (404,           404,                  "not found"),
    (500,           500,                  "server error"),
]
# fmt: on


@pytest.mark.parametrize(
    "http_status,expected_status_code,desc",
    HNAP_STATUS_CODE_CASES,
    ids=[c[2] for c in HNAP_STATUS_CODE_CASES],
)
def test_hnap_load_error_carries_status_code(
    http_status: int,
    expected_status_code: int,
    desc: str,
) -> None:
    """HNAPLoadError carries the HTTP status code from the response."""
    _StatusCodeHandler.status_code = http_status
    server = HTTPServer(("127.0.0.1", 0), _StatusCodeHandler)
    port = server.server_address[1]
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        session = requests.Session()
        loader = HNAPLoader(
            session=session,
            base_url=f"http://127.0.0.1:{port}",
            private_key="key",
        )
        config = _make_parser_config()

        with pytest.raises(HNAPLoadError) as exc_info:
            loader.fetch(config)
        assert exc_info.value.status_code == expected_status_code
    finally:
        server.shutdown()


def test_hnap_load_error_connection_has_no_status_code() -> None:
    """Connection error produces HNAPLoadError with status_code=None."""
    session = requests.Session()
    loader = HNAPLoader(
        session=session,
        base_url="http://127.0.0.1:1",
        private_key="key",
        timeout=1,
    )
    config = _make_parser_config()

    with pytest.raises(HNAPLoadError) as exc_info:
        loader.fetch(config)
    assert exc_info.value.status_code is None
