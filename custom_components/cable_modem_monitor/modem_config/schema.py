"""Pydantic schema for modem.yaml configuration files.

This module defines the complete schema for declarative modem configuration.
modem.yaml is the single source of truth for each supported modem, containing:

    - Identity: manufacturer, model, brand aliases
    - Authentication: strategy, form config, HNAP config, session management
    - Detection: pre_auth (entry page), post_auth (data pages)
    - Capabilities: what data the parser can extract
    - Hardware: DOCSIS version, chipset, release/EOL dates
    - Pages: public/protected URLs, data source paths
    - Provenance: sources for facts (FCC filings, datasheets, etc.)
    - Documentation: ISPs, research notes, external references

Dual-Purpose Schema:
    modem.yaml serves two purposes, controlled by status_info.status:

    1. Parser Configuration (status: verified, awaiting_verification)
       - Requires: parser.class, parser.module
       - Used at runtime to configure working modem parsers

    2. Modem Database Entry (status: in_progress, unsupported)
       - Requires: manufacturer, model only
       - Documents modems that are WIP or have no exposed status pages
       - Populates the modem database/README for user reference

Schema Structure:
    ModemConfig (root)
    ├── AuthConfig
    │   ├── FormAuthConfig / FormSuccessConfig
    │   ├── HnapAuthConfig / HnapActionsConfig
    │   ├── UrlTokenAuthConfig
    │   ├── RestApiAuthConfig
    │   └── SessionConfig
    ├── DetectionConfig (pre_auth, post_auth)
    ├── PagesConfig (public, protected, data sources)
    ├── HardwareConfig (DOCSIS, chipset, dates)
    ├── SourcesConfig (provenance tracking)
    └── StatusMetadata (verification status)

Enums:
    - AuthStrategy: none, basic, form, hnap, url_token, rest_api
    - Capability: downstream_channels, upstream_channels, system_uptime, etc.
    - ParserStatus: in_progress, awaiting_verification, verified, unsupported
    - DataParadigm: html, hnap, rest_api

Usage:
    from modem_config.schema import ModemConfig
    config = ModemConfig(**yaml.safe_load(modem_yaml_content))

Note:
    Uses Pydantic v1 API for Home Assistant compatibility.
    Forward references resolved via update_forward_refs() at module end.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator

# =============================================================================
# ENUMS
# =============================================================================


class AuthStrategy(str, Enum):
    """Supported authentication strategies."""

    NONE = "none"  # No authentication required (all pages public)
    BASIC = "basic"  # HTTP Basic Auth (401 challenge)
    FORM = "form"  # HTML form-based login
    HNAP = "hnap"  # HNAP/SOAP protocol auth
    URL_TOKEN = "url_token"  # URL token session auth
    REST_API = "rest_api"  # JSON REST API


class PasswordEncoding(str, Enum):
    """Password encoding methods for form auth."""

    PLAIN = "plain"
    BASE64 = "base64"


class DataFormat(str, Enum):
    """Data format types."""

    HTML = "html"
    JSON = "json"
    XML = "xml"


class TableLayout(str, Enum):
    """Table layout for HTML parsing."""

    STANDARD = "standard"  # Rows = channels, cols = metrics
    TRANSPOSED = "transposed"  # Rows = metrics, cols = channels
    JAVASCRIPT_EMBEDDED = "javascript_embedded"  # Data in JS variables, not HTML tables


class DocsisVersion(str, Enum):
    """DOCSIS specification versions."""

    V30 = "3.0"
    V31 = "3.1"


class ParserStatus(str, Enum):
    """Parser verification/lifecycle status."""

    IN_PROGRESS = "in_progress"  # Actively being developed
    AWAITING_VERIFICATION = "awaiting_verification"  # Released, awaiting user confirmation
    VERIFIED = "verified"  # Confirmed working by user
    UNSUPPORTED = "unsupported"  # Modem locked down, kept for documentation


class DataParadigm(str, Enum):
    """How the modem presents data.

    Used by Discovery Intelligence to filter modem candidates.
    """

    HTML = "html"  # Traditional web pages with tables
    HNAP = "hnap"  # HNAP/SOAP protocol
    REST_API = "rest_api"  # JSON REST API


class Capability(str, Enum):
    """Modem capabilities that can be declared in modem.yaml.

    These define what data a parser can extract. The integration uses these
    to conditionally create sensor entities.

    Channel Data (required for basic functionality):
        scqam_downstream: SC-QAM downstream channels (DOCSIS 3.0+)
            Parser returns: downstream[] with power, snr, frequency, modulation
        scqam_upstream: SC-QAM/ATDMA upstream channels (DOCSIS 3.0+)
            Parser returns: upstream[] with power, frequency, modulation
        ofdm_downstream: OFDM downstream channels (DOCSIS 3.1)
            Parser returns: ofdm_downstream[] with power, snr, frequency
        ofdma_upstream: OFDMA upstream channels (DOCSIS 3.1)
            Parser returns: ofdma_upstream[] with power, frequency

    System Information:
        system_uptime: Human-readable uptime string
            Parser returns: system_info.system_uptime (e.g., "7 days 00:00:01")
        last_boot_time: Calculated boot timestamp (derived from uptime)
            Parser returns: system_info.last_boot_time (ISO format)
        hardware_version: Hardware/board version
            Parser returns: system_info.hardware_version
        software_version: Firmware/software version
            Parser returns: system_info.software_version

    Actions:
        restart: Modem supports remote restart
            Parser implements: restart(session, base_url) -> bool
    """

    # Channel data (by modulation type)
    SCQAM_DOWNSTREAM = "scqam_downstream"
    SCQAM_UPSTREAM = "scqam_upstream"
    OFDM_DOWNSTREAM = "ofdm_downstream"
    OFDMA_UPSTREAM = "ofdma_upstream"

    # System information
    SYSTEM_UPTIME = "system_uptime"
    LAST_BOOT_TIME = "last_boot_time"
    HARDWARE_VERSION = "hardware_version"
    SOFTWARE_VERSION = "software_version"

    # Actions
    RESTART = "restart"


# =============================================================================
# AUTH CONFIGURATION MODELS
# =============================================================================


class FormSuccessConfig(BaseModel):
    """Configuration for detecting successful form login."""

    redirect: str | None = Field(
        default=None,
        description="Expected redirect URL on success",
    )
    indicator: str | None = Field(
        default=None,
        description="String in response or min response length",
    )


class FormAuthConfig(BaseModel):
    """Configuration for form-based authentication.

    Used by: MB7621, CM2000, XB7, CGA2121, G54
    """

    action: str = Field(description="Form submission URL")
    method: str = Field(default="POST", description="HTTP method")
    username_field: str = Field(description="Form field name for username")
    password_field: str = Field(description="Form field name for password")
    password_encoding: PasswordEncoding = Field(
        default=PasswordEncoding.PLAIN,
        description="How password is encoded before submission",
    )
    hidden_fields: dict[str, str] = Field(
        default_factory=dict,
        description="Additional hidden form fields (CSRF, etc.)",
    )
    success: FormSuccessConfig | None = Field(
        default=None,
        description="How to detect successful login",
    )


class HnapAuthConfig(BaseModel):
    """Configuration for HNAP/SOAP authentication.

    Used by: S33, MB8611
    """

    endpoint: str = Field(default="/HNAP1/", description="HNAP endpoint URL")
    namespace: str = Field(
        default="http://purenetworks.com/HNAP1/",
        description="SOAP namespace",
    )
    empty_action_value: str = Field(
        default="",
        description="Value for empty SOAP actions (modem-specific quirk)",
    )
    formats: list[str] = Field(
        default_factory=lambda: ["json"],
        description="Supported formats in order of preference",
    )
    actions: HnapActionsConfig | None = Field(
        default=None,
        description="HNAP action names for various operations",
    )


class HnapActionsConfig(BaseModel):
    """HNAP action names for various operations."""

    login: str = Field(default="Login")
    downstream: str = Field(default="GetCustomerStatusDownstreamChannelInfo")
    upstream: str = Field(default="GetCustomerStatusUpstreamChannelInfo")
    restart: str | None = Field(default=None)


class UrlTokenAuthConfig(BaseModel):
    """Configuration for URL-based token authentication.

    Used by: SB8200
    """

    login_page: str = Field(description="Page that initiates login")
    data_page: str | None = Field(
        default=None,
        description="Page to fetch after auth. Defaults to login_page if not set.",
    )
    login_prefix: str = Field(
        default="login_",
        description="URL prefix for login token",
    )
    token_prefix: str = Field(
        default="ct_",
        description="URL prefix for session token",
    )
    session_cookie: str = Field(description="Cookie name for session")
    success_indicator: str | None = Field(
        default=None,
        description="String indicating successful auth",
    )


class RestApiAuthConfig(BaseModel):
    """Configuration for REST API authentication.

    Used by: Virgin Hub 5
    """

    base_path: str = Field(description="Base path for API endpoints")
    endpoints: dict[str, str] = Field(
        default_factory=dict,
        description="Endpoint paths for various data types",
    )


class AuthVariant(BaseModel):
    """Configuration for auth variants (firmware-specific)."""

    strategy: AuthStrategy = Field(description="Auth strategy for this variant")
    condition: str | None = Field(
        default=None,
        description="Condition for this variant (e.g., firmware version)",
    )
    fallback: bool = Field(
        default=False,
        description="Try this variant if primary fails",
    )


class AuthStrategyEntry(BaseModel):
    """A single auth strategy configuration for ordered try-until-success.

    Used in `auth.strategies[]` to define multiple auth approaches for modems
    where firmware variations change auth requirements (e.g., SB6190 with
    older firmware has no auth, newer firmware requires form auth).
    """

    strategy: AuthStrategy = Field(description="Auth strategy type")
    form: FormAuthConfig | None = Field(
        default=None,
        description="Form auth config (if strategy=form)",
    )
    hnap: HnapAuthConfig | None = Field(
        default=None,
        description="HNAP auth config (if strategy=hnap)",
    )
    url_token: UrlTokenAuthConfig | None = Field(
        default=None,
        description="URL token auth config (if strategy=url_token)",
    )


class SessionConfig(BaseModel):
    """Configuration for session management."""

    cookie_name: str | None = Field(
        default=None,
        description="Session cookie name",
    )
    max_concurrent: int = Field(
        default=0,
        description="Max concurrent sessions (0 = unlimited)",
    )
    logout_endpoint: str | None = Field(
        default=None,
        description="URL for logout (session-limited modems)",
    )
    logout_required: bool = Field(
        default=False,
        description="Whether logout is required after each operation",
    )


class AuthConfig(BaseModel):
    """Complete authentication configuration."""

    strategy: AuthStrategy = Field(
        default=AuthStrategy.NONE,
        description="Primary auth strategy (defaults to none, discovery determines actual)",
    )
    form: FormAuthConfig | None = Field(default=None)
    basic: dict[str, Any] | None = Field(default=None)
    hnap: HnapAuthConfig | None = Field(default=None)
    url_token: UrlTokenAuthConfig | None = Field(default=None)
    rest_api: RestApiAuthConfig | None = Field(default=None)
    variants: list[AuthVariant] = Field(default_factory=list)
    session: SessionConfig | None = Field(default=None)

    strategies: list[AuthStrategyEntry] = Field(
        default_factory=list,
        description="Ordered list of auth strategies to try until success. "
        "Used when firmware variations change auth requirements.",
    )
    # Note: login_markers moved to detection.pre_auth


# =============================================================================
# PAGES CONFIGURATION
# =============================================================================


class PagesConfig(BaseModel):
    """Configuration for modem pages and data sources."""

    public: list[str] = Field(
        default_factory=list,
        description="Pages that don't require authentication",
    )
    protected: list[str] = Field(
        default_factory=list,
        description="Pages that require authentication",
    )
    data: dict[str, str] = Field(
        default_factory=dict,
        description="Data source pages by type (downstream_channels, etc.)",
    )
    hnap_actions: dict[str, str] = Field(
        default_factory=dict,
        description="HNAP action names for data types",
    )


# =============================================================================
# PARSER CONFIGURATION
# =============================================================================


class DelimitersConfig(BaseModel):
    """Delimiter configuration for parsing structured text."""

    field: str = Field(default="^", description="Field delimiter")
    record: str = Field(default="|+|", description="Record delimiter")


class ParserFormatConfig(BaseModel):
    """Parser format configuration."""

    type: DataFormat = Field(default=DataFormat.HTML)
    table_layout: TableLayout = Field(default=TableLayout.STANDARD)
    delimiters: DelimitersConfig | None = Field(default=None)


class ParserConfig(BaseModel):
    """Parser configuration."""

    class_name: str = Field(alias="class", description="Parser class name")
    module: str = Field(description="Python module path")
    format: ParserFormatConfig | None = Field(default=None)


# =============================================================================
# DETECTION CONFIGURATION
# =============================================================================


class DetectionConfig(BaseModel):
    """Configuration for modem detection/identification.

    Detection uses an elimination model with AND logic:
    1. Fetch entry page (unauthenticated)
    2. Match pre_auth patterns → eliminate non-matches → candidates
    3. Authenticate using generic auth discovery (index.yaml patterns)
    4. Fetch data page (authenticated)
    5. Match post_auth patterns → eliminate more → one remaining

    All patterns in a list must match (AND logic) for the modem to
    remain a candidate.
    """

    pre_auth: list[str] = Field(
        default_factory=list,
        description="Patterns that must ALL match on the entry/login page (before auth). "
        "Used to narrow candidates when only the login form is visible. "
        "Examples: 'NETGEAR', 'MB7621', '/goform/login', 'moto.css'",
    )
    post_auth: list[str] = Field(
        default_factory=list,
        description="Patterns that must ALL match on data pages (after auth). "
        "Used to confirm modem identity when pre_auth leaves multiple candidates. "
        "Examples: 'CM2000', 'Downstream Channel Status', 'Nighthawk'",
    )
    page_hint: str | None = Field(
        default=None,
        description="Path to fetch for post_auth matching (e.g., '/DocsisStatus.htm')",
    )
    json_markers: list[str] = Field(
        default_factory=list,
        description="Patterns for REST API JSON response detection",
    )
    model_aliases: list[str] = Field(
        default_factory=list,
        description="Alternative model names (e.g., 'SuperHub 5' for 'Hub 5')",
    )


# =============================================================================
# HARDWARE CONFIGURATION
# =============================================================================


class HardwareConfig(BaseModel):
    """Hardware configuration."""

    docsis_version: DocsisVersion = Field(description="DOCSIS specification version")
    chipset: str | None = Field(default=None, description="Hardware chipset")
    release_date: str | None = Field(
        default=None,
        description="Device release date (YYYY or YYYY-MM format)",
    )
    end_of_life: str | None = Field(
        default=None,
        description="Device end-of-life date (YYYY or YYYY-MM format)",
    )


# =============================================================================
# BEHAVIORS CONFIGURATION
# =============================================================================


class BehaviorsConfig(BaseModel):
    """Special modem behaviors."""

    restart_window_seconds: int = Field(
        default=0,
        description="Seconds to ignore zero power during restart",
    )
    zero_power_during_restart: bool = Field(
        default=False,
        description="Whether modem reports zero power during restart",
    )
    requires_multi_page_fetch: bool = Field(
        default=False,
        description="Whether data requires fetching multiple pages",
    )


# =============================================================================
# PROVENANCE TRACKING
# =============================================================================


class SourcesConfig(BaseModel):
    """Provenance tracking for modem configuration facts.

    Tracks where hardware facts, auth config, and detection hints came from.
    This helps maintainers verify and update information, and helps contributors
    understand where data originated.

    Example:
        sources:
          chipset: "FCC ID: PPD-MB7621 (internal photos)"
          release_date: "https://www.motorola.com/MB7621"
          auth_config: "HAR capture from @maintainer"
          detection_hints: "PR #55 - verified"
    """

    chipset: str | None = Field(
        default=None,
        description="Source for chipset information (FCC ID, datasheet URL, etc.)",
    )
    release_date: str | None = Field(
        default=None,
        description="Source for release date (official page, press release, etc.)",
    )
    auth_config: str | None = Field(
        default=None,
        description="Source for auth configuration (HAR capture, issue #, etc.)",
    )
    detection_hints: str | None = Field(
        default=None,
        description="Source for detection hints (PR #, contributor, etc.)",
    )
    hardware: str | None = Field(
        default=None,
        description="Source for general hardware info (FCC ID, iFixit, etc.)",
    )


# =============================================================================
# METADATA CONFIGURATION
# =============================================================================


class ContributorConfig(BaseModel):
    """Contributor attribution."""

    github: str = Field(description="GitHub username")
    contribution: str = Field(description="Contribution description")


class FixturesMetadata(BaseModel):
    """Fixtures metadata."""

    path: str | None = Field(
        default=None,
        description="Relative path to fixtures directory (e.g., 'modems/arris/sb8200/fixtures')",
    )
    source: str = Field(
        default="diagnostics",
        description="Source of fixtures (diagnostics or har)",
    )
    firmware_tested: str | None = Field(
        default=None,
        description="Firmware version tested",
    )
    last_validated: str | None = Field(
        default=None,
        description="Date of last validation",
    )
    captured_from_issue: int | None = Field(
        default=None,
        description="GitHub issue number where fixtures were captured",
    )


class AttributionConfig(BaseModel):
    """Attribution configuration."""

    contributors: list[ContributorConfig] = Field(default_factory=list)


class StatusMetadata(BaseModel):
    """Parser/modem status metadata."""

    status: ParserStatus = Field(
        default=ParserStatus.AWAITING_VERIFICATION,
        description="Parser lifecycle status",
    )
    verification_source: str | None = Field(
        default=None,
        description="Link to issue, forum post, or commit confirming status",
    )


# =============================================================================
# BRAND ALIASES
# =============================================================================


class BrandAlias(BaseModel):
    """Brand alias for same hardware sold under different names.

    Example: Virgin Media Hub 5 is a rebranded Sagemcom F3896.
    Same hardware/firmware, different branding.
    """

    manufacturer: str = Field(description="Alternative manufacturer name")
    model: str = Field(description="Alternative model name")


# =============================================================================
# MAIN CONFIG MODEL
# =============================================================================


class ModemConfig(BaseModel):
    """Complete modem configuration from modem.yaml.

    This is the main schema that represents a complete modem configuration,
    covering all 16 supported modems with their various auth strategies
    and configurations.
    """

    # Identity
    manufacturer: str = Field(description="Modem manufacturer")
    model: str = Field(description="Modem model name")
    brands: list[BrandAlias] = Field(
        default_factory=list,
        description="Alternative brand names for same hardware",
    )

    # Data paradigm - how the modem presents data
    paradigm: DataParadigm = Field(
        default=DataParadigm.HTML,
        description="How modem presents data (html, hnap, rest_api)",
    )

    # Hardware
    hardware: HardwareConfig | None = Field(default=None)

    # Provenance tracking
    sources: SourcesConfig | None = Field(
        default=None,
        description="Provenance tracking for where facts came from",
    )

    # Network
    protocol: str = Field(default="http", description="HTTP or HTTPS")
    default_host: str = Field(
        default="192.168.100.1",
        description="Default modem IP address",
    )
    default_port: int = Field(default=80, description="Default port")

    # Authentication
    auth: AuthConfig = Field(description="Authentication configuration")

    # Pages
    pages: PagesConfig | None = Field(default=None)

    # Parser
    parser: ParserConfig | None = Field(default=None)

    # Detection
    detection: DetectionConfig | None = Field(default=None)

    # Capabilities - validated against Capability enum
    capabilities: list[Capability] = Field(
        default_factory=list,
        description="Supported capabilities - see Capability enum for valid values",
    )

    # Behaviors
    behaviors: BehaviorsConfig | None = Field(default=None)

    # Metadata
    status_info: StatusMetadata | None = Field(default=None)
    fixtures: FixturesMetadata | None = Field(default=None)
    attribution: AttributionConfig | None = Field(default=None)

    # Documentation (for modem database, not runtime)
    isps: list[str] = Field(
        default_factory=list,
        description="Known ISPs that use this modem (e.g., Comcast, Cox, Virgin Media)",
    )
    notes: str | None = Field(
        default=None,
        description="Research notes, known limitations, or other freeform documentation",
    )
    references: dict[str, str] = Field(
        default_factory=dict,
        description="External documentation links (e.g., {'review': 'https://...', 'gpl_source': 'https://...'})",
    )

    class Config:
        """Pydantic config."""

        populate_by_name = True

    @model_validator(mode="after")
    def validate_required_fields_by_status(self) -> ModemConfig:
        """Enforce required fields based on modem status.

        modem.yaml serves two purposes:
        1. Configuration for working parsers (verified, awaiting_verification)
        2. Documentation for unsupported/WIP modems (unsupported, in_progress)

        Working parsers require parser.class and parser.module to function.
        Documentation-only entries just need basic identity info.
        """
        status = self.status_info.status if self.status_info else None

        # These statuses indicate a working/soon-working parser
        requires_parser = status in (ParserStatus.VERIFIED, ParserStatus.AWAITING_VERIFICATION)

        if requires_parser:
            missing = []
            if not self.parser:
                missing.append("parser")
            elif not self.parser.class_name:
                missing.append("parser.class")
            elif not self.parser.module:
                missing.append("parser.module")

            if missing:
                # status is guaranteed non-None here (requires_parser check ensures it)
                status_name = status.value if status else "unknown"
                raise ValueError(
                    f"Modem with status '{status_name}' requires {', '.join(missing)}. "
                    f"Use status 'in_progress' or 'unsupported' for documentation-only entries."
                )

        return self


# =============================================================================
# RESOLVE FORWARD REFERENCES
# =============================================================================
# These models have forward references that need to be resolved after all
# classes are defined. Uses update_forward_refs() for compatibility.

FormAuthConfig.model_rebuild()
HnapAuthConfig.model_rebuild()
AuthStrategyEntry.model_rebuild()
AuthConfig.model_rebuild()
ModemConfig.model_rebuild()
