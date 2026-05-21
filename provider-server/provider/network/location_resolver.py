import ipaddress
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Iterable

import aiohttp
from pydantic import BaseModel, ValidationError, field_validator

from provider.errors import ConfigurationError, ExternalServiceError

logger = logging.getLogger(__name__)

LEGACY_LOCATION_OVERRIDE_ENV_VARS = (
    "GOLEM_PROVIDER_COUNTRY",
    "GOLEM_PROVIDER_PUBLIC_IP",
    "GOLEM_PROVIDER_PUBLIC_ENDPOINT_IP",
)


class ProviderLocation(BaseModel):
    ip_address: str
    country: str

    @field_validator("ip_address")
    @classmethod
    def validate_ip_address(cls, value: str) -> str:
        ip_address = str(value or "").strip()
        if not ip_address:
            raise ValueError("provider IP address is required")
        try:
            ipaddress.ip_address(ip_address)
        except ValueError as exc:
            raise ValueError("provider IP address must be a valid IP address") from exc
        return ip_address

    @field_validator("country")
    @classmethod
    def validate_country(cls, value: str) -> str:
        country = str(value or "").strip().upper()
        if not re.fullmatch(r"[A-Z]{2}", country):
            raise ValueError("provider country must be a two-letter ISO country code")
        return country


@dataclass(frozen=True)
class LocationEndpoint:
    name: str
    url: str
    country_fields: tuple[str, ...]


LOCATION_ENDPOINTS: tuple[LocationEndpoint, ...] = (
    LocationEndpoint("country.is", "https://api.country.is/", ("country",)),
    LocationEndpoint("kamero", "https://geo.kamero.ai/api/geo", ("country",)),
    LocationEndpoint("tgip", "https://api.tgip.eu?format=json", ("country",)),
    LocationEndpoint("ipapi.co", "https://ipapi.co/json/", ("country", "country_code")),
    LocationEndpoint("ifconfig.co", "https://ifconfig.co/json", ("country_iso",)),
)


def reject_provider_location_overrides(env: dict[str, str] | None = None) -> None:
    source = os.environ if env is None else env
    configured = [
        key for key in LEGACY_LOCATION_OVERRIDE_ENV_VARS if str(source.get(key) or "")
    ]
    if configured:
        keys = ", ".join(sorted(configured))
        raise ConfigurationError(
            "Provider public IP and country are resolved automatically and cannot "
            f"be overridden. Remove these settings: {keys}."
        )


async def ensure_provider_location(settings: Any) -> ProviderLocation:
    reject_provider_location_overrides()
    if str(getattr(settings, "PUBLIC_ENDPOINT_MODE", "") or "") == "disabled":
        location = ProviderLocation(ip_address="127.0.0.1", country="ZZ")
        _apply_provider_location(settings, location)
        return location
    try:
        location = ProviderLocation(
            ip_address=getattr(settings, "PUBLIC_IP", None),
            country=getattr(settings, "PROVIDER_COUNTRY", None),
        )
    except ValidationError:
        location = await resolve_provider_location()

    _apply_provider_location(settings, location)
    return location


async def resolve_provider_location(
    *,
    endpoints: Iterable[LocationEndpoint] = LOCATION_ENDPOINTS,
    session: aiohttp.ClientSession | None = None,
    timeout_seconds: float = 5.0,
) -> ProviderLocation:
    if session is not None:
        return await _resolve_with_session(session, endpoints)

    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    async with aiohttp.ClientSession(timeout=timeout) as owned_session:
        return await _resolve_with_session(owned_session, endpoints)


async def _resolve_with_session(
    session: aiohttp.ClientSession,
    endpoints: Iterable[LocationEndpoint],
) -> ProviderLocation:
    errors: list[str] = []
    for endpoint in endpoints:
        try:
            async with session.get(endpoint.url) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
            return _location_from_payload(endpoint, payload)
        except Exception as exc:
            errors.append(f"{endpoint.name}: {exc}")
            logger.warning(
                "Provider location endpoint failed",
                extra={"endpoint": endpoint.name, "url": endpoint.url},
                exc_info=True,
            )

    raise ExternalServiceError(
        "Could not resolve provider public IP and country from any location "
        f"endpoint: {'; '.join(errors)}"
    )


def _location_from_payload(
    endpoint: LocationEndpoint, payload: Any
) -> ProviderLocation:
    if not isinstance(payload, dict):
        raise ValueError("location response must be a JSON object")
    country = _first_present(payload, endpoint.country_fields)
    return ProviderLocation(ip_address=payload.get("ip"), country=country)


def _first_present(payload: dict[str, Any], fields: tuple[str, ...]) -> Any:
    for field in fields:
        value = payload.get(field)
        if value:
            return value
    raise ValueError(f"location response missing country field: {', '.join(fields)}")


def _apply_provider_location(settings: Any, location: ProviderLocation) -> None:
    settings.PUBLIC_IP = location.ip_address
    settings.PROVIDER_COUNTRY = location.country
    if hasattr(settings, "PUBLIC_ENDPOINT_IP"):
        settings.PUBLIC_ENDPOINT_IP = location.ip_address
