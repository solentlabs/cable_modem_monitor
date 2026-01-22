"""Pytest fixtures for core auth mechanism tests.

These fixtures test auth MECHANISMS (form auth, basic auth, HNAP, etc.)
using synthetic responses. They don't test specific modems.

For modem-specific tests, use MockModemServer with modem.yaml configuration.
"""

from __future__ import annotations

import ssl
from collections.abc import Generator
from http.server import BaseHTTPRequestHandler

import pytest

# Import shared infrastructure from parent
# Note: test_certs fixture is discovered automatically by pytest from parent conftest
from tests.integration.conftest import MockServer, _find_free_port  # noqa: F401

# =============================================================================
# Synthetic Test Data
# =============================================================================

MOCK_MODEM_RESPONSE = b"""<!DOCTYPE html>
<html>
<head><title>Cable Modem Status</title></head>
<body>
<h1>Cable Modem Status</h1>
<table id="downstream">
<tr><td>Channel 1</td><td>32</td><td>-1.0 dBmV</td><td>39.0 dB</td></tr>
</table>
</body>
</html>
"""


class MockModemHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler that returns mock modem status page."""

    def log_message(self, format, *args):
        """Suppress logging during tests."""
        pass

    def do_GET(self) -> None:  # noqa: N802
        """Handle GET requests."""
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(MOCK_MODEM_RESPONSE)))
        self.end_headers()
        self.wfile.write(MOCK_MODEM_RESPONSE)


# =============================================================================
# Basic Auth Mock Handler
# =============================================================================


class BasicAuthMockHandler(BaseHTTPRequestHandler):
    """Mock server requiring HTTP Basic Auth.

    Uses "pw" instead of "password" to avoid browser password managers
    flagging these as real credentials during development.
    """

    valid_credentials = ("admin", "pw")

    def log_message(self, format, *args):
        """Suppress logging during tests."""
        pass

    def do_GET(self) -> None:  # noqa: N802
        """Handle GET with Basic Auth check."""
        import base64

        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Basic "):
            try:
                token = auth_header.split(" ", 1)[1]
                decoded = base64.b64decode(token).decode("utf-8")
                username, password = decoded.split(":", 1)
                if (username, password) == self.valid_credentials:
                    self._serve_data_page()
                    return
            except Exception:
                pass

        # Return 401 Unauthorized with WWW-Authenticate header
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="Modem"')
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Unauthorized")

    def _serve_data_page(self) -> None:
        """Serve modem data page."""
        content = MOCK_MODEM_RESPONSE
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


# =============================================================================
# Form Auth Mock Handler
# =============================================================================


class FormAuthMockHandler(BaseHTTPRequestHandler):
    """Mock server with form-based authentication."""

    valid_username = "admin"
    valid_password = "pw"
    authenticated_sessions: set = set()

    def log_message(self, format, *args):
        """Suppress logging during tests."""
        pass

    def do_GET(self) -> None:  # noqa: N802
        """Handle GET requests."""
        # Check session cookie
        cookies = self.headers.get("Cookie", "")
        if "session=authenticated" in cookies or self._check_session(cookies):
            self._serve_data_page()
        else:
            self._serve_login_form()

    def do_POST(self) -> None:  # noqa: N802
        """Handle POST (form submission)."""
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8")

        # Parse form data
        from urllib.parse import parse_qs

        params = parse_qs(post_data)
        username = params.get("username", [""])[0]
        password = params.get("password", [""])[0]

        if username == self.valid_username and password == self.valid_password:
            # Set session cookie and redirect to data page
            import uuid

            session_id = str(uuid.uuid4())
            self.authenticated_sessions.add(session_id)
            self.send_response(302)
            self.send_header("Location", "/status.html")
            self.send_header("Set-Cookie", f"session={session_id}; Path=/")
            self.end_headers()
        else:
            # Return login form again (wrong creds)
            self._serve_login_form()

    def _check_session(self, cookies: str) -> bool:
        """Check if session cookie is valid."""
        for cookie in cookies.split(";"):
            if "session=" in cookie:
                session_id = cookie.split("=", 1)[1].strip()
                return session_id in self.authenticated_sessions
        return False

    def _serve_login_form(self) -> None:
        """Serve login form."""
        content = b"""<!DOCTYPE html>
<html><head><title>Login</title></head>
<body>
<form action="/login" method="POST">
    <input type="text" name="username" placeholder="Username">
    <input type="password" name="password" placeholder="Password">
    <input type="hidden" name="csrf_token" value="test-csrf-token">
    <input type="submit" value="Login">
</form>
</body></html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _serve_data_page(self) -> None:
        """Serve modem data page."""
        content = MOCK_MODEM_RESPONSE
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


# =============================================================================
# HNAP Auth Mock Handler
# =============================================================================


class HNAPAuthMockHandler(BaseHTTPRequestHandler):
    """Mock server with HNAP/SOAP authentication (HNAP_SESSION pattern).

    Implements the full HNAP challenge-response flow:
    1. GET / or /Login.html -> Serve login page with SOAPAction.js
    2. POST /HNAP1/ with Login action -> Return challenge
    3. POST /HNAP1/ with LoginPassword -> Verify and return OK/FAILED
    """

    valid_username = "admin"
    valid_password = "pw"
    # Simulated challenge values
    challenge = "1234567890ABCDEF"
    public_key = "FEDCBA0987654321"
    cookie = "uid=test-session-id"
    # Track authenticated sessions
    authenticated_sessions: set = set()

    def log_message(self, format, *args):
        """Suppress logging during tests."""
        pass

    def do_GET(self) -> None:  # noqa: N802
        """Serve HNAP login page with SOAPAction.js script."""
        if self.path == "/" or "Login" in self.path:
            self._serve_hnap_login_page()
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        """Handle HNAP SOAP login requests."""
        import json

        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8")
        soap_action = self.headers.get("SOAPAction", "")
        content_type = self.headers.get("Content-Type", "")

        # Handle Login action
        if "Login" in soap_action or "/HNAP1/" in self.path:
            is_json = "application/json" in content_type

            if is_json:
                try:
                    data = json.loads(post_data)
                    login_data = data.get("Login", {})
                    private_key = login_data.get("LoginPassword", "")

                    if not private_key:
                        # First request - return challenge
                        self._send_json_challenge()
                    else:
                        # Second request - always accept for testing
                        self._send_json_success()
                    return
                except json.JSONDecodeError:
                    pass

            # XML/SOAP style - return challenge or success
            if "<LoginPassword>" in post_data:
                self._send_soap_success()
            else:
                self._send_soap_challenge()
        else:
            self._send_error("Unknown action")

    def _send_json_challenge(self) -> None:
        """Send JSON challenge response."""
        import json

        response = {
            "LoginResponse": {
                "LoginResult": "OK",
                "Challenge": self.challenge,
                "PublicKey": self.public_key,
                "Cookie": self.cookie,
            }
        }
        content = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Set-Cookie", f"uid={self.cookie}; Path=/")
        self.end_headers()
        self.wfile.write(content)

    def _send_json_success(self) -> None:
        """Send JSON login success."""
        import json

        response = {"LoginResponse": {"LoginResult": "OK"}}
        content = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _send_soap_challenge(self) -> None:
        """Send SOAP challenge response."""
        content = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <LoginResponse xmlns="http://purenetworks.com/HNAP1/">
      <LoginResult>OK</LoginResult>
      <Challenge>{self.challenge}</Challenge>
      <PublicKey>{self.public_key}</PublicKey>
      <Cookie>{self.cookie}</Cookie>
    </LoginResponse>
  </soap:Body>
</soap:Envelope>""".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/xml; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Set-Cookie", f"uid={self.cookie}; Path=/")
        self.end_headers()
        self.wfile.write(content)

    def _send_soap_success(self) -> None:
        """Send SOAP login success."""
        content = b"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <LoginResponse xmlns="http://purenetworks.com/HNAP1/">
      <LoginResult>OK</LoginResult>
    </LoginResponse>
  </soap:Body>
</soap:Envelope>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/xml; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _send_error(self, error: str) -> None:
        """Send SOAP error response."""
        content = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <ErrorResponse>
      <Error>{error}</Error>
    </ErrorResponse>
  </soap:Body>
</soap:Envelope>""".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/xml; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _serve_hnap_login_page(self) -> None:
        """Serve login page with HNAP detection scripts."""
        content = b"""<!DOCTYPE html>
<html><head>
<title>Login</title>
<script type="text/javascript" src="js/SOAP/SOAPAction.js"></script>
<script type="text/javascript" src="js/Login.js"></script>
</head>
<body>
<form id="loginForm">
    <input type="text" id="username" name="username">
    <input type="password" id="password" name="password">
    <button type="button" onclick="doLogin()">Login</button>
</form>
</body></html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


# =============================================================================
# Redirect Auth Mock Handler
# =============================================================================


class RedirectAuthMockHandler(BaseHTTPRequestHandler):
    """Mock server that uses meta refresh redirect to login page."""

    authenticated = False

    def log_message(self, format, *args):
        """Suppress logging during tests."""
        pass

    def do_GET(self) -> None:  # noqa: N802
        """Handle GET with redirect to login."""
        if self.path == "/login":
            self._serve_login_form()
        elif self.path == "/status":
            cookies = self.headers.get("Cookie", "")
            if "session=authenticated" in cookies:
                self._serve_data_page()
            else:
                self._serve_meta_refresh_redirect()
        else:
            self._serve_meta_refresh_redirect()

    def do_POST(self) -> None:  # noqa: N802
        """Handle form submission."""
        self.send_response(302)
        self.send_header("Location", "/status")
        self.send_header("Set-Cookie", "session=authenticated; Path=/")
        self.end_headers()

    def _serve_meta_refresh_redirect(self) -> None:
        """Serve page with meta refresh redirect."""
        content = b'<html><head><meta http-equiv="refresh" content="0;url=/login"></head></html>'
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _serve_login_form(self) -> None:
        """Serve login form."""
        content = b"""<!DOCTYPE html>
<html><head><title>Login</title></head>
<body>
<form action="/login" method="POST">
    <input type="text" name="user" placeholder="Username">
    <input type="password" name="pass" placeholder="Password">
    <input type="submit" value="Login">
</form>
</body></html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _serve_data_page(self) -> None:
        """Serve modem data page."""
        content = MOCK_MODEM_RESPONSE
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


# =============================================================================
# HTTP 302 Redirect Mock Handler
# =============================================================================


class HTTP302RedirectMockHandler(BaseHTTPRequestHandler):
    """Mock server using HTTP 302 redirects (not meta refresh)."""

    valid_username = "admin"
    valid_password = "pw"
    authenticated_sessions: set = set()

    def log_message(self, format, *args):
        """Suppress logging during tests."""
        pass

    def do_GET(self) -> None:  # noqa: N802
        """Handle GET with 302 redirect to login."""
        cookies = self.headers.get("Cookie", "")

        if self.path == "/login":
            self._serve_login_form()
        elif self.path == "/data" or self.path == "/":
            if self._is_authenticated(cookies):
                self._serve_data_page()
            else:
                # 302 redirect to login
                self.send_response(302)
                self.send_header("Location", "/login")
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        """Handle login form submission."""
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8")

        from urllib.parse import parse_qs

        params = parse_qs(post_data)
        username = params.get("username", [""])[0]
        password = params.get("password", [""])[0]

        if username == self.valid_username and password == self.valid_password:
            import uuid

            session_id = str(uuid.uuid4())
            self.authenticated_sessions.add(session_id)
            # 302 redirect to data page with session cookie
            self.send_response(302)
            self.send_header("Location", "/data")
            self.send_header("Set-Cookie", f"session={session_id}; Path=/")
            self.end_headers()
        else:
            # 302 back to login on failure
            self.send_response(302)
            self.send_header("Location", "/login?error=1")
            self.end_headers()

    def _is_authenticated(self, cookies: str) -> bool:
        """Check if request has valid session cookie."""
        for cookie in cookies.split(";"):
            if "session=" in cookie:
                session_id = cookie.split("=", 1)[1].strip()
                return session_id in self.authenticated_sessions
        return False

    def _serve_login_form(self) -> None:
        """Serve login form."""
        content = b"""<!DOCTYPE html>
<html><head><title>Login</title></head>
<body>
<form action="/login" method="POST">
    <input type="text" name="username" placeholder="Username">
    <input type="password" name="password" placeholder="Password">
    <input type="submit" value="Login">
</form>
</body></html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _serve_data_page(self) -> None:
        """Serve modem data page."""
        content = MOCK_MODEM_RESPONSE
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


# =============================================================================
# Form Base64 Mock Handler (FORM_BASE64 pattern)
# =============================================================================


class FormBase64MockHandler(BaseHTTPRequestHandler):
    """Mock server requiring base64-encoded password in form submission."""

    valid_username = "admin"
    valid_password = "p@ss!word"  # Special chars to test encoding

    def log_message(self, format, *args):
        """Suppress logging during tests."""
        pass

    def do_GET(self) -> None:  # noqa: N802
        """Serve login form or data page."""
        cookies = self.headers.get("Cookie", "")
        if "session=authenticated" in cookies:
            self._serve_data_page()
        else:
            self._serve_login_form()

    def do_POST(self) -> None:  # noqa: N802
        """Handle form submission with base64 password."""
        import base64
        from urllib.parse import parse_qs, unquote

        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8")

        params = parse_qs(post_data)
        username = params.get("username", [""])[0]
        encoded_password = params.get("password", [""])[0]

        # Decode: base64 -> URL-encoded -> original
        try:
            url_encoded = base64.b64decode(encoded_password).decode("utf-8")
            decoded_password = unquote(url_encoded)
        except Exception:
            decoded_password = ""

        if username == self.valid_username and decoded_password == self.valid_password:
            self.send_response(302)
            self.send_header("Location", "/status")
            self.send_header("Set-Cookie", "session=authenticated; Path=/")
            self.end_headers()
        else:
            self._serve_login_form()

    def _serve_login_form(self) -> None:
        """Serve login form with base64 encoding script."""
        content = b"""<!DOCTYPE html>
<html><head><title>Login</title>
<script>
function encodePassword() {
    var pass = document.getElementById('password').value;
    var encoded = btoa(escape(pass));
    document.getElementById('password').value = encoded;
}
</script>
</head>
<body>
<form action="/login" method="POST" onsubmit="encodePassword()">
    <input type="text" name="username" id="username" placeholder="Username">
    <input type="password" name="password" id="password" placeholder="Password">
    <input type="submit" value="Login">
</form>
</body></html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _serve_data_page(self) -> None:
        """Serve modem data page."""
        content = MOCK_MODEM_RESPONSE
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


# =============================================================================
# HTTPS Form Auth (wraps FormAuthMockHandler)
# =============================================================================


class HTTPSFormAuthMockHandler(FormAuthMockHandler):
    """FormAuthMockHandler for use with HTTPS."""

    pass


# =============================================================================
# Fixtures for Core Mechanism Tests
# =============================================================================


@pytest.fixture
def basic_auth_server() -> Generator[MockServer, None, None]:
    """Provide mock server requiring HTTP Basic Auth."""
    port = _find_free_port()
    server = MockServer(port=port, ssl_context=None, handler_class=BasicAuthMockHandler)
    server.start()
    yield server
    server.stop()


@pytest.fixture
def form_auth_server() -> Generator[MockServer, None, None]:
    """Provide mock server with form-based authentication."""
    FormAuthMockHandler.authenticated_sessions = set()
    port = _find_free_port()
    server = MockServer(port=port, ssl_context=None, handler_class=FormAuthMockHandler)
    server.start()
    yield server
    server.stop()


@pytest.fixture
def hnap_auth_server() -> Generator[MockServer, None, None]:
    """Provide mock server with HNAP-style login page."""
    port = _find_free_port()
    server = MockServer(port=port, ssl_context=None, handler_class=HNAPAuthMockHandler)
    server.start()
    yield server
    server.stop()


@pytest.fixture
def redirect_auth_server() -> Generator[MockServer, None, None]:
    """Provide mock server with meta refresh redirect to login."""
    port = _find_free_port()
    server = MockServer(port=port, ssl_context=None, handler_class=RedirectAuthMockHandler)
    server.start()
    yield server
    server.stop()


@pytest.fixture
def http_302_redirect_server() -> Generator[MockServer, None, None]:
    """Provide server using HTTP 302 redirects."""
    HTTP302RedirectMockHandler.authenticated_sessions = set()
    port = _find_free_port()
    server = MockServer(port=port, ssl_context=None, handler_class=HTTP302RedirectMockHandler)
    server.start()
    yield server
    server.stop()


@pytest.fixture
def form_base64_server() -> Generator[MockServer, None, None]:
    """Provide server requiring base64-encoded password."""
    port = _find_free_port()
    server = MockServer(port=port, ssl_context=None, handler_class=FormBase64MockHandler)
    server.start()
    yield server
    server.stop()


@pytest.fixture
def https_form_auth_server(test_certs) -> Generator[MockServer, None, None]:
    """Provide HTTPS server with form-based authentication."""
    HTTPSFormAuthMockHandler.authenticated_sessions = set()
    cert_path, key_path = test_certs
    port = _find_free_port()

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_path, key_path)

    server = MockServer(port=port, ssl_context=context, handler_class=HTTPSFormAuthMockHandler)
    server.start()
    yield server
    server.stop()
