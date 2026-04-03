"""Tests for CBN protocol primitives (compal_encrypt).

Table-driven with known test vectors and round-trip verification.
"""

from __future__ import annotations

import base64
import hashlib

import pytest
from solentlabs.cable_modem_monitor_core.protocol.cbn import compal_encrypt

# ---------------------------------------------------------------------------
# Known test vectors — generated from the Python implementation and verified
# via round-trip decrypt.  The algorithm mirrors CBN_Encrypt from Compal's
# encrypt_cryptoJS.js: AES-256-CBC, key=SHA256(token), iv=MD5(token),
# output = base64(":" + hex(ciphertext)).
# ---------------------------------------------------------------------------

# fmt: off
# ┌──────────────────────┬──────────────────────────┬──────────────────────────────────────────────────┐
# │ password             │ session_token            │ expected                                         │
# ├──────────────────────┼──────────────────────────┼──────────────────────────────────────────────────┤
# │ "password123"        │ "abc123token"            │ "OmZmMTFkOWUyMGY5OTdjNjg5ZjY5MjMzNDU3M2E3MmU1" │
# │ "MySecretPwd!"       │ "9876543210abcdef"       │ "OmNiMTEwMTU5NTc1MmRjNTY4M2ExMjkyMWZlZjEwYWQ0" │
# │ ""                   │ "sometoken"              │ "OjE0ZjI1NDAxMGNjZjIxZGUwN2Y5OWEzZTQ0ODE2ODU2" │
# │ "short"              │ "a"                      │ "OmM1NDk4YWU1MDFiYzFmZjRkNDM3MjM5NDgyYzAwZGVk" │
# └──────────────────────┴──────────────────────────┴──────────────────────────────────────────────────┘
ENCRYPT_VECTORS = [
    ("password123",  "abc123token",       "OmZmMTFkOWUyMGY5OTdjNjg5ZjY5MjMzNDU3M2E3MmU1"),
    ("MySecretPwd!", "9876543210abcdef",  "OmNiMTEwMTU5NTc1MmRjNTY4M2ExMjkyMWZlZjEwYWQ0"),
    ("",             "sometoken",         "OjE0ZjI1NDAxMGNjZjIxZGUwN2Y5OWEzZTQ0ODE2ODU2"),
    ("short",        "a",                 "OmM1NDk4YWU1MDFiYzFmZjRkNDM3MjM5NDgyYzAwZGVk"),
]
# fmt: on


@pytest.mark.parametrize(
    "password,token,expected",
    ENCRYPT_VECTORS,
    ids=[f"{v[0] or 'empty'}_{v[1][:8]}" for v in ENCRYPT_VECTORS],
)
def test_compal_encrypt_known_vector(password: str, token: str, expected: str) -> None:
    """Known plaintext/token produces expected ciphertext."""
    assert compal_encrypt(password, token) == expected


# ---------------------------------------------------------------------------
# Round-trip: encrypt → manual decrypt → original password
# ---------------------------------------------------------------------------


def _decrypt_cbn(encrypted: str, session_token: str) -> str:
    """Manual decrypt — inverse of compal_encrypt for verification."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives.padding import PKCS7

    raw = base64.b64decode(encrypted).decode("utf-8")
    assert raw[0] == ":"
    ct = bytes.fromhex(raw[1:])
    key = hashlib.sha256(session_token.encode()).digest()
    iv = hashlib.md5(session_token.encode()).digest()  # noqa: S324
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    padded = decryptor.update(ct) + decryptor.finalize()
    unpadder = PKCS7(128).unpadder()
    return (unpadder.update(padded) + unpadder.finalize()).decode("utf-8")


# fmt: off
ROUND_TRIP_CASES = [
    ("hello",          "token123"),
    ("complex!@#$%^",  "longtoken_with_stuff_12345"),
    ("",               "emptypassword_token"),
    ("x" * 100,        "repeated_token"),
]
# fmt: on


@pytest.mark.parametrize(
    "password,token",
    ROUND_TRIP_CASES,
    ids=[f"rt_{v[0][:8] or 'empty'}_{v[1][:8]}" for v in ROUND_TRIP_CASES],
)
def test_compal_encrypt_round_trip(password: str, token: str) -> None:
    """Encrypt then decrypt recovers original password."""
    encrypted = compal_encrypt(password, token)
    assert _decrypt_cbn(encrypted, token) == password


# ---------------------------------------------------------------------------
# Output format verification
# ---------------------------------------------------------------------------


def test_output_format() -> None:
    """Output is valid base64, decodes to ':' + hex string."""
    result = compal_encrypt("test", "token")
    decoded = base64.b64decode(result).decode("utf-8")
    assert decoded.startswith(":")
    # hex part must be valid hex and even-length
    hex_part = decoded[1:]
    assert len(hex_part) % 2 == 0
    bytes.fromhex(hex_part)  # raises ValueError if invalid hex
