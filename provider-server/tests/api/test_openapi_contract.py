from provider.app import app


def test_openapi_exposes_typed_provider_contracts():
    schema = app.openapi()

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
    components = schema["components"]["schemas"]
    assert "ssh_user" in components["VMAccessInfo"]["properties"]
    assert "ssh_user" in components["VMAccessInfo"]["required"]
    assert "ssh_user" in components["VMAccessPendingResponse"]["properties"]
    assert "ssh_user" in components["VMAccessPendingResponse"]["required"]
    for schema_name in ["VMInfo", "CreateVMJobResponse", "CreateVMJobStatus"]:
        properties = components[schema_name]["properties"]
        assert "lifecycle_stage" in properties
        assert "status_message" in properties
        assert "progress" in properties
        assert "transitioning" in properties
        assert "next_poll_seconds" in properties
