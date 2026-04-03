"""Tests for CBNLoader.

Table-driven for error scenarios. Mock HTTP session for all tests.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import requests
from requests.cookies import RequestsCookieJar
from solentlabs.cable_modem_monitor_core.loaders.cbn import CBNLoader
from solentlabs.cable_modem_monitor_core.loaders.fetch_list import ResourceTarget

_SAMPLE_XML = "<downstream_table><downstream><freq>500</freq></downstream></downstream_table>"
_MALFORMED_XML = "this is not xml {{"


def _make_session(token: str = "tok") -> MagicMock:
    """Create a mock session with sessionToken cookie."""
    session = MagicMock(spec=requests.Session)
    jar = RequestsCookieJar()
    jar.set("sessionToken", token)
    session.cookies = jar
    return session


def _make_loader(
    session: MagicMock,
    *,
    getter_endpoint: str = "/xml/getter.xml",
    cookie_name: str = "sessionToken",
    timeout: int = 10,
    model: str = "T100",
) -> CBNLoader:
    """Create a CBNLoader with defaults."""
    return CBNLoader(
        session=session,
        base_url="http://192.168.0.1",
        getter_endpoint=getter_endpoint,
        session_cookie_name=cookie_name,
        timeout=timeout,
        model=model,
    )


def _targets(*funs: str) -> list[ResourceTarget]:
    """Create ResourceTarget list from fun values."""
    return [ResourceTarget(path=f, format="xml") for f in funs]


def _mock_response(
    status_code: int = 200,
    text: str = _SAMPLE_XML,
    content: bytes = b"",
    ok: bool | None = None,
) -> MagicMock:
    """Build a mock requests.Response."""
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.text = text
    resp.content = content or text.encode()
    resp.ok = ok if ok is not None else (200 <= status_code < 400)
    return resp


# ---------------------------------------------------------------------------
# Successful fetch
# ---------------------------------------------------------------------------


class TestSuccessfulFetch:
    """Successful CBN resource loading."""

    def test_single_target(self) -> None:
        """Single target returns parsed XML element."""
        session = _make_session("tok123")
        session.post.return_value = _mock_response()

        loader = _make_loader(session)
        result = loader.fetch(_targets("10"))

        assert "10" in result
        assert result["10"].tag == "downstream_table"

    def test_multiple_targets(self) -> None:
        """Multiple targets each get their own entry."""
        session = _make_session()

        xml_ds = "<downstream_table><ds><freq>500</freq></ds></downstream_table>"
        xml_us = "<upstream_table><us><freq>30</freq></us></upstream_table>"
        responses = [
            _mock_response(text=xml_ds, content=xml_ds.encode()),
            _mock_response(text=xml_us, content=xml_us.encode()),
        ]
        session.post.side_effect = responses

        loader = _make_loader(session)
        result = loader.fetch(_targets("10", "11"))

        assert len(result) == 2
        assert result["10"].tag == "downstream_table"
        assert result["11"].tag == "upstream_table"

    def test_token_is_first_param(self) -> None:
        """POST body starts with token= parameter."""
        session = _make_session("my_token")
        session.post.return_value = _mock_response()

        loader = _make_loader(session)
        loader.fetch(_targets("10"))

        data_call = session.post.call_args_list[0]
        post_body = data_call.kwargs.get("data", "")
        assert post_body.startswith("token=my_token")

    def test_no_logout_in_loader(self) -> None:
        """Loader does NOT send logout — collector handles it."""
        session = _make_session()
        session.post.return_value = _mock_response()

        loader = _make_loader(session)
        loader.fetch(_targets("10"))

        # Only one POST: data fetch (no logout)
        assert session.post.call_count == 1


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Errors are logged, targets skipped, fetch continues."""

    def test_non_200_skipped(self) -> None:
        """Non-200 response skips the target."""
        session = _make_session()

        bad_resp = _mock_response(status_code=500, ok=False)
        good_resp = _mock_response()
        session.post.side_effect = [bad_resp, good_resp]

        loader = _make_loader(session)
        result = loader.fetch(_targets("10", "11"))

        assert "10" not in result
        assert "11" in result

    def test_network_error_skipped(self) -> None:
        """ConnectionError on one target doesn't stop others."""
        session = _make_session()

        session.post.side_effect = [
            requests.ConnectionError("refused"),
            _mock_response(),
        ]

        loader = _make_loader(session)
        result = loader.fetch(_targets("10", "11"))

        assert "10" not in result
        assert "11" in result

    def test_malformed_xml_skipped(self) -> None:
        """Malformed XML response skips the target."""
        session = _make_session()

        bad_xml = _mock_response(text=_MALFORMED_XML, content=_MALFORMED_XML.encode())
        good_xml = _mock_response()
        session.post.side_effect = [bad_xml, good_xml]

        loader = _make_loader(session)
        result = loader.fetch(_targets("10", "11"))

        assert "10" not in result
        assert "11" in result
