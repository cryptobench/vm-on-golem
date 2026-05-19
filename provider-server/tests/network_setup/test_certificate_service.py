from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from provider.network_setup.certificate_service import CertificateMaintenanceService
from provider.network_setup.domain import CertificateState


def _settings(tmp_path, **overrides):
    values = {
        "DEV_MODE": False,
        "SECURE_SETUP_IN_DEVELOPMENT": False,
        "PUBLIC_ENDPOINT_MODE": "auto_ip_https",
        "PUBLIC_IP": "127.0.0.1",
        "CERT_DIR": str(tmp_path),
        "CERT_RENEW_BEFORE_HOURS": 24,
        "HOST": "127.0.0.1",
        "ACME_HTTP_INTERNAL_PORT": 0,
        "ACME_DIRECTORY_URL": "https://example.invalid/directory",
        "ACME_ACCOUNT_EMAIL": "",
        "ACME_PROFILE": "shortlived",
        "CERT_RENEWAL_ENABLED": True,
        "CERT_RENEWAL_CHECK_INTERVAL_SECONDS": 3600,
        "CERT_RENEWAL_RETRY_INITIAL_SECONDS": 300,
        "CERT_RENEWAL_RETRY_MAX_SECONDS": 21600,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _write_ip_cert(
    tmp_path,
    *,
    ip: str = "127.0.0.1",
    expires_in: timedelta = timedelta(days=5),
    overwrite_key: bool = True,
):
    import ipaddress

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, ip)])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + expires_in)
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address(ip))]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    if overwrite_key:
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


def test_certificate_status_reports_missing_certificate(tmp_path):
    service = CertificateMaintenanceService(_settings(tmp_path))

    status = service.refresh_status()

    assert status.state == CertificateState.FAILED
    assert status.last_error == "missing certificate"
    assert service.endpoint_is_advertisable() is False


def test_certificate_status_reports_wrong_ip_san(tmp_path):
    _write_ip_cert(tmp_path, ip="127.0.0.2")
    service = CertificateMaintenanceService(_settings(tmp_path))

    status = service.refresh_status("127.0.0.1")

    assert status.state == CertificateState.FAILED
    assert status.last_error == "certificate does not match public IP"
    assert service.endpoint_is_advertisable() is False


def test_certificate_status_reports_mismatched_key(tmp_path):
    _write_ip_cert(tmp_path)
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    (tmp_path / "provider-ip.key").write_bytes(
        other_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    service = CertificateMaintenanceService(_settings(tmp_path))

    status = service.refresh_status()

    assert status.state == CertificateState.FAILED
    assert status.last_error == "certificate key does not match"
    assert service.endpoint_is_advertisable() is False


def test_certificate_status_reports_valid_certificate(tmp_path):
    _write_ip_cert(tmp_path, expires_in=timedelta(days=5))
    service = CertificateMaintenanceService(_settings(tmp_path))

    status = service.refresh_status()

    assert status.state == CertificateState.VALID
    assert status.expires_at is not None
    assert status.renew_after is not None
    assert status.last_error is None
    assert service.endpoint_is_advertisable() is True


def test_certificate_status_reports_renewal_due_certificate(tmp_path):
    _write_ip_cert(tmp_path, expires_in=timedelta(hours=2))
    service = CertificateMaintenanceService(
        _settings(tmp_path, CERT_RENEW_BEFORE_HOURS=24)
    )

    status = service.refresh_status()

    assert status.state == CertificateState.RENEWAL_DUE
    assert status.last_error is None
    assert service.endpoint_is_advertisable() is True


def test_certificate_status_reports_expired_certificate(tmp_path):
    _write_ip_cert(tmp_path, expires_in=timedelta(hours=-1))
    service = CertificateMaintenanceService(_settings(tmp_path))

    status = service.refresh_status()

    assert status.state == CertificateState.EXPIRED
    assert service.endpoint_is_advertisable() is False


@pytest.mark.asyncio
async def test_background_check_noops_for_valid_certificate(tmp_path, monkeypatch):
    _write_ip_cert(tmp_path, expires_in=timedelta(days=5))
    service = CertificateMaintenanceService(_settings(tmp_path))

    async def fail_issue(_public_ip):
        raise AssertionError("certificate should not be renewed")

    monkeypatch.setattr(service, "_issue_certificate", fail_issue)

    renewed = await service.check_once()

    assert renewed is False
    assert service.get_status().state == CertificateState.VALID


@pytest.mark.asyncio
async def test_background_check_renews_due_certificate_and_reloads_edge(
    tmp_path, monkeypatch
):
    _write_ip_cert(tmp_path, expires_in=timedelta(minutes=10))
    service = CertificateMaintenanceService(
        _settings(tmp_path, CERT_RENEW_BEFORE_HOURS=1)
    )
    reloads = 0

    async def issue(_public_ip):
        _write_ip_cert(tmp_path, expires_in=timedelta(days=5))

    async def reload_edge():
        nonlocal reloads
        reloads += 1

    monkeypatch.setattr(service, "_issue_certificate", issue)

    renewed = await service.check_once(on_renewed=reload_edge)

    assert renewed is True
    assert reloads == 1
    assert service.get_status().state == CertificateState.RENEWED
    assert service.get_status().last_error is None


@pytest.mark.asyncio
async def test_background_check_failure_keeps_usable_certificate_advertisable(
    tmp_path, monkeypatch
):
    _write_ip_cert(tmp_path, expires_in=timedelta(minutes=10))
    service = CertificateMaintenanceService(
        _settings(tmp_path, CERT_RENEW_BEFORE_HOURS=1)
    )

    async def fail_issue(_public_ip):
        raise RuntimeError("acme unavailable")

    monkeypatch.setattr(service, "_issue_certificate", fail_issue)

    with pytest.raises(RuntimeError, match="acme unavailable"):
        await service.check_once()

    assert service.get_status().state == CertificateState.FAILED
    assert service.get_status().last_error == "acme unavailable"
    assert service.endpoint_is_advertisable() is True
