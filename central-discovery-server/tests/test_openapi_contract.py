from central_discovery.main import app


def test_openapi_exposes_typed_central_discovery_contracts():
    schema = app.openapi()

    paths = schema["paths"]
    assert paths["/api/v1/advertisements"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["items"]["$ref"].endswith("/AdvertisementResponse")
    assert paths["/api/v1/advertisements/{provider_id}"]["delete"]["responses"][
        "200"
    ]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/DeleteAdvertisementResponse"
    )
    assert paths["/health"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["$ref"].endswith("/HealthResponse")
