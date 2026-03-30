"""Tests for FormSjclAuthManager."""

from __future__ import annotations

import hashlib
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESCCM
from solentlabs.cable_modem_monitor_core.auth.form_sjcl import (
    FormSjclAuthManager,
    _derive_key,
    _fetch_page_vars,
)
from solentlabs.cable_modem_monitor_core.models.modem_config.auth import (
    FormSjclAuth,
)

# Pre-computed test values.
# password="password", salt="1122334455667788", iterations=1000,
# key_length=128, iv="aabbccddeeff0011", tag_length=16.
_TEST_SALT = "1122334455667788"
_TEST_IV = "aabbccddeeff0011"
_TEST_SESSION_ID = "test_session_id"
_TEST_CSRF_NONCE = "test_csrf_nonce_12345"
_TEST_ENCRYPTED_NONCE = "cbd2ef8ec63fc993cbcd49052f671e994329237485185d24b13ae145ef11f07d2d5ab3ecd7"


def _make_config(**overrides: Any) -> FormSjclAuth:
    """Build a FormSjclAuth config with defaults."""
    defaults: dict[str, Any] = {
        "strategy": "form_sjcl",
        "login_endpoint": "/php/ajaxSet_Password.php",
        "login_page": "/",
        "session_validation_endpoint": "/php/ajaxSet_Session.php",
        "pbkdf2_iterations": 1000,
        "pbkdf2_key_length": 128,
        "ccm_tag_length": 16,
        "encrypt_aad": "loginPassword",
        "decrypt_aad": "nonce",
        "csrf_header": "csrfNonce",
    }
    defaults.update(overrides)
    return FormSjclAuth.model_validate(defaults)


def _login_page_html(
    iv: str = _TEST_IV,
    salt: str = _TEST_SALT,
    session_id: str = _TEST_SESSION_ID,
) -> str:
    """Build a minimal login page with JS variables."""
    return (
        f"<html><script>"
        f"var myIv = '{iv}';\n"
        f"var mySalt = '{salt}';\n"
        f"currentSessionId = '{session_id}';\n"
        f"</script></html>"
    )


class TestDeriveKey:
    """PBKDF2 key derivation utility."""

    def test_basic_derivation(self) -> None:
        """Derives raw bytes from password and salt."""
        result = _derive_key("password", "salt", 1000, 128)
        assert len(result) == 16  # 128 bits = 16 bytes
        assert isinstance(result, bytes)

    def test_deterministic(self) -> None:
        """Same inputs produce same output."""
        a = _derive_key("password", "salt", 1000, 128)
        b = _derive_key("password", "salt", 1000, 128)
        assert a == b

    def test_matches_hashlib(self) -> None:
        """Matches hashlib.pbkdf2_hmac directly."""
        expected = hashlib.pbkdf2_hmac("sha256", b"pass", b"salt", 1000, dklen=16)
        result = _derive_key("pass", "salt", 1000, 128)
        assert result == expected


class TestAesCcm:
    """AES-CCM encrypt/decrypt round-trip using cryptography directly."""

    def test_round_trip(self) -> None:
        """Encrypt then decrypt returns original plaintext."""
        key = _derive_key("password", _TEST_SALT, 1000, 128)
        iv = bytes.fromhex(_TEST_IV)
        plaintext = b"hello world"
        aad = b"test"

        cipher = AESCCM(key, tag_length=16)
        encrypted = cipher.encrypt(iv, plaintext, aad)
        decrypted = cipher.decrypt(iv, encrypted, aad)
        assert decrypted == plaintext

    def test_wrong_aad_fails(self) -> None:
        """Decrypt with wrong AAD raises InvalidTag."""
        key = _derive_key("password", _TEST_SALT, 1000, 128)
        iv = bytes.fromhex(_TEST_IV)

        cipher = AESCCM(key, tag_length=16)
        encrypted = cipher.encrypt(iv, b"data", b"correct_aad")

        with pytest.raises(InvalidTag):
            cipher.decrypt(iv, encrypted, b"wrong_aad")

    def test_wrong_key_fails(self) -> None:
        """Decrypt with wrong key raises InvalidTag."""
        key1 = _derive_key("password1", _TEST_SALT, 1000, 128)
        key2 = _derive_key("password2", _TEST_SALT, 1000, 128)
        iv = bytes.fromhex(_TEST_IV)

        cipher1 = AESCCM(key1, tag_length=16)
        encrypted = cipher1.encrypt(iv, b"secret", b"aad")

        cipher2 = AESCCM(key2, tag_length=16)
        with pytest.raises(InvalidTag):
            cipher2.decrypt(iv, encrypted, b"aad")


class TestFetchPageVars:
    """JS variable extraction from login page."""

    def test_extracts_variables(self) -> None:
        """Extracts myIv, mySalt, currentSessionId from page."""
        session = requests.Session()
        resp = MagicMock()
        resp.text = _login_page_html()
        with patch.object(session, "get", return_value=resp):
            result = _fetch_page_vars(session, "http://modem/", 10)

        assert isinstance(result, dict)
        assert result["myIv"] == _TEST_IV
        assert result["mySalt"] == _TEST_SALT
        assert result["currentSessionId"] == _TEST_SESSION_ID

    def test_network_error_propagates(self) -> None:
        """ConnectionError propagates for collector to classify as CONNECTIVITY."""
        session = requests.Session()
        with (
            patch.object(session, "get", side_effect=requests.ConnectionError("refused")),
            pytest.raises(requests.ConnectionError),
        ):
            _fetch_page_vars(session, "http://modem/", 10)


class TestFormSjclAuthManager:
    """FormSjclAuthManager AES-CCM encrypted form auth."""

    def test_successful_login(self, session: requests.Session) -> None:
        """Full SJCL login flow succeeds with CSRF nonce extraction."""
        config = _make_config()
        manager = FormSjclAuthManager(config)

        page_resp = MagicMock()
        page_resp.text = _login_page_html()

        login_resp = MagicMock()
        login_resp.status_code = 200
        login_resp.json.return_value = {
            "p_status": "AdminMatch",
            "encryptData": _TEST_ENCRYPTED_NONCE,
        }

        session_resp = MagicMock()
        session_resp.status_code = 200
        session_resp.json.return_value = {"LoginStatus": "yes"}

        with patch.object(session, "get", return_value=page_resp), patch.object(session, "post") as mock_post:
            mock_post.side_effect = [login_resp, session_resp]

            result = manager.authenticate(session, "http://192.168.0.1", "admin", "password")

        assert result.success is True
        assert session.headers.get("csrfNonce") == _TEST_CSRF_NONCE
        assert mock_post.call_count == 2

    def test_login_rejected(self, session: requests.Session) -> None:
        """Reports error when p_status is not AdminMatch."""
        config = _make_config()
        manager = FormSjclAuthManager(config)

        page_resp = MagicMock()
        page_resp.text = _login_page_html()

        login_resp = MagicMock()
        login_resp.status_code = 200
        login_resp.json.return_value = {
            "p_status": "Lockout",
            "encryptData": "",
        }

        with (
            patch.object(session, "get", return_value=page_resp),
            patch.object(session, "post", return_value=login_resp),
        ):
            result = manager.authenticate(session, "http://192.168.0.1", "admin", "wrong")

        assert result.success is False
        assert "Lockout" in result.error

    def test_missing_iv_variable(self, session: requests.Session) -> None:
        """Reports error when login page is missing myIv."""
        config = _make_config()
        manager = FormSjclAuthManager(config)

        page_resp = MagicMock()
        page_resp.text = "<html><script>var mySalt = 'abc';</script></html>"

        with patch.object(session, "get", return_value=page_resp):
            result = manager.authenticate(session, "http://192.168.0.1", "admin", "password")

        assert result.success is False
        assert "myIv" in result.error

    def test_page_fetch_connection_error_propagates(self, session: requests.Session) -> None:
        """ConnectionError on login page fetch propagates for collector."""
        config = _make_config()
        manager = FormSjclAuthManager(config)

        with (
            patch.object(session, "get", side_effect=requests.ConnectionError("refused")),
            pytest.raises(requests.ConnectionError),
        ):
            manager.authenticate(session, "http://192.168.0.1", "admin", "password")

    def test_login_post_connection_error_propagates(self, session: requests.Session) -> None:
        """ConnectionError on login POST propagates for collector."""
        config = _make_config()
        manager = FormSjclAuthManager(config)

        page_resp = MagicMock()
        page_resp.text = _login_page_html()

        with (
            patch.object(session, "get", return_value=page_resp),
            patch.object(session, "post", side_effect=requests.ConnectionError("lost")),
            pytest.raises(requests.ConnectionError),
        ):
            manager.authenticate(session, "http://192.168.0.1", "admin", "password")

    def test_login_response_not_json(self, session: requests.Session) -> None:
        """Reports error when login response is not JSON."""
        config = _make_config()
        manager = FormSjclAuthManager(config)

        page_resp = MagicMock()
        page_resp.text = _login_page_html()

        login_resp = MagicMock()
        login_resp.json.side_effect = ValueError("not json")

        with (
            patch.object(session, "get", return_value=page_resp),
            patch.object(session, "post", return_value=login_resp),
        ):
            result = manager.authenticate(session, "http://192.168.0.1", "admin", "password")

        assert result.success is False
        assert "json" in result.error.lower()

    def test_nonce_decryption_failure(self, session: requests.Session) -> None:
        """Reports error when response decryption fails."""
        config = _make_config()
        manager = FormSjclAuthManager(config)

        page_resp = MagicMock()
        page_resp.text = _login_page_html()

        login_resp = MagicMock()
        login_resp.status_code = 200
        login_resp.json.return_value = {
            "p_status": "AdminMatch",
            "encryptData": "deadbeef" * 4,  # garbage ciphertext
        }

        with (
            patch.object(session, "get", return_value=page_resp),
            patch.object(session, "post", return_value=login_resp),
        ):
            result = manager.authenticate(session, "http://192.168.0.1", "admin", "password")

        assert result.success is False
        assert "decryption failed" in result.error.lower()

    def test_no_session_validation(self, session: requests.Session) -> None:
        """Succeeds without session validation when endpoint is empty."""
        config = _make_config(session_validation_endpoint="")
        manager = FormSjclAuthManager(config)

        page_resp = MagicMock()
        page_resp.text = _login_page_html()

        login_resp = MagicMock()
        login_resp.status_code = 200
        login_resp.json.return_value = {
            "p_status": "AdminMatch",
            "encryptData": _TEST_ENCRYPTED_NONCE,
        }

        with (
            patch.object(session, "get", return_value=page_resp),
            patch.object(session, "post", return_value=login_resp),
        ):
            result = manager.authenticate(session, "http://192.168.0.1", "admin", "password")

        assert result.success is True
        assert session.headers.get("csrfNonce") == _TEST_CSRF_NONCE

    def test_no_csrf_header(self, session: requests.Session) -> None:
        """Succeeds without decrypting nonce when csrf_header is empty."""
        config = _make_config(csrf_header="")
        manager = FormSjclAuthManager(config)

        page_resp = MagicMock()
        page_resp.text = _login_page_html()

        login_resp = MagicMock()
        login_resp.status_code = 200
        login_resp.json.return_value = {
            "p_status": "AdminMatch",
            "encryptData": "anything",
        }

        session_resp = MagicMock()
        session_resp.status_code = 200
        session_resp.json.return_value = {"LoginStatus": "yes"}

        with patch.object(session, "get", return_value=page_resp), patch.object(session, "post") as mock_post:
            mock_post.side_effect = [login_resp, session_resp]

            result = manager.authenticate(session, "http://192.168.0.1", "admin", "password")

        assert result.success is True
