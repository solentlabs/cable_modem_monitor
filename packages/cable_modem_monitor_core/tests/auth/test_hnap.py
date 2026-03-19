"""Tests for HnapAuthManager (stub)."""

from __future__ import annotations

import requests
from solentlabs.cable_modem_monitor_core.auth.hnap import HnapAuthManager


class TestHnapAuthManager:
    """HNAP auth is a hard stop — always fails."""

    def test_always_fails(self, session: requests.Session) -> None:
        """HNAP auth returns hard-stop error."""
        manager = HnapAuthManager()
        result = manager.authenticate(session, "http://192.168.100.1", "admin", "password")
        assert result.success is False
        assert "not yet supported" in result.error
        assert "HNAP" in result.error

    def test_no_side_effects(self, session: requests.Session) -> None:
        """Session is not modified on hard stop."""
        manager = HnapAuthManager()
        manager.authenticate(session, "http://192.168.100.1", "admin", "password")
        assert session.auth is None
        assert len(session.cookies) == 0
