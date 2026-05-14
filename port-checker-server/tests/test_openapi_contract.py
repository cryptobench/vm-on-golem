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
    assert paths["/check-tls"]["post"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["$ref"].endswith("/TlsCheckResponse")
    operation_ids = {
        operation["operationId"]
        for methods in paths.values()
        for operation in methods.values()
    }
    assert "check_ports_check_ports_post" in operation_ids
    assert "health_check_health_get" in operation_ids
    assert all(not operation_id.startswith("proxy_") for operation_id in operation_ids)
    assert all(not path.startswith("/proxy") for path in paths)
