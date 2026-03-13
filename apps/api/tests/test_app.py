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
    assert response.json()["info"]["title"] == "Benchloop API"


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
