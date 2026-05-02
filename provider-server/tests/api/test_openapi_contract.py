from provider.app import create_app


def test_openapi_exposes_typed_provider_contracts():
    schema = create_app().openapi()

    assert schema["openapi"]
    paths = schema["paths"]
    assert "/api/v1/openapi.json" not in paths
    assert paths["/api/v1/vms"]["post"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["$ref"].endswith("/VMInfo")
    assert paths["/api/v1/vms"]["post"]["responses"]["202"]["content"][
        "application/json"
    ]["schema"]["$ref"].endswith("/CreateVMJobResponse")
    assert paths["/api/v1/vms/{requestor_name}/access"]["get"]["responses"]["202"][
        "content"
    ]["application/json"]["schema"]["$ref"].endswith("/VMAccessPendingResponse")
