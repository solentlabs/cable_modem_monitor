"""Health configuration for modem.yaml.

Per MODEM_YAML_SPEC.md Health section.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class HealthConfig(BaseModel):
    """Health check probe configuration.

    Controls which probes the HealthMonitor runs. All default to True
    -- only override for modems with known limitations.

    Attributes:
        http_probe: Whether HTTP health probes are enabled. Set to
            False for fragile modems where HTTP traffic between
            collections risks crashes.
        supports_head: Whether the modem handles HTTP HEAD correctly.
            Set to False for modems that return 405 or unexpected
            responses. When False, HTTP probes use GET instead.
        supports_icmp: Whether ICMP ping is expected to work. Network-
            dependent hint -- auto-detection during setup overrides.
    """

    model_config = ConfigDict(extra="forbid")
    http_probe: bool = True
    supports_head: bool = True
    supports_icmp: bool = True
