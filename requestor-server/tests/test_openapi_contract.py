import requestor.api.main as api_main


def test_openapi_exposes_typed_requestor_contracts():
    schema = api_main.app.openapi()

    paths = schema["paths"]
    assert paths["/api/v1/providers"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["$ref"].endswith("/ProviderListResponse")
    assert paths["/api/v1/settings"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["$ref"].endswith("/SettingsResponse")
    assert paths["/api/v1/vms/{name}/snapshots"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["items"]["$ref"].endswith("/VMSnapshot")
