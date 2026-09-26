"""Tests for SJCL protocol primitives (PBKDF2 key derivation, AES-CCM).

TEST DATA TABLES
================
This module uses table-driven tests. Tables are defined at the top
of the file with ASCII box-drawing comments for readability.

Known-answer vectors come from ``tests/auth/fixtures/sjcl_known_answers.json``.
They are independent of our code: what SJCL produces when the salt is hex-decoded
via ``sjcl.codec.hex.toBits()`` before PBKDF2.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from cryptography.exceptions import InvalidTag
from solentlabs.cable_modem_monitor_core.protocol.sjcl import (
    SjclInputError,
    decode_iv,
    decrypt,
    derive_key,
    encrypt,
    ensure_available,
)

from tests._helpers import load_fixture

_KAT = load_fixture(Path(__file__).parent.parent / "auth" / "fixtures" / "sjcl_known_answers.json")
_VECTORS: list[dict[str, Any]] = _KAT["vectors"]
_WRONG_UTF8_SALT_KEY_HEX: str = _KAT["regression_guard"]["wrong_key_hex"]
_VECTOR_IDS = [f"vector{i}" for i in range(len(_VECTORS))]

_KEY = bytes.fromhex("000102030405060708090a0b0c0d0e0f")
_IV_7 = "aabbccddeeff00"

# =============================================================================
# Test Data Tables
# =============================================================================

# ┌──────────────────────────────┬──────────┬──────────────────────────┐
# │ iv_hex                       │ accepted │ description              │
# ├──────────────────────────────┼──────────┼──────────────────────────┤
# │ 6 bytes                      │ False    │ below RFC 3610 minimum   │
# │ 7 bytes                      │ True     │ RFC 3610 minimum         │
# │ 13 bytes                     │ True     │ RFC 3610 maximum         │
# │ 14 bytes                     │ False    │ above RFC 3610 maximum   │
# │ "zzzz"                       │ False    │ not hex                  │
# └──────────────────────────────┴──────────┴──────────────────────────┘
#
# fmt: off
IV_CASES = [
    # (iv_hex,               accepted, description)
    ("aa" * 6,               False,    "6_bytes_rejected"),
    ("aa" * 7,               True,     "7_bytes_accepted"),
    ("aa" * 13,              True,     "13_bytes_accepted"),
    ("aa" * 14,              False,    "14_bytes_rejected"),
    ("zzzz",                 False,    "non_hex_rejected"),
]
# fmt: on

# ┌───────────────────────────────┬─────────────────┬─────┬──────────────┬───────────────────────┐
# │ plaintext                     │ aad             │ tag │ iv_hex       │ description           │
# ├───────────────────────────────┼─────────────────┼─────┼──────────────┼───────────────────────┤
# │ '{"a":"b"}' (str)             │ "shared"        │ 16  │ 7 bytes      │ compact JSON string   │
# │ b"raw bytes"                  │ "shared"        │ 16  │ 7 bytes      │ bytes plaintext       │
# │ ""                            │ ""              │ 16  │ 7 bytes      │ empty plaintext + AAD │
# │ "non-ascii é"                 │ "aad"           │ 8   │ 13 bytes     │ UTF-8, short tag      │
# └───────────────────────────────┴─────────────────┴─────┴──────────────┴───────────────────────┘
#
# fmt: off
ROUND_TRIP_CASES = [
    # (plaintext,        aad,      tag, iv_hex,     description)
    ('{"a":"b"}',        "shared", 16,  _IV_7,      "compact_json_str"),
    (b"raw bytes",       "shared", 16,  _IV_7,      "bytes_plaintext"),
    ("",                 "",       16,  _IV_7,      "empty_plaintext_and_aad"),
    ("non-ascii é", "aad",    8,   "11" * 13,  "utf8_short_tag_13_byte_iv"),
]
# fmt: on


# =============================================================================
# Known-answer vectors
# =============================================================================


@pytest.mark.parametrize("vec", _VECTORS, ids=_VECTOR_IDS)
def test_derive_key_matches_reference(vec: dict[str, Any]) -> None:
    """Derived key matches the SJCL reference value."""
    key = derive_key(vec["password"], vec["salt_hex"], vec["iterations"], vec["key_length_bits"])
    assert key.hex() == vec["expected_key_hex"]


@pytest.mark.parametrize("vec", _VECTORS, ids=_VECTOR_IDS)
def test_derive_key_hex_decodes_salt(vec: dict[str, Any]) -> None:
    """Salt is hex-decoded, not UTF-8 encoded; the two readings give different keys."""
    utf8_key = hashlib.pbkdf2_hmac(
        "sha256",
        vec["password"].encode("utf-8"),
        vec["salt_hex"].encode("utf-8"),
        vec["iterations"],
        dklen=vec["key_length_bits"] // 8,
    )
    assert utf8_key.hex() == _WRONG_UTF8_SALT_KEY_HEX
    key = derive_key(vec["password"], vec["salt_hex"], vec["iterations"], vec["key_length_bits"])
    assert key != utf8_key


@pytest.mark.parametrize("vec", _VECTORS, ids=_VECTOR_IDS)
def test_encrypt_matches_reference(vec: dict[str, Any]) -> None:
    """Encrypting the reference plaintext produces the reference hex ciphertext."""
    ciphertext_hex = encrypt(
        bytes.fromhex(vec["expected_key_hex"]),
        vec["iv_hex"],
        vec["plaintext"],
        vec["encrypt_aad"],
        vec["ccm_tag_length"],
    )
    assert ciphertext_hex == vec["expected_ciphertext_hex"]


@pytest.mark.parametrize("vec", _VECTORS, ids=_VECTOR_IDS)
def test_decrypt_matches_reference(vec: dict[str, Any]) -> None:
    """Decrypting the reference nonce ciphertext produces the reference plaintext."""
    plaintext = decrypt(
        bytes.fromhex(vec["expected_key_hex"]),
        vec["iv_hex"],
        vec["expected_nonce_ciphertext_hex"],
        vec["decrypt_aad"],
        vec["ccm_tag_length"],
    )
    assert plaintext.decode("utf-8") == vec["nonce_plaintext"]


# =============================================================================
# Round trip and authentication failures
# =============================================================================


@pytest.mark.parametrize(
    "plaintext,aad,tag_length,iv_hex,desc",
    ROUND_TRIP_CASES,
    ids=[c[4] for c in ROUND_TRIP_CASES],
)
def test_round_trip(plaintext: str | bytes, aad: str, tag_length: int, iv_hex: str, desc: str) -> None:
    """Encrypt then decrypt with the same AAD returns the original bytes."""
    ciphertext_hex = encrypt(_KEY, iv_hex, plaintext, aad, tag_length)
    expected = plaintext.encode("utf-8") if isinstance(plaintext, str) else plaintext
    assert decrypt(_KEY, iv_hex, ciphertext_hex, aad, tag_length) == expected


def test_wrong_aad_fails_decrypt() -> None:
    """Decrypting with a different AAD fails authentication."""
    ciphertext_hex = encrypt(_KEY, _IV_7, "secret", "right", 16)
    with pytest.raises(InvalidTag):
        decrypt(_KEY, _IV_7, ciphertext_hex, "wrong", 16)


def test_tampered_ciphertext_fails_decrypt() -> None:
    """Flipping one ciphertext bit fails authentication."""
    ciphertext = bytearray.fromhex(encrypt(_KEY, _IV_7, "secret", "aad", 16))
    ciphertext[0] ^= 0x01
    with pytest.raises(InvalidTag):
        decrypt(_KEY, _IV_7, ciphertext.hex(), "aad", 16)


def test_non_hex_ciphertext_is_input_error() -> None:
    """Malformed ciphertext hex is rejected before any decryption."""
    with pytest.raises(SjclInputError, match="not valid hex"):
        decrypt(_KEY, _IV_7, "zz", "aad", 16)


# =============================================================================
# IV validation
# =============================================================================


@pytest.mark.parametrize(
    "iv_hex,accepted,desc",
    IV_CASES,
    ids=[c[2] for c in IV_CASES],
)
def test_decode_iv(iv_hex: str, accepted: bool, desc: str) -> None:
    """IV must be hex and 7-13 bytes per RFC 3610."""
    if accepted:
        assert decode_iv(iv_hex) == bytes.fromhex(iv_hex)
    else:
        with pytest.raises(SjclInputError):
            decode_iv(iv_hex)


@pytest.mark.parametrize(
    "iv_hex,accepted,desc",
    [c for c in IV_CASES if not c[1]],
    ids=[c[2] for c in IV_CASES if not c[1]],
)
def test_encrypt_rejects_invalid_iv(iv_hex: str, accepted: bool, desc: str) -> None:
    """Encrypt applies the same IV rule as decode_iv."""
    with pytest.raises(SjclInputError):
        encrypt(_KEY, iv_hex, "x", "aad", 16)


def test_decode_iv_error_names_the_source() -> None:
    """Caller-supplied label names the IV in the error message."""
    with pytest.raises(SjclInputError, match=r"^pageIv decoded to 2 bytes, AES-CCM nonce must be 7-13 bytes$"):
        decode_iv("aabb", name="pageIv")


# =============================================================================
# Optional dependency
# =============================================================================


def test_ensure_available_raises_without_cryptography() -> None:
    """Missing ``cryptography`` raises ImportError naming the [sjcl] extra."""
    with (
        patch.dict("sys.modules", {"cryptography.hazmat.primitives.ciphers.aead": None}),
        pytest.raises(ImportError, match=r"\[sjcl\]"),
    ):
        ensure_available()
