"""Bearer token authentication for relay endpoints."""

from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    SimpleUser,
)
from starlette.requests import HTTPConnection

from admiral_mcp.config import get_config


class BearerAuthBackend(AuthenticationBackend):
    async def authenticate(self, conn: HTTPConnection):
        config = get_config()
        auth_header = conn.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None
        token = auth_header[7:]
        if token != config.relay_token:
            return None
        return AuthCredentials(["authenticated"]), SimpleUser("relay")


def require_auth(conn: HTTPConnection) -> bool:
    """Check Bearer token on a request. Returns True if valid."""
    config = get_config()
    auth_header = conn.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return False
    token = auth_header[7:]
    return token == config.relay_token
