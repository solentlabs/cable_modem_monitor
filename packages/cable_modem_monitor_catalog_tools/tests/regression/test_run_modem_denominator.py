"""A HAR the pipeline rejects stays in the fleet accuracy denominator.

Pins INTAKE_PIPELINE.md § Intake Pipeline Regression: a HAR the pipeline
cannot process scores zero against its full field count. Uses a synthetic
modem directory, not a catalog modem.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import yaml
from solentlabs.cable_modem_monitor_catalog_tools.validate_har import validate_har

# The regression runner is a script, not an installed module, so load it by path.
_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "intake_pipeline_regression.py"
_spec = importlib.util.spec_from_file_location("intake_pipeline_regression", _SCRIPT)
assert _spec is not None and _spec.loader is not None
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
run_modem = _module.run_modem

# One downstream channel of three fields plus one system_info field.
_EXPECTED = {
    "downstream": [{"channel_id": 1, "frequency": 555000000, "power": 1.5}],
    "upstream": [],
    "system_info": {"software_version": "1.0"},
}
_EXPECTED_FIELDS = 4

# A session cookie on the first request marks a post-auth capture, a validate_har hard stop.
_POST_AUTH_HAR = {
    "log": {
        "entries": [
            {
                "request": {
                    "method": "GET",
                    "url": "http://192.168.100.1/status.html",
                    "headers": [],
                    "cookies": [{"name": "sessionid", "value": "abc"}],
                },
                "response": {
                    "status": 200,
                    "headers": [{"name": "Content-Type", "value": "text/html"}],
                    "content": {"mimeType": "text/html", "text": "<html></html>"},
                },
            }
        ]
    }
}


def _write_modem_dir(root: Path) -> Path:
    """Build a minimal modem directory whose HAR fails validate_har."""
    modem_dir = root / "vendor" / "model"
    test_data = modem_dir / "test_data"
    test_data.mkdir(parents=True)
    (modem_dir / "modem.yaml").write_text(yaml.safe_dump({"manufacturer": "Vendor", "model": "Model"}))
    (modem_dir / "parser.yaml").write_text(yaml.safe_dump({}))
    (test_data / "modem.har").write_text(json.dumps(_POST_AUTH_HAR))
    (test_data / "modem.expected.json").write_text(json.dumps(_EXPECTED))
    return modem_dir


def test_validate_har_failure_scores_zero_against_full_field_count(tmp_path: Path) -> None:
    """A HAR rejected at validate_har counts every committed field and matches none."""
    modem_dir = _write_modem_dir(tmp_path)
    har_path = modem_dir / "test_data" / "modem.har"

    # Precondition: rejected for the session cookie, not for some other reason.
    validation = validate_har(har_path)
    assert not validation.valid
    assert any("session cookies" in issue for issue in validation.issues)

    result = run_modem("vendor/model", har_path, modem_dir)

    assert result.stage_failed == "validate_har"
    assert result.total_fields == _EXPECTED_FIELDS
    assert result.matching_fields == 0
