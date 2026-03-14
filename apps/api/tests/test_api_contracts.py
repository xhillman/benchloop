from pydantic import ValidationError

from benchloop_api.api.contracts import (
    ApiRequestModel,
    ApiResponseModel,
    build_error_responses,
)
from benchloop_api.errors import ErrorEnvelope


class ExampleRequest(ApiRequestModel):
    prompt: str


class ExampleResponse(ApiResponseModel):
    status: str


def test_request_models_forbid_extra_fields_and_strip_strings() -> None:
    payload = ExampleRequest.model_validate(
        {
            "prompt": "  hello world  ",
        },
    )

    assert payload.prompt == "hello world"

    try:
        ExampleRequest.model_validate({"prompt": "ok", "unexpected": True})
    except ValidationError as exc:
        errors = exc.errors()
    else:
        raise AssertionError("Expected request model validation to fail on extra fields.")

    assert errors[0]["type"] == "extra_forbidden"


def test_response_models_support_attribute_loading() -> None:
    class ResponsePayload:
        status = "ok"

    payload = ExampleResponse.model_validate(ResponsePayload())

    assert payload.status == "ok"


def test_error_response_docs_use_shared_error_envelope() -> None:
    responses = build_error_responses(401, 404, 500)

    assert responses == {
        401: {
            "description": "Authentication required.",
            "model": ErrorEnvelope,
        },
        404: {
            "description": "Resource not found.",
            "model": ErrorEnvelope,
        },
        500: {
            "description": "Unexpected server error.",
            "model": ErrorEnvelope,
        },
    }
