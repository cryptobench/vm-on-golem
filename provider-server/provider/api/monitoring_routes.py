from typing import Optional

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse

from provider.container import Container
from provider.monitoring.domain import (
    AlertRule,
    GuestMetricAccepted,
    GuestMetricPayload,
    MetricScope,
    MetricsHistoryResponse,
    MetricsLatestResponse,
    MetricSource,
    MonitoringOverview,
    WebhookConfig,
    WebhookTestResponse,
)
from provider.monitoring.services import MonitoringService

router = APIRouter()


@router.get("/monitoring/overview", response_model=MonitoringOverview)
@inject
async def monitoring_overview(
    monitoring_service: MonitoringService = Depends(
        Provide[Container.monitoring_service]
    ),
) -> MonitoringOverview:
    return await monitoring_service.overview()


@router.get("/monitoring/metrics/latest", response_model=MetricsLatestResponse)
@inject
async def monitoring_latest(
    monitoring_service: MonitoringService = Depends(
        Provide[Container.monitoring_service]
    ),
) -> MetricsLatestResponse:
    return monitoring_service.latest()


@router.get("/monitoring/metrics/history", response_model=MetricsHistoryResponse)
@inject
async def monitoring_history(
    scope: MetricScope = Query(default=MetricScope.HOST),
    range: str = Query(default="1h"),
    vm_id: Optional[str] = Query(default=None),
    source: Optional[MetricSource] = Query(default=None),
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
) -> GuestMetricAccepted:
    try:
        return await monitoring_service.record_guest_sample(vm_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.get(
    "/vms/{requestor_name}/metrics/latest", response_model=MetricsLatestResponse
)
@inject
async def vm_metrics_latest(
    requestor_name: str,
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
    range: str = Query(default="1h"),
    source: Optional[MetricSource] = Query(default=None),
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
    monitoring_service: MonitoringService = Depends(
        Provide[Container.monitoring_service]
    ),
) -> list[dict]:
    return monitoring_service.active_alerts()


@router.get("/monitoring/alert-rules", response_model=list[AlertRule])
@inject
async def list_alert_rules(
    monitoring_service: MonitoringService = Depends(
        Provide[Container.monitoring_service]
    ),
) -> list[AlertRule]:
    return monitoring_service.list_alert_rules()


@router.post("/monitoring/alert-rules", response_model=AlertRule)
@inject
async def create_alert_rule(
    rule: AlertRule,
    monitoring_service: MonitoringService = Depends(
        Provide[Container.monitoring_service]
    ),
) -> AlertRule:
    return monitoring_service.create_alert_rule(rule)


@router.get("/monitoring/webhooks", response_model=list[WebhookConfig])
@inject
async def list_webhooks(
    monitoring_service: MonitoringService = Depends(
        Provide[Container.monitoring_service]
    ),
) -> list[WebhookConfig]:
    return monitoring_service.list_webhooks()


@router.post("/monitoring/webhooks", response_model=WebhookConfig)
@inject
async def create_webhook(
    webhook: WebhookConfig,
    monitoring_service: MonitoringService = Depends(
        Provide[Container.monitoring_service]
    ),
) -> WebhookConfig:
    return monitoring_service.create_webhook(webhook)


@router.post(
    "/monitoring/webhooks/{webhook_id}/test", response_model=WebhookTestResponse
)
@inject
async def test_webhook(
    webhook_id: int,
    monitoring_service: MonitoringService = Depends(
        Provide[Container.monitoring_service]
    ),
) -> WebhookTestResponse:
    try:
        return await monitoring_service.test_webhook(webhook_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/metrics")
@inject
async def prometheus_metrics(
    monitoring_service: MonitoringService = Depends(
        Provide[Container.monitoring_service]
    ),
) -> PlainTextResponse:
    return PlainTextResponse(
        await monitoring_service.prometheus_metrics(),
        media_type="text/plain; version=0.0.4",
    )
