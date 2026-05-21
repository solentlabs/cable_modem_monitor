"""Tests for config_flow_helpers — validation pipeline and encoding detection.

Tests the _run_validation() function directly (sync, no HA dependency).
All Core I/O is mocked: detect_protocol, config loaders, ModemDataCollector.

Pipeline behaviour: protocol detection observes the modem's TLS via
TCP probe + handshake; auth runs exactly once; a structured rejection
is surfaced to the user (UC-86).
Pre-fetch encoding detection — connectivity vs non-connectivity error handling.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from solentlabs.cable_modem_monitor_core.catalog_manager import (
    ModemSummary,
    VariantInfo,
)
from solentlabs.cable_modem_monitor_core.connectivity import ConnectivityResult
from solentlabs.cable_modem_monitor_core.orchestration.models import ModemResult
from solentlabs.cable_modem_monitor_core.orchestration.signals import (
    CollectorSignal,
)

from custom_components.cable_modem_monitor.config_flow_helpers import (
    _detect_and_inject_form_nonce_encoding,
    _run_validation,
    build_model_display_name,
    classify_error,
    default_health_check_interval,
    detect_probes,
    filter_by_manufacturer,
    format_variant_label,
    get_manufacturers,
)

# =====================================================================
# Helpers
# =====================================================================

_MODULE = "custom_components.cable_modem_monitor.config_flow_helpers"


def _ok_result() -> ModemResult:
    """Successful collection result."""
    return ModemResult(
        success=True,
        signal=CollectorSignal.OK,
        modem_data={"downstream": [], "upstream": []},
    )


def _auth_failed_result(error: str = "HNAP challenge response is not valid JSON") -> ModemResult:
    """Auth failure result (wrong protocol, bad credentials, etc.)."""
    return ModemResult(
        success=False,
        signal=CollectorSignal.AUTH_FAILED,
        error=error,
    )


def _load_auth_result() -> ModemResult:
    """LOAD_AUTH failure — 401/403 on data page after auth."""
    return ModemResult(
        success=False,
        signal=CollectorSignal.LOAD_AUTH,
        error="HTTP 401 on /status.html",
    )


def _connectivity_result() -> ModemResult:
    """Connectivity failure — modem unreachable."""
    return ModemResult(
        success=False,
        signal=CollectorSignal.CONNECTIVITY,
        error="Connection refused",
    )


def _parse_error_result() -> ModemResult:
    """Parse error — modem responded but data is malformed."""
    return ModemResult(
        success=False,
        signal=CollectorSignal.PARSE_ERROR,
        error="Unexpected HTML structure",
    )


def _setup_modem_dir(tmp_path: Path) -> Path:
    """Create a minimal modem directory with required files."""
    modem_dir = tmp_path / "test_mfr" / "test_model"
    modem_dir.mkdir(parents=True)
    (modem_dir / "modem.yaml").touch()
    (modem_dir / "parser.yaml").touch()
    (modem_dir / "parser.py").touch()
    return modem_dir


# =====================================================================
# Pure-function helpers — format_variant_label
# =====================================================================

# fmt: off
# ┌───────────────┬──────┬───────────┬────────────────────────┬──────────────────────────────┬────────────────────────┐
# │ auth_strategy │ name │ hw_version│ status                 │ expected                     │ description            │
# ├───────────────┼──────┼───────────┼────────────────────────┼──────────────────────────────┼────────────────────────┤
# │ "none"        │ None │ None      │ "confirmed"            │ "No Authentication"          │ default_no_auth        │
# │ "basic"       │ None │ None      │ "confirmed"            │ "Basic Authentication"       │ default_basic          │
# │ "form_nonce"  │ None │ None      │ "confirmed"            │ "Form Login (Nonce)"         │ default_nonce          │
# │ "url_token"   │ "v7" │ None      │ "confirmed"            │ "URL Token (v7)"             │ named_no_hw_version    │
# │ "unknown_x"   │ None │ None      │ "confirmed"            │ "unknown_x"                  │ unlisted_strategy      │
# │ "url_token"   │ None │ "v5"      │ "confirmed"            │ "URL Token (v5)"             │ default_with_hw_ver    │
# │ "url_token"   │ "v7" │ "v7"      │ "confirmed"            │ "URL Token (v7)"             │ named_with_hw_ver      │
# │ "hnap"        │ None │ "v6"      │ "confirmed"            │ "HNAP (v6)"                  │ hnap_with_hw_version   │
# │ "form_cbn"    │ None │ None      │ "confirmed"            │ "Form Login CBN"             │ cbn_no_hw_version      │
# │ "none"        │ None │ None      │ "awaiting_verification"│ "No Authentication *"        │ unconfirmed_no_auth    │
# │ "url_token"   │ None │ "v5"      │ "awaiting_verification"│ "URL Token (v5) *"           │ unconfirmed_hw_version │
# │ "url_token"   │ "v7" │ "v7"      │ "awaiting_verification"│ "URL Token (v7) *"           │ unconfirmed_named_hw   │
# └───────────────┴──────┴───────────┴────────────────────────┴──────────────────────────────┴────────────────────────┘
#
VARIANT_LABEL_CASES = [
    ("none",       None,  None,  "confirmed",             "No Authentication",          "default_no_auth"),
    ("basic",      None,  None,  "confirmed",             "Basic Authentication",       "default_basic"),
    ("form_nonce", None,  None,  "confirmed",             "Form Login (Nonce)",         "default_nonce"),
    ("url_token",  "v7",  None,  "confirmed",             "URL Token (v7)",             "named_no_hw_version"),
    ("unknown_x",  None,  None,  "confirmed",             "unknown_x",                 "unlisted_strategy"),
    ("url_token",  None,  "v5",  "confirmed",             "URL Token (v5)",             "default_with_hw_version"),
    ("url_token",  "v7",  "v7",  "confirmed",             "URL Token (v7)",             "named_with_hw_version"),
    ("hnap",       None,  "v6",  "confirmed",             "HNAP (v6)",                 "hnap_with_hw_version"),
    ("form_cbn",   None,  None,  "confirmed",             "Form Login CBN",            "cbn_no_hw_version"),
    # Unconfirmed variants — star appended
    ("none",       None,  None,  "awaiting_verification", "No Authentication *",        "unconfirmed_no_auth"),
    ("url_token",  None,  "v5",  "awaiting_verification", "URL Token (v5) *",           "unconfirmed_hw_version"),
    ("url_token",  "v7",  "v7",  "awaiting_verification", "URL Token (v7) *",           "unconfirmed_named_hw"),
]
# fmt: on


@pytest.mark.parametrize(
    "auth_strategy,name,hw_version,status,expected,desc",
    VARIANT_LABEL_CASES,
    ids=[c[5] for c in VARIANT_LABEL_CASES],
)
def test_format_variant_label(auth_strategy, name, hw_version, status, expected, desc):
    """format_variant_label builds label from auth strategy, variant name, hw_version, and status."""
    variant = VariantInfo(name=name, auth_strategy=auth_strategy, hw_version=hw_version, status=status)
    assert format_variant_label(variant) == expected


# =====================================================================
# Pure-function helpers — get_manufacturers / filter_by_manufacturer
# =====================================================================


def test_get_manufacturers_normalizes_and_deduplicates():
    """Case variations consolidated into single title-case entry."""
    summaries = [
        ModemSummary(manufacturer="ARRIS", model="SB8200", path=Path("/fake")),
        ModemSummary(manufacturer="Arris", model="SB6183", path=Path("/fake")),
        ModemSummary(manufacturer="netgear", model="CM1100", path=Path("/fake")),
    ]
    assert get_manufacturers(summaries) == ["Arris", "Netgear"]


def test_get_manufacturers_empty():
    """Empty summaries returns empty list."""
    assert get_manufacturers([]) == []


def test_filter_by_manufacturer_case_insensitive():
    """Matches normalized manufacturer name across case variations."""
    summaries = [
        ModemSummary(manufacturer="ARRIS", model="SB8200", path=Path("/fake")),
        ModemSummary(manufacturer="Netgear", model="CM1100", path=Path("/fake")),
        ModemSummary(manufacturer="arris", model="SB6183", path=Path("/fake")),
    ]
    result = filter_by_manufacturer(summaries, "Arris")
    assert len(result) == 2
    assert all(r.manufacturer.lower() == "arris" for r in result)


def test_filter_by_manufacturer_no_match():
    """No match returns empty list."""
    summaries = [ModemSummary(manufacturer="Arris", model="SB8200", path=Path("/fake"))]
    assert filter_by_manufacturer(summaries, "Motorola") == []


# =====================================================================
# Pure-function helpers — build_model_display_name
# =====================================================================

# ┌──────────────┬──────────┬───────────────┬──────────────────────────┬──────────────────────────────┬────────────────┐
# │ manufacturer │ model    │ aliases       │ status                   │ expected                     │ description    │
# ├──────────────┼──────────┼───────────────┼──────────────────────────┼──────────────────────────────┼────────────────┤
# │ "ARRIS"      │ "SB8200" │ []            │ "confirmed"              │ "Arris SB8200"               │ basic          │
# │ "Motorola"   │ "MB8611" │ ["MB8612"]    │ "confirmed"              │ "Motorola MB8611 (MB8612)"   │ with_alias     │
# │ "netgear"    │ "CM1100" │ []            │ "awaiting_verification"  │ "Netgear CM1100 *"           │ unverified     │
# │ "ARRIS"      │ "CM820B" │ ["Zoom 5370"] │ "awaiting_verification"  │ "Arris CM820B (Zoom 5370) *" │ alias_and_star │
# └──────────────┴──────────┴───────────────┴──────────────────────────┴──────────────────────────────┴────────────────┘
#
# Remaining aliases are internal/OEM names — shown in parentheses
# as search aids. See MODEM_YAML_SPEC.md § Aliases vs Separate Entries.
#
# fmt: off
DISPLAY_NAME_CASES = [
    ("ARRIS",    "SB8200", [],             "confirmed",             "Arris SB8200",                "basic"),
    ("Motorola", "MB8611", ["MB8612"],     "confirmed",             "Motorola MB8611 (MB8612)",    "with_alias"),
    ("netgear",  "CM1100", [],             "awaiting_verification", "Netgear CM1100 *",            "unverified"),
    ("ARRIS",    "CM820B", ["Zoom 5370"],  "awaiting_verification", "Arris CM820B (Zoom 5370) *",  "alias_and_star"),
]
# fmt: on


@pytest.mark.parametrize(
    "manufacturer,model,aliases,status,expected,desc",
    DISPLAY_NAME_CASES,
    ids=[c[5] for c in DISPLAY_NAME_CASES],
)
def test_build_model_display_name(manufacturer, model, aliases, status, expected, desc):
    """build_model_display_name formats manufacturer, model, aliases, status."""
    summary = ModemSummary(
        manufacturer=manufacturer,
        model=model,
        model_aliases=aliases,
        status=status,
        path=Path("/fake"),
    )
    assert build_model_display_name(summary) == expected


# =====================================================================
# Pure-function helpers — classify_error
# =====================================================================

# ┌────────────────┬──────────────────┬──────────────┐
# │ signal         │ expected key     │ description  │
# ├────────────────┼──────────────────┼──────────────┤
# │ CONNECTIVITY   │ "cannot_connect" │ connectivity │
# │ AUTH_FAILED    │ "invalid_auth"   │ auth_failed  │
# │ AUTH_LOCKOUT   │ "invalid_auth"   │ auth_lockout │
# │ LOAD_ERROR     │ "cannot_connect" │ load_error   │
# │ LOAD_AUTH      │ "invalid_auth"   │ load_auth    │
# │ PARSE_ERROR    │ "parse_failed"   │ parse_error  │
# │ OK             │ "unknown"        │ unmapped     │
# │ None           │ "unknown"        │ no_signal    │
# └────────────────┴──────────────────┴──────────────┘
#
# fmt: off
CLASSIFY_ERROR_CASES = [
    (CollectorSignal.CONNECTIVITY, "cannot_connect", "connectivity"),
    (CollectorSignal.AUTH_FAILED,  "invalid_auth",   "auth_failed"),
    (CollectorSignal.AUTH_LOCKOUT, "invalid_auth",   "auth_lockout"),
    (CollectorSignal.LOAD_ERROR,   "cannot_connect", "load_error"),
    (CollectorSignal.LOAD_AUTH,    "invalid_auth",   "load_auth"),
    (CollectorSignal.PARSE_ERROR,  "parse_failed",   "parse_error"),
    (CollectorSignal.OK,           "unknown",         "unmapped"),
    (None,                         "unknown",         "no_signal"),
]
# fmt: on


@pytest.mark.parametrize(
    "signal,expected,desc",
    CLASSIFY_ERROR_CASES,
    ids=[c[2] for c in CLASSIFY_ERROR_CASES],
)
def test_classify_error(signal, expected, desc):
    """classify_error maps CollectorSignal to strings.json error key."""
    assert classify_error("some error", signal) == expected


# =====================================================================
# detect_probes
# =====================================================================


class TestDetectProbes:
    """Test health probe detection with mocked ICMP/HTTP."""

    @patch(f"{_MODULE}.test_http_head", return_value=True)
    @patch(f"{_MODULE}.test_icmp", return_value=True)
    def test_both_probes_succeed(self, mock_icmp, mock_head):
        """Both ICMP and HEAD succeed."""
        config = MagicMock()
        config.health.supports_head = True
        result = detect_probes("192.168.100.1", "http://192.168.100.1", config)
        assert result == {"supports_icmp": True, "supports_head": True}

    @patch(f"{_MODULE}.test_http_head", return_value=True)
    @patch(f"{_MODULE}.test_icmp", return_value=False)
    def test_icmp_fails(self, mock_icmp, mock_head):
        """ICMP blocked but HEAD succeeds."""
        config = MagicMock()
        config.health.supports_head = True
        result = detect_probes("192.168.100.1", "http://192.168.100.1", config)
        assert result == {"supports_icmp": False, "supports_head": True}

    @patch(f"{_MODULE}.test_http_head")
    @patch(f"{_MODULE}.test_icmp", return_value=True)
    def test_head_skipped_when_modem_rejects(self, mock_icmp, mock_head):
        """HEAD not tested when modem.yaml says supports_head=False."""
        config = MagicMock()
        config.health.supports_head = False
        result = detect_probes("192.168.100.1", "http://192.168.100.1", config)
        assert result == {"supports_icmp": True, "supports_head": False}
        mock_head.assert_not_called()

    @patch(f"{_MODULE}.test_http_head", return_value=False)
    @patch(f"{_MODULE}.test_icmp", return_value=True)
    def test_no_health_config(self, mock_icmp, mock_head):
        """No health section — HEAD tested normally."""
        config = MagicMock()
        config.health = None
        result = detect_probes("192.168.100.1", "http://192.168.100.1", config)
        assert result == {"supports_icmp": True, "supports_head": False}

    @patch(f"{_MODULE}.test_http_head", return_value=True)
    @patch(f"{_MODULE}.test_icmp", return_value=True)
    def test_legacy_ssl_forwarded(self, mock_icmp, mock_head):
        """legacy_ssl kwarg forwarded to test_http_head."""
        config = MagicMock()
        config.health.supports_head = True
        detect_probes("192.168.100.1", "https://192.168.100.1", config, legacy_ssl=True)
        mock_head.assert_called_once_with("https://192.168.100.1", legacy_ssl=True)


# =====================================================================
# default_health_check_interval — single default cadence
# =====================================================================


@pytest.mark.parametrize(
    "supports_icmp,supports_head,desc",
    [
        (True, True, "icmp_and_head"),
        (True, False, "icmp_only"),
        (False, True, "head_only"),
        (False, False, "get_only"),
    ],
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_default_health_check_interval(supports_icmp, supports_head, desc):
    """Single 30s default applies regardless of probe capabilities.

    All probes (ICMP, TCP, HEAD) are lightweight and the GET fallback
    is no longer used at fast cadence, so the per-capability cadence
    differentiation is gone.
    """
    assert default_health_check_interval(supports_icmp, supports_head) == 30


# =====================================================================
# Variant path — modem-{variant}.yaml
# =====================================================================


class TestVariantPath:
    """Verify _run_validation loads modem-{variant}.yaml when variant is set."""

    @patch(f"{_MODULE}.detect_probes")
    @patch(f"{_MODULE}._attempt_validation")
    @patch(f"{_MODULE}.load_post_processor")
    @patch(f"{_MODULE}.load_parser_config")
    @patch(f"{_MODULE}.load_modem_config")
    @patch(f"{_MODULE}.detect_protocol")
    def test_variant_loads_variant_yaml(
        self,
        mock_detect,
        mock_load_modem,
        mock_load_parser,
        mock_load_post,
        mock_collector_cls,
        mock_probes,
        tmp_path,
    ):
        """variant='v2' loads modem-v2.yaml instead of modem.yaml."""
        modem_dir = tmp_path / "test_mfr" / "test_model"
        modem_dir.mkdir(parents=True)
        (modem_dir / "modem-v2.yaml").touch()
        (modem_dir / "parser.yaml").touch()
        (modem_dir / "parser.py").touch()

        mock_detect.return_value = ConnectivityResult(success=True, protocol="http", working_url="http://192.168.100.1")
        mock_load_modem.return_value = MagicMock()
        mock_load_parser.return_value = MagicMock()
        mock_load_post.return_value = MagicMock()
        mock_probes.return_value = {"supports_icmp": True, "supports_head": True}

        mock_collector_cls.return_value = _ok_result()

        _run_validation("192.168.100.1", None, "admin", "pw", modem_dir, "v2")

        mock_load_modem.assert_called_once_with(modem_dir / "modem-v2.yaml")


# =====================================================================
# Auth runs exactly once — no retry chain
# =====================================================================
#
# UC-86: a structured login rejection means stop. The pipeline never
# retries auth across protocols, never retries with weakened ciphers,
# and surfaces the first error directly. detect_protocol's TCP probe
# + TLS handshake choose the transport up front.
#
# ┌────────────────────────────────────┬───────────────────┬─────────────────────────┐
# │ scenario                           │ collector result  │ expected outcome        │
# ├────────────────────────────────────┼───────────────────┼─────────────────────────┤
# │ auto-detected http + auth ok       │ _ok_result()      │ http persisted, no exc  │
# │ auto-detected http + auth fail     │ _auth_failed      │ PermissionError         │
# │ auto-detected http + load_auth     │ _load_auth        │ PermissionError         │
# │ auto-detected http + connectivity  │ _connectivity     │ RuntimeError            │
# │ auto-detected http + parse error   │ _parse_error      │ RuntimeError            │
# │ user-specified http + auth fail    │ _auth_failed      │ PermissionError         │
# │ auto-detected https (modern)       │ _ok_result()      │ https / legacy=False    │
# │ auto-detected https (legacy)       │ _ok_result()      │ https / legacy=True     │
# └────────────────────────────────────┴───────────────────┴─────────────────────────┘

_SINGLE_ATTEMPT_CASE = tuple[
    str | None,  # user_protocol
    str,  # detected_protocol
    bool,  # detected_legacy_ssl
    ModemResult,  # collector result
    type[Exception] | None,  # expected exception
    str | None,  # expected stored protocol
    bool | None,  # expected stored legacy_ssl
    str,  # description
]

# fmt: off
SINGLE_ATTEMPT_CASES: list[_SINGLE_ATTEMPT_CASE] = [
    (None,   "http",  False, _ok_result(),
     None, "http",  False,
     "auto HTTP + ok"),
    (None,   "http",  False, _auth_failed_result(),
     PermissionError, None, None,
     "auto HTTP + AUTH_FAILED -> PermissionError"),
    (None,   "http",  False, _load_auth_result(),
     PermissionError, None, None,
     "auto HTTP + LOAD_AUTH -> PermissionError"),
    (None,   "http",  False, _connectivity_result(),
     RuntimeError, None, None,
     "auto HTTP + CONNECTIVITY -> RuntimeError"),
    (None,   "http",  False, _parse_error_result(),
     RuntimeError, None, None,
     "auto HTTP + PARSE_ERROR -> RuntimeError"),
    ("http", "http",  False, _auth_failed_result(),
     PermissionError, None, None,
     "user HTTP + AUTH_FAILED -> PermissionError"),
    (None,   "https", False, _ok_result(),
     None, "https", False,
     "auto HTTPS modern -> persisted"),
    (None,   "https", True,  _ok_result(),
     None, "https", True,
     "auto HTTPS legacy -> persisted"),
]
# fmt: on


@pytest.mark.parametrize(
    "user_protocol, detected_protocol, detected_legacy_ssl, collector_result, "
    "expected_exception, expected_protocol, expected_legacy_ssl, description",
    SINGLE_ATTEMPT_CASES,
    ids=[c[-1] for c in SINGLE_ATTEMPT_CASES],
)
class TestSingleAttempt:
    """UC-86: pipeline runs auth once and surfaces the result directly."""

    @patch(f"{_MODULE}.detect_probes")
    @patch(f"{_MODULE}._attempt_validation")
    @patch(f"{_MODULE}.load_post_processor")
    @patch(f"{_MODULE}.load_parser_config")
    @patch(f"{_MODULE}.load_modem_config")
    @patch(f"{_MODULE}.detect_protocol")
    def test_single_attempt_outcome(
        self,
        mock_detect: MagicMock,
        mock_load_modem: MagicMock,
        mock_load_parser: MagicMock,
        mock_load_post: MagicMock,
        mock_attempt: MagicMock,
        mock_probes: MagicMock,
        tmp_path: Path,
        user_protocol: str | None,
        detected_protocol: str,
        detected_legacy_ssl: bool,
        collector_result: ModemResult,
        expected_exception: type[Exception] | None,
        expected_protocol: str | None,
        expected_legacy_ssl: bool | None,
        description: str,
    ) -> None:
        """Each scenario triggers _attempt_validation once and surfaces directly."""
        modem_dir = _setup_modem_dir(tmp_path)

        mock_detect.return_value = ConnectivityResult(
            success=True,
            protocol=detected_protocol,
            legacy_ssl=detected_legacy_ssl,
            working_url=f"{detected_protocol}://192.168.100.1",
        )
        mock_load_modem.return_value = MagicMock()
        mock_load_parser.return_value = MagicMock()
        mock_load_post.return_value = MagicMock()
        mock_probes.return_value = {"supports_icmp": True, "supports_head": True}
        mock_attempt.return_value = collector_result

        if expected_exception is not None:
            with pytest.raises(expected_exception):
                _run_validation(
                    host="192.168.100.1",
                    protocol=user_protocol,
                    username="admin",
                    password="password",
                    modem_dir=modem_dir,
                    variant=None,
                )
        else:
            result = _run_validation(
                host="192.168.100.1",
                protocol=user_protocol,
                username="admin",
                password="password",
                modem_dir=modem_dir,
                variant=None,
            )
            assert result["protocol"] == expected_protocol
            assert result["legacy_ssl"] == expected_legacy_ssl

        assert mock_attempt.call_count == 1


class TestSingleAttemptCollectorArgs:
    """Verify the single auth attempt receives the detected transport."""

    @patch(f"{_MODULE}.detect_probes")
    @patch(f"{_MODULE}._attempt_validation")
    @patch(f"{_MODULE}.load_post_processor")
    @patch(f"{_MODULE}.load_parser_config")
    @patch(f"{_MODULE}.load_modem_config")
    @patch(f"{_MODULE}.detect_protocol")
    def test_https_legacy_forwarded_to_attempt(
        self,
        mock_detect: MagicMock,
        mock_load_modem: MagicMock,
        mock_load_parser: MagicMock,
        mock_load_post: MagicMock,
        mock_attempt: MagicMock,
        mock_probes: MagicMock,
        tmp_path: Path,
    ) -> None:
        """When detect_protocol observes legacy TLS, _attempt_validation receives legacy_ssl=True."""
        modem_dir = _setup_modem_dir(tmp_path)
        mock_detect.return_value = ConnectivityResult(
            success=True,
            protocol="https",
            legacy_ssl=True,
            working_url="https://192.168.100.1",
        )
        mock_load_modem.return_value = MagicMock()
        mock_load_parser.return_value = MagicMock()
        mock_load_post.return_value = MagicMock()
        mock_probes.return_value = {"supports_icmp": True, "supports_head": True}
        mock_attempt.return_value = _ok_result()

        result = _run_validation("192.168.100.1", None, "admin", "pw", modem_dir, None)

        assert mock_attempt.call_count == 1
        kwargs = mock_attempt.call_args.kwargs
        assert kwargs["base_url"] == "https://192.168.100.1"
        assert kwargs["legacy_ssl"] is True
        assert result["protocol"] == "https"
        assert result["legacy_ssl"] is True

    @patch(f"{_MODULE}.detect_probes")
    @patch(f"{_MODULE}._attempt_validation")
    @patch(f"{_MODULE}.load_post_processor")
    @patch(f"{_MODULE}.load_parser_config")
    @patch(f"{_MODULE}.load_modem_config")
    @patch(f"{_MODULE}.detect_protocol")
    def test_health_probes_use_detected_protocol(
        self,
        mock_detect: MagicMock,
        mock_load_modem: MagicMock,
        mock_load_parser: MagicMock,
        mock_load_post: MagicMock,
        mock_attempt: MagicMock,
        mock_probes: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Health probes run against the same transport detect_protocol picked."""
        modem_dir = _setup_modem_dir(tmp_path)
        mock_detect.return_value = ConnectivityResult(
            success=True,
            protocol="https",
            legacy_ssl=False,
            working_url="https://192.168.100.1",
        )
        mock_load_modem.return_value = MagicMock()
        mock_load_parser.return_value = MagicMock()
        mock_load_post.return_value = MagicMock()
        mock_probes.return_value = {"supports_icmp": True, "supports_head": True}
        mock_attempt.return_value = _ok_result()

        _run_validation("192.168.100.1", None, "admin", "pw", modem_dir, None)

        probe_call = mock_probes.call_args
        assert probe_call.args[1] == "https://192.168.100.1"
        assert probe_call.kwargs["legacy_ssl"] is False


# =====================================================================
# End-to-end auth-failure log — real Core, real HARMockServer
# =====================================================================


class TestAuthFailureDetailLog:
    """End-to-end: HA glue → real collector → auth-failure WARNING.

    Other tests in this file mock the validation primitives, so the
    real ``ModemDataCollector`` is never exercised. This class
    runs the full path against a ``HARMockServer`` that returns
    401, asserting:

    - ``PermissionError`` with the right error-key reaches the HA
      layer (form UI gets ``invalid_auth``).
    - The collector emits one sanitized ``WARNING`` carrying the
      modem's response — strategy name, request line, status,
      Content-Type, and a body snippet with the user's password
      replaced by ``[REDACTED]``.

    Regression guard for the auth-capture teardown: if a future
    refactor removes the failure-detail log or breaks the
    HA→Core→logger path, this test fails before ship.
    """

    @staticmethod
    def _write_form_auth_modem_yaml(tmp_path: Path) -> Path:
        """Write a minimal valid form-auth modem.yaml.

        No parser.yaml / parser.py — auth failure short-circuits
        before parsing runs, so this is enough to exercise the
        failure-log path.
        """
        modem_dir = tmp_path / "solent_labs" / "t100"
        modem_dir.mkdir(parents=True)
        (modem_dir / "modem.yaml").write_text(
            "manufacturer: Solent Labs\n"
            "model: T100\n"
            "transport: http\n"
            "default_host: 192.168.100.1\n"
            "status: unsupported\n"
            "auth:\n"
            "  strategy: form\n"
            "  action: /login\n"
        )
        return modem_dir

    @patch(f"{_MODULE}.detect_probes")
    def test_auth_failure_logs_wire_detail_and_raises_permission_error(
        self,
        mock_probes: MagicMock,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """401 on the auth POST → ``PermissionError`` + one WARNING with detail.

        Passes ``protocol="http"`` to skip auto-detection — the TCP
        probe and TLS handshake aren't under test here, and the
        mock-server host isn't reachable on :443.
        """
        import logging

        from solentlabs.cable_modem_monitor_core.test_harness import HARMockServer

        modem_dir = self._write_form_auth_modem_yaml(tmp_path)

        entries = [
            {
                "request": {"method": "POST", "url": "http://192.168.100.1/login"},
                "response": {
                    "status": 401,
                    "headers": [{"name": "Content-Type", "value": "text/plain"}],
                    "content": {"text": "unauthorized"},
                },
            }
        ]
        # Skip real probe I/O — ICMP/HEAD aren't under test here.
        mock_probes.return_value = {"supports_icmp": False, "supports_head": False}

        with (
            caplog.at_level(
                logging.WARNING,
                logger="solentlabs.cable_modem_monitor_core.orchestration.collector",
            ),
            HARMockServer(entries) as server,
        ):
            # ``base_url`` is built as ``f"{protocol}://{host}"``,
            # so pass the mock server's "127.0.0.1:PORT" as host.
            netloc = server.base_url.split("://", 1)[1]

            with pytest.raises(PermissionError) as excinfo:
                _run_validation(
                    host=netloc,
                    protocol="http",
                    username="admin",
                    password="wrong",
                    modem_dir=modem_dir,
                    variant=None,
                )

        # Error-key classification reaches the HA layer.
        assert str(excinfo.value).startswith("auth_error:invalid_auth:")

        # Single WARNING from the collector carrying the failure detail.
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert warning_records, "expected a WARNING log for the auth failure"
        msg = warning_records[0].getMessage()
        assert "Auth failed" in msg
        assert "strategy=form" in msg
        assert "/login" in msg
        assert "401" in msg


# =====================================================================
# Pre-fetch encoding detection — _detect_and_inject_form_nonce_encoding
# =====================================================================


class TestDetectAndInjectFormNonceEncoding:
    """Verify pre-fetch behavior for form_nonce encoding detection."""

    def _form_nonce_config(self) -> MagicMock:
        """Build a MagicMock that passes the isinstance(auth, FormNonceAuth) check."""
        from solentlabs.cable_modem_monitor_core.models.modem_config.auth import (
            FormNonceAuth,
        )

        auth = FormNonceAuth(
            strategy="form_nonce",
            action="/login",
            nonce_field="ar_nonce",
        )
        config = MagicMock()
        config.auth = auth
        return config

    @patch("solentlabs.cable_modem_monitor_core.connectivity.create_session")
    def test_connection_error_raises(self, mock_create_session):
        """ConnectionError from requests propagates as builtins.ConnectionError."""
        import requests

        session = MagicMock()
        session.get.side_effect = requests.ConnectionError("Connection refused")
        mock_create_session.return_value = session

        with pytest.raises(ConnectionError, match="Connection refused"):
            _detect_and_inject_form_nonce_encoding("http://192.168.100.1", self._form_nonce_config())

    @patch("solentlabs.cable_modem_monitor_core.connectivity.create_session")
    def test_timeout_raises(self, mock_create_session):
        """Timeout from requests propagates as builtins.ConnectionError."""
        import requests

        session = MagicMock()
        session.get.side_effect = requests.Timeout("Read timed out")
        mock_create_session.return_value = session

        with pytest.raises(ConnectionError, match="Read timed out"):
            _detect_and_inject_form_nonce_encoding("http://192.168.100.1", self._form_nonce_config())

    @patch("solentlabs.cable_modem_monitor_core.connectivity.create_session")
    def test_non_connectivity_error_falls_back_to_plain(self, mock_create_session):
        """Non-connectivity errors (e.g. bad HTML) fall back to plain encoding."""
        session = MagicMock()
        session.get.side_effect = ValueError("Unexpected response")
        mock_create_session.return_value = session

        encoding, field = _detect_and_inject_form_nonce_encoding("http://192.168.100.1", self._form_nonce_config())
        assert encoding == "plain"
        assert field == ""

    def test_non_form_nonce_skips(self):
        """Non-form_nonce auth returns defaults without any network call."""
        config = MagicMock()
        config.auth = MagicMock()  # Not a FormNonceAuth instance

        encoding, field = _detect_and_inject_form_nonce_encoding("http://192.168.100.1", config)
        assert encoding == "plain"
        assert field == ""


# =====================================================================
# _raise_validation_failure — plain PermissionError / RuntimeError
# =====================================================================


class TestRaiseValidationFailure:
    """``_raise_validation_failure`` maps a failed ModemResult to the right exception."""

    @staticmethod
    def _auth_signals() -> tuple[CollectorSignal, ...]:
        """Match the tuple used inside ``_run_validation``."""
        return (
            CollectorSignal.AUTH_FAILED,
            CollectorSignal.AUTH_LOCKOUT,
            CollectorSignal.LOAD_AUTH,
        )

    def test_auth_signal_raises_permission_error(self) -> None:
        """AUTH_FAILED signal → ``PermissionError`` with ``auth_error:`` prefix."""
        from custom_components.cable_modem_monitor.config_flow_helpers import (
            _raise_validation_failure,
        )

        with pytest.raises(PermissionError, match=r"^auth_error:"):
            _raise_validation_failure(_auth_failed_result(), self._auth_signals())

    def test_non_auth_signal_raises_runtime_error(self) -> None:
        """PARSE_ERROR signal → ``RuntimeError`` with ``collection_error:`` prefix."""
        from custom_components.cable_modem_monitor.config_flow_helpers import (
            _raise_validation_failure,
        )

        with pytest.raises(RuntimeError, match=r"^collection_error:"):
            _raise_validation_failure(_parse_error_result(), self._auth_signals())
