"""Tests for ``verify_diagnostics`` — diagnostics → verified.json transform.

Three test layers:

- **Fixture-pair tests** (``test_diagnostics_to_verified_json``): byte-exact
  round-trip from synthetic input JSON to expected output. Each ``*.input.json``
  in ``fixtures/verify_diagnostics/cases/`` has a sibling ``*.expected.json``;
  adding a new case = drop two files in the directory.
- **Table-driven warning + error tests**: small data overrides at module top,
  one parameterized test per concern.
- **CLI tests** via ``_main(argv=…)`` with ``capsys``: exercise the read-only
  and ``--write`` paths without spawning subprocesses.

All tests use a synthetic Solent Labs T100 / T200 catalog under
``fixtures/verify_diagnostics/catalog/`` to satisfy the no-modem-specific
references rule (docs/CODE_REVIEW.md § Test File Standards).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from solentlabs.cable_modem_monitor_catalog_tools.verify_diagnostics import (
    VerifyResult,
    _main,
    verify_diagnostics,
)

_FIXTURES = Path(__file__).parent / "fixtures" / "verify_diagnostics"
_CATALOG = _FIXTURES / "catalog"
_CASES = _FIXTURES / "cases"

_TEST_VERSION = "3.14.0-test"
_TEST_DATE = date(2026, 5, 1)


# ---------------------------------------------------------------------------
# Healthy synthetic diagnostics — base for warning/error override cases
# ---------------------------------------------------------------------------

_HEALTHY_DATA: dict[str, Any] = {
    "config_entry": {
        "manufacturer": "Solent Labs",
        "model": "T100",
        "variant": None,
    },
    "core_diagnostics": {},
    "data_coordinator": {"last_update_success": True, "update_interval": "0:10:00"},
    "health_coordinator": {"last_update_success": True, "update_interval": "0:00:30"},
    "modem_data": {"error": ""},
    "system_info": {
        "docsis_status": "Operational",
        "system_uptime": "1 day",
        "hardware_version": "1.0",
        "software_version": "1.0",
        "total_corrected": 0,
        "total_uncorrected": 0,
    },
    "downstream_channels": [{"lock_status": "locked", "channel_id": 1}],
    "upstream_channels": [{"lock_status": "locked", "channel_id": 1}],
}


def _write_diag(tmp_path: Path, data: dict[str, Any]) -> Path:
    """Write a synthetic HA-shaped diagnostics file to a tmp path."""
    diag = {"home_assistant": {}, "data": data}
    diag_path = tmp_path / "diag.json"
    diag_path.write_text(json.dumps(diag), encoding="utf-8")
    return diag_path


def _patched(**overrides: Any) -> dict[str, Any]:
    """Healthy base with top-level data-section overrides applied."""
    return {**_HEALTHY_DATA, **overrides}


# ---------------------------------------------------------------------------
# Fixture-pair tests: byte-exact transform contract
# ---------------------------------------------------------------------------

_CASE_NAMES = sorted(p.stem.removesuffix(".input") for p in _CASES.glob("*.input.json"))


@pytest.mark.parametrize("case", _CASE_NAMES)
def test_diagnostics_to_verified_json_byte_exact(case: str) -> None:
    """Each *.input.json renders to its sibling *.expected.json byte-exact."""
    input_path = _CASES / f"{case}.input.json"
    expected = (_CASES / f"{case}.expected.json").read_text(encoding="utf-8")

    result = verify_diagnostics(
        input_path,
        version=_TEST_VERSION,
        catalog_root=_CATALOG,
        verified_at=_TEST_DATE,
    )

    assert result.serialize() == expected


def test_paths_resolve_to_correct_variant_files() -> None:
    """Multi-variant modem with variant='basic' targets modem-basic.* files."""
    result = verify_diagnostics(
        _CASES / "multi_variant_basic.input.json",
        version=_TEST_VERSION,
        catalog_root=_CATALOG,
        verified_at=_TEST_DATE,
    )

    assert result.variant == "basic"
    assert result.verified_path.name == "modem-basic.verified.json"
    assert result.yaml_path.name == "modem-basic.yaml"


def test_paths_resolve_to_unsuffixed_files_for_null_variant() -> None:
    """variant=None targets modem.verified.json and modem.yaml (no suffix)."""
    result = verify_diagnostics(
        _CASES / "single_variant.input.json",
        version=_TEST_VERSION,
        catalog_root=_CATALOG,
        verified_at=_TEST_DATE,
    )

    assert result.variant is None
    assert result.verified_path.name == "modem.verified.json"
    assert result.yaml_path.name == "modem.yaml"


# ---------------------------------------------------------------------------
# Warning tests: table-driven
# ---------------------------------------------------------------------------

_PARTIAL_SYSTEM_INFO = {**_HEALTHY_DATA["system_info"], "hardware_version": None}
_PII_SYSTEM_INFO = {
    **_HEALTHY_DATA["system_info"],
    "mac_address": "50:bb:9f:53:92:10",
    "serial_number": "469930085355204103",
}

_WARNING_CASES = [
    pytest.param(
        _patched(data_coordinator={"last_update_success": False, "update_interval": "0:10:00"}),
        "last_update_success is false",
        id="last_update_success_false",
    ),
    pytest.param(
        _patched(modem_data={"error": "auth failed"}),
        "modem_data.error is non-empty",
        id="modem_data_error_nonempty",
    ),
    pytest.param(
        _patched(last_error={"type": "Foo", "message": "boom"}),
        "diagnostics contains 'last_error'",
        id="last_error_present",
    ),
    pytest.param(
        _patched(downstream_channels=[]),
        "downstream_channels is empty",
        id="empty_downstream",
    ),
    pytest.param(
        _patched(upstream_channels=[]),
        "upstream_channels is empty",
        id="empty_upstream",
    ),
    pytest.param(
        _patched(system_info=_PARTIAL_SYSTEM_INFO),
        "system_info missing fields",
        id="partial_system_info",
    ),
    pytest.param(
        _patched(system_info=_PII_SYSTEM_INFO),
        "stripped PII from system_info",
        id="pii_system_info_stripped",
    ),
]


@pytest.mark.parametrize("data,expected_substring", _WARNING_CASES)
def test_warning_triggers(
    tmp_path: Path,
    data: dict[str, Any],
    expected_substring: str,
) -> None:
    """Each warning condition surfaces a recognizable message."""
    diag_path = _write_diag(tmp_path, data)

    result = verify_diagnostics(
        diag_path,
        version=_TEST_VERSION,
        catalog_root=_CATALOG,
        verified_at=_TEST_DATE,
    )

    assert any(
        expected_substring in w for w in result.warnings
    ), f"expected warning containing {expected_substring!r}, got: {result.warnings}"


def test_pii_fields_stripped_from_system_info(tmp_path: Path) -> None:
    """mac_address and serial_number are removed from the built fixture."""
    diag_path = _write_diag(tmp_path, _patched(system_info=_PII_SYSTEM_INFO))

    result = verify_diagnostics(
        diag_path,
        version=_TEST_VERSION,
        catalog_root=_CATALOG,
        verified_at=_TEST_DATE,
    )

    sysinfo = result.verified_json["system_info"]
    assert "mac_address" not in sysinfo
    assert "serial_number" not in sysinfo
    assert sysinfo["docsis_status"] == "Operational"  # non-PII fields retained


def test_no_warnings_on_healthy_diagnostics(tmp_path: Path) -> None:
    """A clean healthy payload produces zero warnings."""
    diag_path = _write_diag(tmp_path, _HEALTHY_DATA)

    result = verify_diagnostics(
        diag_path,
        version=_TEST_VERSION,
        catalog_root=_CATALOG,
        verified_at=_TEST_DATE,
    )

    assert result.warnings == []


# ---------------------------------------------------------------------------
# Error tests: table-driven
# ---------------------------------------------------------------------------

# Each row: (id, mutation_callable_or_none, exception_type, message_substring).
# A mutation of None means "skip writing the diag file" (FileNotFoundError test).

_ERROR_CASES = [
    pytest.param(
        None,
        FileNotFoundError,
        "Diagnostics file not found",
        id="missing_diagnostics_file",
    ),
    pytest.param(
        lambda d: {"no_data_wrapper": True},
        ValueError,
        "missing top-level 'data' object",
        id="missing_data_wrapper",
    ),
    pytest.param(
        lambda d: {"home_assistant": {}, "data": {**d, "config_entry": {"manufacturer": "Solent Labs"}}},
        ValueError,
        "missing manufacturer/model",
        id="missing_model",
    ),
    pytest.param(
        lambda d: {"home_assistant": {}, "data": {**d, "config_entry": {**d["config_entry"], "model": "Unknown"}}},
        FileNotFoundError,
        "Modem package not found in catalog",
        id="model_not_in_catalog",
    ),
]


@pytest.mark.parametrize("mutation,exc_type,msg", _ERROR_CASES)
def test_error_paths(
    tmp_path: Path,
    mutation: Any,
    exc_type: type[Exception],
    msg: str,
) -> None:
    """Each error condition raises the expected exception with a clear message."""
    diag_path = tmp_path / "diag.json"

    if mutation is None:
        # Don't write the file at all
        pass
    else:
        payload = mutation(_HEALTHY_DATA)
        diag_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(exc_type, match=msg):
        verify_diagnostics(
            diag_path,
            version=_TEST_VERSION,
            catalog_root=_CATALOG,
            verified_at=_TEST_DATE,
        )


# ---------------------------------------------------------------------------
# Direct asserts: shape invariants
# ---------------------------------------------------------------------------


def test_serialize_ends_with_object_close_and_newline() -> None:
    """Output always ends with '\\n}\\n' to match catalog convention."""
    result = verify_diagnostics(
        _CASES / "single_variant.input.json",
        version=_TEST_VERSION,
        catalog_root=_CATALOG,
        verified_at=_TEST_DATE,
    )

    assert result.serialize().endswith("\n}\n")


def test_serialize_renders_channel_objects_one_per_line() -> None:
    """Each channel object occupies a single line in the rendered output."""
    result = verify_diagnostics(
        _CASES / "multi_variant_basic.input.json",
        version=_TEST_VERSION,
        catalog_root=_CATALOG,
        verified_at=_TEST_DATE,
    )

    output = result.serialize()
    inside_array = False
    for line in output.splitlines():
        if '"downstream_channels": [' in line or '"upstream_channels": [' in line:
            inside_array = True
            continue
        if inside_array and line.strip() == "]" or line.strip() == "],":
            inside_array = False
            continue
        if inside_array:
            stripped = line.strip().rstrip(",")
            assert stripped.startswith("{") and stripped.endswith(
                "}"
            ), f"expected single-line channel object, got: {line!r}"


def test_verify_result_is_dataclass() -> None:
    """Sanity check the public API returns a VerifyResult."""
    result = verify_diagnostics(
        _CASES / "single_variant.input.json",
        version=_TEST_VERSION,
        catalog_root=_CATALOG,
        verified_at=_TEST_DATE,
    )

    assert isinstance(result, VerifyResult)


def test_default_catalog_root_resolves_from_installed_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When catalog_root is None, the function imports CATALOG_PATH.

    Monkeypatch the imported module so we don't hit the real catalog
    and can assert the fallback path actually runs.
    """
    import solentlabs.cable_modem_monitor_catalog as catalog_pkg

    monkeypatch.setattr(catalog_pkg, "CATALOG_PATH", _CATALOG)

    diag_path = _write_diag(tmp_path, _HEALTHY_DATA)
    result = verify_diagnostics(
        diag_path,
        version=_TEST_VERSION,
        verified_at=_TEST_DATE,
    )

    assert result.manufacturer == "Solent Labs"


def test_serialize_handles_missing_channel_arrays() -> None:
    """A verified_json missing channel arrays still serializes cleanly."""
    skeleton = {
        "verified_at": "2026-05-01",
        "version": _TEST_VERSION,
        "config_entry": {"manufacturer": "Solent Labs", "model": "T100"},
    }
    result = VerifyResult(
        verified_json=skeleton,
        verified_path=Path("/dev/null"),
        yaml_path=Path("/dev/null"),
        manufacturer="Solent Labs",
        model="T100",
        variant=None,
    )

    output = result.serialize()

    assert output.endswith("\n}\n")
    assert "downstream_channels" not in output
    assert "upstream_channels" not in output


def test_manufacturer_override_resolves_when_field_absent(tmp_path: Path) -> None:
    """When config_entry doesn't expose manufacturer/model, override fills the gap."""
    sparse_data = {
        "config_entry": {"title": "Solent Labs T100 (192.168.100.1)", "host": "192.168.100.1"},
        "core_diagnostics": {},
        "data_coordinator": {"last_update_success": True, "update_interval": "0:10:00"},
        "health_coordinator": {"last_update_success": True, "update_interval": "0:00:30"},
        "modem_data": {"error": ""},
        "system_info": _HEALTHY_DATA["system_info"],
        "downstream_channels": _HEALTHY_DATA["downstream_channels"],
        "upstream_channels": _HEALTHY_DATA["upstream_channels"],
    }
    diag_path = _write_diag(tmp_path, sparse_data)

    result = verify_diagnostics(
        diag_path,
        version=_TEST_VERSION,
        catalog_root=_CATALOG,
        verified_at=_TEST_DATE,
        manufacturer_override="Solent Labs",
        model_override="T100",
    )

    assert result.manufacturer == "Solent Labs"
    assert result.model == "T100"
    assert result.variant is None


def test_model_override_resolves_catalog_dir_mismatch(tmp_path: Path) -> None:
    """Diagnostics says model 'T100', catalog dir is 't200' — override wins."""
    diag_path = _write_diag(tmp_path, _HEALTHY_DATA)

    result = verify_diagnostics(
        diag_path,
        version=_TEST_VERSION,
        catalog_root=_CATALOG,
        verified_at=_TEST_DATE,
        model_override="T200",
        variant_override="basic",
    )

    assert result.model == "T200"
    assert result.variant == "basic"
    assert result.verified_path.name == "modem-basic.verified.json"


def test_variant_override_empty_string_forces_none(tmp_path: Path) -> None:
    """Passing variant_override='' forces single-variant resolution.

    An empty string is the explicit "no variant" signal at the CLI
    boundary (since None already means "fall through to config_entry").
    """
    data_with_variant = _patched(config_entry={**_HEALTHY_DATA["config_entry"], "model": "T200", "variant": "basic"})
    diag_path = _write_diag(tmp_path, data_with_variant)

    result = verify_diagnostics(
        diag_path,
        version=_TEST_VERSION,
        catalog_root=_CATALOG,
        verified_at=_TEST_DATE,
        variant_override="",
    )

    assert result.variant is None
    assert result.verified_path.name == "modem.verified.json"


def test_imported_system_info_fields_drive_warnings(tmp_path: Path) -> None:
    """Smoke-check the SYSTEM_INFO_FIELDS registry import is wired up.

    Removing ``docsis_status`` (a registry-managed Tier-1 field) must
    surface a partial-confirmation warning. If the import broke, no
    warning would fire and this test would catch it.
    """
    data = _patched(system_info={**_HEALTHY_DATA["system_info"], "docsis_status": None})
    diag_path = _write_diag(tmp_path, data)

    result = verify_diagnostics(
        diag_path,
        version=_TEST_VERSION,
        catalog_root=_CATALOG,
        verified_at=_TEST_DATE,
    )

    assert any("docsis_status" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


def test_cli_read_only_prints_paths_and_skips_write(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Without --write, the CLI prints metadata but writes no file."""
    diag_path = _write_diag(tmp_path, _HEALTHY_DATA)
    target = _CATALOG / "solent_labs" / "t100" / "test_data" / "modem.verified.json"
    if target.exists():
        target.unlink()

    code = _main(
        [
            str(diag_path),
            "--version",
            _TEST_VERSION,
            "--verified-at",
            _TEST_DATE.isoformat(),
            "--catalog-root",
            str(_CATALOG),
        ]
    )

    out = capsys.readouterr()
    assert code == 0
    assert "Solent Labs" in out.out
    assert "T100" in out.out
    assert "read-only" in out.out
    assert not target.exists()


def test_cli_write_creates_verified_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """With --write, the CLI writes the file and announces the path."""
    diag_path = _write_diag(tmp_path, _HEALTHY_DATA)
    target = _CATALOG / "solent_labs" / "t100" / "test_data" / "modem.verified.json"
    if target.exists():
        target.unlink()

    code = _main(
        [
            str(diag_path),
            "--version",
            _TEST_VERSION,
            "--verified-at",
            _TEST_DATE.isoformat(),
            "--catalog-root",
            str(_CATALOG),
            "--write",
        ]
    )

    try:
        out = capsys.readouterr()
        assert code == 0
        assert target.exists()
        assert "wrote" in out.out
        assert target.read_text(encoding="utf-8").endswith("\n}\n")
    finally:
        if target.exists():
            target.unlink()


def test_cli_returns_nonzero_on_missing_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A missing diagnostics path exits 1 with stderr explanation."""
    code = _main(
        [
            str(tmp_path / "nope.json"),
            "--version",
            _TEST_VERSION,
            "--catalog-root",
            str(_CATALOG),
        ]
    )

    err = capsys.readouterr().err
    assert code == 1
    assert "Diagnostics file not found" in err


def test_cli_prints_warnings_to_stderr(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Warnings go to stderr, not stdout (so pipelines can split them)."""
    data = _patched(downstream_channels=[])
    diag_path = _write_diag(tmp_path, data)

    code = _main(
        [
            str(diag_path),
            "--version",
            _TEST_VERSION,
            "--verified-at",
            _TEST_DATE.isoformat(),
            "--catalog-root",
            str(_CATALOG),
        ]
    )

    captured = capsys.readouterr()
    assert code == 0
    assert "warnings:" in captured.err
    assert "downstream_channels is empty" in captured.err
