"""Test case discovery from modem directory structure.

Walks a modems directory (or single modem directory) and discovers
runnable test cases — each HAR file paired with its golden file,
modem config, and parser config.

Config resolution follows MODEM_DIRECTORY_SPEC.md:
- ``modem.har`` -> ``modem.yaml``
- ``modem-{name}.har`` -> ``modem-{name}.yaml`` if exists, else ``modem.yaml``

Action test cases are discovered separately via ``discover_restart_tests``.
HAR resolution for restart tests (first match wins):

1. ``test_data/modem-restart.har`` — dedicated restart capture
2. ``test_data/modem.har`` — combined capture, when ``modem.yaml`` declares
   ``actions.restart`` (contributor captured data collection and restart in
   the same session)

No golden file is produced — pass/fail is determined by ``ActionResult.success``.

See MODEM_DIRECTORY_SPEC.md § test_data/ Directory.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModemTestCase:
    """A single discoverable modem test case.

    Attributes:
        name: Human-readable test ID (e.g., ``{manufacturer}/{model}/modem``).
        modem_dir: Path to the modem directory (parent of ``test_data/``).
        har_path: Path to the ``.har`` file.
        golden_path: Expected path to ``.expected.json``. May not exist
            on disk — the runner checks and returns a structured error.
        modem_config_path: Resolved ``modem*.yaml`` path.
        parser_config_path: Path to ``parser.yaml``, or ``None`` if
            parser.py-only.
        parser_py_path: Path to ``parser.py``, or ``None`` if absent.
    """

    name: str
    modem_dir: Path
    har_path: Path
    golden_path: Path
    modem_config_path: Path
    parser_config_path: Path | None
    parser_py_path: Path | None


def discover_modem_tests(modems_dir: Path) -> list[ModemTestCase]:
    """Discover test cases from a modems directory tree.

    Walks ``{mfr}/{model}/test_data/`` directories under *modems_dir*,
    or if *modems_dir* itself contains a ``test_data/`` subdirectory,
    treats it as a single modem directory.

    Args:
        modems_dir: Root modems directory (e.g., ``catalog/modems/``)
            or a single modem directory (e.g., ``modems/{manufacturer}/{model}``).

    Returns:
        List of discovered test cases, sorted by name.
    """
    cases: list[ModemTestCase] = []

    # Single modem directory: has test_data/ directly
    tests_subdir = modems_dir / "test_data"
    if tests_subdir.is_dir():
        _discover_from_modem_dir(modems_dir, modems_dir.parent.parent, cases)
        return sorted(cases, key=lambda c: c.name)

    # Walk {mfr}/{model}/ directories
    if not modems_dir.is_dir():
        return cases

    for mfr_dir in sorted(modems_dir.iterdir()):
        if not mfr_dir.is_dir() or mfr_dir.name.startswith("."):
            continue
        for model_dir in sorted(mfr_dir.iterdir()):
            if not model_dir.is_dir() or model_dir.name.startswith("."):
                continue
            _discover_from_modem_dir(model_dir, modems_dir, cases)

    return sorted(cases, key=lambda c: c.name)


def _discover_from_modem_dir(
    modem_dir: Path,
    root: Path,
    cases: list[ModemTestCase],
) -> None:
    """Discover test cases from a single modem directory."""
    tests_dir = modem_dir / "test_data"
    if not tests_dir.is_dir():
        return

    # Check for parser config/code
    parser_yaml = modem_dir / "parser.yaml"
    parser_py = modem_dir / "parser.py"
    has_parser_yaml = parser_yaml.is_file()
    has_parser_py = parser_py.is_file()

    if not has_parser_yaml and not has_parser_py:
        _logger.debug(
            "Skipping %s: no parser.yaml or parser.py",
            modem_dir,
        )
        return

    for har_path in sorted(tests_dir.glob("*.har")):
        if har_path.stem == "modem-restart":
            continue  # action fixture — consumed by discover_restart_tests, not data collection
        case = _build_test_case(
            har_path,
            modem_dir,
            root,
            parser_yaml if has_parser_yaml else None,
            parser_py if has_parser_py else None,
        )
        if case is not None:
            cases.append(case)


def _build_test_case(
    har_path: Path,
    modem_dir: Path,
    root: Path,
    parser_yaml: Path | None,
    parser_py: Path | None,
) -> ModemTestCase | None:
    """Build a ModemTestCase from a HAR file path.

    Returns ``None`` if modem config cannot be resolved.
    """
    stem = har_path.stem
    golden_path = har_path.with_suffix("").with_suffix(".expected.json")

    # Config resolution per MODEM_DIRECTORY_SPEC
    modem_config_path = _resolve_modem_config(stem, modem_dir)
    if modem_config_path is None:
        _logger.debug(
            "Skipping %s: no modem config resolved",
            har_path,
        )
        return None

    # Build human-readable name from path relative to root
    try:
        relative = modem_dir.relative_to(root)
        name = f"{relative}/{stem}"
    except ValueError:
        name = f"{modem_dir.name}/{stem}"

    return ModemTestCase(
        name=name,
        modem_dir=modem_dir,
        har_path=har_path,
        golden_path=golden_path,
        modem_config_path=modem_config_path,
        parser_config_path=parser_yaml,
        parser_py_path=parser_py,
    )


@dataclass(frozen=True)
class RestartTestCase:
    """A discoverable restart action test case.

    Attributes:
        name: Human-readable test ID (e.g., ``{manufacturer}/{model}/restart``).
        modem_dir: Path to the modem directory (parent of ``test_data/``).
        har_path: Resolved HAR path — ``test_data/modem-restart.har`` if present,
            else ``test_data/modem.har`` when ``modem.yaml`` declares ``actions.restart``.
        modem_config_path: Path to ``modem.yaml``.
    """

    name: str
    modem_dir: Path
    har_path: Path
    modem_config_path: Path


def discover_restart_tests(modems_dir: Path) -> list[RestartTestCase]:
    """Discover restart action test cases from a modems directory tree.

    Resolves the restart HAR via a first-match rule (see MODEM_DIRECTORY_SPEC.md
    § test_data/ Directory). Always pairs with ``modem.yaml`` — restart actions
    are declared on the primary config, not on auth variants.

    Args:
        modems_dir: Root modems directory (e.g., ``catalog/modems/``)
            or a single modem directory (e.g., ``modems/{manufacturer}/{model}``).

    Returns:
        List of discovered restart test cases, sorted by name.
    """
    cases: list[RestartTestCase] = []

    # Single modem directory: has test_data/ directly
    if (modems_dir / "test_data").is_dir():
        _discover_restart_from_modem_dir(modems_dir, modems_dir.parent.parent, cases)
        return sorted(cases, key=lambda c: c.name)

    if not modems_dir.is_dir():
        return cases

    for mfr_dir in sorted(modems_dir.iterdir()):
        if not mfr_dir.is_dir() or mfr_dir.name.startswith("."):
            continue
        for model_dir in sorted(mfr_dir.iterdir()):
            if not model_dir.is_dir() or model_dir.name.startswith("."):
                continue
            _discover_restart_from_modem_dir(model_dir, modems_dir, cases)

    return sorted(cases, key=lambda c: c.name)


def _discover_restart_from_modem_dir(
    modem_dir: Path,
    root: Path,
    cases: list[RestartTestCase],
) -> None:
    """Discover a restart test case from a single modem directory.

    HAR resolution (first match wins):
    1. ``test_data/modem-restart.har`` — dedicated restart capture
    2. ``test_data/modem.har`` — combined capture, when modem.yaml declares actions.restart
    """
    modem_config_path = modem_dir / "modem.yaml"
    if not modem_config_path.is_file():
        return

    dedicated = modem_dir / "test_data" / "modem-restart.har"
    if dedicated.is_file():
        har_path = dedicated
    else:
        # Fall back to modem.har only when actions.restart is declared.
        try:
            config = yaml.safe_load(modem_config_path.read_text(encoding="utf-8"))
        except Exception:
            return
        if not (config.get("actions") or {}).get("restart"):
            return
        combined = modem_dir / "test_data" / "modem.har"
        if not combined.is_file():
            return
        har_path = combined

    try:
        relative = modem_dir.relative_to(root)
        name = f"{relative}/restart"
    except ValueError:
        name = f"{modem_dir.name}/restart"

    cases.append(
        RestartTestCase(
            name=name,
            modem_dir=modem_dir,
            har_path=har_path,
            modem_config_path=modem_config_path,
        )
    )


def _resolve_modem_config(stem: str, modem_dir: Path) -> Path | None:
    """Resolve the modem config path for a HAR file stem.

    Resolution order (most specific wins):

    1. Exact match: ``modem-form-nonce-b64.yaml``
    2. Stem walk: strip trailing ``-segment`` and retry
       (``modem-form-nonce.yaml``, etc.)
    3. Fallback: ``modem.yaml``

    Stem walking supports test variants that share a config — e.g.,
    ``modem-form-nonce-b64.har`` reuses ``modem-form-nonce.yaml``
    when the only difference is firmware behaviour detected at
    runtime, not YAML configuration.

    Returns:
        Path to the resolved config, or ``None`` if no config found.
    """
    # Tier 1: exact match (modem-{name}.yaml or modem.yaml)
    exact = modem_dir / f"{stem}.yaml"
    if exact.is_file():
        return exact

    # Tier 2: walk up stem segments (strip last -segment each round)
    current = stem
    while "-" in current:
        current = current.rsplit("-", 1)[0]
        candidate = modem_dir / f"{current}.yaml"
        if candidate.is_file():
            return candidate

    # Tier 3: fallback to modem.yaml
    default = modem_dir / "modem.yaml"
    if default.is_file():
        return default

    return None
