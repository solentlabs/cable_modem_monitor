"""Integration tests for HNAP SOAP challenge-response authentication.

These tests verify the full HNAP authentication workflow:
1. Initial login request with username/password
2. Server returns Challenge + PublicKey + Cookie
3. Client computes HMAC-based private key
4. Subsequent requests include HNAP_AUTH header
5. Data fetches use authenticated session

Tests the HNAP_SESSION auth pattern using synthetic mock servers.
"""

from __future__ import annotations

import requests

from custom_components.cable_modem_monitor.core.auth.handler import AuthHandler
from custom_components.cable_modem_monitor.core.auth.types import AuthStrategyType
from tests.integration.conftest import HNAPSoapMockHandler


class TestHNAPSoapLogin:
    """Test HNAP SOAP login with challenge-response."""

    def test_soap_login_returns_challenge(self, hnap_soap_server):
        """Verify SOAP login request receives challenge response."""
        session = requests.Session()
        session.verify = False

        # Build SOAP login envelope
        envelope = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <Login xmlns="http://purenetworks.com/HNAP1/">
      <Username>admin</Username>
      <Password>password</Password>
    </Login>
  </soap:Body>
</soap:Envelope>"""

        response = session.post(
            f"{hnap_soap_server.url}/HNAP1/",
            data=envelope,
            headers={
                "SOAPAction": '"http://purenetworks.com/HNAP1/Login"',
                "Content-Type": "text/xml; charset=utf-8",
            },
            timeout=10,
        )

        assert response.status_code == 200
        assert "<LoginResult>OK</LoginResult>" in response.text
        assert "<Challenge>" in response.text
        assert "<PublicKey>" in response.text
        assert "<Cookie>" in response.text

    def test_soap_login_invalid_credentials_fails(self, hnap_soap_server):
        """Verify SOAP login with wrong credentials fails."""
        session = requests.Session()
        session.verify = False

        envelope = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <Login xmlns="http://purenetworks.com/HNAP1/">
      <Username>wrong</Username>
      <Password>wrong</Password>
    </Login>
  </soap:Body>
</soap:Envelope>"""

        response = session.post(
            f"{hnap_soap_server.url}/HNAP1/",
            data=envelope,
            headers={
                "SOAPAction": '"http://purenetworks.com/HNAP1/Login"',
                "Content-Type": "text/xml; charset=utf-8",
            },
            timeout=10,
        )

        assert response.status_code == 200
        assert "<LoginResult>FAILED</LoginResult>" in response.text

    def test_soap_login_sets_session_cookie(self, hnap_soap_server):
        """Verify SOAP login sets session cookie."""
        session = requests.Session()
        session.verify = False

        envelope = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <Login xmlns="http://purenetworks.com/HNAP1/">
      <Username>admin</Username>
      <Password>password</Password>
    </Login>
  </soap:Body>
</soap:Envelope>"""

        response = session.post(
            f"{hnap_soap_server.url}/HNAP1/",
            data=envelope,
            headers={
                "SOAPAction": '"http://purenetworks.com/HNAP1/Login"',
                "Content-Type": "text/xml; charset=utf-8",
            },
            timeout=10,
        )

        assert response.status_code == 200
        # Session should have received a cookie
        assert len(session.cookies) > 0 or "Set-Cookie" in response.headers


class TestHNAPDataFetch:
    """Test HNAP data fetching after authentication."""

    def test_data_fetch_without_auth_fails(self, hnap_soap_server):
        """Verify data fetch without HNAP_AUTH header fails."""
        session = requests.Session()
        session.verify = False

        # Try to fetch data without authenticating
        envelope = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <GetMotoStatusConnectionInfo xmlns="http://purenetworks.com/HNAP1/">
    </GetMotoStatusConnectionInfo>
  </soap:Body>
</soap:Envelope>"""

        response = session.post(
            f"{hnap_soap_server.url}/HNAP1/",
            data=envelope,
            headers={
                "SOAPAction": '"http://purenetworks.com/HNAP1/GetMotoStatusConnectionInfo"',
                "Content-Type": "text/xml; charset=utf-8",
            },
            timeout=10,
        )

        assert response.status_code == 200
        assert "SessionTimeout" in response.text or "Error" in response.text

    def test_data_fetch_with_auth_succeeds(self, hnap_soap_server):
        """Verify data fetch with HNAP_AUTH header succeeds."""
        session = requests.Session()
        session.verify = False

        # First, login to get session
        login_envelope = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <Login xmlns="http://purenetworks.com/HNAP1/">
      <Username>admin</Username>
      <Password>password</Password>
    </Login>
  </soap:Body>
</soap:Envelope>"""

        login_response = session.post(
            f"{hnap_soap_server.url}/HNAP1/",
            data=login_envelope,
            headers={
                "SOAPAction": '"http://purenetworks.com/HNAP1/Login"',
                "Content-Type": "text/xml; charset=utf-8",
            },
            timeout=10,
        )
        assert "<LoginResult>OK</LoginResult>" in login_response.text

        # Now fetch data with HNAP_AUTH header and session cookie
        data_envelope = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <GetMotoStatusConnectionInfo xmlns="http://purenetworks.com/HNAP1/">
    </GetMotoStatusConnectionInfo>
  </soap:Body>
</soap:Envelope>"""

        # Include HNAP_AUTH header (timestamp + signature)
        # The cookie should be sent automatically by the session
        session.cookies.set("uid", HNAPSoapMockHandler.cookie)

        response = session.post(
            f"{hnap_soap_server.url}/HNAP1/",
            data=data_envelope,
            headers={
                "SOAPAction": '"http://purenetworks.com/HNAP1/GetMotoStatusConnectionInfo"',
                "Content-Type": "text/xml; charset=utf-8",
                "HNAP_AUTH": "ABCD1234567890ABCDEF1234567890AB 1234567890",
            },
            timeout=10,
        )

        assert response.status_code == 200
        # Should get modem data, not error
        assert "Cable Modem Status" in response.text or "downstream" in response.text.lower()


class TestHNAPAuthHandler:
    """Test AuthHandler with HNAP_SESSION strategy."""

    def test_auth_handler_hnap_strategy_detected(self, hnap_soap_server):
        """Verify AuthHandler can be initialized with HNAP strategy."""
        handler = AuthHandler(
            strategy=AuthStrategyType.HNAP_SESSION,
            hnap_config={
                "endpoint": "/HNAP1/",
                "namespace": "http://purenetworks.com/HNAP1/",
            },
        )

        assert handler.strategy == AuthStrategyType.HNAP_SESSION
        assert handler.hnap_config["endpoint"] == "/HNAP1/"

    def test_auth_handler_hnap_no_credentials_fails(self, hnap_soap_server):
        """Verify HNAP auth fails without credentials."""
        handler = AuthHandler(
            strategy=AuthStrategyType.HNAP_SESSION,
            hnap_config={
                "endpoint": "/HNAP1/",
                "namespace": "http://purenetworks.com/HNAP1/",
            },
        )

        session = requests.Session()
        session.verify = False

        success, html = handler.authenticate(
            session=session,
            base_url=hnap_soap_server.url,
            username=None,
            password=None,
        )

        assert success is False


class TestHNAPLoginPageDetection:
    """Test HNAP login page detection."""

    def test_hnap_login_page_has_soap_script(self, hnap_soap_server):
        """Verify HNAP login page contains SOAPAction.js script reference."""
        session = requests.Session()
        session.verify = False

        response = session.get(hnap_soap_server.url, timeout=10)

        assert response.status_code == 200
        assert "SOAPAction.js" in response.text

    def test_hnap_login_page_has_login_form(self, hnap_soap_server):
        """Verify HNAP login page has login form elements."""
        session = requests.Session()
        session.verify = False

        response = session.get(hnap_soap_server.url, timeout=10)

        assert response.status_code == 200
        assert 'type="password"' in response.text.lower() or "type='password'" in response.text.lower()
        assert "username" in response.text.lower()
