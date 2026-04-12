"""Mock auth handlers — driven by modem.yaml config.

Subpackage structure:
- base.py — AuthHandler (no-auth base) + shared ActionConfig helper
- basic.py — BasicAuthHandler (HTTP Basic)
- form.py — FormAuthHandler (cookie/IP session gating)
- form_cbn.py — FormCbnAuthHandler (CBN AES-256-CBC crypto protocol)
- form_nonce.py — FormNonceAuthHandler (serves login page for encoding detection)
- form_pbkdf2.py — FormPbkdf2AuthHandler (PBKDF2 challenge-response)
- form_sjcl.py — FormSjclAuthHandler (AES-CCM crypto protocol)
- hnap.py — HnapAuthHandler (HMAC challenge-response protocol)
- factory.py — create_auth_handler dispatch

Module names match ``auth.strategy`` literals for dynamic import.
"""

from .base import AuthHandler
from .basic import BasicAuthHandler
from .factory import create_auth_handler
from .form import FormAuthHandler
from .form_cbn import FormCbnAuthHandler
from .form_nonce import FormNonceAuthHandler
from .form_pbkdf2 import FormPbkdf2AuthHandler
from .form_sjcl import FormSjclAuthHandler
from .hnap import HnapAuthHandler

__all__ = [
    "AuthHandler",
    "BasicAuthHandler",
    "FormAuthHandler",
    "FormCbnAuthHandler",
    "FormNonceAuthHandler",
    "FormPbkdf2AuthHandler",
    "FormSjclAuthHandler",
    "HnapAuthHandler",
    "create_auth_handler",
]
