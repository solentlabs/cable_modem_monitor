"""Catalog modem tests — schema validation, HAR replay, spec conformance.

Auto-parametrized by conftest.py:
- ``modem_yaml_path``: every modem*.yaml validates through Pydantic
- ``modem_test_case``: HAR + golden file pairs run full orchestrator cycle
  AND validate the committed golden against PARSING_SPEC contracts when
  the modem's ``status`` is ``confirmed``

No modem-specific test code here. Adding a modem = adding files.

The spec-conformance gate enforces PARSING_SPEC field contracts on
``status: confirmed`` modems only. ``awaiting_verification`` and
``unsupported`` modems are exempt — drift is expected during onboarding
and is allowed until the modem is promoted. Promotion to ``confirmed``
requires zero violations.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from solentlabs.cable_modem_monitor_core.config_loader import load_modem_config
from solentlabs.cable_modem_monitor_core.spec_conformance import validate_modem_data
from solentlabs.cable_modem_monitor_core.test_harness import (
    ModemTestCase,
    RestartTestCase,
    run_modem_restart_test,
    run_modem_test_orchestrated,
)


def test_modem_yaml_schema(modem_yaml_path: Path) -> None:
    """Every modem.yaml in the catalog passes Pydantic schema validation."""
    load_modem_config(modem_yaml_path)


def test_modem_har_replay(modem_test_case: ModemTestCase) -> None:
    """Each modem's HAR replay produces expected output via orchestrator."""
    result = run_modem_test_orchestrated(modem_test_case)
    assert result.passed, (
        f"{result.test_name}: {result.error}" if result.error else f"{result.test_name}: golden file mismatch"
    )


def test_confirmed_modem_golden_spec_conformance(modem_test_case: ModemTestCase) -> None:
    """Confirmed modems' goldens conform to PARSING_SPEC field contracts.

    Awaiting_verification and unsupported modems are skipped: drift is
    allowed during onboarding. The bar is enforced at promotion time —
    flipping ``status:`` to ``confirmed`` requires the golden to already
    pass every rule the validator enforces.
    """
    config = yaml.safe_load(modem_test_case.modem_config_path.read_text(encoding="utf-8"))
    if config.get("status") != "confirmed":
        return
    if not modem_test_case.golden_path.is_file():
        return

    data = json.loads(modem_test_case.golden_path.read_text(encoding="utf-8"))
    violations = validate_modem_data(data, modem=modem_test_case.name)

    if violations:
        details = "\n".join(f"  - {v.path} ({v.rule}): {v.value!r} — {v.message}" for v in violations)
        msg = (
            f"{modem_test_case.name}: confirmed modem has "
            f"{len(violations)} spec-conformance violation(s):\n{details}\n\n"
            f"Either fix the parser/golden, or downgrade modem.yaml "
            f"status to awaiting_verification."
        )
        raise AssertionError(msg)


def test_modem_restart_action(restart_test_case: RestartTestCase) -> None:
    """Each modem with a restart HAR fixture exercises the action pipeline against a mock server.

    Adding restart action coverage for a modem = declaring actions.restart
    with the restart click captured in test_data/modem.har (one HAR per
    variant). No test code changes needed.
    """
    result = run_modem_restart_test(restart_test_case)
    assert result.passed, f"{result.test_name}: {result.error}"
