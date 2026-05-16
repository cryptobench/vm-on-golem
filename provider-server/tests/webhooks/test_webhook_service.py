import asyncio
import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from provider.webhooks.domain import (
    WebhookConfig,
    WebhookDeliveryAttempt,
    WebhookPreviewRequest,
    WebhookTemplate,
)
from provider.webhooks.repo import WebhookRepository
from provider.webhooks.service import WebhookService


def test_repo_migrates_legacy_webhook_rows_and_retains_recent_attempts(tmp_path: Path):
    db_path = tmp_path / "monitoring.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE webhooks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                enabled INTEGER NOT NULL,
                last_status TEXT,
                last_error TEXT,
                last_delivered_at TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO webhooks (name, url, enabled) VALUES (?, ?, ?)",
            ("Legacy", "https://example.test/webhook", 1),
        )

    repo = WebhookRepository(str(db_path))
    repo.init_schema()

    webhook = repo.list_webhooks()[0]
    assert webhook.name == "Legacy"
    assert webhook.service_type == "generic_json"
    assert "alert.fired" in webhook.events
    assert webhook.template.title == "{{summary}}"

    assert webhook.id is not None
    for index in range(105):
        repo.add_delivery_attempt(
            WebhookDeliveryAttempt(
                webhook_id=webhook.id,
                event_id=f"event-{index}",
                event_type="vm.ready",
                attempt=1,
                status="failed",
                error="boom",
            )
        )

    attempts = repo.list_delivery_attempts(webhook.id)
    assert len(attempts) == 100
    assert attempts[0].attempted_at.tzinfo is not None
    assert attempts[-1].event_id == "event-5"


@pytest.mark.asyncio
async def test_service_filters_events_formats_payloads_and_retries(tmp_path: Path):
    repo = WebhookRepository(str(tmp_path / "monitoring.sqlite"))
    service = WebhookService(
        {"PROVIDER_ID": "provider-1", "WEBHOOK_RETRY_DELAY_SECONDS": 0},
        repo,
    )
    matching = service.create_webhook(
        WebhookConfig(
            name="Discord",
            url="https://example.test/discord",
            service_type="discord",
            events=["vm.ready"],
            template=WebhookTemplate(
                title="{{summary}}",
                message="VM {{resource.id}} is ready",
                footer="{{provider.id}}",
            ),
        )
    )
    service.create_webhook(
        WebhookConfig(
            name="Ignored",
            url="https://example.test/ignored",
            service_type="slack",
            events=["alert.fired"],
        )
    )
    service._post_webhook = AsyncMock(side_effect=[(500, "bad"), (204, None)])

    await service.emit(
        "vm.ready",
        resource_type="vm",
        resource_id="vm-a",
        severity="info",
        summary="VM is online",
        data={"status": "running"},
    )

    assert service._post_webhook.await_count == 2
    first_payload = service._post_webhook.await_args_list[0].args[1]
    assert first_payload["content"] == "VM vm-a is ready"
    assert first_payload["embeds"][0]["footer"]["text"] == "provider-1"

    assert matching.id is not None
    attempts = repo.list_delivery_attempts(matching.id)
    assert [attempt.status for attempt in attempts] == ["success", "failed"]
    assert repo.get_webhook(matching.id).last_status == "success"


def test_preview_uses_same_formatter_as_delivery(tmp_path: Path):
    service = WebhookService(
        {"PROVIDER_ID": "provider-1"}, WebhookRepository(str(tmp_path / "db.sqlite"))
    )
    request = WebhookPreviewRequest(
        service_type="slack",
        event_type="payment.stream.lost",
        template=WebhookTemplate(
            title="{{summary}}",
            message="{{data.vm_id}} lost stream {{resource.id}}",
        ),
    )

    preview = service.preview(request)
    event = service.sample_event("payment.stream.lost")
    payload = service.format_payload("slack", request.template, event)

    assert preview.payload == payload
    assert preview.payload["text"] == "requestor-vm-id lost stream 42"


def test_generic_json_preview_returns_canonical_event(tmp_path: Path):
    service = WebhookService(
        {"PROVIDER_ID": "provider-1"}, WebhookRepository(str(tmp_path / "db.sqlite"))
    )

    preview = service.preview(
        WebhookPreviewRequest(service_type="generic_json", event_type="vm.failed")
    )

    assert preview.payload["event_type"] == "vm.failed"
    assert preview.payload["provider_id"] == "provider-1"
    assert preview.payload["resource"]["type"] == "vm"
