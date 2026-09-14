"""Zoho CRM response envelopes and the error catalog.

Every route builds responses through these helpers so the wire format stays
identical to the real API.
"""

from typing import Any

from pydantic import BaseModel, Field

from app.utils import audit_stamp

# code -> (http status, default message)
ERROR_CATALOG: dict[str, tuple[int, str]] = {
    "INVALID_TOKEN": (401, "invalid oauth token"),
    "OAUTH_SCOPE_MISMATCH": (401, "invalid oauth scope to access this URL"),
    "AUTHENTICATION_FAILURE": (401, "authentication failed"),
    "NO_PERMISSION": (403, "no permission to read"),
    "INVALID_MODULE": (400, "the module name given seems to be invalid"),
    "RESOURCE_NOT_FOUND": (404, "the record does not exist"),
    "INVALID_URL_PATTERN": (400, "Please check if the URL trying to access is a correct one"),
    "MANDATORY_NOT_FOUND": (400, "required field not found"),
    "INVALID_DATA": (400, "invalid data"),
    "INVALID_QUERY_PARAM": (400, "one of the expected parameter is missing or invalid"),
    "INVALID_QUERY": (400, "invalid query formed"),
    "REQUIRED_PARAM_MISSING": (400, "required parameter is missing"),
    "DUPLICATE_DATA": (400, "duplicate data"),
    "LIMIT_EXCEEDED": (400, "maximum number of records allowed is exceeded"),
    "API_LIMIT_EXCEEDED": (429, "number of allowed API calls exceeded"),
    "TOO_MANY_REQUESTS": (429, "concurrency limit exceeded"),
    "INTERNAL_ERROR": (500, "internal server error"),
}


class ZohoAPIError(Exception):
    """Raised anywhere in the app; rendered as a Zoho-shaped error body."""

    def __init__(
        self,
        code: str,
        message: str | None = None,
        details: dict[str, Any] | None = None,
        status_code: int | None = None,
    ) -> None:
        default_status, default_message = ERROR_CATALOG.get(code, (400, "error"))
        self.code = code
        self.message = message or default_message
        self.details = details or {}
        self.status_code = status_code or default_status
        super().__init__(f"{code}: {self.message}")

    def body(self) -> dict[str, Any]:
        return error_body(self.code, self.message, self.details)


def error_body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "code": code,
        "details": details or {},
        "message": message,
        "status": "error",
    }


def list_info(page: int, per_page: int, count: int, more_records: bool) -> dict[str, Any]:
    return {
        "per_page": per_page,
        "count": count,
        "page": page,
        "more_records": more_records,
    }


def record_list_body(
    records: list[dict[str, Any]],
    page: int,
    per_page: int,
    more_records: bool,
) -> dict[str, Any]:
    return {
        "data": records,
        "info": list_info(page, per_page, len(records), more_records),
    }


def success_result(record_id: str, created_time: str, modified_time: str, message: str) -> dict[str, Any]:
    return {
        "code": "SUCCESS",
        "details": {
            "Modified_Time": modified_time,
            "Modified_By": audit_stamp(),
            "Created_Time": created_time,
            "id": record_id,
            "Created_By": audit_stamp(),
            "$approval_state": "approved",
        },
        "message": message,
        "status": "success",
    }


def error_result(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return error_body(code, message, details)


def write_body(results: list[dict[str, Any]]) -> dict[str, Any]:
    return {"data": results}


def delete_success(record_id: str) -> dict[str, Any]:
    return {
        "code": "SUCCESS",
        "details": {"id": record_id},
        "message": "record deleted",
        "status": "success",
    }


class TokenResponse(BaseModel):
    access_token: str
    scope: str = "ZohoCRM.modules.ALL,ZohoCRM.settings.ALL"
    api_domain: str
    token_type: str = "Bearer"
    expires_in: int


class RecordsPayload(BaseModel):
    """Zoho write payload: {"data": [ ... ], "trigger": [...]}"""

    data: list[dict[str, Any]] = Field(default_factory=list)
    trigger: list[str] | None = None
    duplicate_check_fields: list[str] | None = None


class COQLPayload(BaseModel):
    select_query: str
