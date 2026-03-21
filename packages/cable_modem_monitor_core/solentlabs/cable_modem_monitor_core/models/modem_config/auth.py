"""Auth strategy models for modem.yaml.

Seven strategies as a discriminated union on the 'strategy' field.
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


AuthConfig = Annotated[
    Annotated[NoneAuth, Tag("none")]
    | Annotated[BasicAuth, Tag("basic")]
    | Annotated[FormAuth, Tag("form")]
    | Annotated[FormNonceAuth, Tag("form_nonce")]
    | Annotated[UrlTokenAuth, Tag("url_token")]
    | Annotated[HnapAuth, Tag("hnap")]
    | Annotated[FormPbkdf2Auth, Tag("form_pbkdf2")],
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
    }
)
HNAP_AUTH_STRATEGIES: frozenset[str] = frozenset({"hnap"})
