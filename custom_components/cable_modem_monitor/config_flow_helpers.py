"""Config flow helpers — I/O and data transformation for the setup wizard.

Wraps Core APIs (catalog browsing, connectivity probing, data
collection) in ``hass.async_add_executor_job()`` and provides
HA-specific helpers for building form schemas and classifying errors.

All blocking I/O runs in an executor thread.  This module never
blocks the HA event loop.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from solentlabs.cable_modem_monitor_catalog import CATALOG_PATH
from solentlabs.cable_modem_monitor_core.catalog_manager import (
    ModemSummary,
    VariantInfo,
    list_modems,
    list_variants,
)
from solentlabs.cable_modem_monitor_core.config_loader import (
    load_modem_config,
    load_parser_config,
)
from solentlabs.cable_modem_monitor_core.connectivity import (
    ConnectivityResult,
    detect_protocol,
    test_http_head,
    test_icmp,
)
from solentlabs.cable_modem_monitor_core.models.modem_config import ModemConfig
from solentlabs.cable_modem_monitor_core.orchestration import ModemDataCollector
from solentlabs.cable_modem_monitor_core.orchestration.models import ModemResult
from solentlabs.cable_modem_monitor_core.orchestration.signals import (
    CollectorSignal,
)
from solentlabs.cable_modem_monitor_core.test_harness.runner import (
    load_post_processor,
)

from .lib.host_validation import parse_host_input

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(f"{__package__}.config_flow")


# ---------------------------------------------------------------------------
# Auth strategy display labels
# ---------------------------------------------------------------------------

AUTH_STRATEGY_LABELS: dict[str, str] = {
    "none": "No Authentication",
    "basic": "Basic Authentication",
    "form": "Form Login",
    "form_nonce": "Form Login (Nonce)",
    "form_pbkdf2": "Form Login (PBKDF2)",
    "form_sjcl": "Form Login (SJCL)",
    "url_token": "URL Token",
    "hnap": "HNAP",
}


def format_variant_label(variant: VariantInfo) -> str:
    """Build a human-readable label for a variant dropdown entry.

    Format: ``{auth label}`` or ``{auth label} ({ISPs})``.

    Examples::

        "No Authentication"
        "Basic Authentication (Comcast, Spectrum)"
        "Form Login (Nonce)"

    Args:
        variant: Variant info from the catalog manager.
    """
    label = AUTH_STRATEGY_LABELS.get(variant.auth_strategy, variant.auth_strategy)
    if variant.isps:
        return f"{label} ({', '.join(variant.isps)})"
    return label


# ---------------------------------------------------------------------------
# Catalog browsing (async wrappers around Core sync API)
# ---------------------------------------------------------------------------


async def load_modem_catalog(hass: HomeAssistant) -> list[ModemSummary]:
    """Load all modem summaries from the catalog package.

    Runs in executor — reads YAML files from disk.
    """
    return await hass.async_add_executor_job(list_modems, CATALOG_PATH)


async def load_variant_list(
    hass: HomeAssistant,
    modem_dir: Path,
) -> list[VariantInfo]:
    """Load variant info for a modem directory.

    Runs in executor — reads YAML files from disk.
    """
    return await hass.async_add_executor_job(list_variants, modem_dir)


def _normalize_manufacturer(name: str) -> str:
    """Normalize manufacturer name to title case for display.

    modem.yaml stores the manufacturer as seen in the wild (e.g.,
    ``ARRIS``, ``Arris``). The UI presents a normalized form so
    case variations don't appear as separate entries.
    """
    return name.title()


def get_manufacturers(summaries: list[ModemSummary]) -> list[str]:
    """Extract sorted unique manufacturer names, normalized for display.

    Case variations (e.g., ``ARRIS`` and ``Arris``) are consolidated
    into a single title-case entry. The raw modem.yaml values are
    preserved — normalization is presentation-only.
    """
    return sorted({_normalize_manufacturer(s.manufacturer) for s in summaries})


def filter_by_manufacturer(
    summaries: list[ModemSummary],
    manufacturer: str,
) -> list[ModemSummary]:
    """Filter summaries to a single manufacturer (case-insensitive)."""
    return [s for s in summaries if _normalize_manufacturer(s.manufacturer) == manufacturer]


def build_model_display_name(summary: ModemSummary) -> str:
    """Build the display string for the model dropdown.

    Format: ``{manufacturer} {model}`` with aliases in parentheses
    and ``*`` for unverified.

    Remaining aliases are internal/OEM names and manufacturer rebrands
    (not distinct products). See ``MODEM_YAML_SPEC.md`` § Aliases vs
    Separate Entries for the rules.

    Examples::

        "Arris SB8200"
        "Motorola MB8611 (MB8600, MB8612)"
        "Netgear CM1100 *"
    """
    parts = [_normalize_manufacturer(summary.manufacturer), summary.model]

    if summary.model_aliases:
        parts.append(f"({', '.join(summary.model_aliases)})")

    if summary.status != "verified":
        parts.append("*")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------

# Maps exceptions to strings.json error keys.  These keys are looked
# up by HA's frontend in strings.json / translations/*.json.

_SIGNAL_ERROR_MAP: dict[CollectorSignal, str] = {
    CollectorSignal.CONNECTIVITY: "cannot_connect",
    CollectorSignal.AUTH_FAILED: "invalid_auth",
    CollectorSignal.AUTH_LOCKOUT: "invalid_auth",
    CollectorSignal.LOAD_ERROR: "cannot_connect",
    CollectorSignal.LOAD_AUTH: "invalid_auth",
    CollectorSignal.PARSE_ERROR: "parse_failed",
}


def classify_error(error: str | None, signal: CollectorSignal | None = None) -> str:
    """Classify a validation failure into a strings.json error key.

    Args:
        error: Human-readable error message (for logging).
        signal: CollectorSignal from ModemResult, if available.

    Returns:
        Error key string for HA form display.
    """
    if signal is not None:
        return _SIGNAL_ERROR_MAP.get(signal, "unknown")
    return "unknown"


# ---------------------------------------------------------------------------
# Probe detection (shared by validation pipeline and Reset Entities)
# ---------------------------------------------------------------------------


def detect_probes(
    host: str,
    base_url: str,
    modem_config: ModemConfig,
    *,
    legacy_ssl: bool = False,
) -> dict[str, bool]:
    """Detect ICMP and HTTP HEAD probe support.

    Respects modem.yaml ``health.supports_head`` as a ceiling — if the
    modem is known to reject HEAD, the test is skipped and GET is used.
    ICMP is always tested (network-dependent, modem.yaml is only a hint).

    Args:
        host: Bare hostname/IP for ICMP test.
        base_url: Full URL for HTTP HEAD test.
        modem_config: Loaded modem config (provides health defaults).
        legacy_ssl: Whether to use legacy SSL ciphers for HEAD test.

    Returns:
        Dict with ``supports_icmp`` and ``supports_head`` booleans.
    """
    health_cfg = modem_config.health
    supports_icmp = test_icmp(host)
    if health_cfg and not health_cfg.supports_head:
        supports_head = False
    else:
        supports_head = test_http_head(base_url, legacy_ssl=legacy_ssl)
    return {"supports_icmp": supports_icmp, "supports_head": supports_head}


# ---------------------------------------------------------------------------
# Validation pipeline
# ---------------------------------------------------------------------------


def _try_collect(
    modem_config: ModemConfig,
    parser_config: Any,
    post_processor: Any,
    base_url: str,
    username: str,
    password: str,
    legacy_ssl: bool,
) -> ModemResult:
    """Create a collector and execute one poll attempt.

    Factored out of :func:`_run_validation` so the protocol retry loop
    can call it with different ``base_url`` / ``legacy_ssl`` values
    without duplicating collector setup.

    Args:
        modem_config: Loaded modem configuration.
        parser_config: Loaded parser configuration (or None).
        post_processor: Loaded post-processor callable (or None).
        base_url: Full URL including protocol (e.g., ``https://192.168.100.1``).
        username: Login credential.
        password: Login credential.
        legacy_ssl: Whether to use legacy SSL ciphers.

    Returns:
        ``ModemResult`` from the collector.
    """
    collector = ModemDataCollector(
        modem_config=modem_config,
        parser_config=parser_config,
        post_processor=post_processor,
        base_url=base_url,
        username=username,
        password=password,
        legacy_ssl=legacy_ssl,
    )
    return collector.execute()


def _run_validation(
    host: str,
    protocol: str | None,
    username: str,
    password: str,
    modem_dir: Path,
    variant: str | None,
) -> dict[str, Any]:
    """Execute the full validation pipeline (sync — runs in executor).

    Pipeline:
        1. Protocol detection (HTTP/HTTPS/legacy SSL)
        2. Health-probe discovery (ICMP, HTTP HEAD)
        3. Load modem + parser config from catalog
        4. Create ModemDataCollector and execute one poll
        5. Return results for config entry

    Args:
        host: Bare hostname/IP (no protocol prefix).
        protocol: User-specified protocol, or None for auto-detect.
        username: Modem username (empty string if no auth).
        password: Modem password (empty string if no auth).
        modem_dir: Path to modem directory in catalog.
        variant: Variant name, or None for default.

    Returns:
        Dict with all fields needed for the config entry.

    Raises:
        ConnectionError: Protocol detection failed (modem unreachable).
        PermissionError: Authentication failed.
        RuntimeError: Parse/collection failed.
    """
    # -- Step 1: Protocol detection -------------------------------------------
    auto_detected_http = False
    if protocol:
        # User specified protocol — skip detection
        base_url = f"{protocol}://{host}"
        legacy_ssl = False
        _LOGGER.info("Using user-specified protocol: %s", protocol)
    else:
        conn: ConnectivityResult = detect_protocol(host)
        if not conn.success:
            raise ConnectionError(conn.error or f"Cannot connect to {host}")
        base_url = conn.working_url or f"http://{host}"
        protocol = conn.protocol or "http"
        legacy_ssl = conn.legacy_ssl
        auto_detected_http = protocol == "http"
        _LOGGER.info("Protocol detected: %s (legacy_ssl=%s)", protocol, legacy_ssl)

    # -- Step 2: Load config from catalog -------------------------------------
    modem_yaml = (modem_dir / f"modem-{variant}.yaml") if variant else (modem_dir / "modem.yaml")
    parser_yaml = modem_dir / "parser.yaml"
    parser_py = modem_dir / "parser.py"

    modem_config = load_modem_config(modem_yaml)
    parser_config = load_parser_config(parser_yaml) if parser_yaml.exists() else None
    post_processor = load_post_processor(parser_py) if parser_py.exists() else None

    # -- Step 3: Test data collection -----------------------------------------
    result = _try_collect(
        modem_config,
        parser_config,
        post_processor,
        base_url,
        username,
        password,
        legacy_ssl,
    )

    # -- Step 3a: Protocol retry (UC-85) --------------------------------------
    # Some modems respond on HTTP (port 80) but only authenticate over HTTPS.
    # If auth failed on auto-detected HTTP, retry with HTTPS before giving up.
    auth_signals = (CollectorSignal.AUTH_FAILED, CollectorSignal.AUTH_LOCKOUT, CollectorSignal.LOAD_AUTH)
    if not result.success and auto_detected_http and result.signal in auth_signals:
        _LOGGER.info("Auth failed on auto-detected HTTP — retrying with HTTPS")
        http_result = result  # preserve the original auth signal
        https_url = f"https://{host}"
        result = _try_collect(
            modem_config,
            parser_config,
            post_processor,
            https_url,
            username,
            password,
            legacy_ssl=False,
        )
        if result.success:
            base_url, protocol, legacy_ssl = https_url, "https", False
        elif result.signal in auth_signals:
            # HTTPS with modern ciphers also failed — try legacy SSL
            _LOGGER.info("HTTPS also failed — retrying with legacy SSL ciphers")
            result = _try_collect(
                modem_config,
                parser_config,
                post_processor,
                https_url,
                username,
                password,
                legacy_ssl=True,
            )
            if result.success:
                base_url, protocol, legacy_ssl = https_url, "https", True
        elif result.signal == CollectorSignal.CONNECTIVITY:
            # HTTPS not available — restore the original HTTP auth error
            # so the user sees "Login failed" instead of "Modem not responding"
            _LOGGER.info("HTTPS not available — using original HTTP auth result")
            result = http_result

    if not result.success:
        _LOGGER.error("Validation failed: signal=%s, error=%s", result.signal, result.error)
        error_key = classify_error(result.error, result.signal)
        if result.signal in auth_signals:
            raise PermissionError(f"auth_error:{error_key}:{result.error}")
        raise RuntimeError(f"collection_error:{error_key}:{result.error}")

    _LOGGER.info("Validation succeeded: %d data keys", len(result.modem_data or {}))

    # -- Step 4: Health-probe discovery ---------------------------------------
    probes = detect_probes(host, base_url, modem_config, legacy_ssl=legacy_ssl)
    supports_icmp = probes["supports_icmp"]
    supports_head = probes["supports_head"]

    # -- Step 5: Build result dict --------------------------------------------
    return {
        "protocol": protocol,
        "legacy_ssl": legacy_ssl,
        "supports_icmp": supports_icmp,
        "supports_head": supports_head,
    }


async def validate_connection(
    hass: HomeAssistant,
    *,
    host: str,
    username: str,
    password: str,
    modem_dir: Path,
    variant: str | None,
) -> dict[str, Any]:
    """Run the full validation pipeline for the config flow.

    Decomposes the raw host input, then delegates to
    :func:`_run_validation` in an executor thread.

    Args:
        hass: Home Assistant instance.
        host: Raw host input from the user (may include protocol).
        username: Modem username.
        password: Modem password.
        modem_dir: Path to modem directory in catalog.
        variant: Variant name, or None for default.

    Returns:
        Dict with protocol, legacy_ssl, supports_icmp, supports_head.

    Raises:
        ConnectionError: Modem unreachable.
        PermissionError: Authentication failed.
        RuntimeError: Collection/parse failed.
    """
    hostname, user_protocol = parse_host_input(host)

    return await hass.async_add_executor_job(
        _run_validation,
        hostname,
        user_protocol,
        username,
        password,
        modem_dir,
        variant,
    )
