import asyncio

import httpx

from benchloop_api.app import create_app


def request(app, method: str, path: str) -> httpx.Response:
    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path)

    return asyncio.run(run_request())


def test_health_endpoint_reports_runtime_status() -> None:
    app = create_app()

    response = request(app, "GET", "/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "benchloop-api",
        "environment": "local",
    }


def test_openapi_docs_are_enabled_outside_production() -> None:
    app = create_app({"environment": "development"})

    response = request(app, "GET", "/openapi.json")

    assert response.status_code == 200
    schema = response.json()

    assert schema["info"]["title"] == "Benchloop API"
    assert schema["components"]["securitySchemes"] == {
        "ClerkBearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": (
                "Use a Clerk-issued session token in the Authorization header "
                "as `Bearer <token>`."
            ),
        }
    }
    assert schema["paths"]["/api/v1/health"]["get"]["responses"]["500"]["content"] == {
        "application/json": {
            "schema": {"$ref": "#/components/schemas/ErrorEnvelope"},
        }
    }


def test_openapi_docs_are_disabled_in_production() -> None:
    app = create_app({"environment": "production"})

    response = request(app, "GET", "/openapi.json")

    assert response.status_code == 404


def test_http_exceptions_use_structured_error_envelope() -> None:
    app = create_app()

    response = request(app, "GET", "/api/v1/missing")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Not Found",
            "details": None,
        }
    }


def test_app_wires_encryption_service() -> None:
    app = create_app({"encryption_key": "test-encryption-key-material"})

    ciphertext = app.state.encryption_service.encrypt("sk-test-123")

    assert ciphertext != "sk-test-123"
    assert app.state.encryption_service.decrypt(ciphertext) == "sk-test-123"
