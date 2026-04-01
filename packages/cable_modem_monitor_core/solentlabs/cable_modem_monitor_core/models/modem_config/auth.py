"""Auth strategy models for modem.yaml.

Eight strategies as a discriminated union on the 'strategy' field.
Per MODEM_YAML_SPEC.md Auth section.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag


class NoneAuth(BaseModel):
    """No authentication required."""

    model_config = ConfigDict(extra="forbid")
    strategy: Literal["none"]


class BasicAuth(BaseModel):
    """HTTP Basic Authentication."""

    model_config = ConfigDict(extra="forbid")
    strategy: Literal["basic"]
    challenge_cookie: bool = False
    cookie_name: str = ""


class FormSuccess(BaseModel):
    """Success detection for form auth."""

    model_config = ConfigDict(extra="forbid")
    redirect: str = ""
    indicator: str = ""


class FormAuth(BaseModel):
    """HTML form POST login."""

    model_config = ConfigDict(extra="forbid")
    strategy: Literal["form"]
    action: str
    method: str = "POST"
    username_field: str = "username"
    password_field: str = "password"
    encoding: Literal["plain", "base64"] = "plain"
    cookie_name: str = ""
    hidden_fields: dict[str, str] = Field(default_factory=dict)
    login_page: str = ""
    form_selector: str = ""
    success: FormSuccess | None = None


class FormNonceAuth(BaseModel):
    """Form POST with client-generated nonce."""

    model_config = ConfigDict(extra="forbid")
    strategy: Literal["form_nonce"]
    action: str
    username_field: str = "username"
    password_field: str = "password"
    nonce_field: str
    nonce_length: int = 8
    cookie_name: str = ""
    success_prefix: str = "Url:"
    error_prefix: str = "Error:"


class UrlTokenAuth(BaseModel):
    """Credentials encoded in URL query string."""

    model_config = ConfigDict(extra="forbid")
    strategy: Literal["url_token"]
    login_page: str
    login_prefix: str = ""
    success_indicator: str = ""
    ajax_login: bool = False
    auth_header_data: bool = False
    cookie_name: str = ""
    token_prefix: str = ""


class HnapAuth(BaseModel):
    """HNAP HMAC challenge-response authentication."""

    model_config = ConfigDict(extra="forbid")
    strategy: Literal["hnap"]
    hmac_algorithm: Literal["md5", "sha256"]


class FormPbkdf2Auth(BaseModel):
    """Multi-round-trip PBKDF2 challenge-response auth."""

    model_config = ConfigDict(extra="forbid")
    strategy: Literal["form_pbkdf2"]
    login_endpoint: str
    salt_trigger: str = "seeksalthash"
    pbkdf2_iterations: int
    pbkdf2_key_length: int
    double_hash: bool = True
    csrf_init_endpoint: str = ""
    csrf_header: str = ""
    cookie_name: str = ""


class FormSjclAuth(BaseModel):
    """SJCL (Stanford JavaScript Crypto Library) AES-CCM encrypted form auth.

    Some modem firmwares use the SJCL JavaScript library to encrypt
    credentials client-side with AES-CCM before POSTing. The server
    response is also encrypted — must decrypt to extract the CSRF
    nonce for subsequent requests. Key is derived via PBKDF2 from
    the password and a per-session salt provided by the server.

    Requires the ``cryptography`` package: install Core with the
    ``[sjcl]`` extra.
    """

    model_config = ConfigDict(extra="forbid")
    strategy: Literal["form_sjcl"]
    login_page: str = "/"
    login_endpoint: str
    session_validation_endpoint: str = ""
    pbkdf2_iterations: int
    pbkdf2_key_length: int
    ccm_tag_length: int = 16
    encrypt_aad: str = "loginPassword"
    decrypt_aad: str = "nonce"
    csrf_header: str = ""
    cookie_name: str = ""


AuthConfig = Annotated[
    Annotated[NoneAuth, Tag("none")]
    | Annotated[BasicAuth, Tag("basic")]
    | Annotated[FormAuth, Tag("form")]
    | Annotated[FormNonceAuth, Tag("form_nonce")]
    | Annotated[UrlTokenAuth, Tag("url_token")]
    | Annotated[HnapAuth, Tag("hnap")]
    | Annotated[FormPbkdf2Auth, Tag("form_pbkdf2")]
    | Annotated[FormSjclAuth, Tag("form_sjcl")],
    Discriminator("strategy"),
]

# Auth strategies valid per transport
HTTP_AUTH_STRATEGIES: frozenset[str] = frozenset(
    {
        "none",
        "basic",
        "form",
        "form_nonce",
        "url_token",
        "form_pbkdf2",
        "form_sjcl",
    }
)
HNAP_AUTH_STRATEGIES: frozenset[str] = frozenset({"hnap"})
