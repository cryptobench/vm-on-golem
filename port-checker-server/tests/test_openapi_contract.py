from port_checker.app import create_app
from port_checker.config import Settings


def test_openapi_exposes_typed_port_checker_contracts():
    schema = create_app(Settings()).openapi()

    paths = schema["paths"]
    assert paths["/check-ports"]["post"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["$ref"].endswith("/PortCheckResponse")
    assert paths["/health"]["get"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ]["$ref"].endswith("/HealthResponse")
    assert "proxy_provider_get" in {
        operation["operationId"]
        for methods in paths.values()
        for operation in methods.values()
    }
