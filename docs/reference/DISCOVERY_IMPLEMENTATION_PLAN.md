# Discovery Intelligence Implementation Plan

> **Epic:** Constraint-Based Discovery with Actionable Intelligence
> **Target:** v3.12.0+
> **Status:** Planning

## Overview

Transform modem discovery from "try all parsers" to a signal-based constraint satisfaction system that produces actionable intelligence for both matched and unmatched modems.

## Prerequisites

Before starting, complete these cleanups from the modem.yaml migration:

- [ ] Hardcode HNAP protocol constants (endpoint, namespace, empty_action_value)
- [ ] Remove redundant `auth.hnap` section from S33/MB8611 modem.yaml (keep only `pages.hnap_actions`)
- [ ] Keep `auth.url_token` in SB8200 modem.yaml (modem-specific, required)
- [ ] Update adapter to return HNAP constants directly (not from modem.yaml)

---

## Phase 1: Foundation

**Goal:** Simplify current state, establish protocol constants

### Tasks

#### 1.1 Create HNAP Protocol Constants
```python
# custom_components/cable_modem_monitor/core/protocols/hnap.py

HNAP_ENDPOINT = "/HNAP1/"
HNAP_NAMESPACE = "http://purenetworks.com/HNAP1/"
HNAP_EMPTY_ACTION_VALUE = ""
HNAP_CONTENT_TYPE = "application/json"
```

#### 1.2 Update HNAP Auth Handler
- Import constants from protocol module
- Remove dependency on modem.yaml for protocol-level config
- Keep modem.yaml dependency for action names only

#### 1.3 Simplify modem.yaml Files
- S33: Remove `auth.hnap` section (use protocol constants)
- MB8611: Remove `auth.hnap` section (use protocol constants)
- SB8200: Keep `auth.url_token` (modem-specific)

#### 1.4 Update Adapter
- `get_hnap_hints()` returns protocol constants (hardcoded)
- `get_js_auth_hints()` still reads from modem.yaml

### Deliverables
- [ ] `core/protocols/hnap.py` with constants
- [ ] Updated auth handler using constants
- [ ] Simplified modem.yaml files
- [ ] All tests passing

---

## Phase 2: Discovery Signals Framework

**Goal:** Define signal types and capture infrastructure

### Tasks

#### 2.1 Define Signal Types
```python
# custom_components/cable_modem_monitor/core/discovery/signals.py

from enum import Enum
from dataclasses import dataclass

class SignalType(Enum):
    PARADIGM_HTML = "paradigm_html"
    PARADIGM_HNAP = "paradigm_hnap"
    PARADIGM_REST = "paradigm_rest"
    AUTH_NONE = "auth_none"
    AUTH_BASIC = "auth_basic"
    AUTH_FORM = "auth_form"
    MODEL_STRING = "model_string"
    MANUFACTURER_HINT = "manufacturer_hint"
    HNAP_ACTION_PREFIX = "hnap_action_prefix"

@dataclass
class DiscoverySignal:
    signal_type: SignalType
    value: str
    confidence: float  # 0.0 to 1.0
    source: str  # Where this signal came from
```

#### 2.2 Create Signal Collectors
```python
# Paradigm detection
def detect_paradigm(host: str, session) -> list[DiscoverySignal]:
    """Probe endpoints and detect data paradigm."""

# Auth detection (enhance existing)
def detect_auth_signals(response) -> list[DiscoverySignal]:
    """Extract auth-related signals from response."""

# Content analysis
def extract_content_signals(html: str) -> list[DiscoverySignal]:
    """Extract model strings, manufacturer hints from content."""
```

#### 2.3 Signal Aggregator
```python
@dataclass
class DiscoveryResult:
    signals: list[DiscoverySignal]
    timestamp: datetime
    host: str

    def get_signals_by_type(self, signal_type: SignalType) -> list[DiscoverySignal]:
        ...

    def to_dict(self) -> dict:
        """For diagnostics export."""
```

### Deliverables
- [ ] `core/discovery/signals.py` with types
- [ ] `core/discovery/collectors.py` with signal collectors
- [ ] Integration with existing auth discovery
- [ ] Signals captured in diagnostics

---

## Phase 3: modem.yaml Constraints

**Goal:** Add paradigm field, make modem.yaml usable for filtering

### Tasks

#### 3.1 Update Schema
```python
# In schema.py

class DataParadigm(str, Enum):
    HTML = "html"
    HNAP = "hnap"
    REST_API = "rest_api"

class ModemConfig(BaseModel):
    # ... existing fields ...
    paradigm: DataParadigm = Field(
        default=DataParadigm.HTML,
        description="How modem presents data"
    )
```

#### 3.2 Update modem.yaml Files
Add `paradigm` field to all modem.yaml files:
```yaml
# HNAP modems
paradigm: hnap

# REST API modems
paradigm: rest_api

# HTML modems (default, can be omitted)
paradigm: html
```

#### 3.3 Create Constraint Matcher
```python
# core/discovery/constraints.py

def modem_matches_signals(
    modem_config: ModemConfig,
    signals: list[DiscoverySignal]
) -> tuple[bool, float, list[str]]:
    """
    Check if modem config matches discovery signals.

    Returns:
        (matches: bool, confidence: float, reasons: list[str])
    """
```

### Deliverables
- [ ] Updated schema with `paradigm` field
- [ ] All modem.yaml files updated
- [ ] Constraint matcher function
- [ ] Tests for constraint matching

---

## Phase 4: Discovery Filtering

**Goal:** Use signals to filter modem candidates

### Tasks

#### 4.1 Candidate Filter
```python
# core/discovery/filter.py

def filter_candidates(
    signals: list[DiscoverySignal],
    all_configs: list[ModemConfig]
) -> list[tuple[ModemConfig, float, list[str]]]:
    """
    Filter modem configs by signals.

    Returns list of (config, match_score, match_reasons) sorted by score.
    """
```

#### 4.2 Integrate with Existing Discovery
- Call filter before iterating parsers
- Use filtered list to prioritize parser order
- Log filtering decisions for debugging

#### 4.3 Parser Detection Optimization
- Skip parsers whose modem.yaml doesn't match signals
- Only call `can_parse()` on likely candidates
- Fall back to full iteration if filtering produces no matches

### Deliverables
- [ ] Candidate filter function
- [ ] Integration with auth discovery
- [ ] Optimized parser detection
- [ ] Performance benchmarks

---

## Phase 5: Discovery Intelligence Reports

**Goal:** Produce actionable output for unmatched modems

### Tasks

#### 5.1 Report Generator
```python
# core/discovery/report.py

@dataclass
class DiscoveryReport:
    host: str
    signals: list[DiscoverySignal]
    candidates: list[CandidateMatch]
    recommendation: str
    next_steps: list[str]

    def to_markdown(self) -> str:
        """Human-readable report."""

    def to_dict(self) -> dict:
        """For diagnostics JSON."""

@dataclass
class CandidateMatch:
    config: ModemConfig
    score: float
    matches: list[str]
    mismatches: list[str]
```

#### 5.2 Recommendation Engine
```python
def generate_recommendation(
    signals: list[DiscoverySignal],
    candidates: list[CandidateMatch]
) -> tuple[str, list[str]]:
    """
    Generate recommendation and next steps.

    Cases:
    - Exact match: "Detected as {model}"
    - Close match: "Appears to be variant of {model}"
    - No match: "Unknown modem, captures needed"
    """
```

#### 5.3 Integration Points
- Show report in config flow when no match
- Include in diagnostics JSON
- Log for debugging

### Deliverables
- [ ] Report data structures
- [ ] Recommendation engine
- [ ] Markdown and JSON formatters
- [ ] Config flow integration

---

## Phase 6: Integration

**Goal:** Connect discovery intelligence to existing workflows

### Tasks

#### 6.1 Diagnostics Integration
- Include DiscoveryReport in diagnostics download
- Capture all signals gathered during setup
- Include closest matches and reasons

#### 6.2 Triage Skill Integration
- Update `modem-request-triage` skill to use discovery data
- Auto-extract relevant info from diagnostics
- Generate PR/modem.yaml from close matches

#### 6.3 Issue Template Updates
- Update issue templates to reference discovery report
- Add fields for common signals
- Link to closest match if identified

#### 6.4 User-Facing Messages
- Improve "unsupported modem" message in HA
- Show discovery report in config flow
- Provide clear next steps

### Deliverables
- [ ] Diagnostics includes discovery data
- [ ] Updated triage skill
- [ ] Improved issue templates
- [ ] Better user messaging

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Time to add new modem (variant) | ~2 hours | ~15 minutes |
| User friction for unsupported modem | High (unclear next steps) | Low (actionable guidance) |
| Discovery accuracy | N/A | >90% correct paradigm detection |
| Parser detection time | O(n) all parsers | O(k) filtered candidates |

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Signal detection false positives | Wrong modem selected | Require parser.can_parse() confirmation |
| Over-engineering | Delayed delivery | YAGNI - implement only what's needed |
| Breaking existing detection | Regression | Keep current detection as fallback |
| Performance regression | Slower setup | Benchmark and optimize probing |

---

## Dependencies

- modem.yaml migration complete (current work)
- Existing auth discovery system
- Diagnostics download system
- modem-request-triage skill

---

## Open Questions

1. Should paradigm detection happen before or after auth discovery?
2. How to handle modems that support multiple paradigms (rare)?
3. Should discovery report be shown in HA UI or just in logs/diagnostics?
4. How much probing is acceptable during setup (latency vs accuracy)?

---

## Future Enhancements

- **Pre-commit modem.yaml validation**: Add hook to validate all modem.yaml files against Pydantic schema before commit. Catches invalid configs (null fields, unknown enum values) before they hit main.

---

**Document Version:** 1.0
**Created:** January 2026
**Author:** Ken Schulz (@kwschulz)
