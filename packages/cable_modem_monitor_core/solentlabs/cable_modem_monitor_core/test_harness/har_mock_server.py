"""Auth-aware HAR mock server for end-to-end testing.

Re-exports from submodules for backwards compatibility.
Implementation split across: routes.py, auth/ subpackage, server.py.

See ONBOARDING_SPEC.md HAR Mock Server section.
"""

from .auth import (
    AuthHandler,
    BasicAuthHandler,
    FormAuthHandler,
    FormSjclAuthHandler,
    HnapAuthHandler,
    create_auth_handler,
)
from .routes import RouteEntry, build_routes, normalize_path
from .server import HARMockServer

__all__ = [
    "AuthHandler",
    "BasicAuthHandler",
    "FormAuthHandler",
    "FormSjclAuthHandler",
    "HARMockServer",
    "HnapAuthHandler",
    "RouteEntry",
    "build_routes",
    "create_auth_handler",
    "normalize_path",
]
