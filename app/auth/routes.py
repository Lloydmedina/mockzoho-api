"""Zoho Accounts OAuth endpoints.

Mirrors accounts.zoho.com behaviour, including the quirk that credential
failures come back as HTTP 200 with an `{"error": "..."}` body.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from app.auth.tokens import token_store
from app.config import settings

router = APIRouter(tags=["OAuth"])

DEFAULT_SCOPE = "ZohoCRM.modules.ALL,ZohoCRM.settings.ALL"
TEST_CLIENT_ID = "1000.MOCKCLIENTID"
TEST_CLIENT_SECRET = "mock_client_secret"
TEST_REFRESH_TOKEN = "1000.mockrefreshtoken.refresh"
SUPPORTED_GRANTS = {"refresh_token", "client_credentials", "authorization_code"}


async def _merged_params(request: Request) -> dict[str, str]:
    params: dict[str, str] = dict(request.query_params)
    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        params.update({key: str(value) for key, value in form.items()})
    elif "application/json" in content_type:
        try:
            body = await request.json()
        except Exception:
            body = None
        if isinstance(body, dict):
            params.update({key: str(value) for key, value in body.items()})
    return params


def _oauth_error(error: str) -> JSONResponse:
    return JSONResponse(status_code=200, content={"error": error})


@router.post(
    "/oauth/v2/token",
    summary="Issue an access token",
    description=(
        "Supports `grant_type=refresh_token` (server-to-server, the recommended flow), "
        "`client_credentials`, and `authorization_code`. Parameters may be sent as query "
        "string, form-encoded body, or JSON.\n\n"
        "Credentials are accepted as-is unless `MOCKZOHO_EXPECTED_CLIENT_ID` / "
        "`MOCKZOHO_EXPECTED_CLIENT_SECRET` / `MOCKZOHO_EXPECTED_REFRESH_TOKEN` are configured. "
        "Failures return HTTP 200 with an `{\"error\": ...}` body, exactly like Zoho.\n\n"
        f"For local testing use `client_id={TEST_CLIENT_ID}`, `client_secret={TEST_CLIENT_SECRET}`, "
        f"`refresh_token={TEST_REFRESH_TOKEN}` (any values work unless enforcement is configured)."
    ),
)
async def issue_token(
    request: Request,
    grant_type: Annotated[
        str | None,
        Query(
            description="Grant type: `refresh_token`, `client_credentials`, or `authorization_code`",
            example="refresh_token",
        ),
    ] = None,
    client_id: Annotated[
        str | None,
        Query(description="Client ID from the Zoho API console", example=TEST_CLIENT_ID),
    ] = None,
    client_secret: Annotated[
        str | None,
        Query(description="Client secret from the Zoho API console", example=TEST_CLIENT_SECRET),
    ] = None,
    refresh_token: Annotated[
        str | None,
        Query(description="Refresh token (required for `grant_type=refresh_token`)", example=TEST_REFRESH_TOKEN),
    ] = None,
    code: Annotated[
        str | None,
        Query(description="Authorization code (required for `grant_type=authorization_code`)"),
    ] = None,
    redirect_uri: Annotated[
        str | None,
        Query(description="Callback URL registered in the Zoho API console (required for `grant_type=authorization_code`)"),
    ] = None,
    soid: Annotated[
        str | None,
        Query(description="Zoho organization ID (required for `grant_type=client_credentials`)"),
    ] = None,
    scope: Annotated[
        str | None,
        Query(description="Comma-separated scopes for the issued token", example=DEFAULT_SCOPE),
    ] = None,
) -> JSONResponse:
    params = await _merged_params(request)
    grant_type = params.get("grant_type", "refresh_token")

    if grant_type not in SUPPORTED_GRANTS:
        return _oauth_error("unsupported_grant_type")

    client_id = params.get("client_id")
    client_secret = params.get("client_secret")
    if not client_id or not client_secret:
        return _oauth_error("invalid_client")
    if settings.expected_client_id and client_id != settings.expected_client_id:
        return _oauth_error("invalid_client")
    if settings.expected_client_secret and client_secret != settings.expected_client_secret:
        return _oauth_error("invalid_client")

    if grant_type == "refresh_token":
        refresh_token = params.get("refresh_token")
        if not refresh_token:
            return _oauth_error("invalid_code")
        if settings.expected_refresh_token and refresh_token != settings.expected_refresh_token:
            return _oauth_error("invalid_code")
    elif grant_type == "client_credentials":
        if not params.get("soid"):
            return _oauth_error("invalid_request")
    elif grant_type == "authorization_code":
        if not params.get("code"):
            return _oauth_error("invalid_code")

    scope = params.get("scope") or DEFAULT_SCOPE
    token = token_store.issue(scope)

    if grant_type == "refresh_token":
        token_store.link_refresh_token(refresh_token, token.access_token)

    payload: dict[str, Any] = {
        "access_token": token.access_token,
        "api_domain": settings.api_domain,
        "token_type": "Bearer",
        "expires_in": token.expires_in,
    }
    if grant_type == "client_credentials":
        payload["scope"] = token.scope
    if grant_type == "authorization_code":
        refresh_token_value = f"1000.{token.access_token.split('.')[1]}.refresh"
        token_store.link_refresh_token(refresh_token_value, token.access_token)
        payload["refresh_token"] = refresh_token_value
    return JSONResponse(status_code=200, content=payload)


@router.post(
    "/oauth/v2/token/revoke",
    summary="Revoke a refresh or access token",
    description="Returns `{\"status\": \"success\"}` whether or not the token was known, like Zoho.",
)
@router.post(
    "/oauth/v2/revoke/token",
    summary="Revoke a refresh or access token (developer docs path)",
    description="Alias for `/oauth/v2/token/revoke`. The newer Zoho developer docs use this path.",
)
async def revoke_token(
    request: Request,
    token: Annotated[
        str | None,
        Query(description="Access or refresh token to revoke", example="1000.mockrefreshtoken.refresh"),
    ] = None,
) -> JSONResponse:
    params = await _merged_params(request)
    candidate = params.get("token") or params.get("refresh_token") or ""
    token_store.revoke(candidate)
    return JSONResponse(status_code=200, content={"status": "success"})
