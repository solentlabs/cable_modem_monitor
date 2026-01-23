"""Discovery signal types and data structures.

Signals are atomic pieces of information gathered during modem probing
that can be used to filter and identify modem candidates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class SignalType(str, Enum):
    """Types of discovery signals that can be gathered."""

    # Paradigm detection - how the modem presents data
    PARADIGM_HTML = "paradigm_html"
    PARADIGM_HNAP = "paradigm_hnap"
    PARADIGM_REST = "paradigm_rest"

    # Auth detection - authentication method signals
    AUTH_NONE = "auth_none"
    AUTH_BASIC = "auth_basic"
    AUTH_FORM = "auth_form"
    AUTH_HNAP = "auth_hnap"
    AUTH_URL_TOKEN = "auth_url_token"

    # Content signals - extracted from response content
    MODEL_STRING = "model_string"
    MANUFACTURER_HINT = "manufacturer_hint"
    HNAP_ACTION_PREFIX = "hnap_action_prefix"
    JSON_MARKER = "json_marker"
    HTML_MARKER = "html_marker"

    # Network signals - from probing behavior
    HTTP_STATUS = "http_status"
    REDIRECT_URL = "redirect_url"
    CONTENT_TYPE = "content_type"


@dataclass
class DiscoverySignal:
    """A single discovery signal gathered during probing.

    Attributes:
        signal_type: The type of signal (from SignalType enum)
        value: The signal value (model string, URL, etc.)
        confidence: Confidence level 0.0-1.0
        source: Where the signal came from (URL, header name, etc.)
        raw_data: Optional raw data for debugging
    """

    signal_type: SignalType
    value: str
    confidence: float  # 0.0 to 1.0
    source: str  # Where this signal came from (URL, header, etc.)
    raw_data: Any = None  # Optional raw data for debugging

    def __post_init__(self) -> None:
        """Validate confidence is in valid range."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be 0.0-1.0, got {self.confidence}")


@dataclass
class DiscoveryResult:
    """Aggregated discovery signals from a probing session.

    Collects all signals gathered during modem discovery and provides
    helper methods for filtering and analysis.
    """

    host: str
    timestamp: datetime = field(default_factory=datetime.now)
    signals: list[DiscoverySignal] = field(default_factory=list)

    def add_signal(self, signal: DiscoverySignal) -> None:
        """Add a signal to the result set."""
        self.signals.append(signal)

    def get_signals_by_type(self, signal_type: SignalType) -> list[DiscoverySignal]:
        """Get all signals of a specific type."""
        return [s for s in self.signals if s.signal_type == signal_type]

    def get_paradigm_signal(self) -> DiscoverySignal | None:
        """Get the highest-confidence paradigm signal.

        Returns:
            The paradigm signal with highest confidence, or None if no
            paradigm signals have been gathered.
        """
        paradigm_types = {
            SignalType.PARADIGM_HTML,
            SignalType.PARADIGM_HNAP,
            SignalType.PARADIGM_REST,
        }
        paradigm_signals = [s for s in self.signals if s.signal_type in paradigm_types]
        if not paradigm_signals:
            return None
        return max(paradigm_signals, key=lambda s: s.confidence)

    def get_highest_confidence(self, *signal_types: SignalType) -> DiscoverySignal | None:
        """Get the highest-confidence signal from the specified types.

        Args:
            signal_types: One or more SignalType values to filter by

        Returns:
            The signal with highest confidence, or None if no matching signals
        """
        matching = [s for s in self.signals if s.signal_type in signal_types]
        if not matching:
            return None
        return max(matching, key=lambda s: s.confidence)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for diagnostics export."""
        return {
            "host": self.host,
            "timestamp": self.timestamp.isoformat(),
            "signals": [
                {
                    "type": s.signal_type.value,
                    "value": s.value,
                    "confidence": s.confidence,
                    "source": s.source,
                }
                for s in self.signals
            ],
        }
