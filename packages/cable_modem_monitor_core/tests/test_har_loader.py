"""Tests for HAR loading and resource building.

Covers load_har_json() (LFS pointer detection, normal loading) and
build_resource_dict() (JSON body sniffing, root-level array wrapping, JSON-RPC
results keyed by method).
"""

from __future__ import annotations

import base64
import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from solentlabs.cable_modem_monitor_core.har import (
    LfsPointerError,
    build_resource_dict,
    load_har_json,
)

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "har_loader"


def _fixture_text(name: str) -> str:
    """Read a har_loader fixture file as text."""
    return (_FIXTURE_DIR / name).read_text(encoding="utf-8").strip()


LFS_POINTER = (
    "version https://git-lfs.github.com/spec/v1\n"
    "oid sha256:4d7a214614ab2935c943f9e0ff69d22eadbb8f32b1258daaa5e2ca24d17e2393\n"
    "size 12345\n"
)

MINIMAL_HAR: dict[str, Any] = {"log": {"entries": []}}


class TestLoadHarJsonNormal:
    """Normal (non-LFS) loading path."""

    def test_loads_valid_har(self, tmp_path: Path) -> None:
        har_file = tmp_path / "modem.har"
        har_file.write_text(json.dumps(MINIMAL_HAR), encoding="utf-8")

        result = load_har_json(har_file)

        assert result == MINIMAL_HAR

    def test_accepts_string_path(self, tmp_path: Path) -> None:
        har_file = tmp_path / "modem.har"
        har_file.write_text(json.dumps(MINIMAL_HAR), encoding="utf-8")

        result = load_har_json(str(har_file))

        assert result == MINIMAL_HAR

    def test_raises_on_invalid_json(self, tmp_path: Path) -> None:
        har_file = tmp_path / "bad.har"
        har_file.write_text("not json", encoding="utf-8")

        with pytest.raises(json.JSONDecodeError):
            load_har_json(har_file)

    def test_raises_on_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_har_json(tmp_path / "missing.har")


class TestLoadHarJsonLfsDetection:
    """LFS pointer detection and recovery."""

    def test_detects_lfs_pointer(self, tmp_path: Path) -> None:
        har_file = tmp_path / "modem.har"
        har_file.write_text(LFS_POINTER, encoding="utf-8")

        # Mock subprocess so the test doesn't actually invoke `git lfs pull`
        # against the surrounding repository (which would have side effects
        # on the working tree / index).
        with (
            patch("subprocess.run", side_effect=FileNotFoundError),
            pytest.raises(LfsPointerError, match="Git LFS pointer"),
        ):
            load_har_json(har_file)

    def test_error_message_includes_install_instructions(self, tmp_path: Path) -> None:
        har_file = tmp_path / "modem.har"
        har_file.write_text(LFS_POINTER, encoding="utf-8")

        with (
            patch("subprocess.run", side_effect=FileNotFoundError),
            pytest.raises(LfsPointerError, match="git lfs install"),
        ):
            load_har_json(har_file)

    def test_attempts_git_lfs_pull(self, tmp_path: Path) -> None:
        har_file = tmp_path / "modem.har"
        har_file.write_text(LFS_POINTER, encoding="utf-8")

        with (
            patch("subprocess.run", side_effect=FileNotFoundError) as mock_run,
            pytest.raises(LfsPointerError),
        ):
            load_har_json(har_file)

        mock_run.assert_called_once()
        assert mock_run.call_args[0][0] == ["git", "lfs", "pull"]

    def test_recovers_after_successful_pull(self, tmp_path: Path) -> None:
        har_file = tmp_path / "modem.har"
        har_file.write_text(LFS_POINTER, encoding="utf-8")

        def fake_pull(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
            """Simulate git lfs pull by replacing pointer with real content."""
            har_file.write_text(json.dumps(MINIMAL_HAR), encoding="utf-8")
            return subprocess.CompletedProcess(args=[], returncode=0)

        with patch("subprocess.run", side_effect=fake_pull):
            result = load_har_json(har_file)

        assert result == MINIMAL_HAR

    def test_raises_if_still_pointer_after_pull(self, tmp_path: Path) -> None:
        har_file = tmp_path / "modem.har"
        har_file.write_text(LFS_POINTER, encoding="utf-8")

        # Pull "succeeds" but file is still a pointer (e.g. LFS server unreachable)
        with (
            patch(
                "subprocess.run",
                return_value=subprocess.CompletedProcess(args=[], returncode=0),
            ),
            pytest.raises(LfsPointerError, match="git lfs install"),
        ):
            load_har_json(har_file)

    def test_non_lfs_content_not_detected(self, tmp_path: Path) -> None:
        har_file = tmp_path / "modem.har"
        har_file.write_text(json.dumps({"version": "1.2", "log": {"entries": []}}), encoding="utf-8")

        result = load_har_json(har_file)

        assert result["version"] == "1.2"


def _har_entry(
    url: str,
    body: str,
    mime: str = "text/html",
    status: int = 200,
    method: str = "GET",
) -> dict:
    """Build a minimal HAR entry for testing."""
    return {
        "request": {"url": url, "method": method},
        "response": {
            "status": status,
            "content": {"mimeType": mime, "text": body},
        },
    }


def _har_file(tmp_path: Path, entries: list[dict]) -> Path:
    """Write a HAR file and return its path."""
    path = tmp_path / "modem.har"
    path.write_text(json.dumps({"log": {"entries": entries}}), encoding="utf-8")
    return path


class TestBuildResourceDictJsonSniffing:
    """JSON body sniffing when Content-Type says text/html."""

    def test_json_object_with_html_content_type(self, tmp_path: Path) -> None:
        body = _fixture_text("system_info.json")
        har = _har_file(tmp_path, [_har_entry("https://192.168.100.1/data/info.asp", body)])

        resources = build_resource_dict(str(har))

        assert isinstance(resources["/data/info.asp"], dict)
        assert resources["/data/info.asp"]["hwVersion"] == "1A"

    def test_json_array_wrapped_as_raw(self, tmp_path: Path) -> None:
        body = _fixture_text("channel_list.json")
        har = _har_file(tmp_path, [_har_entry("https://192.168.100.1/data/dsinfo.asp", body)])

        resources = build_resource_dict(str(har))

        result = resources["/data/dsinfo.asp"]
        assert isinstance(result, dict)
        assert "_raw" in result
        assert result["_raw"][0]["channelId"] == "1"

    def test_json_content_type_also_wraps_arrays(self, tmp_path: Path) -> None:
        body = _fixture_text("channel_list.json")
        har = _har_file(tmp_path, [_har_entry("https://192.168.100.1/api/status", body, mime="application/json")])

        resources = build_resource_dict(str(har))

        result = resources["/api/status"]
        assert isinstance(result, dict)
        assert result["_raw"][0]["channelId"] == "1"

    def test_html_body_not_parsed_as_json(self, tmp_path: Path) -> None:
        from bs4 import BeautifulSoup

        body = _fixture_text("status_page.html")
        har = _har_file(tmp_path, [_har_entry("https://192.168.100.1/status.html", body)])

        resources = build_resource_dict(str(har))

        assert isinstance(resources["/status.html"], BeautifulSoup)

    def test_invalid_json_with_html_content_type_falls_back_to_html(self, tmp_path: Path) -> None:
        from bs4 import BeautifulSoup

        body = "[invalid json but starts with bracket"
        har = _har_file(tmp_path, [_har_entry("https://192.168.100.1/data/broken.asp", body)])

        resources = build_resource_dict(str(har))

        assert isinstance(resources["/data/broken.asp"], BeautifulSoup)


def _hnap_entry(
    url: str,
    response_body: str,
    *,
    soap_action: str = "http://purenetworks.com/HNAP1/GetMultipleHNAPs",
) -> dict:
    """Build a minimal HNAP POST HAR entry."""
    return {
        "request": {
            "url": url,
            "method": "POST",
            "headers": [{"name": "SOAPAction", "value": soap_action}],
        },
        "response": {
            "status": 200,
            "content": {"mimeType": "application/json", "text": response_body},
        },
    }


# -----------------------------------------------------------------------
# build_resource_dict — _build_http_resources skip branches
# -----------------------------------------------------------------------


class TestBuildResourceDictSkipBranches:
    """Defensive skip branches in HTTP resource building."""

    def test_non_200_status_skipped(self, tmp_path: Path) -> None:
        """Entries with non-200 status are skipped (not added to resources)."""
        har = _har_file(
            tmp_path,
            [_har_entry("https://192.168.100.1/status.html", "x", status=404)],
        )
        resources = build_resource_dict(str(har))
        assert "/status.html" not in resources

    def test_empty_url_path_skipped(self, tmp_path: Path) -> None:
        """Entries whose URL has no path component are skipped."""
        # urlparse("") yields path="" — triggers the `if not url_path: continue`
        har = _har_file(tmp_path, [_har_entry("", "body")])
        resources = build_resource_dict(str(har))
        assert resources == {}

    def test_empty_body_text_skipped(self, tmp_path: Path) -> None:
        """Entries with empty response body text are skipped."""
        har = _har_file(
            tmp_path,
            [_har_entry("https://192.168.100.1/empty.html", "")],
        )
        resources = build_resource_dict(str(har))
        assert "/empty.html" not in resources

    def test_base64_decode_failure_skipped(self, tmp_path: Path) -> None:
        """Entries with corrupted base64 encoding are skipped."""
        entry = _har_entry("https://192.168.100.1/binary.bin", "!!!not-base64!!!")
        entry["response"]["content"]["encoding"] = "base64"
        har = _har_file(tmp_path, [entry])

        resources = build_resource_dict(str(har))

        assert "/binary.bin" not in resources

    def test_base64_encoded_text_decoded(self, tmp_path: Path) -> None:
        """Valid base64 encoding is decoded before mime-type detection."""
        body = base64.b64encode(_fixture_text("system_info.json").encode("utf-8")).decode("ascii")
        entry = _har_entry("https://192.168.100.1/info.json", body, mime="application/json")
        entry["response"]["content"]["encoding"] = "base64"
        har = _har_file(tmp_path, [entry])

        resources = build_resource_dict(str(har))

        assert resources["/info.json"]["hwVersion"] == "1A"

    def test_undecodable_body_skipped(self, tmp_path: Path) -> None:
        """Body that's neither JSON nor HTML produces no resource entry."""
        # Plain text body without JSON markers and without HTML tags
        har = _har_file(
            tmp_path,
            [
                _har_entry(
                    "https://192.168.100.1/plain.bin",
                    "raw binary content",
                    mime="application/octet-stream",
                )
            ],
        )
        resources = build_resource_dict(str(har))
        assert "/plain.bin" not in resources

    def test_invalid_json_with_json_content_type_returns_none(self, tmp_path: Path) -> None:
        """Invalid JSON body with application/json mime type is dropped."""
        har = _har_file(
            tmp_path,
            [
                _har_entry(
                    "https://192.168.100.1/api/info",
                    "not valid json {{{",
                    mime="application/json",
                )
            ],
        )
        resources = build_resource_dict(str(har))
        assert "/api/info" not in resources


# -----------------------------------------------------------------------
# HNAP resource extraction — merge_hnap_har_responses + helpers
# -----------------------------------------------------------------------


class TestHnapResourceExtraction:
    """HNAP response merging and SOAPAction parsing."""

    def test_hnap_resource_dict_built_from_har(self, tmp_path: Path) -> None:
        """build_resource_dict prefers HNAP entries when present."""
        body = _fixture_text("hnap_multi_response.json")
        har = _har_file(
            tmp_path,
            [_hnap_entry("https://192.168.100.1/HNAP1/", body)],
        )

        resources = build_resource_dict(str(har))

        assert "hnap_response" in resources
        merged = resources["hnap_response"]
        assert "GetChannelInfoResponse" in merged
        # GetMultipleHNAPsResult should be filtered out
        assert "GetMultipleHNAPsResult" not in merged

    def test_hnap_login_action_excluded(self, tmp_path: Path) -> None:
        """SOAPAction containing 'Login' is treated as auth, not data — falls back to HTTP."""
        body = _fixture_text("hnap_multi_response.json")
        # Login action: should be filtered out by is_hnap_data_entry
        har = _har_file(
            tmp_path,
            [
                _hnap_entry(
                    "https://192.168.100.1/HNAP1/",
                    body,
                    soap_action="http://purenetworks.com/HNAP1/Login",
                )
            ],
        )

        resources = build_resource_dict(str(har))

        # No HNAP data found → falls through to HTTP path
        assert "hnap_response" not in resources

    def test_hnap_non_post_excluded(self, tmp_path: Path) -> None:
        """GET request to /HNAP1/ is not treated as HNAP data."""
        body = _fixture_text("hnap_multi_response.json")
        entry = _hnap_entry("https://192.168.100.1/HNAP1/", body)
        entry["request"]["method"] = "GET"
        har = _har_file(tmp_path, [entry])

        resources = build_resource_dict(str(har))

        assert "hnap_response" not in resources

    def test_hnap_non_hnap_path_excluded(self, tmp_path: Path) -> None:
        """POST to a non-HNAP path is not treated as HNAP data."""
        body = json.dumps({"foo": "bar"})
        entry = _hnap_entry("https://192.168.100.1/api/data", body)
        har = _har_file(tmp_path, [entry])

        resources = build_resource_dict(str(har))

        assert "hnap_response" not in resources

    def test_hnap_missing_soap_action_header_returns_empty(self, tmp_path: Path) -> None:
        """Request without a SOAPAction header has soap_action == '' (empty fallback)."""
        from solentlabs.cable_modem_monitor_core.har import get_soap_action

        # Direct unit test of the helper
        request: dict = {"headers": []}
        assert get_soap_action(request) == ""

    def test_hnap_empty_body_skipped(self, tmp_path: Path) -> None:
        """HNAP entry with empty response body contributes nothing."""
        entry = _hnap_entry("https://192.168.100.1/HNAP1/", "")
        har = _har_file(tmp_path, [entry])

        resources = build_resource_dict(str(har))

        assert "hnap_response" not in resources

    def test_hnap_invalid_json_skipped(self, tmp_path: Path) -> None:
        """HNAP entry with malformed JSON contributes nothing."""
        entry = _hnap_entry("https://192.168.100.1/HNAP1/", "not valid json {{{")
        har = _har_file(tmp_path, [entry])

        resources = build_resource_dict(str(har))

        assert "hnap_response" not in resources

    def test_hnap_base64_encoded_body_decoded(self, tmp_path: Path) -> None:
        """HNAP body stored with HAR base64 encoding is decoded before merging."""
        body = _fixture_text("hnap_multi_response.json")
        entry = _hnap_entry(
            "https://192.168.100.1/HNAP1/",
            base64.b64encode(body.encode("utf-8")).decode("ascii"),
        )
        entry["response"]["content"]["encoding"] = "base64"
        har = _har_file(tmp_path, [entry])

        resources = build_resource_dict(str(har))

        assert "hnap_response" in resources
        assert "GetChannelInfoResponse" in resources["hnap_response"]

    def test_hnap_corrupt_base64_body_skipped(self, tmp_path: Path) -> None:
        """HNAP entry with corrupted base64 encoding contributes nothing."""
        entry = _hnap_entry("https://192.168.100.1/HNAP1/", "!!!not-base64!!!")
        entry["response"]["content"]["encoding"] = "base64"
        har = _har_file(tmp_path, [entry])

        resources = build_resource_dict(str(har))

        assert "hnap_response" not in resources


# -----------------------------------------------------------------------
# _is_html_content — content-sniffing branch
# -----------------------------------------------------------------------


class TestHtmlContentSniffing:
    """HTML detection by leading-tag sniffing when MIME is non-HTML."""

    def test_doctype_html_sniffed(self, tmp_path: Path) -> None:
        """Body starting with <!DOCTYPE is detected as HTML even with octet mime."""
        from bs4 import BeautifulSoup

        body = _fixture_text("doctype_page.html")
        entry = _har_entry("https://192.168.100.1/page", body, mime="application/octet-stream")
        har = _har_file(tmp_path, [entry])

        resources = build_resource_dict(str(har))

        assert isinstance(resources["/page"], BeautifulSoup)


# -----------------------------------------------------------------------
# build_resource_dict — JSON-RPC transport
# -----------------------------------------------------------------------

_RPC_URL = "https://192.168.0.1/cgi-bin/router.php"


def _rpc_entry(method: str, reply: dict[str, Any]) -> dict[str, Any]:
    """A JSON-RPC 2.0 call and its reply, as a HAR entry."""
    return {
        "request": {
            "url": _RPC_URL,
            "method": "POST",
            "postData": {"text": json.dumps({"jsonrpc": "2.0", "method": method, "params": [], "id": 1})},
        },
        "response": {
            "status": 200,
            "content": {"mimeType": "application/json", "text": json.dumps({"jsonrpc": "2.0", "id": 1, **reply})},
        },
    }


_ONE: dict[str, Any] = {"result": {"x": 1}}
_TWO: dict[str, Any] = {"result": {"x": 2}}
_ERR: dict[str, Any] = {"error": {"code": "msgFail"}}

# =============================================================================
# JSON-RPC resource test data
# =============================================================================
#
# ┌──────────────────────────────┬──────────────────────┬──────────────────────────┐
# │ calls (method → reply)       │ resources            │ description              │
# ├──────────────────────────────┼──────────────────────┼──────────────────────────┤
# │ A → {x: 1}                   │ A: {x: 1}            │ keyed by method          │
# │ A → [1]                      │ A: {_raw: [1]}       │ non-object wrapped       │
# │ A → error                    │ none                 │ an error is not data     │
# │ A → {x: 1}, A → {x: 2}       │ A: {x: 2}            │ later result wins        │
# │ A → {x: 1}, A → error        │ A: {x: 1}            │ result beats error       │
# └──────────────────────────────┴──────────────────────┴──────────────────────────┘
#
# fmt: off
JSONRPC_RESOURCE_CASES: list[tuple[list[dict[str, Any]], dict[str, Any], str]] = [
    # (calls,                                            resources,              id)
    ([_rpc_entry("A", _ONE)],                            {"A": {"x": 1}},        "keyed-by-method"),
    ([_rpc_entry("A", {"result": [1]})],                 {"A": {"_raw": [1]}},   "non-object-wrapped"),
    ([_rpc_entry("A", _ERR)],                            {},                     "error-is-not-data"),
    ([_rpc_entry("A", _ONE), _rpc_entry("A", _TWO)],     {"A": {"x": 2}},        "later-result-wins"),
    ([_rpc_entry("A", _ONE), _rpc_entry("A", _ERR)],     {"A": {"x": 1}},        "result-beats-error"),
]
# fmt: on


@pytest.mark.parametrize(
    "calls,expected",
    [c[:2] for c in JSONRPC_RESOURCE_CASES],
    ids=[c[2] for c in JSONRPC_RESOURCE_CASES],
)
def test_jsonrpc_resources(tmp_path: Path, calls: list[dict[str, Any]], expected: dict[str, Any]) -> None:
    """Each method's result, as the JSON-RPC loader hands it to the parser."""
    assert build_resource_dict(str(_har_file(tmp_path, calls)), transport="jsonrpc") == expected


def test_jsonrpc_only_when_told(tmp_path: Path) -> None:
    """Without the transport, JSON-RPC calls read as HTTP: firmware plumbing never switches the shape."""
    resources = build_resource_dict(str(_har_file(tmp_path, [_rpc_entry("A", _ONE)])))
    assert set(resources) == {"/cgi-bin/router.php"}


def _cbn_entry(fun: str, body: str, path: str = "/xml/getter.xml") -> dict[str, Any]:
    """A CBN call (token first, a fun code) and its XML answer, as a HAR entry."""
    return {
        "request": {"url": f"http://192.168.100.1{path}", "method": "POST", "postData": {"text": f"token=T&fun={fun}"}},
        "response": {"status": 200, "content": {"mimeType": "text/xml", "text": body}},
    }


_DS = "<downstream_table><downstream><freq>1</freq></downstream></downstream_table>"
_DS2 = "<downstream_table><downstream><freq>2</freq></downstream></downstream_table>"

# =============================================================================
# CBN resource test data
# =============================================================================
#
# ┌────────────────────────────────────────┬──────────────────────┬──────────────────────────┐
# │ calls (fun → body)                     │ resources (root tag) │ description              │
# ├────────────────────────────────────────┼──────────────────────┼──────────────────────────┤
# │ getter 10 → table                      │ 10: table, freq 1    │ keyed by fun             │
# │ getter 10 → table, getter 10 → table 2 │ 10: freq 2           │ later answer wins        │
# │ getter 10 → table, getter 10 → empty   │ 10: freq 1           │ unparseable is skipped   │
# │ setter 8 → <setter/>                   │ none                 │ only the getter is data  │
# └────────────────────────────────────────┴──────────────────────┴──────────────────────────┘
#
# fmt: off
CBN_RESOURCE_CASES: list[tuple[list[dict[str, Any]], dict[str, str], str]] = [
    # (calls,                                                        fun → first freq, id)
    ([_cbn_entry("10", _DS)],                                        {"10": "1"},      "keyed-by-fun"),
    ([_cbn_entry("10", _DS), _cbn_entry("10", _DS2)],                {"10": "2"},      "later-answer-wins"),
    ([_cbn_entry("10", _DS), _cbn_entry("10", "")],                  {"10": "1"},      "unparseable-skipped"),
    ([_cbn_entry("8", "<setter></setter>", path="/xml/setter.xml")], {},               "getter-only"),
]
# fmt: on


@pytest.mark.parametrize("calls,expected", [c[:2] for c in CBN_RESOURCE_CASES], ids=[c[2] for c in CBN_RESOURCE_CASES])
def test_cbn_resources(tmp_path: Path, calls: list[dict[str, Any]], expected: dict[str, str]) -> None:
    """Each getter fun code's parsed XML root, as the CBN loader hands it to the parser."""
    resources = build_resource_dict(str(_har_file(tmp_path, calls)), transport="cbn")
    assert {fun: root.findtext("downstream/freq") for fun, root in resources.items()} == expected


def test_cbn_getter_endpoint_is_configurable(tmp_path: Path) -> None:
    """A firmware with its own getter path is read from that path."""
    calls = [_cbn_entry("10", _DS, path="/cgi/get.xml")]
    assert set(build_resource_dict(str(_har_file(tmp_path, calls)), transport="cbn")) == set()
    assert set(
        build_resource_dict(str(_har_file(tmp_path, calls)), transport="cbn", getter_endpoint="/cgi/get.xml")
    ) == {"10"}
