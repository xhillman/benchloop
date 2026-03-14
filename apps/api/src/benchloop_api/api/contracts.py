from collections.abc import Iterable
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, ConfigDict

from benchloop_api.errors import ErrorEnvelope

API_V1_PREFIX = "/api/v1"
AUTH_SCHEME_NAME = "ClerkBearer"
AUTH_SCHEME_DESCRIPTION = (
    "Use a Clerk-issued session token in the Authorization header "
    "as `Bearer <token>`."
)

_ERROR_RESPONSE_DESCRIPTIONS = {
    400: "Request rejected.",
    401: "Authentication required.",
    403: "Permission denied.",
    404: "Resource not found.",
    409: "Request conflicts with current state.",
    422: "Request validation failed.",
    502: "Upstream provider request failed.",
    500: "Unexpected server error.",
}


class ApiContractModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class ApiRequestModel(ApiContractModel):
    """Base model for request payloads exposed on the public API."""


class ApiResponseModel(ApiContractModel):
    """Base model for response payloads exposed on the public API."""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


def build_error_responses(*status_codes: int) -> dict[int, dict[str, Any]]:
    return {
        status_code: {
            "description": _ERROR_RESPONSE_DESCRIPTIONS[status_code],
            "model": ErrorEnvelope,
        }
        for status_code in status_codes
    }


def install_openapi_contract(app: FastAPI) -> None:
    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )

        components = openapi_schema.setdefault("components", {})
        security_schemes = components.setdefault("securitySchemes", {})
        security_schemes[AUTH_SCHEME_NAME] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": AUTH_SCHEME_DESCRIPTION,
        }

        app.openapi_schema = openapi_schema
        return openapi_schema

    app.openapi = custom_openapi


def documented_error_statuses(
    *,
    include_auth: bool = False,
    extra_statuses: Iterable[int] = (),
) -> dict[int, dict[str, Any]]:
    status_codes = [422, 500]
    if include_auth:
        status_codes = [401, 403, *status_codes]
    status_codes.extend(extra_statuses)

    seen: set[int] = set()
    ordered_status_codes = []
    for status_code in status_codes:
        if status_code not in seen:
            seen.add(status_code)
            ordered_status_codes.append(status_code)

    return build_error_responses(*ordered_status_codes)
