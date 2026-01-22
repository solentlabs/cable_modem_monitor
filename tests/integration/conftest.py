"""Pytest fixtures for integration tests with mock HTTP/HTTPS servers.

These fixtures provide real servers for testing SSL/TLS behavior,
including legacy cipher support and certificate handling.
"""

from __future__ import annotations

import contextlib
import ipaddress
import os
import socket
import ssl
import tempfile
import threading
from collections.abc import Generator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from .mock_modem_server import MockModemServer

# Test response HTML (minimal modem-like response)
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


def _find_free_port() -> int:
    """Find an available port for the test server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port: int = s.getsockname()[1]
        return port


def _generate_self_signed_cert(cert_dir: str) -> tuple[str, str]:
    """Generate a self-signed certificate for testing.

    Returns:
        Tuple of (cert_path, key_path)

    Raises:
        ImportError: If cryptography package is not available (pytest.skip handles this)
    """
    from datetime import datetime, timedelta

    # Import cryptography - required for SSL certificate generation
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    # Generate private key
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    # Generate certificate
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Test"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Test"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Cable Modem Monitor Tests"),
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
        ]
    )

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow())
        .not_valid_after(datetime.utcnow() + timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                ]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    # Write cert and key to files
    cert_path = os.path.join(cert_dir, "cert.pem")
    key_path = os.path.join(cert_dir, "key.pem")

    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    with open(key_path, "wb") as f:
        f.write(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    return cert_path, key_path


class MockServer:
    """Wrapper for test HTTP/HTTPS server with lifecycle management."""

    def __init__(
        self,
        port: int,
        ssl_context: ssl.SSLContext | None = None,
        handler_class: type = MockModemHandler,
    ):
        self.port = port
        self.ssl_context = ssl_context
        self.handler_class = handler_class
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        """Get the server URL."""
        scheme = "https" if self.ssl_context else "http"
        return f"{scheme}://127.0.0.1:{self.port}"

    def start(self):
        """Start the server in a background thread."""
        self._server = HTTPServer(("127.0.0.1", self.port), self.handler_class)

        if self.ssl_context:
            self._server.socket = self.ssl_context.wrap_socket(
                self._server.socket,
                server_side=True,
            )

        self._thread = threading.Thread(target=self._server.serve_forever)
        self._thread.daemon = True
        self._thread.start()

    def stop(self):
        """Stop the server."""
        if self._server:
            self._server.shutdown()
            self._server.server_close()
        if self._thread:
            self._thread.join(timeout=5)


@pytest.fixture(scope="session")
def test_certs() -> Generator[tuple[str, str], None, None]:
    """Generate self-signed certificates for HTTPS testing.

    Yields:
        Tuple of (cert_path, key_path)
    """
    pytest.importorskip("cryptography", reason="cryptography package required for SSL tests")
    with tempfile.TemporaryDirectory() as cert_dir:
        cert_path, key_path = _generate_self_signed_cert(cert_dir)
        yield cert_path, key_path


@pytest.fixture
def http_server() -> Generator[MockServer, None, None]:
    """Provide a plain HTTP server (no SSL).

    Use this to verify that LegacySSLAdapter is NOT mounted for HTTP URLs.
    """
    port = _find_free_port()
    server = MockServer(port=port, ssl_context=None)
    server.start()
    yield server
    server.stop()


@pytest.fixture
def https_modern_server(test_certs) -> Generator[MockServer, None, None]:
    """Provide an HTTPS server with modern ciphers (default SSL context).

    Use this to verify that connections work with default settings.
    """
    cert_path, key_path = test_certs
    port = _find_free_port()

    # Modern SSL context with default (secure) settings
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_path, key_path)

    server = MockServer(port=port, ssl_context=context)
    server.start()
    yield server
    server.stop()


@pytest.fixture
def https_legacy_server(test_certs) -> Generator[MockServer, None, None]:
    """Provide an HTTPS server that ONLY accepts legacy ciphers.

    This simulates older modem firmware that requires SECLEVEL=0.
    Use this to verify that LegacySSLAdapter works correctly.
    """
    cert_path, key_path = test_certs
    port = _find_free_port()

    # Legacy SSL context - only accepts weak ciphers
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_path, key_path)

    # Set to only accept legacy ciphers that modern clients reject by default
    # This simulates old modem firmware behavior
    # DES-CBC3-SHA is a legacy cipher that requires SECLEVEL=0 on modern Python
    try:
        context.set_ciphers("DES-CBC3-SHA")
    except ssl.SSLError:
        # If the cipher isn't available, use any legacy cipher
        context.set_ciphers("DEFAULT:@SECLEVEL=0")
        # Then restrict further if possible
        with contextlib.suppress(ssl.SSLError):
            context.set_ciphers("3DES:@SECLEVEL=0")

    server = MockServer(port=port, ssl_context=context)
    server.start()
    yield server
    server.stop()


@pytest.fixture
def https_self_signed_server(test_certs) -> Generator[MockServer, None, None]:
    """Provide an HTTPS server with self-signed certificate.

    Use this to verify that verify=False works correctly.
    Same as https_modern_server but explicitly named for clarity.
    """
    cert_path, key_path = test_certs
    port = _find_free_port()

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_path, key_path)

    server = MockServer(port=port, ssl_context=context)
    server.start()
    yield server
    server.stop()


# =============================================================================
# SB8200 Auth Mock Server
# =============================================================================

# Load SB8200 fixture HTML (v3.12.0: moved to modems/)
_SB8200_FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "modems",
    "arris",
    "sb8200",
    "fixtures",
    "cmconnectionstatus.html",
)


def _load_sb8200_fixture() -> bytes:
    """Load SB8200 fixture HTML."""
    # Use Windows-1252 encoding (fixture has copyright symbol)
    with open(_SB8200_FIXTURE_PATH, encoding="cp1252") as f:
        return f.read().encode("utf-8")


class SB8200MockHandler(BaseHTTPRequestHandler):
    """Mock SB8200 modem with configurable auth modes.

    Class attributes control behavior:
        require_auth: If True, requires URL-based auth (Travis's variant)
        valid_credentials: Expected "user:password" string
    """

    require_auth = False
    valid_credentials = "admin:pw"
    _fixture_html: bytes | None = None

    def log_message(self, format, *args):
        """Suppress logging during tests."""
        pass

    @classmethod
    def get_fixture_html(cls) -> bytes:
        """Lazy-load and cache fixture HTML."""
        if cls._fixture_html is None:
            cls._fixture_html = _load_sb8200_fixture()
        return cls._fixture_html

    def do_GET(self) -> None:  # noqa: N802
        """Handle GET requests with optional auth."""
        import base64

        # No-auth mode (Tim's variant) - serve pages directly
        if not self.require_auth:
            self._serve_status_page()
            return

        # Auth mode (Travis's variant)
        if "login_" in self.path:
            # Extract and validate base64 credentials from URL
            try:
                token = self.path.split("login_")[1].split("&")[0].split("?")[0]
                decoded = base64.b64decode(token).decode("utf-8")
                if decoded == self.valid_credentials:
                    self._serve_status_page()
                    return
            except Exception:
                pass
            self._send_401()
        elif self.path == "/" or self.path == "":
            # Root page - serve login page (or minimal response for detection)
            self._serve_login_page()
        else:
            # Any other page without auth - 401
            self._send_401()

    def _serve_status_page(self) -> None:
        """Serve the SB8200 status page fixture."""
        content = self.get_fixture_html()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _serve_login_page(self) -> None:
        """Serve minimal login page with model detection span."""
        content = b"""<!DOCTYPE html>
<html><head><title>Login</title></head>
<body>
<span id="thisModelNumberIs">SB8200</span>
<form action="">
<input type="text" id="username" name="username">
<input type="password" id="password" name="password">
<input type="button" id="loginButton" value="Login">
</form>
</body></html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _send_401(self) -> None:
        """Send 401 Unauthorized response."""
        content = b"Unauthorized"
        self.send_response(401)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


@pytest.fixture
def sb8200_server_noauth() -> Generator[MockServer, None, None]:
    """Provide SB8200 mock server without auth (Tim's variant).

    This simulates older firmware that doesn't require login.
    """
    SB8200MockHandler.require_auth = False
    port = _find_free_port()
    server = MockServer(port=port, ssl_context=None, handler_class=SB8200MockHandler)
    server.start()
    yield server
    server.stop()


@pytest.fixture
def sb8200_server_auth() -> Generator[MockServer, None, None]:
    """Provide SB8200 mock server with URL-based auth (Travis's variant).

    This simulates newer firmware that requires login via URL query param:
    /cmconnectionstatus.html?login_<base64(user:pass)>
    """
    SB8200MockHandler.require_auth = True
    SB8200MockHandler.valid_credentials = "admin:pw"
    port = _find_free_port()
    server = MockServer(port=port, ssl_context=None, handler_class=SB8200MockHandler)
    server.start()
    yield server
    server.stop()


@pytest.fixture
def sb8200_server_auth_https(test_certs) -> Generator[MockServer, None, None]:
    """Provide SB8200 mock server with HTTPS + auth (full Travis scenario).

    This simulates the complete scenario: HTTPS with self-signed cert + auth.
    """
    SB8200MockHandler.require_auth = True
    SB8200MockHandler.valid_credentials = "admin:pw"

    cert_path, key_path = test_certs
    port = _find_free_port()

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_path, key_path)

    server = MockServer(port=port, ssl_context=context, handler_class=SB8200MockHandler)
    server.start()
    yield server
    server.stop()


# =============================================================================
# Auth Discovery Mock Servers
# =============================================================================


class BasicAuthMockHandler(BaseHTTPRequestHandler):
    """Mock server requiring HTTP Basic Auth."""

    valid_credentials = ("admin", "password")

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


class FormAuthMockHandler(BaseHTTPRequestHandler):
    """Mock server with form-based authentication."""

    valid_username = "admin"
    valid_password = "password"
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


class HNAPAuthMockHandler(BaseHTTPRequestHandler):
    """Mock server with HNAP/SOAP authentication (like S33/MB8611).

    Implements the full HNAP challenge-response flow:
    1. GET / or /Login.html -> Serve login page with SOAPAction.js
    2. POST /HNAP1/ with Login action -> Return challenge
    3. POST /HNAP1/ with LoginPassword -> Verify and return OK/FAILED
    """

    valid_username = "admin"
    valid_password = "password"
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


# =============================================================================
# HNAP SOAP Mock Server (Challenge-Response)
# =============================================================================


class HNAPSoapMockHandler(BaseHTTPRequestHandler):
    """Mock HNAP server implementing full SOAP challenge-response authentication.

    This simulates modems like S33/MB8611 that use HNAP/SOAP for auth:
    1. Client sends Login request
    2. Server returns Challenge + PublicKey + Cookie
    3. Client computes HMAC response using private key derived from password
    4. Subsequent requests include HNAP_AUTH header with computed signature
    """

    valid_username = "admin"
    valid_password = "password"
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
        """Serve HNAP login page."""
        if self.path == "/" or "Login" in self.path:
            self._serve_hnap_login_page()
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        """Handle HNAP SOAP requests."""
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8")
        soap_action = self.headers.get("SOAPAction", "")

        # Check for Login action
        if "Login" in soap_action:
            self._handle_login(post_data)
        elif "GetMoto" in soap_action or "GetMultiple" in soap_action:
            self._handle_data_request(post_data)
        else:
            self._send_error("Unknown SOAP action")

    def _handle_login(self, post_data: str) -> None:
        """Handle HNAP Login request - return challenge or verify credentials."""
        import json

        # Check if this is a JSON request (MB8611 style)
        is_json = "application/json" in self.headers.get("Content-Type", "")

        if is_json:
            try:
                data = json.loads(post_data)
                login_data = data.get("Login", {})
                username = login_data.get("Username", "")
                password = login_data.get("Password", "")
                private_key = login_data.get("LoginPassword", "")

                if username and password and not private_key:
                    # First login request - return challenge
                    self._send_json_challenge()
                    return
                elif private_key:
                    # Second request - verify computed password
                    expected_key = self._compute_private_key(self.valid_password)
                    if private_key == expected_key:
                        self._send_json_success()
                    else:
                        self._send_json_failure()
                    return
            except json.JSONDecodeError:
                pass

        # XML/SOAP style
        if f"<Username>{self.valid_username}</Username>" in post_data:
            if f"<Password>{self.valid_password}</Password>" in post_data:
                # Simple password match (first phase or simplified auth)
                self._send_soap_challenge()
            elif "<LoginPassword>" in post_data:
                # Check computed password
                self._send_soap_success()
            else:
                self._send_soap_failure()
        else:
            self._send_soap_failure()

    def _compute_private_key(self, password: str) -> str:
        """Compute expected private key from password and challenge.

        Note: This uses HMAC-MD5 because we're implementing the HNAP protocol
        which is defined by the modem manufacturer. We cannot change the algorithm
        as the real modem expects this exact computation. This is test fixture code
        that mimics the modem's authentication, not a security implementation choice.
        """
        import hashlib
        import hmac

        # HNAP protocol mandates HMAC-MD5 - this is what the modem expects
        # private_key = HMAC-MD5(public_key + password, challenge)
        key_material = self.public_key + password
        computed = (
            hmac.new(
                self.challenge.encode("utf-8"),
                key_material.encode("utf-8"),
                hashlib.md5,  # lgtm[py/weak-sensitive-data-hashing] HNAP protocol requirement
            )
            .hexdigest()
            .upper()
        )
        return computed

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
        self.authenticated_sessions.add(self.cookie)

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

    def _send_json_failure(self) -> None:
        """Send JSON login failure."""
        import json

        response = {"LoginResponse": {"LoginResult": "FAILED"}}
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
        self.authenticated_sessions.add(self.cookie)

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

    def _send_soap_failure(self) -> None:
        """Send SOAP login failure."""
        content = b"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <LoginResponse xmlns="http://purenetworks.com/HNAP1/">
      <LoginResult>FAILED</LoginResult>
    </LoginResponse>
  </soap:Body>
</soap:Envelope>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/xml; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _handle_data_request(self, post_data: str) -> None:
        """Handle HNAP data request (requires auth)."""
        # Check HNAP_AUTH header
        hnap_auth = self.headers.get("HNAP_AUTH", "")
        cookies = self.headers.get("Cookie", "")

        if not hnap_auth or self.cookie not in cookies:
            self._send_error("SessionTimeout")
            return

        # Return mock modem data
        self.send_response(200)
        self.send_header("Content-Type", "text/xml; charset=utf-8")
        content = MOCK_MODEM_RESPONSE
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
# Session Expiry Mock Server
# =============================================================================


class SessionExpiryMockHandler(BaseHTTPRequestHandler):
    """Mock server that expires sessions after N requests.

    Used to test session re-authentication during polling.
    """

    valid_username = "admin"
    valid_password = "password"
    # Session tracking: session_id -> request_count
    session_requests: dict = {}
    max_requests_per_session = 3  # Expire after 3 requests

    def log_message(self, format, *args):
        """Suppress logging during tests."""
        pass

    def do_GET(self) -> None:  # noqa: N802
        """Handle GET with session expiry check."""
        cookies = self.headers.get("Cookie", "")
        session_id = self._extract_session_id(cookies)

        if session_id and self._is_session_valid(session_id):
            # Check count BEFORE incrementing (allows redirect + N requests)
            current_count = self.session_requests.get(session_id, 0)
            if current_count > self.max_requests_per_session:
                # Session expired - require re-auth
                self._serve_login_form()
            else:
                # Serve data, THEN increment counter
                self._serve_data_page()
                self.session_requests[session_id] = current_count + 1
        else:
            self._serve_login_form()

    def do_POST(self) -> None:  # noqa: N802
        """Handle login POST."""
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8")

        from urllib.parse import parse_qs

        params = parse_qs(post_data)
        username = params.get("username", [""])[0]
        password = params.get("password", [""])[0]

        if username == self.valid_username and password == self.valid_password:
            import uuid

            session_id = str(uuid.uuid4())
            self.session_requests[session_id] = 0
            self.send_response(302)
            self.send_header("Location", "/status")
            self.send_header("Set-Cookie", f"session={session_id}; Path=/")
            self.end_headers()
        else:
            self._serve_login_form()

    def _extract_session_id(self, cookies: str) -> str | None:
        """Extract session ID from cookies."""
        for cookie in cookies.split(";"):
            if "session=" in cookie:
                return cookie.split("=", 1)[1].strip()
        return None

    def _is_session_valid(self, session_id: str) -> bool:
        """Check if session is valid (not expired)."""
        return session_id in self.session_requests

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
# HTTP 302 Redirect Mock Server
# =============================================================================


class HTTP302RedirectMockHandler(BaseHTTPRequestHandler):
    """Mock server using HTTP 302 redirects (not meta refresh).

    Tests proper handling of Location-based redirects.
    """

    valid_username = "admin"
    valid_password = "password"
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
# FORM_BASE64 Mock Server (MB7621 style)
# =============================================================================


class FormBase64MockHandler(BaseHTTPRequestHandler):
    """Mock server requiring base64-encoded password in form submission.

    Simulates Motorola MB7621 behavior:
    1. Password is URL-encoded (JavaScript escape())
    2. Then base64 encoded
    3. Submitted as form field
    """

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
            # JavaScript escape() doesn't encode: @*_+-./
            # Python unquote is close but not exact - for test purposes this works
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
# HTTPS Form Auth Mock Handler (wraps FormAuthMockHandler for HTTPS)
# =============================================================================


class HTTPSFormAuthMockHandler(FormAuthMockHandler):
    """FormAuthMockHandler for use with HTTPS.

    Inherits all behavior from FormAuthMockHandler.
    """

    pass


# =============================================================================
# New Fixtures
# =============================================================================


@pytest.fixture
def hnap_soap_server() -> Generator[MockServer, None, None]:
    """Provide HNAP SOAP server with challenge-response auth."""
    HNAPSoapMockHandler.authenticated_sessions = set()
    port = _find_free_port()
    server = MockServer(port=port, ssl_context=None, handler_class=HNAPSoapMockHandler)
    server.start()
    yield server
    server.stop()


@pytest.fixture
def session_expiry_server() -> Generator[MockServer, None, None]:
    """Provide server that expires sessions after N requests."""
    SessionExpiryMockHandler.session_requests = {}
    SessionExpiryMockHandler.max_requests_per_session = 3
    port = _find_free_port()
    server = MockServer(port=port, ssl_context=None, handler_class=SessionExpiryMockHandler)
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


# =============================================================================
# MODEM.YAML-DRIVEN MOCK SERVERS (MockModemServer)
# =============================================================================
# These fixtures use MockModemServer which reads modem.yaml configuration
# and serves fixtures from the modem's fixtures/ directory.
# This is the preferred approach - add new modem tests here, not above.
# =============================================================================

MODEMS_DIR = Path(__file__).parent.parent.parent / "modems"


@pytest.fixture
def mb7621_modem_server() -> Generator[MockModemServer, None, None]:
    """MB7621 server using modem.yaml configuration.

    Uses:
    - auth.strategy: form
    - auth.form.password_encoding: base64
    - auth.form.success.redirect: /MotoHome.asp
    - pages.public includes "/" (shows login even after auth)

    Replaces: mb7621_style_server, form_base64_server
    """
    modem_path = MODEMS_DIR / "motorola" / "mb7621"
    with MockModemServer.from_modem_path(modem_path) as server:
        yield server


@pytest.fixture
def sb8200_modem_server() -> Generator[MockModemServer, None, None]:
    """SB8200 server using modem.yaml configuration.

    Uses:
    - auth.strategy: url_token
    - URL token session authentication

    Replaces: sb8200_auth_server, sb8200_no_auth_server
    """
    modem_path = MODEMS_DIR / "arris" / "sb8200"
    with MockModemServer.from_modem_path(modem_path) as server:
        yield server


@pytest.fixture
def s33_modem_server() -> Generator[MockModemServer, None, None]:
    """S33 server using modem.yaml configuration.

    Uses:
    - auth.strategy: hnap
    - HNAP SOAP authentication

    Replaces: hnap_auth_server, hnap_soap_server
    """
    modem_path = MODEMS_DIR / "arris" / "s33"
    with MockModemServer.from_modem_path(modem_path) as server:
        yield server


@pytest.fixture
def g54_modem_server() -> Generator[MockModemServer, None, None]:
    """G54 server using modem.yaml configuration.

    Uses:
    - auth.strategy: form
    - auth.form.password_encoding: plain

    Replaces: form_auth_server (for plain form auth tests)
    """
    modem_path = MODEMS_DIR / "arris" / "g54"
    with MockModemServer.from_modem_path(modem_path) as server:
        yield server


@pytest.fixture
def sb6190_modem_server() -> Generator[MockModemServer, None, None]:
    """SB6190 server using modem.yaml configuration.

    Uses:
    - auth.strategy: basic
    - HTTP Basic authentication

    Replaces: basic_auth_server
    """
    modem_path = MODEMS_DIR / "arris" / "sb6190"
    with MockModemServer.from_modem_path(modem_path) as server:
        yield server


@pytest.fixture
def cga2121_modem_server() -> Generator[MockModemServer, None, None]:
    """CGA2121 server using modem.yaml configuration.

    Uses:
    - auth.strategy: form
    - auth.form.password_encoding: plain

    Good for form auth tests.
    """
    modem_path = MODEMS_DIR / "technicolor" / "cga2121"
    with MockModemServer.from_modem_path(modem_path) as server:
        yield server


@pytest.fixture
def mb8611_modem_server() -> Generator[MockModemServer, None, None]:
    """MB8611 server using modem.yaml configuration.

    Uses:
    - auth.strategy: hnap
    - HNAP SOAP authentication (similar to S33)
    """
    modem_path = MODEMS_DIR / "motorola" / "mb8611"
    with MockModemServer.from_modem_path(modem_path) as server:
        yield server
