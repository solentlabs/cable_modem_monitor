"""CBN (Compal Broadband Networks) protocol primitives.

Shared encryption function used by ``form_cbn`` auth. Replicates the
``CBN_Encrypt`` function from Compal's ``encrypt_cryptoJS.js`` which
uses CryptoJS v3.1.2.

Algorithm
---------
1. ``key = SHA256(sessionToken)`` — 32 bytes (AES-256)
2. ``iv  = MD5(sessionToken)``   — 16 bytes (CBC block size)
3. ``ciphertext = AES-256-CBC(password, key, iv)`` with PKCS7 padding
4. ``result = base64(":" + hex(ciphertext))``

Requires the ``cryptography`` package: install Core with ``[cbn]``.

Also owns typed access to the CBN auth block's transport parameters
(``cbn_params``) for the generic collector and action dispatcher.
"""

from __future__ import annotations

import base64
import hashlib
from typing import TYPE_CHECKING

from ..models.modem_config.auth import FormCbnAuth

if TYPE_CHECKING:
    from ..models.modem_config.auth import AuthConfig


def cbn_params(auth: AuthConfig | None) -> FormCbnAuth:
    """The CBN auth block, or its model defaults when the entry declares none."""
    # CBN has exactly one strategy (TestProtocolLockedTransports), so the
    # transport owns these reads; generic code routes here reading nothing.
    return auth if isinstance(auth, FormCbnAuth) else FormCbnAuth(strategy="form_cbn")


def compal_encrypt(password: str, session_token: str) -> str:
    """Replicate CBN_Encrypt from Compal's encrypt_cryptoJS.js.

    Args:
        password: Plaintext password.
        session_token: Value of the ``sessionToken`` cookie.

    Returns:
        Encrypted password string for the login POST body.

    Raises:
        ImportError: If ``cryptography`` is not installed.
    """
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives.padding import PKCS7
    except ImportError:
        raise ImportError(
            "cryptography package required for form_cbn auth. "
            "Install with: pip install solentlabs-cable-modem-monitor-core[cbn]"
        ) from None

    # Derive key and IV from session token
    token_bytes = session_token.encode("utf-8")
    key = hashlib.sha256(token_bytes).digest()  # 32 bytes
    iv = hashlib.md5(token_bytes).digest()  # 16 bytes  # noqa: S324

    # AES-256-CBC encrypt with PKCS7 padding
    padder = PKCS7(128).padder()
    padded = padder.update(password.encode("utf-8")) + padder.finalize()

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()

    # ":" + hex(ciphertext), then base64 encode
    hex_ct = ciphertext.hex()
    return base64.b64encode((":" + hex_ct).encode("utf-8")).decode("utf-8")
