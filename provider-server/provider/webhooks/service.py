from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Optional

import aiohttp

from provider.utils.time import utc_now

from .domain import (
    WebhookConfig,
    WebhookDeliveryAttempt,
    WebhookEvent,
    WebhookEventType,
    WebhookPreviewRequest,
    WebhookPreviewResponse,
    WebhookResource,
    WebhookServiceType,
    WebhookTemplate,
    WebhookTestRequest,
    WebhookTestResponse,
)
from .repo import WebhookRepository

logger = logging.getLogger(__name__)

_VARIABLE = re.compile(r"{{\s*([^}]+?)\s*}}")


class WebhookService:
    """Formats and delivers provider webhook events."""

    def __init__(
        self,
        settings: Any,
        repo: WebhookRepository,
        event_broadcaster: Any = None,
    ):
        self.settings = settings
        self.repo = repo
        self.event_broadcaster = event_broadcaster

    def list_webhooks(self) -> list[WebhookConfig]:
        return self.repo.list_webhooks()

    def create_webhook(self, webhook: WebhookConfig) -> WebhookConfig:
        return self.repo.create_webhook(webhook)

    def update_webhook(self, webhook_id: int, webhook: WebhookConfig) -> WebhookConfig:
        return self.repo.update_webhook(webhook_id, webhook)

    def delete_webhook(self, webhook_id: int) -> None:
        self.repo.delete_webhook(webhook_id)

    def list_delivery_attempts(self, webhook_id: int) -> list[WebhookDeliveryAttempt]:
        return self.repo.list_delivery_attempts(webhook_id)

    def preview(self, request: WebhookPreviewRequest) -> WebhookPreviewResponse:
        event = self.sample_event(request.event_type)
        return WebhookPreviewResponse(
            service_type=request.service_type,
            payload=self.format_payload(request.service_type, request.template, event),
        )

    async def test_webhook(
        self, webhook_id: int, request: Optional[WebhookTestRequest] = None
    ) -> WebhookTestResponse:
        webhook = self.repo.get_webhook(webhook_id)
        event = self.sample_event((request or WebhookTestRequest()).event_type)
        payload = self.format_payload(webhook.service_type, webhook.template, event)
        status, error = await self._deliver_with_retries(webhook, event, payload)
        return WebhookTestResponse(
            ok=error is None,
            status=status,
            error=error,
            event_id=event.event_id,
            payload=payload,
        )

    async def emit(
        self,
        event_type: WebhookEventType,
        *,
        resource_type: str,
        resource_id: str,
        severity: str = "info",
        summary: str,
        data: Optional[dict[str, Any]] = None,
    ) -> WebhookEvent:
        event = WebhookEvent(
            event_type=event_type,
            provider_id=str(self._setting("PROVIDER_ID", "") or ""),
            resource=WebhookResource(type=resource_type, id=resource_id),
            severity=severity,
            summary=summary,
            data=data or {},
        )
        await self.emit_event(event)
        return event

    async def emit_event(self, event: WebhookEvent) -> None:
        for webhook in self.repo.list_webhooks():
            if not webhook.enabled or webhook.id is None:
                continue
            if event.event_type not in webhook.events:
                continue
            payload = self.format_payload(webhook.service_type, webhook.template, event)
            status, error = await self._deliver_with_retries(webhook, event, payload)
            if error is not None:
                logger.warning(
                    "Webhook delivery failed",
                    extra={
                        "webhook_id": webhook.id,
                        "event_type": event.event_type,
                        "status": status,
                        "error": error,
                    },
                )

    def sample_event(self, event_type: WebhookEventType) -> WebhookEvent:
        resource_type = "provider"
        resource_id = str(self._setting("PROVIDER_ID", "") or "provider")
        severity = "info"
        summary = "Provider webhook test"
        data: dict[str, Any] = {"test": True}
        if event_type.startswith("vm."):
            resource_type = "vm"
            resource_id = "requestor-vm-id"
            summary = {
                "vm.ready": "VM is online",
                "vm.failed": "VM creation failed",
                "vm.stopped": "VM stopped",
                "vm.deleted": "VM deleted",
            }.get(event_type, summary)
            severity = "critical" if event_type == "vm.failed" else "info"
        elif event_type.startswith("alert."):
            resource_type = "alert"
            resource_id = "host-cpu-high"
            severity = "warning" if event_type == "alert.fired" else "info"
            summary = (
                "Host CPU alert fired"
                if event_type == "alert.fired"
                else "Host CPU alert resolved"
            )
            data = {
                "metric": "cpu_percent",
                "value": 91,
                "threshold": 85,
                "scope": "host",
            }
        elif event_type == "payment.stream.lost":
            resource_type = "stream"
            resource_id = "42"
            severity = "critical"
            summary = "Payment stream lost"
            data = {"vm_id": "requestor-vm-id", "reason": "stream terminated"}
        return WebhookEvent(
            event_type=event_type,
            provider_id=str(self._setting("PROVIDER_ID", "") or ""),
            resource=WebhookResource(type=resource_type, id=resource_id),
            severity=severity,
            summary=summary,
            data=data,
        )

    def format_payload(
        self,
        service_type: WebhookServiceType,
        template: WebhookTemplate,
        event: WebhookEvent,
    ) -> dict[str, Any]:
        if service_type == "discord":
            return self._discord_payload(template, event)
        if service_type == "slack":
            return self._slack_payload(template, event)
        return event.model_dump(mode="json")

    async def _deliver_with_retries(
        self, webhook: WebhookConfig, event: WebhookEvent, payload: dict[str, Any]
    ) -> tuple[Optional[int], Optional[str]]:
        if webhook.id is None:
            return None, "webhook id is required"
        self.repo.update_webhook_result(webhook.id, "pending")
        await self._publish_webhooks()
        status: Optional[int] = None
        error: Optional[str] = None
        attempts = int(self._setting("WEBHOOK_RETRY_ATTEMPTS", 3))
        for attempt in range(1, attempts + 1):
            status, error = await self._post_webhook(webhook.url, payload)
            delivery_status = "success" if error is None else "failed"
            self.repo.add_delivery_attempt(
                WebhookDeliveryAttempt(
                    webhook_id=webhook.id,
                    event_id=event.event_id,
                    event_type=event.event_type,
                    attempt=attempt,
                    status=delivery_status,
                    http_status=status,
                    error=error,
                )
            )
            self.repo.update_webhook_result(
                webhook.id, delivery_status, http_status=status, error=error
            )
            await self._publish_webhooks()
            if error is None:
                return status, None
            if attempt < attempts:
                await asyncio.sleep(
                    float(self._setting("WEBHOOK_RETRY_DELAY_SECONDS", 0.25))
                    * (2 ** (attempt - 1))
                )
        return status, error

    async def _post_webhook(
        self, url: str, payload: dict[str, Any]
    ) -> tuple[Optional[int], Optional[str]]:
        timeout = aiohttp.ClientTimeout(
            total=float(self._setting("MONITORING_WEBHOOK_TIMEOUT_SECONDS", 5))
        )
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload) as response:
                    if 200 <= response.status < 300:
                        return response.status, None
                    return response.status, await response.text()
        except Exception as exc:
            return None, str(exc)

    async def _publish_webhooks(self) -> None:
        if self.event_broadcaster is not None:
            await self.event_broadcaster.publish(["webhooks"])

    def _discord_payload(
        self, template: WebhookTemplate, event: WebhookEvent
    ) -> dict[str, Any]:
        fields = [
            {
                "name": self._render(field.name, event),
                "value": self._render(field.value, event),
                "inline": True,
            }
            for field in template.fields
            if field.name.strip()
        ]
        embed: dict[str, Any] = {
            "title": self._render(template.title, event),
            "description": self._render(template.message, event),
            "color": self._discord_color(template.color, event),
            "fields": fields,
            "timestamp": utc_now().isoformat(),
        }
        footer = self._render(template.footer, event)
        if footer:
            embed["footer"] = {"text": footer}
        return {"content": self._render(template.message, event), "embeds": [embed]}

    def _slack_payload(
        self, template: WebhookTemplate, event: WebhookEvent
    ) -> dict[str, Any]:
        title = self._render(template.title, event)
        message = self._render(template.message, event)
        fields = [
            {
                "type": "mrkdwn",
                "text": f"*{self._render(field.name, event)}*\n{self._render(field.value, event)}",
            }
            for field in template.fields
            if field.name.strip()
        ]
        blocks: list[dict[str, Any]] = []
        if title:
            blocks.append(
                {"type": "header", "text": {"type": "plain_text", "text": title}}
            )
        if message:
            blocks.append(
                {"type": "section", "text": {"type": "mrkdwn", "text": message}}
            )
        if fields:
            blocks.append({"type": "section", "fields": fields})
        footer = self._render(template.footer, event)
        if footer:
            blocks.append(
                {"type": "context", "elements": [{"type": "mrkdwn", "text": footer}]}
            )
        return {"text": message or title or event.summary, "blocks": blocks}

    def _render(self, text: str, event: WebhookEvent) -> str:
        values = {
            "event.type": event.event_type,
            "event.id": event.event_id,
            "created_at": event.created_at.isoformat(),
            "provider.id": event.provider_id,
            "resource.type": event.resource.type,
            "resource.id": event.resource.id,
            "severity": event.severity,
            "summary": event.summary,
        }

        def replace(match: re.Match[str]) -> str:
            key = match.group(1).strip()
            if key.startswith("data."):
                value = event.data
                for part in key[5:].split("."):
                    if not isinstance(value, dict) or part not in value:
                        return ""
                    value = value[part]
                return str(value)
            return str(values.get(key, ""))

        return _VARIABLE.sub(replace, text)

    @staticmethod
    def _discord_color(color: str, event: WebhookEvent) -> int:
        if color != "severity":
            try:
                return int(color.lstrip("#"), 16)
            except ValueError:
                pass
        return {
            "info": 0x3B82F6,
            "warning": 0xF59E0B,
            "critical": 0xEF4444,
        }.get(event.severity, 0x3B82F6)

    def _setting(self, name: str, default: Any = None) -> Any:
        if isinstance(self.settings, dict):
            return self.settings.get(name, default)
        return getattr(self.settings, name, default)
