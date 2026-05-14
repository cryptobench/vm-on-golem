import asyncio
import socket
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from aiohttp import web
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

import provider.network_setup.service as network_setup_service
from provider.network_setup.certs import cert_is_valid_for_ip
from provider.network_setup.nat import (
    NatMappingResult,
    _mapping_conflict_detail,
    _upnp_error_detail,
)
from provider.network_setup.render import render_startup_panel
from provider.network_setup.service import NetworkSetupService, _format_port_ranges


class FakeNatMapper:
    def __init__(self, success=True, detail: str | None = None):
        self.success = success
        self.detail = detail
        self.calls = []

    async def ensure_tcp_mapping(self, public_port, internal_port, description):
        self.calls.append((public_port, internal_port, description))
        return NatMappingResult(
            self.success, self.detail or ("ok" if self.success else "blocked")
        )


def _free_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _settings(tmp_path, **overrides):
    vm_port_start = _free_port()
    values = {
        "DEV_MODE": False,
        "SECURE_SETUP_IN_DEVELOPMENT": False,
        "SKIP_PORT_VERIFICATION": False,
        "PUBLIC_ENDPOINT_MODE": "auto_ip_https",
        "PUBLIC_IP": "127.0.0.1",
        "PUBLIC_ENDPOINT_IP": "auto",
        "PORT_RANGE_START": vm_port_start,
        "PORT_RANGE_END": vm_port_start + 2,
        "PUBLIC_HTTPS_PORT": _free_port(),
        "PUBLIC_HTTPS_INTERNAL_PORT": _free_port(),
        "ACME_HTTP_PUBLIC_PORT": _free_port(),
        "ACME_HTTP_INTERNAL_PORT": _free_port(),
        "ACME_DIRECTORY_URL": "https://example.invalid/directory",
        "ACME_PROFILE": "shortlived",
        "ACME_ACCOUNT_EMAIL": "",
        "CERT_DIR": str(tmp_path),
        "CERT_RENEW_BEFORE_HOURS": 1,
        "NAT_AUTO_MAPPING_ENABLED": False,
        "PORT_CHECK_TLS_URL": "",
        "HOST": "127.0.0.1",
        "PORT": _free_port(),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _write_ip_cert(tmp_path, ip="127.0.0.1", expires_days=5):
    import ipaddress

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, ip)])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow() - timedelta(minutes=1))
        .not_valid_after(datetime.utcnow() + timedelta(days=expires_days))
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address(ip))]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    (tmp_path / "provider-ip.key").write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    (tmp_path / "provider-ip.crt").write_bytes(
        cert.public_bytes(serialization.Encoding.PEM)
    )


def _port_state_sequence(events, stage_name: str, port: int) -> list[str]:
    states = []
    for event in events:
        stage = next(stage for stage in event["stages"] if stage["name"] == stage_name)
        check = next(
            (check for check in stage.get("port_checks", []) if check["port"] == port),
            None,
        )
        if check is None:
            continue
        if not states or states[-1] != check["state"]:
            states.append(check["state"])
    return states


def _assert_port_progression(
    events, stage_name: str, port: int, final_state: str
) -> None:
    states = _port_state_sequence(events, stage_name, port)
    assert states == ["pending", "checking", final_state]


async def _start_fake_port_checker(blocked_ports: set[int] | None = None):
    app = web.Application()
    requests = []
    if blocked_ports is None:
        blocked_ports = set()

    async def check_ports(request):
        payload = await request.json()
        requests.append(payload)
        results = {}
        for port in payload["ports"]:
            if port in blocked_ports:
                results[str(port)] = {"accessible": False, "error": "blocked"}
                continue
            try:
                _reader, writer = await asyncio.open_connection(
                    payload["provider_ip"], port
                )
                writer.close()
                await writer.wait_closed()
                results[str(port)] = {"accessible": True, "error": None}
            except Exception as exc:
                results[str(port)] = {"accessible": False, "error": str(exc)}
        return web.json_response(
            {
                "success": any(result["accessible"] for result in results.values()),
                "results": results,
                "message": "ok",
            }
        )

    async def check_tls(request):
        payload = await request.json()
        return web.json_response(
            {"valid": True, "peer": f"{payload['host']}:{payload['port']}"}
        )

    app.router.add_post("/check-ports", check_ports)
    app.router.add_post("/check-tls", check_tls)
    runner = web.AppRunner(app)
    await runner.setup()
    port = _free_port()
    site = web.TCPSite(runner, "127.0.0.1", port)
    await site.start()
    return runner, f"http://127.0.0.1:{port}", requests


def test_cert_validation_accepts_ip_san(tmp_path):
    _write_ip_cert(tmp_path)

    valid, detail = cert_is_valid_for_ip(
        tmp_path / "provider-ip.crt",
        tmp_path / "provider-ip.key",
        "127.0.0.1",
        renew_before_hours=1,
    )

    assert valid is True
    assert "valid" in detail


def test_upnp_error_detail_preserves_raw_error():
    detail = _upnp_error_detail(RuntimeError("ConflictInMappingEntry"))

    assert detail == "ConflictInMappingEntry"


def test_upnp_conflict_with_mapping_reports_existing_target():
    detail = _mapping_conflict_detail(80, ("192.168.50.10", 80, "TCP"))

    assert "already mapped" in detail
    assert "192.168.50.10:80" in detail


@pytest.mark.asyncio
async def test_network_setup_reuses_existing_certificate(tmp_path):
    _write_ip_cert(tmp_path)
    settings = _settings(tmp_path)
    service = NetworkSetupService(settings, nat_mapper=FakeNatMapper())

    status = await service.setup()
    await service.cleanup()

    assert status.complete is True
    assert status.endpoint_url is not None
    assert status.stage("certificate").detail.startswith("valid")


@pytest.mark.asyncio
async def test_network_setup_reports_certificate_bind_error(tmp_path):
    http_port = _free_port()
    sock = socket.socket()
    sock.bind(("127.0.0.1", http_port))
    sock.listen()
    settings = _settings(tmp_path, ACME_HTTP_INTERNAL_PORT=http_port)
    service = NetworkSetupService(settings, nat_mapper=FakeNatMapper())

    try:
        with pytest.raises(Exception):
            await service.setup()
    finally:
        sock.close()

    stage = service.status.stage("certificate")
    assert service.status.failed is True
    assert stage.state == "failed"
    assert str(http_port) in stage.detail
    assert "Certificate setup failed:" in (stage.remediation or "")
    assert str(http_port) in (stage.remediation or "")


@pytest.mark.asyncio
async def test_network_setup_reports_acme_error_detail(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    error_detail = "ACME authorization failed: connection refused by validator"

    async def fail_issue_ip_certificate(*_args, **_kwargs):
        raise RuntimeError(error_detail)

    monkeypatch.setattr(
        network_setup_service.NativeAcmeClient,
        "issue_ip_certificate",
        fail_issue_ip_certificate,
    )
    settings = _settings(tmp_path, ACME_HTTP_INTERNAL_PORT=_free_port())
    service = NetworkSetupService(settings, nat_mapper=FakeNatMapper())

    with pytest.raises(Exception):
        await service.setup()

    stage = service.status.stage("certificate")
    assert stage.state == "failed"
    assert stage.detail == error_detail
    assert error_detail in (stage.remediation or "")
    assert error_detail in service.status.message


@pytest.mark.asyncio
async def test_network_setup_verifies_public_ports_from_checker(tmp_path):
    _write_ip_cert(tmp_path)
    http_port = _free_port()
    https_port = _free_port()
    runner, checker_url, requests = await _start_fake_port_checker()
    settings = _settings(
        tmp_path,
        ACME_HTTP_PUBLIC_PORT=http_port,
        ACME_HTTP_INTERNAL_PORT=http_port,
        PUBLIC_HTTPS_PORT=https_port,
        PUBLIC_HTTPS_INTERNAL_PORT=https_port,
        PORT_CHECK_TLS_URL=checker_url,
    )
    service = NetworkSetupService(settings, nat_mapper=FakeNatMapper())
    events = []
    service.status_callback = lambda status: events.append(
        status.model_dump(mode="json")
    )

    try:
        status = await service.setup()
        await service.cleanup()
    finally:
        await runner.cleanup()

    assert status.complete is True
    assert status.stage("network_access").detail == (
        f":{http_port}, :{https_port} reachable"
    )
    assert [check.state for check in status.stage("network_access").port_checks] == [
        "open",
        "open",
    ]
    assert sorted(request["ports"][0] for request in requests[:2]) == sorted(
        [http_port, https_port]
    )
    assert all(request["provider_ip"] == "127.0.0.1" for request in requests[:2])
    _assert_port_progression(events, "network_access", http_port, "open")
    _assert_port_progression(events, "network_access", https_port, "open")


@pytest.mark.asyncio
async def test_network_setup_fails_when_public_port_check_fails(tmp_path):
    _write_ip_cert(tmp_path)
    http_port = _free_port()
    https_port = _free_port()
    runner, checker_url, _requests = await _start_fake_port_checker(
        blocked_ports={http_port}
    )
    settings = _settings(
        tmp_path,
        ACME_HTTP_PUBLIC_PORT=http_port,
        ACME_HTTP_INTERNAL_PORT=http_port,
        PUBLIC_HTTPS_PORT=https_port,
        PUBLIC_HTTPS_INTERNAL_PORT=https_port,
        PORT_CHECK_TLS_URL=checker_url,
    )
    service = NetworkSetupService(settings, nat_mapper=FakeNatMapper())
    events = []
    service.status_callback = lambda status: events.append(
        status.model_dump(mode="json")
    )

    try:
        with pytest.raises(Exception):
            await service.setup()
    finally:
        await runner.cleanup()

    assert service.status.failed is True
    assert service.status.stage("network_access").state == "failed"
    assert service.status.stage("network_access").detail == f":{http_port} unreachable"
    assert {
        check.port: check.state
        for check in service.status.stage("network_access").port_checks
    }[http_port] == "closed"
    assert "not reachable from the internet" in service.status.message
    _assert_port_progression(events, "network_access", http_port, "closed")
    _assert_port_progression(events, "network_access", https_port, "open")


@pytest.mark.asyncio
async def test_network_setup_fails_when_vm_port_range_check_fails(tmp_path):
    _write_ip_cert(tmp_path)
    http_port = _free_port()
    https_port = _free_port()
    blocked_ports = set()
    runner, checker_url, _requests = await _start_fake_port_checker(
        blocked_ports=blocked_ports
    )
    vm_port_start = _free_port()
    blocked_ports.add(vm_port_start)
    settings = _settings(
        tmp_path,
        ACME_HTTP_PUBLIC_PORT=http_port,
        ACME_HTTP_INTERNAL_PORT=http_port,
        PUBLIC_HTTPS_PORT=https_port,
        PUBLIC_HTTPS_INTERNAL_PORT=https_port,
        PORT_RANGE_START=vm_port_start,
        PORT_RANGE_END=vm_port_start + 2,
        PORT_CHECK_TLS_URL=checker_url,
    )
    service = NetworkSetupService(settings, nat_mapper=FakeNatMapper())
    events = []
    service.status_callback = lambda status: events.append(
        status.model_dump(mode="json")
    )

    try:
        with pytest.raises(Exception):
            await service.setup()
    finally:
        await runner.cleanup()

    assert service.status.failed is True
    assert service.status.stage("vm_port_range").state == "failed"
    assert (
        service.status.stage("vm_port_range").detail == f"{vm_port_start} unreachable"
    )
    assert {
        check.port: check.state
        for check in service.status.stage("vm_port_range").port_checks
    }[vm_port_start] == "closed"
    assert "VM port range" in service.status.message
    _assert_port_progression(events, "vm_port_range", vm_port_start, "closed")
    _assert_port_progression(events, "vm_port_range", vm_port_start + 1, "open")


def test_port_range_formatting_compacts_consecutive_ports():
    ports = [50800, 50801, 50802, 50805, 50807, 50808]

    assert _format_port_ranges(ports) == "50800-50802, 50805, 50807-50808"


@pytest.mark.asyncio
async def test_development_skips_secure_setup_unless_enabled(tmp_path):
    settings = _settings(tmp_path, DEV_MODE=True, SECURE_SETUP_IN_DEVELOPMENT=False)
    service = NetworkSetupService(settings, nat_mapper=FakeNatMapper(success=False))

    status = await service.setup()

    assert status.complete is True
    assert status.stage("certificate").detail == "skipped"


@pytest.mark.asyncio
async def test_development_secure_setup_uses_real_path_when_enabled(
    tmp_path, monkeypatch
):
    _write_ip_cert(tmp_path)
    monkeypatch.setenv("GOLEM_PROVIDER_PUBLIC_IP", "127.0.0.1")
    settings = _settings(tmp_path, DEV_MODE=True, SECURE_SETUP_IN_DEVELOPMENT=True)
    service = NetworkSetupService(settings, nat_mapper=FakeNatMapper())

    status = await service.setup()
    await service.cleanup()

    assert status.complete is True
    assert status.stage("certificate").detail.startswith("valid")


def test_development_secure_setup_ignores_auto_lan_public_ip(tmp_path, monkeypatch):
    monkeypatch.delenv("GOLEM_PROVIDER_PUBLIC_IP", raising=False)
    monkeypatch.delenv("GOLEM_PROVIDER_PUBLIC_ENDPOINT_IP", raising=False)
    settings = _settings(
        tmp_path,
        DEV_MODE=True,
        SECURE_SETUP_IN_DEVELOPMENT=True,
        PUBLIC_IP="192.168.2.1",
    )
    service = NetworkSetupService(settings, nat_mapper=FakeNatMapper())

    assert service._configured_public_ip() is None


@pytest.mark.asyncio
async def test_network_setup_fails_when_network_access_fails(tmp_path):
    settings = _settings(tmp_path, NAT_AUTO_MAPPING_ENABLED=True)
    service = NetworkSetupService(settings, nat_mapper=FakeNatMapper(success=False))

    with pytest.raises(Exception):
        await service.setup()

    assert service.status.failed is True
    assert service.status.stage("network_access").state == "failed"


@pytest.mark.asyncio
async def test_network_setup_reports_unavailable_public_port(tmp_path):
    http_port = _free_port()
    http_internal_port = _free_port()
    settings = _settings(
        tmp_path,
        ACME_HTTP_PUBLIC_PORT=http_port,
        ACME_HTTP_INTERNAL_PORT=http_internal_port,
        NAT_AUTO_MAPPING_ENABLED=True,
    )
    events = []
    router_detail = (
        f"Could not create a UPnP TCP mapping for public port {http_port} "
        f"to 192.168.50.48:{http_internal_port}: router refused mapping."
    )
    service = NetworkSetupService(
        settings,
        nat_mapper=FakeNatMapper(success=False, detail=router_detail),
        status_callback=lambda status: events.append(status.model_dump(mode="json")),
    )

    with pytest.raises(Exception):
        await service.setup()

    remediation = service.status.stage("network_access").remediation
    assert remediation is not None
    assert router_detail in remediation
    assert f"public port {http_port}" in remediation
    assert f"internal port {http_internal_port}" in remediation
    assert router_detail in service.status.message
    assert any(
        event["stages"][0]["state"] == "success"
        and event["stages"][1]["state"] == "running"
        for event in events
    )
    assert events[-1]["stages"][0]["state"] == "success"
    assert events[-1]["stages"][1]["state"] == "failed"


def test_ascii_panel_includes_failure_message(tmp_path):
    service = NetworkSetupService(_settings(tmp_path), nat_mapper=FakeNatMapper())
    service.status.stage("network_access").state = "failed"
    service.status.stage("network_access").detail = "port unavailable :443"
    service.status.message = "Golem Provider cannot start in direct mode."

    panel = render_startup_panel(service.status)

    assert "Secure Connection Setup Needs Attention" in panel
    assert "port unavailable" in panel
