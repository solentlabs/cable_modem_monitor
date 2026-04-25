"""Tests for HAR loading and resource building.

Covers load_har_json() (LFS pointer detection, normal loading) and
build_resource_dict() (JSON body sniffing, root-level array wrapping).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from solentlabs.cable_modem_monitor_core.har import (
    LfsPointerError,
    build_resource_dict,
    load_har_json,
)

LFS_POINTER = (
    "version https://git-lfs.github.com/spec/v1\n"
    "oid sha256:4d7a214614ab2935c943f9e0ff69d22eadbb8f32b1258daaa5e2ca24d17e2393\n"
    "size 12345\n"
)

MINIMAL_HAR = {"log": {"entries": []}}


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
        body = json.dumps({"hwVersion": "1A", "swVersion": "2.0"})
        har = _har_file(tmp_path, [_har_entry("https://192.168.100.1/data/info.asp", body)])

        resources = build_resource_dict(str(har))

        assert isinstance(resources["/data/info.asp"], dict)
        assert resources["/data/info.asp"]["hwVersion"] == "1A"

    def test_json_array_wrapped_as_raw(self, tmp_path: Path) -> None:
        body = json.dumps([{"channelId": "1", "frequency": "495000000"}])
        har = _har_file(tmp_path, [_har_entry("https://192.168.100.1/data/dsinfo.asp", body)])

        resources = build_resource_dict(str(har))

        result = resources["/data/dsinfo.asp"]
        assert isinstance(result, dict)
        assert "_raw" in result
        assert result["_raw"][0]["channelId"] == "1"

    def test_json_content_type_also_wraps_arrays(self, tmp_path: Path) -> None:
        body = json.dumps([{"id": 1}])
        har = _har_file(tmp_path, [_har_entry("https://192.168.100.1/api/status", body, mime="application/json")])

        resources = build_resource_dict(str(har))

        result = resources["/api/status"]
        assert isinstance(result, dict)
        assert result["_raw"][0]["id"] == 1

    def test_html_body_not_parsed_as_json(self, tmp_path: Path) -> None:
        from bs4 import BeautifulSoup

        body = "<html><body><table></table></body></html>"
        har = _har_file(tmp_path, [_har_entry("https://192.168.100.1/status.html", body)])

        resources = build_resource_dict(str(har))

        assert isinstance(resources["/status.html"], BeautifulSoup)

    def test_invalid_json_with_html_content_type_falls_back_to_html(self, tmp_path: Path) -> None:
        from bs4 import BeautifulSoup

        body = "[invalid json but starts with bracket"
        har = _har_file(tmp_path, [_har_entry("https://192.168.100.1/data/broken.asp", body)])

        resources = build_resource_dict(str(har))

        assert isinstance(resources["/data/broken.asp"], BeautifulSoup)
