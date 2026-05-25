import json
import os
import secrets
import time
from pathlib import Path
from typing import Any

import httpx

DEFAULT_API_BASE_URL = "http://127.0.0.1:7466/api/v1"


class ProviderCliError(Exception):
    """Raised for operator-facing CLI failures."""


def provider_vm_data_dir() -> Path:
    raw = os.environ.get("GOLEM_PROVIDER_VM_DATA_DIR", "").strip()
    if not raw:
        try:
            from dotenv import dotenv_values

            from provider.config_persistence import active_provider_env_path

            raw = str(
                dotenv_values(active_provider_env_path()).get(
                    "GOLEM_PROVIDER_VM_DATA_DIR"
                )
                or ""
            ).strip()
        except Exception:
            raw = ""
    if raw:
        path = Path(raw).expanduser()
        return path if path.is_absolute() else Path.home() / path
    return Path.home() / ".golem" / "provider" / "vms"


def read_or_create_admin_token() -> str:
    configured = os.environ.get("GOLEM_PROVIDER_ADMIN_TOKEN", "").strip()
    if configured:
        return configured

    path = provider_vm_data_dir() / "provider-admin.token"
    if path.exists():
        value = path.read_text(encoding="utf-8").strip()
        if value:
            return value

    path.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(48)
    path.write_text(token, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return token


def provider_admin_env() -> dict[str, str]:
    return {
        "GOLEM_PROVIDER_ADMIN_TOKEN": read_or_create_admin_token(),
        "GOLEM_PROVIDER_VM_DATA_DIR": str(provider_vm_data_dir()),
        "GOLEM_PROVIDER_DISABLE_RELOAD": "1",
    }


class ProviderAdminClient:
    def __init__(
        self,
        base_url: str = DEFAULT_API_BASE_URL,
        token: str | None = None,
        timeout: float = 10.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token or read_or_create_admin_token()
        self.timeout = timeout

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.request(
                    method,
                    url,
                    headers=self.headers,
                    json=json_body,
                    params=params,
                )
        except httpx.ConnectError as exc:
            raise ProviderCliError(
                "Provider API is not reachable. Run 'golem-provider start' first."
            ) from exc
        except httpx.TimeoutException as exc:
            raise ProviderCliError("Provider API request timed out.") from exc
        except httpx.HTTPError as exc:
            raise ProviderCliError(f"Provider API request failed: {exc}") from exc

        if response.status_code in (401, 403):
            raise ProviderCliError(
                "Provider admin token was rejected by the running provider."
            )
        if response.status_code >= 400:
            raise ProviderCliError(_response_error(response))
        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise ProviderCliError("Provider API returned invalid JSON.") from exc

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        return self.request("GET", path, params=params)

    def post(self, path: str, *, json_body: Any | None = None) -> Any:
        return self.request("POST", path, json_body=json_body)

    def patch(self, path: str, *, json_body: Any | None = None) -> Any:
        return self.request("PATCH", path, json_body=json_body)

    def put(self, path: str, *, json_body: Any | None = None) -> Any:
        return self.request("PUT", path, json_body=json_body)

    def delete(self, path: str) -> Any:
        return self.request("DELETE", path)

    def is_ready(self) -> tuple[bool, str | None]:
        try:
            self.get("/provider/settings")
            return True, None
        except ProviderCliError as exc:
            return False, str(exc)


def wait_for_provider_api(
    *,
    base_url: str = DEFAULT_API_BASE_URL,
    token: str | None = None,
    timeout_seconds: int = 180,
    interval_seconds: float = 1.0,
) -> None:
    client = ProviderAdminClient(base_url=base_url, token=token, timeout=3.0)
    deadline = time.monotonic() + max(1, timeout_seconds)
    last_error: str | None = None
    while time.monotonic() < deadline:
        ready, error = client.is_ready()
        if ready:
            return
        last_error = error
        time.sleep(interval_seconds)
    raise ProviderCliError(
        f"Provider did not become ready within {timeout_seconds}s"
        + (f": {last_error}" if last_error else ".")
    )


def dump_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=False)


def _response_error(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = response.text.strip()
    if isinstance(payload, dict):
        detail = payload.get("detail") or payload.get("error") or payload
    else:
        detail = payload or response.reason_phrase
    return f"Provider API returned HTTP {response.status_code}: {detail}"
