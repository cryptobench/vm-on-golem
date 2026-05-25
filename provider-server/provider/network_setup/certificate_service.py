import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Awaitable, Callable

from ..utils.logging import setup_logger
from .acme import Http01ChallengeServer, NativeAcmeClient
from .certs import CertificateValidation, inspect_ip_certificate
from .domain import CertificateState, CertificateStatus
from .listen_host import listen_host_for_public_ip

logger = setup_logger(__name__)


RenewedCallback = Callable[[], Awaitable[None]]


class CertificateMaintenanceService:
    def __init__(self, settings):
        self.settings = settings
        self._lock = asyncio.Lock()
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._status = CertificateStatus(
            state=CertificateState.DISABLED
            if self._secure_endpoint_disabled()
            else CertificateState.FAILED
        )
        self._usable_until: datetime | None = None

    def get_status(self) -> CertificateStatus:
        return self._status

    def refresh_status(self, public_ip: str | None = None) -> CertificateStatus:
        if self._secure_endpoint_disabled():
            self._set_status(CertificateState.DISABLED, None, last_error=None)
            return self._status
        resolved_ip = public_ip or str(getattr(self.settings, "PUBLIC_IP", "") or "")
        if not resolved_ip:
            self._set_status(
                CertificateState.FAILED,
                None,
                last_error="public IP is not available",
            )
            return self._status
        self._set_status_from_validation(self._inspect(resolved_ip))
        return self._status

    def endpoint_is_advertisable(self) -> bool:
        if self._secure_endpoint_disabled():
            return True
        if self._status.state in {
            CertificateState.VALID,
            CertificateState.RENEWAL_DUE,
            CertificateState.RENEWED,
        }:
            return True
        return self._usable_until is not None and self._usable_until > self._now()

    async def ensure_certificate(self, public_ip: str) -> str:
        async with self._lock:
            result = self._inspect(public_ip)
            self._set_status_from_validation(result)
            if result.valid:
                logger.info("Provider certificate is valid: %s", result.detail)
                return result.detail

            self._set_status(
                CertificateState.RENEWING,
                result,
                last_error=None,
            )
            try:
                await self._issue_certificate(public_ip)
            except Exception as exc:
                self._record_failure(exc, result)
                raise
            renewed = self._inspect(public_ip)
            if not renewed.valid:
                self._set_status_from_validation(renewed)
                raise RuntimeError(renewed.detail)

            self._usable_until = renewed.expires_at
            self._set_status(
                CertificateState.RENEWED,
                renewed,
                last_renewed_at=self._now(),
                last_error=None,
            )
            logger.info("Provider certificate renewed: %s", renewed.detail)
            return renewed.detail

    async def check_once(self, on_renewed: RenewedCallback | None = None) -> bool:
        if self._secure_endpoint_disabled():
            self._set_status(CertificateState.DISABLED, None, last_error=None)
            return False
        public_ip = str(getattr(self.settings, "PUBLIC_IP", "") or "")
        if not public_ip:
            self._set_status(
                CertificateState.FAILED,
                None,
                last_error="public IP is not available",
            )
            raise RuntimeError("public IP is not available")

        async with self._lock:
            result = self._inspect(public_ip)
            self._set_status_from_validation(result)
            if result.valid:
                logger.info("Provider certificate renewal check: %s", result.detail)
                return False

            if not result.renewal_due:
                logger.info(
                    "Provider certificate renewal required before advertising: %s",
                    result.detail,
                )
            else:
                logger.info("Provider certificate renewal due: %s", result.detail)

            self._set_status(CertificateState.RENEWING, result, last_error=None)
            try:
                await self._issue_certificate(public_ip)
            except Exception as exc:
                self._record_failure(exc, result)
                raise

            renewed = self._inspect(public_ip)
            if not renewed.valid:
                self._set_status_from_validation(renewed)
                raise RuntimeError(renewed.detail)

            self._usable_until = renewed.expires_at
            self._set_status(
                CertificateState.RENEWED,
                renewed,
                last_renewed_at=self._now(),
                last_error=None,
            )

        if on_renewed is not None:
            await on_renewed()
        logger.info("Provider certificate renewed in background: %s", renewed.detail)
        return True

    async def start(self, on_renewed: RenewedCallback | None = None) -> None:
        if not bool(getattr(self.settings, "CERT_RENEWAL_ENABLED", True)):
            logger.info("Provider certificate renewal disabled")
            return
        if self._secure_endpoint_disabled():
            self._set_status(CertificateState.DISABLED, None, last_error=None)
            return
        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(
            self._run_loop(on_renewed),
            name="certificate-renewal",
        )

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None

    async def _run_loop(self, on_renewed: RenewedCallback | None) -> None:
        retry_delay = int(
            getattr(self.settings, "CERT_RENEWAL_RETRY_INITIAL_SECONDS", 300)
        )
        max_retry = int(getattr(self.settings, "CERT_RENEWAL_RETRY_MAX_SECONDS", 21600))
        while not self._stop_event.is_set():
            try:
                await self.check_once(on_renewed)
                retry_delay = int(
                    getattr(self.settings, "CERT_RENEWAL_RETRY_INITIAL_SECONDS", 300)
                )
                delay = int(
                    getattr(self.settings, "CERT_RENEWAL_CHECK_INTERVAL_SECONDS", 3600)
                )
            except Exception as exc:
                if self.endpoint_is_advertisable():
                    logger.warning(
                        "Provider certificate renewal failed; existing certificate "
                        "remains usable: %s",
                        exc,
                    )
                else:
                    logger.error("Provider certificate is not usable: %s", exc)
                delay = retry_delay
                retry_delay = min(max_retry, max(retry_delay * 2, retry_delay + 1))

            self._set_next_check(delay)
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass

    async def _issue_certificate(self, public_ip: str) -> None:
        challenge_server = Http01ChallengeServer(
            listen_host_for_public_ip(self.settings.HOST, public_ip),
            int(self.settings.ACME_HTTP_INTERNAL_PORT),
        )
        try:
            await challenge_server.start()
            client = NativeAcmeClient(
                directory_url=self.settings.ACME_DIRECTORY_URL,
                account_key_path=self._account_key_path,
                cert_key_path=self._key_path,
                certificate_path=self._cert_path,
                email=self.settings.ACME_ACCOUNT_EMAIL,
                profile=self.settings.ACME_PROFILE,
            )
            await client.issue_ip_certificate(public_ip, challenge_server)
        finally:
            await challenge_server.stop()

    def _inspect(self, public_ip: str) -> CertificateValidation:
        return inspect_ip_certificate(
            self._cert_path,
            self._key_path,
            public_ip,
            int(self.settings.CERT_RENEW_BEFORE_HOURS),
        )

    def _set_status_from_validation(self, result: CertificateValidation) -> None:
        if result.valid:
            state = CertificateState.VALID
        elif result.expired:
            state = CertificateState.EXPIRED
        elif result.renewal_due:
            state = CertificateState.RENEWAL_DUE
        else:
            state = CertificateState.FAILED
        self._set_status(
            state, result, last_error=None if result.usable else result.detail
        )

    def _record_failure(
        self,
        exc: Exception,
        previous: CertificateValidation,
    ) -> None:
        state = (
            CertificateState.EXPIRED if previous.expired else CertificateState.FAILED
        )
        self._set_status(state, previous, last_error=str(exc) or exc.__class__.__name__)

    def _set_status(
        self,
        state: CertificateState,
        result: CertificateValidation | None,
        *,
        last_renewed_at: datetime | None = None,
        last_error: str | None = None,
    ) -> None:
        now = self._now()
        expires_at = (
            result.expires_at if result is not None else self._status.expires_at
        )
        renew_after = (
            result.renew_after if result is not None else self._status.renew_after
        )
        if result is not None and result.usable:
            self._usable_until = result.expires_at
        elif state == CertificateState.DISABLED:
            self._usable_until = None
        self._status = CertificateStatus(
            state=state,
            expires_at=expires_at,
            renew_after=renew_after,
            last_checked_at=now,
            last_renewed_at=last_renewed_at or self._status.last_renewed_at,
            next_check_at=self._status.next_check_at,
            last_error=last_error,
        )

    def _set_next_check(self, delay_seconds: int) -> None:
        self._status = self._status.model_copy(
            update={"next_check_at": self._now() + timedelta(seconds=delay_seconds)}
        )

    def _secure_endpoint_disabled(self) -> bool:
        return (
            bool(getattr(self.settings, "DEV_MODE", False))
            and not bool(getattr(self.settings, "SECURE_SETUP_IN_DEVELOPMENT", False))
        ) or getattr(self.settings, "PUBLIC_ENDPOINT_MODE", "") == "disabled"

    @property
    def _cert_path(self) -> Path:
        return Path(self.settings.CERT_DIR) / "provider-ip.crt"

    @property
    def _key_path(self) -> Path:
        return Path(self.settings.CERT_DIR) / "provider-ip.key"

    @property
    def _account_key_path(self) -> Path:
        return Path(self.settings.CERT_DIR) / "acme-account.key"

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
