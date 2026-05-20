import pytest

from provider.errors import ExternalServiceError
from provider.network.location_resolver import (
    LOCATION_ENDPOINTS,
    LocationEndpoint,
    ProviderLocation,
    resolve_provider_location,
)


class FakeResponse:
    def __init__(self, payload=None, error: Exception | None = None):
        self.payload = payload
        self.error = error

    async def __aenter__(self):
        if self.error:
            raise self.error
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    def raise_for_status(self):
        return None

    async def json(self, content_type=None):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []

    def get(self, url):
        self.urls.append(url)
        response = self.responses.pop(0)
        if isinstance(response, FakeResponse):
            return response
        return FakeResponse(response)


@pytest.mark.parametrize(
    ("endpoint", "payload"),
    [
        (LOCATION_ENDPOINTS[0], {"ip": "203.0.113.10", "country": "dk"}),
        (LOCATION_ENDPOINTS[1], {"ip": "203.0.113.10", "country": "DK"}),
        (LOCATION_ENDPOINTS[2], {"ip": "203.0.113.10", "country": "DK"}),
        (
            LOCATION_ENDPOINTS[3],
            {"ip": "203.0.113.10", "country_code": "DK"},
        ),
        (LOCATION_ENDPOINTS[4], {"ip": "203.0.113.10", "country_iso": "DK"}),
    ],
)
@pytest.mark.asyncio
async def test_resolves_supported_endpoint_response_shapes(endpoint, payload):
    session = FakeSession([payload])

    location = await resolve_provider_location(endpoints=[endpoint], session=session)

    assert location == ProviderLocation(ip_address="203.0.113.10", country="DK")
    assert session.urls == [endpoint.url]


@pytest.mark.asyncio
async def test_resolver_falls_back_after_endpoint_failure():
    first = LocationEndpoint("bad", "https://bad.example", ("country",))
    second = LocationEndpoint("good", "https://good.example", ("country",))
    session = FakeSession(
        [
            FakeResponse(error=RuntimeError("network down")),
            {"ip": "203.0.113.20", "country": "DK"},
        ]
    )

    location = await resolve_provider_location(
        endpoints=[first, second],
        session=session,
    )

    assert location == ProviderLocation(ip_address="203.0.113.20", country="DK")
    assert session.urls == [first.url, second.url]


@pytest.mark.parametrize(
    "payload",
    [
        ValueError("invalid json"),
        [],
        {"country": "DK"},
        {"ip": "203.0.113.10"},
        {"ip": "not-an-ip", "country": "DK"},
        {"ip": "203.0.113.10", "country": "Denmark"},
    ],
)
@pytest.mark.asyncio
async def test_resolver_rejects_invalid_payloads(payload):
    endpoint = LocationEndpoint("invalid", "https://invalid.example", ("country",))
    session = FakeSession([payload])

    with pytest.raises(ExternalServiceError):
        await resolve_provider_location(endpoints=[endpoint], session=session)


@pytest.mark.asyncio
async def test_resolver_fails_when_all_endpoints_fail():
    endpoints = [
        LocationEndpoint("one", "https://one.example", ("country",)),
        LocationEndpoint("two", "https://two.example", ("country",)),
    ]
    session = FakeSession(
        [
            FakeResponse(error=RuntimeError("first failed")),
            FakeResponse(error=RuntimeError("second failed")),
        ]
    )

    with pytest.raises(ExternalServiceError, match="one: first failed"):
        await resolve_provider_location(endpoints=endpoints, session=session)
