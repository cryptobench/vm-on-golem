from typing import Optional

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse

from provider.auth.dependencies import (
    require_provider_admin,
    require_requestor_vm_access,
)
from provider.auth.domain import AdminIdentity, RequestorIdentity
from provider.container import Container
from provider.live.events import ProviderEventBroadcaster
from provider.monitoring.domain import (
    AlertRule,
    GuestMetricAccepted,
    GuestMetricPayload,
    MetricHistoryRange,
    MetricScope,
    MetricsHistoryResponse,
    MetricsLatestResponse,
    MetricSource,
    MonitoringOverview,
)
from provider.monitoring.services import MonitoringService
from provider.webhooks.domain import (
    WebhookConfig,
    WebhookDeliveryAttempt,
    WebhookPreviewRequest,
    WebhookPreviewResponse,
    WebhookTestRequest,
    WebhookTestResponse,
)
from provider.webhooks.service import WebhookService

router = APIRouter()


@router.get("/monitoring/overview", response_model=MonitoringOverview)
@inject
async def monitoring_overview(
    _admin: AdminIdentity = Depends(require_provider_admin),
    monitoring_service: MonitoringService = Depends(
        Provide[Container.monitoring_service]
    ),
) -> MonitoringOverview:
    return await monitoring_service.overview()


@router.get("/monitoring/metrics/latest", response_model=MetricsLatestResponse)
@inject
async def monitoring_latest(
    _admin: AdminIdentity = Depends(require_provider_admin),
    monitoring_service: MonitoringService = Depends(
        Provide[Container.monitoring_service]
    ),
) -> MetricsLatestResponse:
    return monitoring_service.latest()


@router.get("/monitoring/metrics/history", response_model=MetricsHistoryResponse)
@inject
async def monitoring_history(
    scope: MetricScope = Query(default=MetricScope.HOST),
    range: MetricHistoryRange = Query(default=MetricHistoryRange.ONE_HOUR),
    vm_id: Optional[str] = Query(default=None),
    source: Optional[MetricSource] = Query(default=None),
    _admin: AdminIdentity = Depends(require_provider_admin),
    monitoring_service: MonitoringService = Depends(
        Provide[Container.monitoring_service]
    ),
) -> MetricsHistoryResponse:
    return monitoring_service.history(
        scope=scope, range_name=range, vm_id=vm_id, source=source
    )


@router.post("/monitoring/guest/{vm_id}/samples")
@inject
async def record_guest_sample(
    vm_id: str,
    payload: GuestMetricPayload,
    monitoring_service: MonitoringService = Depends(
        Provide[Container.monitoring_service]
    ),
    event_broadcaster: ProviderEventBroadcaster = Depends(
        Provide[Container.provider_event_broadcaster]
    ),
) -> GuestMetricAccepted:
    result = await monitoring_service.record_guest_sample(vm_id, payload)
    await event_broadcaster.publish(["monitoring", "metrics"])
    return result


@router.get(
    "/vms/{requestor_name}/metrics/latest", response_model=MetricsLatestResponse
)
@inject
async def vm_metrics_latest(
    requestor_name: str,
    _identity: RequestorIdentity = Depends(require_requestor_vm_access),
    monitoring_service: MonitoringService = Depends(
        Provide[Container.monitoring_service]
    ),
) -> MetricsLatestResponse:
    latest = monitoring_service.latest()
    latest.vms = {requestor_name: latest.vms.get(requestor_name, {})}
    return latest


@router.get(
    "/vms/{requestor_name}/metrics/history", response_model=MetricsHistoryResponse
)
@inject
async def vm_metrics_history(
    requestor_name: str,
    range: MetricHistoryRange = Query(default=MetricHistoryRange.ONE_HOUR),
    source: Optional[MetricSource] = Query(default=None),
    _identity: RequestorIdentity = Depends(require_requestor_vm_access),
    monitoring_service: MonitoringService = Depends(
        Provide[Container.monitoring_service]
    ),
) -> MetricsHistoryResponse:
    return monitoring_service.history(
        scope=MetricScope.VM, range_name=range, vm_id=requestor_name, source=source
    )


@router.get("/monitoring/alerts")
@inject
async def active_alerts(
    _admin: AdminIdentity = Depends(require_provider_admin),
    monitoring_service: MonitoringService = Depends(
        Provide[Container.monitoring_service]
    ),
) -> list[dict]:
    return monitoring_service.active_alerts()


@router.get("/monitoring/alert-rules", response_model=list[AlertRule])
@inject
async def list_alert_rules(
    _admin: AdminIdentity = Depends(require_provider_admin),
    monitoring_service: MonitoringService = Depends(
        Provide[Container.monitoring_service]
    ),
) -> list[AlertRule]:
    return monitoring_service.list_alert_rules()


@router.post("/monitoring/alert-rules", response_model=AlertRule)
@inject
async def create_alert_rule(
    rule: AlertRule,
    _admin: AdminIdentity = Depends(require_provider_admin),
    monitoring_service: MonitoringService = Depends(
        Provide[Container.monitoring_service]
    ),
    event_broadcaster: ProviderEventBroadcaster = Depends(
        Provide[Container.provider_event_broadcaster]
    ),
) -> AlertRule:
    created = monitoring_service.create_alert_rule(rule)
    await event_broadcaster.publish(["alert_rules", "alerts"])
    return created


@router.get("/monitoring/webhooks", response_model=list[WebhookConfig])
@inject
async def list_webhooks(
    _admin: AdminIdentity = Depends(require_provider_admin),
    webhook_service: WebhookService = Depends(Provide[Container.webhook_service]),
) -> list[WebhookConfig]:
    return webhook_service.list_webhooks()


@router.post("/monitoring/webhooks", response_model=WebhookConfig)
@inject
async def create_webhook(
    webhook: WebhookConfig,
    _admin: AdminIdentity = Depends(require_provider_admin),
    webhook_service: WebhookService = Depends(Provide[Container.webhook_service]),
    event_broadcaster: ProviderEventBroadcaster = Depends(
        Provide[Container.provider_event_broadcaster]
    ),
) -> WebhookConfig:
    created = webhook_service.create_webhook(webhook)
    await event_broadcaster.publish(["webhooks"])
    return created


@router.put("/monitoring/webhooks/{webhook_id}", response_model=WebhookConfig)
@inject
async def update_webhook(
    webhook_id: int,
    webhook: WebhookConfig,
    _admin: AdminIdentity = Depends(require_provider_admin),
    webhook_service: WebhookService = Depends(Provide[Container.webhook_service]),
    event_broadcaster: ProviderEventBroadcaster = Depends(
        Provide[Container.provider_event_broadcaster]
    ),
) -> WebhookConfig:
    updated = webhook_service.update_webhook(webhook_id, webhook)
    await event_broadcaster.publish(["webhooks"])
    return updated


@router.delete("/monitoring/webhooks/{webhook_id}", status_code=204)
@inject
async def delete_webhook(
    webhook_id: int,
    _admin: AdminIdentity = Depends(require_provider_admin),
    webhook_service: WebhookService = Depends(Provide[Container.webhook_service]),
    event_broadcaster: ProviderEventBroadcaster = Depends(
        Provide[Container.provider_event_broadcaster]
    ),
) -> None:
    webhook_service.delete_webhook(webhook_id)
    await event_broadcaster.publish(["webhooks"])


@router.get(
    "/monitoring/webhooks/{webhook_id}/deliveries",
    response_model=list[WebhookDeliveryAttempt],
)
@inject
async def list_webhook_deliveries(
    webhook_id: int,
    _admin: AdminIdentity = Depends(require_provider_admin),
    webhook_service: WebhookService = Depends(Provide[Container.webhook_service]),
) -> list[WebhookDeliveryAttempt]:
    return webhook_service.list_delivery_attempts(webhook_id)


@router.post("/monitoring/webhooks/preview", response_model=WebhookPreviewResponse)
@inject
async def preview_webhook(
    request: WebhookPreviewRequest,
    _admin: AdminIdentity = Depends(require_provider_admin),
    webhook_service: WebhookService = Depends(Provide[Container.webhook_service]),
) -> WebhookPreviewResponse:
    return webhook_service.preview(request)


@router.post(
    "/monitoring/webhooks/{webhook_id}/test", response_model=WebhookTestResponse
)
@inject
async def test_webhook(
    webhook_id: int,
    request: WebhookTestRequest | None = None,
    _admin: AdminIdentity = Depends(require_provider_admin),
    webhook_service: WebhookService = Depends(Provide[Container.webhook_service]),
    event_broadcaster: ProviderEventBroadcaster = Depends(
        Provide[Container.provider_event_broadcaster]
    ),
) -> WebhookTestResponse:
    result = await webhook_service.test_webhook(webhook_id, request)
    await event_broadcaster.publish(["webhooks"])
    return result


@router.get("/metrics")
@inject
async def prometheus_metrics(
    _admin: AdminIdentity = Depends(require_provider_admin),
    monitoring_service: MonitoringService = Depends(
        Provide[Container.monitoring_service]
    ),
) -> PlainTextResponse:
    return PlainTextResponse(
        await monitoring_service.prometheus_metrics(),
        media_type="text/plain; version=0.0.4",
    )
