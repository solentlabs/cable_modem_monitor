"""Tests for loaders.diagnostics shared utilities."""

from __future__ import annotations

import requests
from solentlabs.cable_modem_monitor_core.loaders.diagnostics import describe_request


def _prepare(headers: dict[str, str]) -> requests.PreparedRequest:
    return requests.Request("GET", "http://192.168.0.1/x?_n=12345", headers=headers).prepare()


class TestDescribeRequest:
    """describe_request formats request shape; values of named headers are redacted."""

    def test_redacts_session_token_headers(self) -> None:
        req = _prepare(
            {
                "X-Requested-With": "XMLHttpRequest",
                "Cookie": "PHPSESSID=abc123",
                "csrfNonce": "deadbeef" * 4,
                "Authorization": "Bearer xyz",
            }
        )
        out = describe_request(req, headers=frozenset({"cookie", "csrfnonce", "authorization"}))
        assert "Cookie=<set, len=16>" in out
        assert "abc123" not in out
        assert "csrfNonce=<set, len=32>" in out
        assert "Authorization=<set, len=10>" in out
        assert "X-Requested-With=XMLHttpRequest" in out

    def test_includes_method_and_full_url_with_query(self) -> None:
        out = describe_request(_prepare({}), headers=frozenset({"cookie"}))
        assert out.startswith("GET http://192.168.0.1/x?_n=12345 [")

    def test_handles_none(self) -> None:
        assert describe_request(None, headers=frozenset({"cookie"})) == "(no PreparedRequest available)"

    def test_redacts_only_listed_headers(self) -> None:
        """Headers whose names are not passed in are emitted verbatim — value and all."""
        req = _prepare({"Authorization": "Bearer secret", "X-Foo": "bar"})
        out = describe_request(req, headers=frozenset({"cookie"}))
        assert "Authorization=Bearer secret" in out
        assert "X-Foo=bar" in out


class TestMaskQuery:
    """A caller that put a session token in the URL declares it; the whole query is masked.

    Redaction is driven by the caller's declaration, never by locating the
    token in the string: a shape match fails open on redirects,
    percent-encoding and prefix collisions.
    """

    @staticmethod
    def _url(url: str) -> requests.PreparedRequest:
        return requests.Request("POST", url).prepare()

    def test_declared_token_query_is_masked(self) -> None:
        out = describe_request(
            self._url("http://192.168.0.1/cgi-bin/router.php?token=s3cr3t"), headers=frozenset(), mask_query=True
        )
        assert "s3cr3t" not in out
        assert out.startswith("POST http://192.168.0.1/cgi-bin/router.php?<set, len=12> [")

    def test_masking_does_not_depend_on_where_the_token_sits(self) -> None:
        out = describe_request(self._url("http://m/x?a=1&ct_s3cr3t"), headers=frozenset(), mask_query=True)
        assert "s3cr3t" not in out
        assert "?<set, len=13>" in out

    def test_undeclared_query_stays_visible(self) -> None:
        """A cache-buster is config, not a secret; it stays in the log."""
        out = describe_request(_prepare({}), headers=frozenset(), mask_query=False)
        assert "?_n=12345" in out

    def test_no_query_nothing_to_mask(self) -> None:
        out = describe_request(self._url("http://m/x"), headers=frozenset(), mask_query=True)
        assert out.startswith("POST http://m/x [")
