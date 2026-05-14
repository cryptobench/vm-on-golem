import pytest

from port_checker.ports.domain import TlsCheckRequest
from port_checker.ports.service import PortCheckService


@pytest.mark.asyncio
async def test_tls_check_reports_unreachable_endpoint():
    service = PortCheckService(timeout=0.1)

    result = await service.check_tls(
        TlsCheckRequest(host="127.0.0.1", port=9, expected_ip="127.0.0.1")
    )

    assert result.valid is False
    assert result.error
