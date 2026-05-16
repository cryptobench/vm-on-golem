import secrets
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from eth_account import Account
from eth_account.messages import encode_typed_data
from jose import JWTError, jwt

from provider.auth.domain import (
    AdminIdentity,
    RequestorIdentity,
    RequestorSession,
    RequestorSessionCommand,
)
from provider.auth.errors import ForbiddenError, UnauthorizedError
from provider.payments.stream_status_service import ZERO_ADDRESS

REQUESTOR_SESSION_DOMAIN = "GolemProviderSession"
REQUESTOR_SESSION_VERSION = "1"
REQUESTOR_TOKEN_AUDIENCE = "golem-provider-requestor"
ADMIN_TOKEN_AUDIENCE = "golem-provider-admin"
JWT_ALGORITHM = "HS256"
DEFAULT_SESSION_TTL_SECONDS = 900


class ProviderAuthService:
    """Shared authorization service for provider API requestors and admins."""

    def __init__(
        self,
        settings: Any,
        stream_map: Any,
        job_store: Any,
        reader_factory: Any,
    ):
        self.settings = settings
        self.stream_map = stream_map
        self.job_store = job_store
        self.reader_factory = reader_factory
        self._seen_session_nonces: dict[tuple[str, str], int] = {}
        self._session_secret: str | None = None
        self._admin_token: str | None = None

    def _setting(self, name: str, default: Any = None) -> Any:
        if isinstance(self.settings, dict):
            return self.settings.get(name, default)
        return getattr(self.settings, name, default)

    def _provider_id(self) -> str:
        provider_id = str(self._setting("PROVIDER_ID", "") or "")
        if not provider_id:
            raise UnauthorizedError("provider identity unavailable")
        return provider_id

    def _vm_data_dir(self) -> Path:
        base = str(self._setting("VM_DATA_DIR", "") or "")
        if not base:
            raise UnauthorizedError("provider VM data directory unavailable")
        return Path(base)

    def _get_or_create_secret(self, filename: str) -> str:
        path = self._vm_data_dir() / filename
        if path.exists():
            value = path.read_text().strip()
            if value:
                return value
        path.parent.mkdir(parents=True, exist_ok=True)
        value = secrets.token_urlsafe(48)
        path.write_text(value)
        try:
            path.chmod(0o600)
        except OSError:
            pass
        return value

    def _session_signing_secret(self) -> str:
        configured = str(self._setting("REQUESTOR_SESSION_SECRET", "") or "").strip()
        if configured:
            return configured
        if self._session_secret is None:
            self._session_secret = self._get_or_create_secret("requestor-session.key")
        return self._session_secret

    def _provider_admin_token(self) -> str:
        configured = str(self._setting("PROVIDER_ADMIN_TOKEN", "") or "").strip()
        if configured:
            return configured
        if self._admin_token is None:
            self._admin_token = self._get_or_create_secret("provider-admin.token")
        return self._admin_token

    def issue_requestor_session(
        self, command: RequestorSessionCommand
    ) -> RequestorSession:
        now = int(time.time())
        if command.deadline < now:
            raise UnauthorizedError("requestor session signature expired")
        if command.scope != "vm":
            raise ForbiddenError("unsupported requestor session scope")
        requestor = self._recover_session_signer(command)
        if requestor.lower() != command.requestor_address.lower():
            raise UnauthorizedError("requestor session signature mismatch")

        self._purge_session_nonces(now)
        nonce_key = (requestor.lower(), command.nonce)
        if nonce_key in self._seen_session_nonces:
            raise UnauthorizedError("requestor session nonce already used")
        self._seen_session_nonces[nonce_key] = command.deadline

        expires_at = min(now + DEFAULT_SESSION_TTL_SECONDS, command.deadline)
        token_id = str(uuid4())
        token = jwt.encode(
            {
                "sub": requestor,
                "vm_id": command.vm_id,
                "jti": token_id,
                "exp": expires_at,
                "aud": REQUESTOR_TOKEN_AUDIENCE,
                "iss": self._provider_id(),
            },
            self._session_signing_secret(),
            algorithm=JWT_ALGORITHM,
        )
        return RequestorSession(
            access_token=token,
            expires_at=expires_at,
            requestor_address=requestor,
            vm_id=command.vm_id,
        )

    def _recover_session_signer(self, command: RequestorSessionCommand) -> str:
        signable = encode_typed_data(
            domain_data={
                "name": REQUESTOR_SESSION_DOMAIN,
                "version": REQUESTOR_SESSION_VERSION,
            },
            message_types={
                "ProviderSession": [
                    {"name": "provider", "type": "address"},
                    {"name": "requestor", "type": "address"},
                    {"name": "vmId", "type": "string"},
                    {"name": "scope", "type": "string"},
                    {"name": "nonce", "type": "string"},
                    {"name": "deadline", "type": "uint256"},
                ]
            },
            message_data={
                "provider": self._provider_id(),
                "requestor": command.requestor_address,
                "vmId": command.vm_id,
                "scope": command.scope,
                "nonce": command.nonce,
                "deadline": command.deadline,
            },
        )
        return Account.recover_message(signable, signature=command.signature)

    def validate_requestor_token(self, token: str) -> RequestorIdentity:
        try:
            claims = jwt.decode(
                token,
                self._session_signing_secret(),
                algorithms=[JWT_ALGORITHM],
                audience=REQUESTOR_TOKEN_AUDIENCE,
                issuer=self._provider_id(),
            )
        except JWTError as exc:
            raise UnauthorizedError("invalid requestor session token") from exc

        requestor = str(claims.get("sub") or "")
        vm_id = str(claims.get("vm_id") or "")
        token_id = str(claims.get("jti") or "")
        expires_at = int(claims.get("exp") or 0)
        if not requestor or not vm_id or not token_id or not expires_at:
            raise UnauthorizedError("invalid requestor session claims")
        return RequestorIdentity(
            requestor_address=requestor,
            vm_id=vm_id,
            token_id=token_id,
            expires_at=expires_at,
        )

    def validate_admin_token(self, token: str) -> AdminIdentity:
        expected = self._provider_admin_token()
        if not token or not secrets.compare_digest(token, expected):
            raise UnauthorizedError("invalid provider admin token")
        return AdminIdentity()

    async def require_vm_access(
        self, identity: RequestorIdentity, vm_id: str
    ) -> RequestorIdentity:
        if identity.vm_id != vm_id:
            raise ForbiddenError("requestor session is scoped to a different VM")
        owner = await self.resolve_vm_owner(vm_id)
        if owner.lower() != identity.requestor_address.lower():
            raise ForbiddenError("requestor does not own this VM")
        return identity

    async def require_job_access(
        self, identity: RequestorIdentity, job_id: str
    ) -> RequestorIdentity:
        job = await self.job_store.get_job(job_id)
        if not job:
            raise ForbiddenError("job owner unavailable")
        if str(job.get("vm_id") or "") != identity.vm_id:
            raise ForbiddenError("requestor session is scoped to a different VM")
        owner = str(job.get("requestor_address") or "")
        if not owner:
            raise ForbiddenError("job owner unavailable")
        if owner.lower() != identity.requestor_address.lower():
            raise ForbiddenError("requestor does not own this VM job")
        return identity

    async def resolve_vm_owner(self, vm_id: str) -> str:
        get_owner = getattr(self.stream_map, "get_owner", None)
        if get_owner is not None:
            owner = await get_owner(vm_id)
            if owner:
                return str(owner)

        stream_id = await self.stream_map.get(vm_id)
        if stream_id is None:
            raise ForbiddenError("VM owner unavailable")

        reader = self.reader_factory()
        try:
            stream = reader.get_stream(int(stream_id))
        except Exception as exc:
            raise ForbiddenError("VM owner lookup failed") from exc
        sender = str(stream.get("sender") or "")
        if not sender or sender.lower() == ZERO_ADDRESS:
            raise ForbiddenError("VM owner unavailable")

        set_owner = getattr(self.stream_map, "set_owner", None)
        if set_owner is not None:
            await set_owner(vm_id, sender)
        return sender

    def _purge_session_nonces(self, now: int) -> None:
        for key, deadline in list(self._seen_session_nonces.items()):
            if deadline < now:
                del self._seen_session_nonces[key]
