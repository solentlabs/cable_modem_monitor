"""HNAP protocol primitives — constants, HMAC signing, auth headers.

Shared by ``auth.hnap``, ``loaders.hnap``, and
``orchestration.actions.hnap_action``.  Centralises the protocol
constants and signing logic that were previously duplicated across
those modules.

See MODEM_YAML_SPEC.md ``hnap`` strategy for protocol background.
"""

from __future__ import annotations

import hashlib
import hmac
import time

# Fixed by protocol — all HNAP modems use this namespace.
HNAP_NAMESPACE = "http://purenetworks.com/HNAP1/"

# Fixed HNAP endpoint.
HNAP_ENDPOINT = "/HNAP1/"

# Timestamp modulo to match firmware's 32-bit integer handling.
# From SOAPAction.js: Math.floor(Date.now()) % 2000000000000
_TIMESTAMP_MODULO = 2_000_000_000_000


def hmac_hex(key: str, message: str, algorithm: str = "md5") -> str:
    """Compute HMAC and return uppercase hex digest.

    Args:
        key: HMAC key string.
        message: HMAC message string.
        algorithm: Hash algorithm (``"md5"`` or ``"sha256"``).

    Returns:
        Uppercase hex digest string.
    """
    digest = hashlib.sha256 if algorithm == "sha256" else hashlib.md5
    return (
        hmac.new(
            key.encode("utf-8"),
            message.encode("utf-8"),
            digest,
        )
        .hexdigest()
        .upper()
    )


def compute_auth_header(
    private_key: str,
    action: str,
    algorithm: str = "md5",
) -> str:
    """Compute the ``HNAP_AUTH`` header value for a request.

    Format: ``HMAC_HEX TIMESTAMP`` where:
    - ``HMAC_HEX`` = HMAC(key=private_key, msg=timestamp + soapActionURI)
    - ``soapActionURI`` includes quotes per protocol:
      ``'"http://purenetworks.com/HNAP1/Login"'``
    - ``TIMESTAMP`` = ``floor(time_ms) % 2_000_000_000_000``

    Args:
        private_key: Signing key (``"withoutloginkey"`` for pre-auth,
            derived key for post-auth).
        action: HNAP action name (e.g., ``"Login"``).
        algorithm: Hash algorithm (``"md5"`` or ``"sha256"``).

    Returns:
        Header value string.
    """
    timestamp = str(int(time.time() * 1000) % _TIMESTAMP_MODULO)
    soap_action_uri = f'"{HNAP_NAMESPACE}{action}"'
    auth_hash = hmac_hex(
        key=private_key,
        message=timestamp + soap_action_uri,
        algorithm=algorithm,
    )
    return f"{auth_hash} {timestamp}"
