"""Mock auth handlers — driven by modem.yaml config.

Subpackage structure:
- base.py — AuthHandler (no-auth base)
- basic.py — BasicAuthHandler (HTTP Basic)
- cbn.py — FormCbnAuthHandler (CBN AES-256-CBC crypto protocol)
- form.py — FormAuthHandler (cookie/IP session gating)
- sjcl.py — FormSjclAuthHandler (AES-CCM crypto protocol)
- hnap.py — HnapAuthHandler (HMAC challenge-response protocol)
- factory.py — create_auth_handler dispatch
"""

from .base import AuthHandler
from .basic import BasicAuthHandler
from .cbn import FormCbnAuthHandler
from .factory import create_auth_handler
from .form import FormAuthHandler
from .hnap import HnapAuthHandler
from .pbkdf2 import FormPbkdf2AuthHandler
from .sjcl import FormSjclAuthHandler

__all__ = [
    "AuthHandler",
    "BasicAuthHandler",
    "FormAuthHandler",
    "FormCbnAuthHandler",
    "FormPbkdf2AuthHandler",
    "FormSjclAuthHandler",
    "HnapAuthHandler",
    "create_auth_handler",
]
