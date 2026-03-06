"""Stress tests for the protocol lock fix.

When a user explicitly specifies http:// or https:// in the host field,
that protocol is a hard override — no runtime fallback to the other protocol.
When no protocol is specified, existing HTTPS→HTTP fallback behavior is preserved.

Tests are organized by scenario:
1. Protocol lock initialization (flag set correctly)
2. _fetch_data respects/ignores protocol lock
3. Interactions with base_url mutations, restart, capture mode
4. Edge cases (uppercase, trailing slash, ports, cached_url)
5. Existing fallback behavior preserved (regression)
6. CM1200-specific scenario (issue #121)
"""

from __future__ import annotations

import pytest
import requests

from custom_components.cable_modem_monitor.core.base_parser import ModemParser
from custom_components.cable_modem_monitor.core.data_orchestrator import DataOrchestrator

TEST_TIMEOUT = 10


class StubParser(ModemParser):
    """Minimal parser for protocol lock tests."""

    name = "Stub"
    manufacturer = "Test"
    model = "Stub"
    url_patterns = [{"path": "/status.htm", "auth_method": "none"}]

    def parse_resources(self, resources) -> dict:
        return {"downstream": [], "upstream": [], "system_info": {}}


# =============================================================================
# 1. PROTOCOL LOCK INITIALIZATION
# =============================================================================
#
# ┌────────────────────────────────────┬──────────┬───────────────────────────┐
# │ host                               │ locked?  │ base_url                  │
# ├────────────────────────────────────┼──────────┼───────────────────────────┤
# │ "https://192.168.100.1"            │ True     │ "https://192.168.100.1"   │
# │ "http://192.168.100.1"             │ True     │ "http://192.168.100.1"    │
# │ "192.168.100.1"                    │ False    │ "https://192.168.100.1"   │
# │ "192.168.100.1" + cached http      │ False    │ "http://192.168.100.1"    │
# │ "http://192.168.100.1/"            │ True     │ "http://192.168.100.1"    │
# │ "https://192.168.100.1:8443"       │ True     │ "https://192.168.100.1:…" │
# │ "HTTP://192.168.100.1"             │ False*   │ see edge case note        │
# └────────────────────────────────────┴──────────┴───────────────────────────┘
# * Case sensitivity — Python startswith is case-sensitive. Uppercase "HTTP://"
#   would NOT be detected. This is acceptable because config_flow normalizes input.
#
# fmt: off
_S = "http://192.168.100.1/status.htm"   # short alias for cached_url
_SS = "https://192.168.100.1/status.htm"  # HTTPS variant

LOCK_INIT_CASES = [
    # (host,                           cached,  proto,    base_url,                      id)
    ("https://192.168.100.1",          None,    "https",  "https://192.168.100.1",       "explicit-https"),
    ("http://192.168.100.1",           None,    "http",   "http://192.168.100.1",        "explicit-http"),
    ("192.168.100.1",                  None,    None,     "https://192.168.100.1",       "bare-no-cache"),
    ("192.168.100.1",                  _S,      None,     "http://192.168.100.1",        "bare-http-cache"),
    ("192.168.100.1",                  _SS,     None,     "https://192.168.100.1",       "bare-https-cache"),
    ("http://192.168.100.1/",          None,    "http",   "http://192.168.100.1",        "trailing-slash"),
    ("https://192.168.100.1:8443",     None,    "https",  "https://192.168.100.1:8443",  "https-port"),
    ("http://192.168.100.1:8080",      None,    "http",   "http://192.168.100.1:8080",   "http-port"),
    # Explicit protocol overrides cached_url
    ("http://192.168.100.1",           _SS,     "http",   "http://192.168.100.1",        "explicit-over-cache"),
    ("https://192.168.100.1",          _S,      "https",  "https://192.168.100.1",       "https-over-http-cache"),
]
# fmt: on


class TestProtocolLockInit:
    """Verify _explicit_protocol is set correctly at init."""

    @pytest.mark.parametrize(
        "host,cached_url,expect_protocol,expect_base_url,desc",
        LOCK_INIT_CASES,
        ids=[c[4] for c in LOCK_INIT_CASES],
    )
    def test_protocol_lock_flag(self, host, cached_url, expect_protocol, expect_base_url, desc):
        orchestrator = DataOrchestrator(host=host, parser=[], cached_url=cached_url, timeout=TEST_TIMEOUT)
        assert orchestrator._explicit_protocol == expect_protocol, f"Failed: {desc}"
        assert orchestrator.base_url == expect_base_url, f"Failed base_url: {desc}"


# =============================================================================
# 2. _fetch_data PROTOCOL BEHAVIOR
# =============================================================================


class TestFetchDataProtocolLock:
    """Verify _fetch_data only tries the locked protocol when locked."""

    def _make_orchestrator(self, host, cached_url=None):
        """Create an orchestrator with StubParser."""
        return DataOrchestrator(host=host, parser=StubParser(), cached_url=cached_url, timeout=TEST_TIMEOUT)

    def test_locked_https_only_tries_https(self, mocker):
        """Locked to HTTPS → only HTTPS URLs attempted, no HTTP fallback."""
        orch = self._make_orchestrator("https://192.168.100.1")

        tried_urls = []

        def mock_get(url, **kwargs):
            tried_urls.append(url)
            raise requests.exceptions.ConnectionError("refused")

        mocker.patch.object(orch.session, "get", side_effect=mock_get)

        result = orch._fetch_data()

        assert result is None  # All failed
        # Should only have tried HTTPS
        assert all("https://" in url for url in tried_urls), f"Non-HTTPS URL tried: {tried_urls}"
        assert not any("http://" in url and "https://" not in url for url in tried_urls)

    def test_locked_http_only_tries_http(self, mocker):
        """Locked to HTTP → only HTTP URLs attempted, no HTTPS fallback."""
        orch = self._make_orchestrator("http://192.168.100.1")

        tried_urls = []

        def mock_get(url, **kwargs):
            tried_urls.append(url)
            raise requests.exceptions.ConnectionError("refused")

        mocker.patch.object(orch.session, "get", side_effect=mock_get)

        result = orch._fetch_data()

        assert result is None
        assert all(url.startswith("http://") for url in tried_urls), f"Non-HTTP URL tried: {tried_urls}"

    def test_locked_https_succeeds_on_https(self, mocker):
        """Locked to HTTPS, HTTPS works → returns data normally."""
        orch = self._make_orchestrator("https://192.168.100.1")

        mock_resp = mocker.Mock()
        mock_resp.status_code = 200
        mock_resp.text = "<html>channel data</html>"
        mocker.patch.object(orch.session, "get", return_value=mock_resp)

        result = orch._fetch_data()

        assert result is not None
        html, url, _ = result
        assert "https://" in url
        assert html == "<html>channel data</html>"

    def test_locked_https_fails_returns_none(self, mocker):
        """Locked to HTTPS, HTTPS fails → returns None (no HTTP fallback)."""
        orch = self._make_orchestrator("https://192.168.100.1")

        mocker.patch.object(orch.session, "get", side_effect=requests.exceptions.ConnectionError("refused"))

        result = orch._fetch_data()
        assert result is None

    def test_locked_http_401_no_fallback(self, mocker):
        """Locked to HTTP, gets 401 → returns None, does NOT try HTTPS.

        This is the CM1200 anti-pattern: user explicitly typed http:// but modem
        needs HTTPS for public pages. The lock means we respect their choice and
        fail. They'll need to change to https://.
        """
        orch = self._make_orchestrator("http://192.168.100.1")

        tried_urls = []

        def mock_get(url, **kwargs):
            tried_urls.append(url)
            resp = mocker.Mock()
            resp.status_code = 401
            return resp

        mocker.patch.object(orch.session, "get", side_effect=mock_get)

        result = orch._fetch_data()

        assert result is None
        assert all(url.startswith("http://") for url in tried_urls)

    def test_locked_https_401_no_fallback(self, mocker):
        """Locked to HTTPS, gets 401 → returns None, does NOT try HTTP."""
        orch = self._make_orchestrator("https://192.168.100.1")

        tried_urls = []

        def mock_get(url, **kwargs):
            tried_urls.append(url)
            resp = mocker.Mock()
            resp.status_code = 401
            return resp

        mocker.patch.object(orch.session, "get", side_effect=mock_get)

        result = orch._fetch_data()

        assert result is None
        assert all("https://" in url for url in tried_urls)


# =============================================================================
# 3. UNLOCKED: EXISTING FALLBACK PRESERVED (REGRESSION)
# =============================================================================


class TestUnlockedFallbackPreserved:
    """Verify unlocked hosts still get HTTPS→HTTP fallback."""

    def _make_orchestrator(self, host="192.168.100.1", cached_url=None):
        return DataOrchestrator(host=host, parser=StubParser(), cached_url=cached_url, timeout=TEST_TIMEOUT)

    def test_unlocked_https_default_falls_back_to_http(self, mocker):
        """Bare IP → defaults to HTTPS → HTTPS fails → falls back to HTTP → success."""
        orch = self._make_orchestrator()
        assert not orch._explicit_protocol

        call_count = [0]

        def mock_get(url, **kwargs):
            call_count[0] += 1
            if "https://" in url:
                raise requests.exceptions.ConnectionError("SSL error")
            resp = mocker.Mock()
            resp.status_code = 200
            resp.text = "<html>data</html>"
            return resp

        mocker.patch.object(orch.session, "get", side_effect=mock_get)

        result = orch._fetch_data()

        assert result is not None
        html, url, _ = result
        assert url.startswith("http://")
        assert orch.base_url == "http://192.168.100.1"

    def test_unlocked_https_default_succeeds_on_https(self, mocker):
        """Bare IP → defaults to HTTPS → HTTPS works → stays HTTPS."""
        orch = self._make_orchestrator()

        mock_resp = mocker.Mock()
        mock_resp.status_code = 200
        mock_resp.text = "<html>data</html>"
        mocker.patch.object(orch.session, "get", return_value=mock_resp)

        result = orch._fetch_data()

        assert result is not None
        _, url, _ = result
        assert "https://" in url

    def test_unlocked_http_cached_no_https_fallback(self, mocker):
        """Bare IP + HTTP cached → starts at HTTP → HTTP fails → no HTTPS fallback.

        This is the current asymmetric behavior (Bug B): HTTP never falls
        forward to HTTPS. This test documents that the protocol lock fix
        does NOT change this behavior — it's a separate issue.
        """
        orch = self._make_orchestrator(cached_url="http://192.168.100.1/status.htm")
        assert not orch._explicit_protocol
        assert orch.base_url.startswith("http://")

        mocker.patch.object(orch.session, "get", side_effect=requests.exceptions.ConnectionError("refused"))

        result = orch._fetch_data()
        assert result is None  # Fails with no HTTPS fallback (current behavior)


# =============================================================================
# 4. BASE_URL MUTATION SAFETY
# =============================================================================


class TestBaseUrlMutationWithLock:
    """Verify base_url mutations respect protocol lock."""

    def test_fetch_data_success_does_not_change_locked_protocol(self, mocker):
        """When locked to HTTPS and fetch succeeds, base_url stays HTTPS."""
        orch = DataOrchestrator(host="https://192.168.100.1", parser=StubParser(), timeout=TEST_TIMEOUT)
        assert orch._explicit_protocol

        mock_resp = mocker.Mock()
        mock_resp.status_code = 200
        mock_resp.text = "<html>ok</html>"
        mocker.patch.object(orch.session, "get", return_value=mock_resp)

        orch._fetch_data()

        # base_url may update but protocol must remain HTTPS
        assert orch.base_url.startswith("https://")

    def test_update_base_url_from_successful_url_preserves_lock_protocol(self):
        """_update_base_url_from_successful_url uses scheme from URL.

        When locked to HTTPS, the successful URL will always be HTTPS,
        so the base_url update preserves the locked protocol.
        """
        orch = DataOrchestrator(host="https://192.168.100.1", parser=StubParser(), timeout=TEST_TIMEOUT)
        assert orch._explicit_protocol

        orch._update_base_url_from_successful_url("https://192.168.100.1/status.htm")
        assert orch.base_url == "https://192.168.100.1"

    def test_multiple_get_modem_data_calls_respect_lock(self, mocker):
        """Protocol lock survives across multiple polling cycles."""
        orch = DataOrchestrator(host="https://192.168.100.1", parser=StubParser(), timeout=TEST_TIMEOUT)
        assert orch._explicit_protocol

        mock_resp = mocker.Mock()
        mock_resp.status_code = 200
        mock_resp.text = "<html>data</html>"
        mocker.patch.object(orch.session, "get", return_value=mock_resp)
        mocker.patch.object(orch, "_login", return_value=(True, None))
        mocker.patch.object(orch, "_parse_data", return_value={"downstream": [], "upstream": []})

        # Simulate 5 polling cycles
        for i in range(5):
            orch.get_modem_data()
            assert orch._explicit_protocol, f"Lock lost after poll {i+1}"
            assert orch.base_url.startswith("https://"), f"Protocol changed after poll {i+1}"


# =============================================================================
# 5. RESTART_MODEM WITH PROTOCOL LOCK
# =============================================================================


class TestRestartModemProtocolLock:
    """Verify restart_modem respects protocol lock."""

    def test_restart_locked_https_only_tries_https(self, mocker):
        """restart_modem with locked HTTPS should not fall back to HTTP."""
        orch = DataOrchestrator(
            host="https://192.168.100.1",
            username="admin",
            password="pass",
            parser=StubParser(),
            timeout=TEST_TIMEOUT,
        )
        assert orch._explicit_protocol

        tried_urls = []

        def mock_get(url, **kwargs):
            tried_urls.append(url)
            # HTTPS connection refused
            raise requests.exceptions.ConnectionError("refused")

        mocker.patch.object(orch.session, "get", side_effect=mock_get)

        result = orch.restart_modem()

        assert result is False
        # Should only have tried HTTPS URLs
        assert all("https://" in url for url in tried_urls)


# =============================================================================
# 6. EDGE CASES
# =============================================================================


class TestProtocolLockEdgeCases:
    """Edge cases that could trip up the protocol lock."""

    def test_uppercase_protocol_not_locked(self):
        """Uppercase 'HTTP://' is not detected as explicit protocol.

        Python's startswith is case-sensitive. 'HTTP://192.168.100.1' does
        not match 'http://'. This is acceptable because config_flow normalizes
        input to lowercase. But this test documents the limitation.
        """
        orch = DataOrchestrator(host="HTTP://192.168.100.1", parser=[], timeout=TEST_TIMEOUT)
        # Uppercase is NOT caught by startswith("http://")
        assert not orch._explicit_protocol

    def test_trailing_slash_still_locked(self):
        """Trailing slash in host is stripped but lock is still set."""
        orch = DataOrchestrator(host="https://192.168.100.1/", parser=[], timeout=TEST_TIMEOUT)
        assert orch._explicit_protocol
        assert orch.base_url == "https://192.168.100.1"

    def test_port_number_preserved_with_lock(self):
        """Protocol lock works with port numbers in host."""
        orch = DataOrchestrator(host="https://192.168.100.1:8443", parser=[], timeout=TEST_TIMEOUT)
        assert orch._explicit_protocol
        assert orch.base_url == "https://192.168.100.1:8443"

    def test_host_with_path_stripped_and_locked(self):
        """If host includes a path, trailing slash is stripped."""
        orch = DataOrchestrator(host="http://192.168.100.1", parser=[], timeout=TEST_TIMEOUT)
        assert orch._explicit_protocol
        # No path component — just protocol + host
        assert orch.base_url == "http://192.168.100.1"

    def test_ipv6_with_explicit_protocol(self):
        """Protocol lock works with IPv6 addresses."""
        orch = DataOrchestrator(host="http://[::1]", parser=[], timeout=TEST_TIMEOUT)
        assert orch._explicit_protocol
        assert orch.base_url == "http://[::1]"

    def test_hostname_with_explicit_protocol(self):
        """Protocol lock works with DNS hostnames."""
        orch = DataOrchestrator(host="https://mymodem.local", parser=[], timeout=TEST_TIMEOUT)
        assert orch._explicit_protocol
        assert orch.base_url == "https://mymodem.local"

    def test_empty_cached_url_with_locked_host(self):
        """Explicit protocol ignores empty string cached_url."""
        orch = DataOrchestrator(
            host="https://192.168.100.1",
            parser=[],
            cached_url="",
            timeout=TEST_TIMEOUT,
        )
        assert orch._explicit_protocol
        assert orch.base_url == "https://192.168.100.1"

    def test_explicit_protocol_is_immutable_after_init(self, mocker):
        """_explicit_protocol should never change after __init__."""
        orch = DataOrchestrator(host="https://192.168.100.1", parser=StubParser(), timeout=TEST_TIMEOUT)

        # Simulate a successful HTTP fetch (shouldn't happen with lock, but
        # verify the flag itself doesn't get flipped)
        mock_resp = mocker.Mock()
        mock_resp.status_code = 200
        mock_resp.text = "<html>data</html>"
        mocker.patch.object(orch.session, "get", return_value=mock_resp)

        orch._fetch_data()

        assert orch._explicit_protocol is not None  # Must remain set


# =============================================================================
# 7. FALLBACK ORCHESTRATOR INHERITANCE
# =============================================================================


class TestFallbackOrchestratorInheritsLock:
    """FallbackOrchestrator extends DataOrchestrator — verify lock propagates."""

    def test_fallback_orchestrator_has_explicit_protocol(self):
        """FallbackOrchestrator should inherit _explicit_protocol from parent."""
        from custom_components.cable_modem_monitor.core.fallback.data_orchestrator import (
            FallbackOrchestrator,
        )

        orch = FallbackOrchestrator(
            host="https://192.168.100.1",
            parser=[],
            timeout=TEST_TIMEOUT,
        )
        assert orch._explicit_protocol is not None

    def test_fallback_orchestrator_unlocked_with_bare_ip(self):
        """FallbackOrchestrator with bare IP should not be locked."""
        from custom_components.cable_modem_monitor.core.fallback.data_orchestrator import (
            FallbackOrchestrator,
        )

        orch = FallbackOrchestrator(
            host="192.168.100.1",
            parser=[],
            timeout=TEST_TIMEOUT,
        )
        assert orch._explicit_protocol is None


# =============================================================================
# 8. PROTOCOL SWITCH LOGGING (when unlocked fallback occurs)
# =============================================================================


class TestProtocolFallbackLogging:
    """When unlocked fallback switches protocol, a warning should be logged."""

    def test_unlocked_fallback_logs_warning(self, mocker, caplog):
        """Switching from HTTPS to HTTP should produce a warning log."""
        import logging

        orch = DataOrchestrator(host="192.168.100.1", parser=StubParser(), timeout=TEST_TIMEOUT)
        assert not orch._explicit_protocol

        call_count = [0]

        def mock_get(url, **kwargs):
            call_count[0] += 1
            if "https://" in url:
                raise requests.exceptions.ConnectionError("SSL error")
            resp = mocker.Mock()
            resp.status_code = 200
            resp.text = "<html>data</html>"
            return resp

        mocker.patch.object(orch.session, "get", side_effect=mock_get)

        with caplog.at_level(logging.WARNING, logger="custom_components.cable_modem_monitor"):
            result = orch._fetch_data()

        assert result is not None
        # After the fix, there should be a warning about protocol switch
        # This test will pass once the warning log is added
        protocol_switch_logged = any(
            "protocol" in record.message.lower() and "fallback" in record.message.lower() for record in caplog.records
        )
        assert protocol_switch_logged, (
            "Expected a warning log about protocol fallback. " f"Got logs: {[r.message for r in caplog.records]}"
        )


# =============================================================================
# 9. CM1200 SCENARIO (issue #121)
# =============================================================================


class TestCM1200Scenario:
    """Reproduce the exact CM1200 issue #121 scenario.

    CM1200 split auth model:
    - HTTPS: /DocsisStatus.htm returns 200 (no auth needed)
    - HTTP:  /DocsisStatus.htm returns 401 (Basic Auth required)

    With explicit https://, the user gets working data.
    With bare IP, protocol detection may pick HTTP first → 401 → 0 channels.
    """

    def _make_cm1200_mock(self, mocker):
        """Create a mock that simulates CM1200's split auth behavior."""

        def mock_get(url, **kwargs):
            resp = mocker.Mock()
            if "https://" in url and "/DocsisStatus.htm" in url:
                resp.status_code = 200
                resp.text = "<html>InitDsTableTagValue(32 channels)</html>"
            elif "http://" in url and "/DocsisStatus.htm" in url:
                resp.status_code = 401
                resp.text = ""
            elif "https://" in url:
                resp.status_code = 200
                resp.text = "<html>CM1200 Home</html>"
            else:
                resp.status_code = 200
                resp.text = "<html>CM1200 Home (HTTP)</html>"
            return resp

        return mock_get

    def test_explicit_https_gets_data(self, mocker):
        """User enters https://192.168.100.1 → locked → HTTPS only → 200 → data."""
        parser = StubParser()
        parser.url_patterns = [{"path": "/DocsisStatus.htm", "auth_method": "none"}]
        orch = DataOrchestrator(host="https://192.168.100.1", parser=parser, timeout=TEST_TIMEOUT)

        mocker.patch.object(orch.session, "get", side_effect=self._make_cm1200_mock(mocker))

        result = orch._fetch_data()

        assert result is not None
        html, url, _ = result
        assert "InitDsTableTagValue" in html
        assert "https://" in url

    def test_explicit_http_gets_401_no_fallback(self, mocker):
        """User enters http://192.168.100.1 → locked → HTTP only → 401 → None.

        The user explicitly chose HTTP. We respect that. They'll need to
        change to https:// to fix it.
        """
        parser = StubParser()
        parser.url_patterns = [{"path": "/DocsisStatus.htm", "auth_method": "none"}]
        orch = DataOrchestrator(host="http://192.168.100.1", parser=parser, timeout=TEST_TIMEOUT)

        mocker.patch.object(orch.session, "get", side_effect=self._make_cm1200_mock(mocker))

        result = orch._fetch_data()
        assert result is None  # 401 with no fallback

    def test_bare_ip_existing_behavior_documented(self, mocker):
        """User enters 192.168.100.1 → unlocked → tries HTTPS first → 200.

        With the default HTTPS-first for bare IP, the CM1200 would actually
        work because /DocsisStatus.htm returns 200 on HTTPS. The problem
        in issue #121 was that setup detected HTTP as working (paradigm-based
        ordering for HTML modems tries HTTP first), cached it, and polling
        used the cached HTTP URL.
        """
        parser = StubParser()
        parser.url_patterns = [{"path": "/DocsisStatus.htm", "auth_method": "none"}]
        orch = DataOrchestrator(host="192.168.100.1", parser=parser, timeout=TEST_TIMEOUT)
        assert not orch._explicit_protocol
        # Default: HTTPS first for bare IP
        assert orch.base_url.startswith("https://")

        mocker.patch.object(orch.session, "get", side_effect=self._make_cm1200_mock(mocker))

        result = orch._fetch_data()

        assert result is not None
        html, url, _ = result
        assert "InitDsTableTagValue" in html  # Got actual data
        assert "https://" in url

    def test_bare_ip_with_http_cache_gets_401(self, mocker):
        """User enters 192.168.100.1 + HTTP cached → HTTP → 401.

        This is the exact #121 failure: setup cached http:// as working_url
        (because HTML paradigm tries HTTP first), and polling uses that.
        The protocol lock does NOT fix this case — only explicit protocol helps.
        """
        parser = StubParser()
        parser.url_patterns = [{"path": "/DocsisStatus.htm", "auth_method": "none"}]
        orch = DataOrchestrator(
            host="192.168.100.1",
            parser=parser,
            cached_url="http://192.168.100.1/DocsisStatus.htm",
            timeout=TEST_TIMEOUT,
        )
        assert not orch._explicit_protocol
        assert orch.base_url.startswith("http://")

        mocker.patch.object(orch.session, "get", side_effect=self._make_cm1200_mock(mocker))

        result = orch._fetch_data()
        # HTTP only → 401 → None (no fallback from HTTP to HTTPS)
        assert result is None


# =============================================================================
# 10. CAPTURE MODE + PROTOCOL LOCK
# =============================================================================


class TestCaptureModeWithLock:
    """Verify capture mode doesn't bypass protocol lock."""

    def test_capture_mode_respects_lock(self, mocker):
        """capture_raw=True with locked protocol should not fallback."""
        orch = DataOrchestrator(host="https://192.168.100.1", parser=StubParser(), timeout=TEST_TIMEOUT)
        assert orch._explicit_protocol

        tried_urls = []

        def mock_get(url, **kwargs):
            tried_urls.append(url)
            resp = mocker.Mock()
            resp.status_code = 200
            resp.text = "<html>data</html>"
            resp.headers = {"Content-Type": "text/html"}
            resp.url = url
            return resp

        mocker.patch.object(orch.session, "get", side_effect=mock_get)

        result = orch._fetch_data(capture_raw=True)

        assert result is not None
        assert all("https://" in url for url in tried_urls)


# =============================================================================
# 11. LEGACY SSL + PROTOCOL LOCK INTERACTION
# =============================================================================


class TestLegacySSLWithLock:
    """Legacy SSL adapter should work correctly with protocol lock."""

    def test_locked_https_with_legacy_ssl(self):
        """Locked to HTTPS + legacy_ssl → LegacySSLAdapter mounted."""
        orch = DataOrchestrator(
            host="https://192.168.100.1",
            parser=[],
            legacy_ssl=True,
            timeout=TEST_TIMEOUT,
        )
        assert orch._explicit_protocol
        # Verify adapter is mounted (session has custom adapter for https://)
        adapters = orch.session.adapters
        assert "https://" in adapters

    def test_locked_http_with_legacy_ssl(self):
        """Locked to HTTP + legacy_ssl → no LegacySSLAdapter needed."""
        orch = DataOrchestrator(
            host="http://192.168.100.1",
            parser=[],
            legacy_ssl=True,
            timeout=TEST_TIMEOUT,
        )
        assert orch._explicit_protocol
        # HTTP doesn't need SSL adapter — should use default
        # (requests always has adapters for both, but we didn't mount LegacySSL)
        assert orch.base_url.startswith("http://")
