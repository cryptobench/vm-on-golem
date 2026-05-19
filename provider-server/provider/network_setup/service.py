import asyncio
import os
import time
from pathlib import Path
from typing import Callable, Literal

import aiohttp

from ..utils.logging import setup_logger
from .acme import AcmeRequestError
from .certificate_service import CertificateMaintenanceService
from .domain import (
    NetworkSetupError,
    PortCheck,
    SetupStage,
    SetupStageName,
    SetupStageState,
    StartupSetupStatus,
)
from .edge import HttpsEdgeServer
from .nat import NatMapper
from .render import render_startup_panel

logger = setup_logger(__name__)

class NetworkSetupService:
    def __init__(
        self,
        settings,
        nat_mapper: NatMapper | None = None,
        certificate_service: CertificateMaintenanceService | None = None,
        status_callback: Callable[[StartupSetupStatus], None] | None = None,
    ):
        self.settings = settings
        self.nat_mapper = nat_mapper or NatMapper(settings.NAT_AUTO_MAPPING_ENABLED)
        self.certificate_service = certificate_service or CertificateMaintenanceService(
            settings
        )
        self.status_callback = status_callback
        self.status = StartupSetupStatus(
            stages=_default_stages(settings),
            api_http_public_port=int(settings.ACME_HTTP_PUBLIC_PORT),
            api_https_public_port=int(settings.PUBLIC_HTTPS_PORT),
            vm_port_range_start=int(settings.PORT_RANGE_START),
            vm_port_range_end=int(settings.PORT_RANGE_END),
        )
        self.https_edge: HttpsEdgeServer | None = None

    async def setup(self) -> StartupSetupStatus:
        if (
            self.settings.DEV_MODE
            and not bool(getattr(self.settings, "SECURE_SETUP_IN_DEVELOPMENT", False))
        ) or self.settings.PUBLIC_ENDPOINT_MODE == "disabled":
            self._succeed(SetupStageName.PUBLIC_IP, "development")
            self._succeed(SetupStageName.NETWORK_ACCESS, "skipped")
            self._succeed(SetupStageName.CERTIFICATE, "skipped")
            self._succeed(SetupStageName.HTTPS_VERIFICATION, "skipped")
            self._succeed(SetupStageName.VM_PORT_RANGE, "skipped")
            self._succeed(SetupStageName.PROVIDER_START, "local mode")
            return self.status

        try:
            public_ip = await self._resolve_public_ip()
            try:
                self.settings.PUBLIC_IP = public_ip
            except Exception:
                pass
            endpoint_url = _endpoint_url(public_ip, self.settings.PUBLIC_HTTPS_PORT)
            self.status.endpoint_url = endpoint_url
            self._succeed(SetupStageName.PUBLIC_IP, public_ip)

            if self.settings.NAT_AUTO_MAPPING_ENABLED:
                await self._prepare_network_access()
            await self._verify_public_ports(public_ip)
            await self._ensure_certificate(public_ip)
            await self._start_https_edge()
            await self._verify_https_endpoint(public_ip)
            await self._verify_vm_port_range(public_ip)
            self._succeed(SetupStageName.PROVIDER_START, "ready")
            self.status.message = "Starting provider..."
            self._emit()
            logger.info("\n%s", render_startup_panel(self.status))
            return self.status
        except Exception as exc:
            if not self.status.failed:
                self._fail(
                    SetupStageName.PROVIDER_START,
                    "blocked",
                    "Golem Provider cannot start in direct mode.",
                )
            self.status.message = _failure_message(self.status) or str(exc)
            self._emit()
            logger.error("\n%s", render_startup_panel(self.status))
            await self.cleanup()
            raise NetworkSetupError(self.status.message, self.status) from exc

    async def cleanup(self) -> None:
        await self.certificate_service.stop()
        if self.https_edge is not None:
            await self.https_edge.stop()
            self.https_edge = None

    async def start_certificate_maintenance(self) -> None:
        await self.certificate_service.start(on_renewed=self.restart_https_edge)

    async def restart_https_edge(self) -> None:
        logger.info("Reloading HTTPS edge with renewed provider certificate")
        if self.https_edge is not None:
            await self.https_edge.stop()
            self.https_edge = None
        await self._start_https_edge()

    async def _resolve_public_ip(self) -> str:
        self._running(SetupStageName.PUBLIC_IP, "checking")
        configured = self._configured_public_ip()
        if configured:
            return configured
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.ipify.org", timeout=10) as response:
                    response.raise_for_status()
                    return (await response.text()).strip()
        except Exception as exc:
            self._fail(
                SetupStageName.PUBLIC_IP,
                "not available",
                "Check the internet connection or set GOLEM_PROVIDER_PUBLIC_IP.",
            )
            raise RuntimeError(f"Could not detect public IP: {exc}") from exc

    async def _prepare_network_access(self) -> None:
        self._running(SetupStageName.NETWORK_ACCESS, "checking")
        mappings = [
            (
                self.settings.ACME_HTTP_PUBLIC_PORT,
                self.settings.ACME_HTTP_INTERNAL_PORT,
                "Golem Provider certificate setup",
            ),
            (
                self.settings.PUBLIC_HTTPS_PORT,
                self.settings.PUBLIC_HTTPS_INTERNAL_PORT,
                "Golem Provider HTTPS",
            ),
        ]
        for public_port, internal_port, description in mappings:
            result = await self.nat_mapper.ensure_tcp_mapping(
                int(public_port),
                int(internal_port),
                description,
            )
            if not result.success:
                self._fail(
                    SetupStageName.NETWORK_ACCESS,
                    f"port unavailable :{public_port}",
                    _network_access_remediation(
                        int(public_port),
                        int(internal_port),
                        result.detail,
                    ),
                )
                raise RuntimeError(result.detail)

    async def _verify_public_ports(self, public_ip: str) -> None:
        public_ports = sorted(
            {
                int(self.settings.ACME_HTTP_PUBLIC_PORT),
                int(self.settings.PUBLIC_HTTPS_PORT),
            }
        )
        internal_ports = sorted(
            {
                int(self.settings.ACME_HTTP_INTERNAL_PORT),
                int(self.settings.PUBLIC_HTTPS_INTERNAL_PORT),
            }
        )
        verifier_url = str(self.settings.PORT_CHECK_TLS_URL or "").rstrip("/")
        verifier_timeout = _port_check_request_timeout(self.settings)
        if not verifier_url:
            self._succeed(
                SetupStageName.NETWORK_ACCESS,
                _ports_detail(public_ports, "mapped"),
            )
            return

        self._running(SetupStageName.NETWORK_ACCESS, "checking")
        self._set_port_checks(
            SetupStageName.NETWORK_ACCESS, _pending_port_checks(public_ports)
        )
        servers: list[asyncio.AbstractServer] = []
        started_at = time.perf_counter()
        try:
            logger.info(
                "Starting temporary listeners for public port verification: "
                "host=%s internal_ports=%s public_ports=%s checker=%s public_ip=%s",
                self.settings.HOST,
                internal_ports,
                public_ports,
                verifier_url,
                public_ip,
            )
            servers = await _start_temporary_tcp_listeners(
                self.settings.HOST, internal_ports
            )
            logger.info(
                "Temporary listeners are ready for public port verification: "
                "internal_ports=%s elapsed=%.2fs",
                internal_ports,
                time.perf_counter() - started_at,
            )
            results = await self._verify_ports_with_progress(
                SetupStageName.NETWORK_ACCESS,
                public_ip,
                public_ports,
                verifier_url,
                verifier_timeout,
                "public",
            )
            blocked_ports = [
                port for port in public_ports if not results.get(port, False)
            ]
            if blocked_ports:
                self._fail(
                    SetupStageName.NETWORK_ACCESS,
                    _ports_detail(blocked_ports, "unreachable"),
                    _public_ports_remediation(blocked_ports),
                )
                raise RuntimeError(
                    f"Public ports are unreachable: {', '.join(map(str, blocked_ports))}"
                )
            self._succeed(
                SetupStageName.NETWORK_ACCESS,
                _ports_detail(public_ports, "reachable"),
            )
            logger.info(
                "Public port verification succeeded: ports=%s elapsed=%.2fs",
                public_ports,
                time.perf_counter() - started_at,
            )
        except Exception as exc:
            error_detail = _verification_error_detail(exc)
            if (
                self.status.stage(SetupStageName.NETWORK_ACCESS).state
                != SetupStageState.FAILED
            ):
                self._fail(
                    SetupStageName.NETWORK_ACCESS,
                    error_detail,
                    "Could not verify public access through the central discovery port-check service.",
                )
            logger.warning(
                "Public port verification failed after %.2fs: ports=%s error=%s",
                time.perf_counter() - started_at,
                public_ports,
                error_detail,
            )
            raise RuntimeError(
                f"Public port verification failed: {error_detail}"
            ) from exc
        finally:
            if servers:
                logger.info(
                    "Stopping temporary listeners for public port verification: "
                    "internal_ports=%s",
                    internal_ports,
                )
            await _stop_temporary_tcp_listeners(servers)

    async def _verify_vm_port_range(self, public_ip: str) -> None:
        start = int(self.settings.PORT_RANGE_START)
        end = int(self.settings.PORT_RANGE_END)
        detail = _port_range_detail(start, end)
        self._running(SetupStageName.VM_PORT_RANGE, detail)
        verifier_url = str(self.settings.PORT_CHECK_TLS_URL or "").rstrip("/")
        verifier_timeout = _port_check_request_timeout(self.settings)
        if not verifier_url:
            self._succeed(SetupStageName.VM_PORT_RANGE, "verification skipped")
            return

        ports = list(range(start, end))
        if not ports:
            self._fail(
                SetupStageName.VM_PORT_RANGE,
                "invalid range",
                f"VM port range {detail} is empty. Check PORT_RANGE_START and PORT_RANGE_END.",
            )
            raise RuntimeError(f"VM port range {detail} is empty")

        self._set_port_checks(SetupStageName.VM_PORT_RANGE, _pending_port_checks(ports))
        servers: list[asyncio.AbstractServer] = []
        started_at = time.perf_counter()
        try:
            logger.info(
                "Starting temporary listeners for VM port verification: "
                "host=%s ports=%s checker=%s public_ip=%s",
                self.settings.HOST,
                ports,
                verifier_url,
                public_ip,
            )
            servers = await _start_temporary_tcp_listeners(self.settings.HOST, ports)
            logger.info(
                "Temporary listeners are ready for VM port verification: "
                "ports=%s elapsed=%.2fs",
                ports,
                time.perf_counter() - started_at,
            )
            results = await self._verify_ports_with_progress(
                SetupStageName.VM_PORT_RANGE,
                public_ip,
                ports,
                verifier_url,
                verifier_timeout,
                "VM",
            )
            blocked_ports = [port for port in ports if not results.get(port, False)]
            if blocked_ports:
                blocked_detail = _format_port_ranges(blocked_ports)
                self._fail(
                    SetupStageName.VM_PORT_RANGE,
                    f"{blocked_detail} unreachable",
                    _vm_port_range_remediation(start, end, blocked_ports),
                )
                raise RuntimeError(
                    "VM ports are unreachable: "
                    + ", ".join(map(str, blocked_ports[:8]))
                )
            self._succeed(SetupStageName.VM_PORT_RANGE, f"{detail} reachable")
            logger.info(
                "VM port verification succeeded: range=%s elapsed=%.2fs",
                detail,
                time.perf_counter() - started_at,
            )
        except Exception as exc:
            error_detail = _verification_error_detail(exc)
            if (
                self.status.stage(SetupStageName.VM_PORT_RANGE).state
                != SetupStageState.FAILED
            ):
                self._fail(
                    SetupStageName.VM_PORT_RANGE,
                    error_detail,
                    "Could not verify VM port forwarding through the central discovery port-check service.",
                )
            logger.warning(
                "VM port verification failed after %.2fs: range=%s error=%s",
                time.perf_counter() - started_at,
                detail,
                error_detail,
            )
            raise RuntimeError(
                f"VM port range verification failed: {error_detail}"
            ) from exc
        finally:
            if servers:
                logger.info(
                    "Stopping temporary listeners for VM port verification: ports=%s",
                    ports,
                )
            await _stop_temporary_tcp_listeners(servers)

    async def _verify_ports_with_progress(
        self,
        stage_name: SetupStageName,
        public_ip: str,
        ports: list[int],
        verifier_url: str,
        verifier_timeout: float,
        label: str,
    ) -> dict[int, bool]:
        async with aiohttp.ClientSession() as session:
            for port in ports:
                self._set_port_check_state(stage_name, port, "checking")
            request_started_at = time.perf_counter()
            logger.debug(
                "Requesting external %s port verification: "
                "checker=%s ports=%s timeout=%.2fs",
                label,
                verifier_url,
                ports,
                verifier_timeout,
            )
            async with session.post(
                f"{verifier_url}/check-ports",
                json={"provider_ip": public_ip, "ports": ports},
                timeout=verifier_timeout,
            ) as response:
                data = await response.json(content_type=None)
                logger.debug(
                    "External %s port verification returned: "
                    "checker=%s ports=%s status=%s elapsed=%.2fs results=%s",
                    label,
                    verifier_url,
                    ports,
                    response.status,
                    time.perf_counter() - request_started_at,
                    data.get("results", {}),
                )
                if response.status != 200:
                    raise RuntimeError(data.get("detail") or await response.text())
            results = {
                port: _port_result_accessible(data.get("results", {}), port)
                for port in ports
            }
            for port, accessible in results.items():
                self._set_port_check_state(
                    stage_name, port, "open" if accessible else "closed"
                )
            return results

    async def _ensure_certificate(self, public_ip: str) -> None:
        self._running(SetupStageName.CERTIFICATE, "checking")
        try:
            detail = await self.certificate_service.ensure_certificate(public_ip)
            self._succeed(SetupStageName.CERTIFICATE, detail)
            return
        except Exception as exc:
            error_detail = _verification_error_detail(exc)
            self._fail(
                SetupStageName.CERTIFICATE,
                error_detail,
                _certificate_setup_remediation(error_detail, self.settings, exc),
            )
            raise RuntimeError(f"Certificate setup failed: {exc}") from exc

    async def _start_https_edge(self) -> None:
        cert_dir = Path(self.settings.CERT_DIR)
        self.https_edge = HttpsEdgeServer(
            host=self.settings.HOST,
            port=int(self.settings.PUBLIC_HTTPS_INTERNAL_PORT),
            cert_path=cert_dir / "provider-ip.crt",
            key_path=cert_dir / "provider-ip.key",
            upstream_base_url=f"http://127.0.0.1:{self.settings.PORT}",
        )
        await self.https_edge.start()

    async def _verify_https_endpoint(self, public_ip: str) -> None:
        self._running(SetupStageName.HTTPS_VERIFICATION, "checking")
        verifier_url = str(self.settings.PORT_CHECK_TLS_URL or "").rstrip("/")
        verifier_timeout = _port_check_request_timeout(self.settings)
        if not verifier_url:
            self._succeed(
                SetupStageName.HTTPS_VERIFICATION, self.status.endpoint_url or ""
            )
            return
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{verifier_url}/check-tls",
                    json={
                        "host": public_ip,
                        "port": int(self.settings.PUBLIC_HTTPS_PORT),
                        "expected_ip": public_ip,
                    },
                    timeout=verifier_timeout,
                ) as response:
                    data = await response.json()
                    if (
                        response.status == 200
                        and not data.get("valid")
                        and _is_expected_staging_tls_trust_error(data, self.settings)
                    ):
                        self._succeed(
                            SetupStageName.HTTPS_VERIFICATION,
                            "staging certificate reachable",
                        )
                        return
                    if response.status != 200 or not data.get("valid"):
                        raise RuntimeError(data.get("error") or await response.text())
            self._succeed(
                SetupStageName.HTTPS_VERIFICATION, self.status.endpoint_url or ""
            )
        except Exception as exc:
            error_detail = _verification_error_detail(exc)
            self._fail(
                SetupStageName.HTTPS_VERIFICATION,
                error_detail,
                _https_verification_remediation(error_detail, self.settings, public_ip),
            )
            raise RuntimeError(f"HTTPS verification failed: {exc}") from exc

    def _running(self, name: SetupStageName, detail: str) -> None:
        self._set(name, SetupStageState.RUNNING, detail, None)

    def _succeed(self, name: SetupStageName, detail: str) -> None:
        self._set(name, SetupStageState.SUCCESS, detail, None)

    def _fail(self, name: SetupStageName, detail: str, remediation: str) -> None:
        self._set(name, SetupStageState.FAILED, detail, remediation)

    def _set(
        self,
        name: SetupStageName,
        state: SetupStageState,
        detail: str,
        remediation: str | None,
    ) -> None:
        stage = self.status.stage(name)
        stage.state = state
        stage.detail = detail
        stage.remediation = remediation
        log = logger.warning if state == SetupStageState.FAILED else logger.info
        log(
            "Network setup stage updated",
            extra={
                "stage": name.value if hasattr(name, "value") else str(name),
                "state": state.value if hasattr(state, "value") else str(state),
                "detail": detail,
            },
        )
        self._emit()

    def _set_port_checks(
        self, name: SetupStageName, port_checks: list[PortCheck]
    ) -> None:
        stage = self.status.stage(name)
        stage.port_checks = port_checks
        self._emit()

    def _set_port_check_state(
        self,
        name: SetupStageName,
        port: int,
        state: Literal["pending", "checking", "open", "closed"],
    ) -> None:
        stage = self.status.stage(name)
        stage.port_checks = [
            check.model_copy(update={"state": state}) if check.port == port else check
            for check in stage.port_checks
        ]
        self._emit()

    def _emit(self) -> None:
        if self.status_callback:
            self.status_callback(self.status)

    def _configured_public_ip(self) -> str | None:
        raw_public_ip = os.environ.get("GOLEM_PROVIDER_PUBLIC_IP")
        if raw_public_ip and raw_public_ip != "auto":
            return raw_public_ip

        raw_endpoint_ip = os.environ.get("GOLEM_PROVIDER_PUBLIC_ENDPOINT_IP")
        if raw_endpoint_ip and raw_endpoint_ip != "auto":
            return raw_endpoint_ip

        # Development config still supports LAN HTTP flows. Secure setup must
        # use the real public IP so ACME and browser trust validation are honest.
        if self.settings.DEV_MODE and bool(
            getattr(self.settings, "SECURE_SETUP_IN_DEVELOPMENT", False)
        ):
            return None

        configured = str(self.settings.PUBLIC_IP or self.settings.PUBLIC_ENDPOINT_IP)
        if configured and configured != "auto":
            return configured
        return None


def _default_stages(settings) -> list[SetupStage]:
    vm_range = _port_range_detail(
        int(settings.PORT_RANGE_START),
        int(settings.PORT_RANGE_END),
    )
    return [
        SetupStage(name=SetupStageName.PUBLIC_IP, label="Public IP detected"),
        SetupStage(
            name=SetupStageName.NETWORK_ACCESS,
            label="Ports 80 and 443 available",
        ),
        SetupStage(name=SetupStageName.CERTIFICATE, label="Checking certificate"),
        SetupStage(
            name=SetupStageName.HTTPS_VERIFICATION, label="Secure endpoint verified"
        ),
        SetupStage(
            name=SetupStageName.VM_PORT_RANGE,
            label=f"VM ports {vm_range} reachable",
        ),
        SetupStage(name=SetupStageName.PROVIDER_START, label="Provider start"),
    ]


def _endpoint_url(host: str, port: int) -> str:
    if int(port) == 443:
        return f"https://{host}"
    return f"https://{host}:{port}"


def _network_access_remediation(
    public_port: int, internal_port: int, setup_detail: str
) -> str:
    return (
        f"{setup_detail} Forward TCP public port {public_port} to this machine's "
        f"internal port {internal_port}, or choose a different public HTTPS/HTTP port."
    )


def _public_ports_remediation(public_ports: list[int]) -> str:
    return (
        f"TCP ports {_format_ports(public_ports)} are not reachable from the internet. "
        "Forward these ports to this machine or choose different public HTTPS/HTTP ports."
    )


def _vm_port_range_remediation(start: int, end: int, blocked_ports: list[int]) -> str:
    blocked = _format_port_ranges(blocked_ports)
    return (
        f"TCP VM port range {_port_range_detail(start, end)} is not reachable from "
        "the internet. Forward that range to this machine for rented VM access. "
        f"Failed ports: {blocked}."
    )


def _certificate_setup_remediation(
    error_detail: str, settings, exc: Exception | None = None
) -> str:
    if isinstance(exc, AcmeRequestError):
        return (
            f"Certificate setup failed: {error_detail}. "
            "The ACME server rejected the certificate request before HTTP-01 "
            "validation completed. Check GOLEM_PROVIDER_ACME_ENV, "
            "GOLEM_PROVIDER_ACME_DIRECTORY_URL, GOLEM_PROVIDER_ACME_PROFILE, "
            "and the ACME account settings."
        )
    public_port = int(settings.ACME_HTTP_PUBLIC_PORT)
    internal_port = int(settings.ACME_HTTP_INTERNAL_PORT)
    return (
        f"Certificate setup failed: {error_detail}. "
        "The ACME HTTP-01 challenge must be reachable from the internet at "
        f"TCP port {public_port} and handled by this machine on local port "
        f"{internal_port}. Check router forwarding, local firewall rules, and "
        f"whether the provider process is allowed to bind local port {internal_port}."
    )


def _https_verification_remediation(error_detail: str, settings, public_ip: str) -> str:
    if _is_tls_trust_error(error_detail):
        return (
            f"HTTPS verification failed: {error_detail}. The endpoint is reachable, "
            "but the certificate chain is not trusted by the external checker. "
            "Use GOLEM_PROVIDER_ACME_ENV=staging only for local validation; use "
            "GOLEM_PROVIDER_ACME_ENV=production for a publicly trusted certificate."
        )
    public_port = int(settings.PUBLIC_HTTPS_PORT)
    internal_port = int(settings.PUBLIC_HTTPS_INTERNAL_PORT)
    return (
        f"HTTPS verification failed: {error_detail}. The external checker tried "
        f"to validate {public_ip}:{public_port}; make sure public TCP port "
        f"{public_port} forwards to this machine's local port {internal_port} "
        "and that the HTTPS edge process is still running."
    )


def _ports_detail(public_ports: list[int], status: str) -> str:
    return f"{_format_ports(public_ports)} {status}"


def _format_ports(public_ports: list[int]) -> str:
    return ", ".join(f":{port}" for port in public_ports)


def _port_range_detail(start: int, end: int) -> str:
    return f"{start}-{end}"


def _format_port_ranges(ports: list[int]) -> str:
    if not ports:
        return ""
    ranges = []
    sorted_ports = sorted(set(ports))
    start = previous = sorted_ports[0]
    for port in sorted_ports[1:]:
        if port == previous + 1:
            previous = port
            continue
        ranges.append(_format_port_range(start, previous))
        start = previous = port
    ranges.append(_format_port_range(start, previous))
    return ", ".join(ranges)


def _format_port_range(start: int, end: int) -> str:
    return str(start) if start == end else f"{start}-{end}"


def _pending_port_checks(ports: list[int]) -> list[PortCheck]:
    return [PortCheck(port=port, state="pending") for port in ports]


def _port_result_accessible(results: dict, port: int) -> bool:
    result = results.get(str(port), results.get(port, {}))
    if not isinstance(result, dict):
        return False
    return bool(result.get("accessible"))


def _verification_error_detail(exc: Exception) -> str:
    if isinstance(exc, asyncio.TimeoutError):
        return "central discovery port-check request timed out"
    return str(exc) or exc.__class__.__name__


def _port_check_request_timeout(settings) -> float:
    return float(getattr(settings, "PORT_CHECK_REQUEST_TIMEOUT", 8.0))


def _is_expected_staging_tls_trust_error(data: dict, settings) -> bool:
    return _is_acme_staging(settings) and _is_tls_trust_error(
        str(data.get("error", ""))
    )


def _is_acme_staging(settings) -> bool:
    return str(getattr(settings, "ACME_ENV", "")).strip().lower() == "staging"


def _is_tls_trust_error(error_detail: str) -> bool:
    normalized = error_detail.lower()
    return (
        "certificate_verify_failed" in normalized
        or "unable to get local issuer certificate" in normalized
    )


async def _start_temporary_tcp_listeners(
    host: str, ports: list[int]
) -> list[asyncio.AbstractServer]:
    servers = []
    try:
        for port in ports:
            server = await asyncio.start_server(_close_temporary_connection, host, port)
            servers.append(server)
        return servers
    except Exception:
        await _stop_temporary_tcp_listeners(servers)
        raise


async def _close_temporary_connection(
    _reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    writer.close()
    await writer.wait_closed()


async def _stop_temporary_tcp_listeners(servers: list[asyncio.AbstractServer]) -> None:
    for server in servers:
        server.close()
    await asyncio.gather(*(server.wait_closed() for server in servers))


def _failure_message(status: StartupSetupStatus) -> str | None:
    for stage in status.stages:
        if stage.state == SetupStageState.FAILED:
            return stage.remediation or stage.detail
    return None
