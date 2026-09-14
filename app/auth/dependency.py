"""`Authorization: Zoho-oauthtoken <token>` guard.

Registered as an APIKeyHeader security scheme so Swagger's Authorize button
works: paste the full header value, e.g. `Zoho-oauthtoken 1000.abc.def`.
"""

from fastapi import Security
from fastapi.security import APIKeyHeader

from app.auth.tokens import token_store
from app.schemas.zoho import ZohoAPIError

zoho_oauth_header = APIKeyHeader(
    name="Authorization",
    scheme_name="ZohoOAuthToken",
    auto_error=False,
    description=(
        "Zoho OAuth header. Value format: `Zoho-oauthtoken <access_token>`. "
        "Grab a token from `POST /oauth/v2/token` first."
    ),
)

TOKEN_PREFIX = "zoho-oauthtoken"


def require_token(authorization: str | None = Security(zoho_oauth_header)) -> str:
    if not authorization:
        raise ZohoAPIError("INVALID_TOKEN", "invalid oauth token")

    scheme, _, value = authorization.strip().partition(" ")
    token = value.strip()
    if scheme.lower() != TOKEN_PREFIX or not token:
        raise ZohoAPIError("INVALID_TOKEN", "invalid oauth token")

    if not token_store.is_valid(token):
        raise ZohoAPIError("INVALID_TOKEN", "invalid oauth token")

    return token
