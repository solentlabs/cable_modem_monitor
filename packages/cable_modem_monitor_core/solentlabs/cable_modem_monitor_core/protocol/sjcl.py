"""SJCL protocol primitives: PBKDF2-HMAC-SHA256 key derivation and AES-CCM.

Shared by the SJCL auth strategies and their test-harness handlers.
Implements the encoding rules SJCL (Stanford JavaScript Crypto Library)
standardizes; firmware wire format (JS variable names, POST fields,
success criteria) stays in each strategy.

Encoding rules
--------------
- Salt and IV arrive as hex strings and are hex-decoded, never UTF-8
  encoded (``sjcl.codec.hex.toBits``).
- Password, plaintext and AAD are UTF-8 encoded.
- IV is the AES-CCM nonce: 7-13 bytes per RFC 3610.
- Ciphertext (with the CCM tag appended) travels as lowercase hex.

Requires the ``cryptography`` package: install Core with ``[sjcl]``.

See AUTH_SJCL_SPEC.md § Crypto Library, the implementation authority.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.ciphers.aead import AESCCM

# RFC 3610: the CCM nonce is 15 - L bytes with L in 2..8.
_IV_MIN_BYTES = 7
_IV_MAX_BYTES = 13


class SjclInputError(ValueError):
    """Malformed hex or IV length, raised before any cipher operation."""


@dataclass(frozen=True)
class SjclSession:
    """SJCL parameters a login derived, reused to encrypt the session's later request bodies."""

    # The key is the password's PBKDF2 output: kept out of repr so no log,
    # exception or diagnostics dump that renders an AuthContext prints it.
    key: bytes = field(repr=False)
    iv_hex: str
    user: str
    aad: str
    tag_length: int


def ensure_available() -> None:
    """Raise ImportError unless the ``cryptography`` package is importable."""
    _aesccm_class()


def derive_key(password: str, salt_hex: str, iterations: int, key_length_bits: int) -> bytes:
    """Derive a raw AES key with PBKDF2-HMAC-SHA256 from a password and hex salt."""
    # Hex-decoding the salt matches sjcl.codec.hex.toBits(salt) ahead of
    # sjcl.misc.pbkdf2(); UTF-8 encoding it yields a different key.
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        iterations,
        dklen=key_length_bits // 8,
    )


def decode_iv(iv_hex: str, *, name: str = "IV") -> bytes:
    """Hex-decode an AES-CCM IV and check its 7-13 byte length."""
    # ``name`` labels the error with the caller's source for the IV.
    try:
        iv = bytes.fromhex(iv_hex)
    except ValueError:
        raise SjclInputError(f"{name} is not valid hex: {iv_hex!r}") from None
    if not _IV_MIN_BYTES <= len(iv) <= _IV_MAX_BYTES:
        raise SjclInputError(
            f"{name} decoded to {len(iv)} bytes, AES-CCM nonce must be {_IV_MIN_BYTES}-{_IV_MAX_BYTES} bytes"
        )
    return iv


def encrypt(key: bytes, iv_hex: str, plaintext: str | bytes, aad: str, tag_length: int) -> str:
    """AES-CCM encrypt and return the ciphertext with its tag as hex."""
    iv = decode_iv(iv_hex)
    data = plaintext.encode("utf-8") if isinstance(plaintext, str) else plaintext
    cipher = _aesccm_class()(key, tag_length=tag_length)
    ciphertext: bytes = cipher.encrypt(iv, data, aad.encode("utf-8"))
    return ciphertext.hex()


def decrypt(key: bytes, iv_hex: str, ciphertext_hex: str, aad: str, tag_length: int) -> bytes:
    """AES-CCM decrypt hex ciphertext and return the plaintext bytes."""
    # Plaintext stays bytes: decoding is the caller's wire-format concern,
    # and a UnicodeDecodeError must not read as a malformed-input error.
    # A failed tag check raises cryptography's InvalidTag.
    iv = decode_iv(iv_hex)
    try:
        ciphertext = bytes.fromhex(ciphertext_hex)
    except ValueError:
        raise SjclInputError("ciphertext is not valid hex") from None
    cipher = _aesccm_class()(key, tag_length=tag_length)
    plaintext: bytes = cipher.decrypt(iv, ciphertext, aad.encode("utf-8"))
    return plaintext


def _aesccm_class() -> type[AESCCM]:
    """Import AESCCM lazily so Core runs without the ``[sjcl]`` extra."""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESCCM
    except ImportError:
        raise ImportError(
            "cryptography package required for SJCL auth. "
            "Install with: pip install solentlabs-cable-modem-monitor-core[sjcl]"
        ) from None
    # Annotated so mypy environments without cryptography's types (the
    # pre-commit hook) see a concrete return type, not Any.
    aesccm: type[AESCCM] = AESCCM
    return aesccm
