from central_discovery.main import app


def test_openapi_keeps_only_http_health_contract():
    schema = app.openapi()
    paths = schema["paths"]

    assert all("advertisement" not in path for path in paths)
    assert paths["/health"]["get"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ]["$ref"].endswith("/HealthResponse")
