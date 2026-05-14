from fastapi.testclient import TestClient

from provider.main import app


class StubHostLiveService:
    async def stream_host(self, websocket, history_range: str = "1h"):
        await websocket.accept()
        await websocket.send_json(
            {
                "type": "hello",
                "generated_at": "2026-05-14T18:00:00+00:00",
                "scope": None,
                "data": {
                    "protocol": "provider-host-live.v1",
                    "history_range": history_range,
                },
                "error": None,
            }
        )


def test_host_live_route_is_websocket_endpoint():
    client = TestClient(app)
    with app.container.host_live_service.override(StubHostLiveService()):
        with client.websocket_connect(
            "/api/v1/monitoring/host/live?history_range=6h"
        ) as websocket:
            event = websocket.receive_json()

    assert event["type"] == "hello"
    assert event["data"]["protocol"] == "provider-host-live.v1"
    assert event["data"]["history_range"] == "6h"
