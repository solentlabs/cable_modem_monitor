"""Tests for ResourceLoaderFactory."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.cable_modem_monitor.core.loaders import (
    HNAPLoader,
    HTMLLoader,
    ResourceLoaderFactory,
    RESTLoader,
)


class TestResourceLoaderFactory:
    """Tests for ResourceLoaderFactory.create()."""

    def test_creates_html_fetcher_by_default(self):
        """Default paradigm creates HTMLLoader."""
        session = MagicMock()
        config = {"paradigm": "html", "pages": {"data": {}}}

        fetcher = ResourceLoaderFactory.create(
            session=session,
            base_url="http://192.168.100.1",
            modem_config=config,
        )

        assert isinstance(fetcher, HTMLLoader)

    def test_creates_html_fetcher_for_html_paradigm(self):
        """Explicit html paradigm creates HTMLLoader."""
        session = MagicMock()
        config = {
            "paradigm": "html",
            "parser": {"format": {"type": "html"}},
            "pages": {"data": {}},
        }

        fetcher = ResourceLoaderFactory.create(
            session=session,
            base_url="http://192.168.100.1",
            modem_config=config,
        )

        assert isinstance(fetcher, HTMLLoader)

    def test_creates_hnap_fetcher_for_hnap_paradigm(self):
        """HNAP paradigm creates HNAPLoader."""
        session = MagicMock()
        builder = MagicMock()
        config = {
            "paradigm": "hnap",
            "pages": {"data": {}, "hnap_actions": {}},
        }

        fetcher = ResourceLoaderFactory.create(
            session=session,
            base_url="http://192.168.100.1",
            modem_config=config,
            hnap_builder=builder,
        )

        assert isinstance(fetcher, HNAPLoader)

    def test_creates_rest_fetcher_for_rest_api_paradigm(self):
        """REST API paradigm creates RESTLoader."""
        session = MagicMock()
        config = {
            "paradigm": "rest_api",
            "pages": {"data": {}},
        }

        fetcher = ResourceLoaderFactory.create(
            session=session,
            base_url="http://192.168.100.1",
            modem_config=config,
        )

        assert isinstance(fetcher, RESTLoader)

    def test_creates_rest_fetcher_for_json_format(self):
        """JSON parser format creates RESTLoader."""
        session = MagicMock()
        config = {
            "paradigm": "rest_api",
            "parser": {"format": {"type": "json"}},
            "pages": {"data": {}},
        }

        fetcher = ResourceLoaderFactory.create(
            session=session,
            base_url="http://192.168.100.1",
            modem_config=config,
        )

        assert isinstance(fetcher, RESTLoader)

    def test_passes_url_token_config_to_html_fetcher(self):
        """URL token config is passed to HTMLLoader."""
        session = MagicMock()
        config = {"paradigm": "html", "pages": {"data": {}}}
        url_token_config = {"session_cookie": "sessionId", "token_prefix": "ct_"}

        fetcher = ResourceLoaderFactory.create(
            session=session,
            base_url="http://192.168.100.1",
            modem_config=config,
            url_token_config=url_token_config,
        )

        assert isinstance(fetcher, HTMLLoader)
        assert fetcher._url_token_config == url_token_config


class TestGetUrlTokenConfig:
    """Tests for ResourceLoaderFactory.get_url_token_config()."""

    def test_returns_none_for_non_url_token_auth(self):
        """Returns None when auth strategy is not url_token."""
        config = {"auth": {"strategy": "form"}}

        result = ResourceLoaderFactory.get_url_token_config(config)

        assert result is None

    def test_returns_config_for_url_token_auth(self):
        """Returns config dict for url_token auth strategy."""
        config = {
            "auth": {
                "strategy": "url_token",
                "url_token": {
                    "session_cookie": "mySessionId",
                    "token_prefix": "tok_",
                },
            }
        }

        result = ResourceLoaderFactory.get_url_token_config(config)

        assert result == {
            "session_cookie": "mySessionId",
            "token_prefix": "tok_",
        }

    def test_returns_none_when_url_token_empty(self):
        """Returns None when url_token dict is empty."""
        config = {
            "auth": {
                "strategy": "url_token",
                "url_token": {},
            }
        }

        result = ResourceLoaderFactory.get_url_token_config(config)

        # Empty url_token returns None (strategy detected but no config)
        assert result is None
