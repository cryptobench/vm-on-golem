from fastapi.testclient import TestClient
from provider.main import app


def test_provider_info_endpoint_returns_eth_and_contracts():
    client = TestClient(app)
    # Override a few config fields
    old = dict(app.container.config())
    cfg = dict(old)
    cfg.update({
        "PROVIDER_ID": "0xProv",
        "STREAM_PAYMENT_ADDRESS": "0xStream",
        "GLM_TOKEN_ADDRESS": "0xGLM",
    })
    try:
        app.container.config.override(cfg)
        resp = client.get("/api/v1/provider/info")
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider_id"] == "0xProv"
        assert data["stream_payment_address"] == "0xStream"
        assert data["glm_token_address"] == "0xGLM"
    finally:
        app.container.config.override(old)
