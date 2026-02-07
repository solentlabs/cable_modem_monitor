"""Tests for RESTLoader."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.cable_modem_monitor.core.loaders.rest import RESTLoader

# Test timeout constant - matches DEFAULT_TIMEOUT from schema
TEST_TIMEOUT = 10


class TestRESTLoader:
    """Tests for RESTLoader."""

    def test_fetches_json_with_ajax_headers(self):
        """REST loader should send modem API-friendly AJAX headers."""
        session = MagicMock()
        response = MagicMock()
        response.ok = True
        response.json.return_value = {"error": "ok", "data": {}}
        session.get.return_value = response

        config = {
            "timeout": TEST_TIMEOUT,
            "pages": {
                "data": {
                    "system_info": "/api/v1/system/ModelName",
                }
            },
        }

        loader = RESTLoader(
            session=session,
            base_url="https://192.168.100.1",
            modem_config=config,
        )

        resources = loader.fetch()

        assert "/api/v1/system/ModelName" in resources
        session.get.assert_called_once()
        call_url = session.get.call_args[0][0]
        call_headers = session.get.call_args[1]["headers"]
        assert call_url.startswith("https://192.168.100.1/api/v1/system/ModelName?_=")
        assert call_headers["Referer"] == "https://192.168.100.1/"
        assert call_headers["X-Requested-With"] == "XMLHttpRequest"

    def test_non_api_path_omits_ajax_header(self):
        """Non-API endpoints should keep minimal headers and no cache-buster."""
        session = MagicMock()
        response = MagicMock()
        response.ok = True
        response.json.return_value = {"ok": True}
        session.get.return_value = response

        config = {
            "timeout": TEST_TIMEOUT,
            "pages": {
                "data": {
                    "diag": "/diagnostics.json",
                }
            },
        }

        loader = RESTLoader(
            session=session,
            base_url="https://192.168.100.1",
            modem_config=config,
        )
        loader.fetch()

        session.get.assert_called_once()
        call_url = session.get.call_args[0][0]
        call_headers = session.get.call_args[1]["headers"]
        assert call_url == "https://192.168.100.1/diagnostics.json"
        assert call_headers == {"Referer": "https://192.168.100.1/", "Accept": "*/*"}
