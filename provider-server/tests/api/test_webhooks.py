from fastapi.testclient import TestClient

from provider.main import app
from provider.webhooks.repo import WebhookRepository
from provider.webhooks.service import WebhookService


def test_webhook_admin_crud_preview_test_and_deliveries(tmp_path, monkeypatch):
    service = WebhookService(
        {"PROVIDER_ID": "provider-1", "WEBHOOK_RETRY_DELAY_SECONDS": 0},
        WebhookRepository(str(tmp_path / "monitoring.sqlite")),
    )

    async def fake_post(_url, _payload):
        return 204, None

    monkeypatch.setattr(service, "_post_webhook", fake_post)

    with app.container.webhook_service.override(service):
        client = TestClient(app)
        created = client.post(
            "/api/v1/monitoring/webhooks",
            json={
                "id": None,
                "name": "Ops",
                "url": "https://example.test/webhook",
                "enabled": True,
                "service_type": "discord",
                "events": ["vm.ready"],
                "template": {
                    "title": "{{summary}}",
                    "message": "VM {{resource.id}} ready",
                    "color": "severity",
                    "fields": [{"name": "Event", "value": "{{event.type}}"}],
                    "footer": "Golem Provider",
                },
                "last_status": None,
                "last_http_status": None,
                "last_error": None,
                "last_delivered_at": None,
            },
        )
        assert created.status_code == 200
        webhook_id = created.json()["id"]

        preview = client.post(
            "/api/v1/monitoring/webhooks/preview",
            json={
                "service_type": "discord",
                "event_type": "vm.ready",
                "template": created.json()["template"],
            },
        )
        assert preview.status_code == 200
        assert preview.json()["payload"]["content"] == "VM requestor-vm-id ready"

        test = client.post(
            f"/api/v1/monitoring/webhooks/{webhook_id}/test",
            json={"event_type": "vm.ready"},
        )
        assert test.status_code == 200
        assert test.json()["ok"] is True

        legacy_test = client.post(f"/api/v1/monitoring/webhooks/{webhook_id}/test")
        assert legacy_test.status_code == 200
        assert legacy_test.json()["ok"] is True

        deliveries = client.get(f"/api/v1/monitoring/webhooks/{webhook_id}/deliveries")
        assert deliveries.status_code == 200
        assert {item["event_type"] for item in deliveries.json()} == {
            "alert.fired",
            "vm.ready",
        }

        updated_payload = created.json()
        updated_payload["name"] = "Ops renamed"
        updated_payload["enabled"] = False
        updated = client.put(
            f"/api/v1/monitoring/webhooks/{webhook_id}", json=updated_payload
        )
        assert updated.status_code == 200
        assert updated.json()["name"] == "Ops renamed"
        assert updated.json()["enabled"] is False
        assert client.get("/api/v1/monitoring/webhooks").json()[0]["enabled"] is False

        deleted = client.delete(f"/api/v1/monitoring/webhooks/{webhook_id}")
        assert deleted.status_code == 204
        assert client.get("/api/v1/monitoring/webhooks").json() == []


def test_webhook_rejects_empty_event_selection(tmp_path):
    service = WebhookService({}, WebhookRepository(str(tmp_path / "monitoring.sqlite")))
    with app.container.webhook_service.override(service):
        client = TestClient(app)
        response = client.post(
            "/api/v1/monitoring/webhooks",
            json={
                "id": None,
                "name": "Bad",
                "url": "https://example.test/webhook",
                "enabled": True,
                "service_type": "slack",
                "events": [],
                "template": {
                    "title": "{{summary}}",
                    "message": "{{summary}}",
                    "color": "severity",
                    "fields": [],
                    "footer": "Golem Provider",
                },
                "last_status": None,
                "last_http_status": None,
                "last_error": None,
                "last_delivered_at": None,
            },
        )

    assert response.status_code == 422
