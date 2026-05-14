from datetime import datetime, timezone

from fastapi.testclient import TestClient

from provider.main import app
from provider.network_setup.domain import CertificateState, CertificateStatus
from provider.summary.domain import ProviderSummary


class StubSummaryService:
    async def get_summary(self):
        return ProviderSummary(
            status="running",
            resources={"total": {}, "available": {}},
            pricing={},
            vms=[],
            env={},
            certificate=CertificateStatus(
                state=CertificateState.VALID,
                expires_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
            ),
        )


def test_summary_endpoint_includes_certificate_status():
    client = TestClient(app)
    with app.container.summary_service.override(StubSummaryService()):
        response = client.get("/api/v1/summary")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert data["certificate"]["state"] == "valid"
    assert data["certificate"]["expires_at"] == "2030-01-01T00:00:00Z"
