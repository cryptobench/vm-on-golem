from ipaddress import IPv4Address, IPv6Address, ip_address
from urllib.parse import parse_qsl, urlencode

from port_checker.errors import ConfigurationError, ValidationError

PortRange = tuple[int, int]

HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
    "accept-encoding",
    "sec-websocket-accept",
    "sec-websocket-extensions",
    "sec-websocket-key",
    "sec-websocket-protocol",
    "sec-websocket-version",
}

PROVIDER_CONTROL_HEADERS = {
    "x-proxy-token",
    "x-proxy-source",
    "x-proxy-arkiv-rpc",
    "x-proxy-arkiv-ws",
}

DIRECT_CONTROL_HEADERS = {
    "x-forward-to",
    "x-forward-protocol",
    "x-proxy-token",
}


def parse_allowed_ports(spec: str) -> list[PortRange]:
    ranges: list[PortRange] = []
    value = (spec or "").strip()
    if not value:
        raise ConfigurationError("Allowed ports spec cannot be empty")
    if value == "*":
        return [(1, 65535)]
    for part in (part.strip() for part in value.split(",") if part.strip()):
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            try:
                start, end = int(start_text), int(end_text)
            except ValueError as exc:
                raise ConfigurationError(f"Invalid allowed port range: {part}") from exc
            if not (1 <= start <= 65535 and 1 <= end <= 65535 and start <= end):
                raise ConfigurationError(f"Invalid allowed port range: {part}")
            ranges.append((start, end))
            continue
        try:
            port = int(part)
        except ValueError as exc:
            raise ConfigurationError(f"Invalid allowed port: {part}") from exc
        if not 1 <= port <= 65535:
            raise ConfigurationError(f"Invalid allowed port: {part}")
        ranges.append((port, port))
    if not ranges:
        raise ConfigurationError("Allowed ports spec cannot be empty")
    return ranges


def is_allowed_port(port: int, ranges: list[PortRange]) -> bool:
    return any(start <= port <= end for start, end in ranges)


def is_public_ip(ip_str: str) -> bool:
    try:
        ip = ip_address(ip_str)
    except ValueError:
        return False
    if isinstance(ip, (IPv4Address, IPv6Address)):
        return not (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
        )
    return False


def normalize_proxy_source(source: str | None) -> str:
    value = (source or "central").strip().lower()
    if value not in {"arkiv", "central"}:
        raise ValidationError("Invalid source; use 'central' or 'arkiv'")
    return value


def forwarded_query(query: str, excluded_keys: set[str]) -> str:
    if not query:
        return ""
    parts = [
        (key, value)
        for key, value in parse_qsl(query, keep_blank_values=True)
        if key not in excluded_keys
    ]
    return urlencode(parts)


def append_query(url: str, query: str) -> str:
    return f"{url}?{query}" if query else url


def case_insensitive_get(headers: dict[str, str], name: str) -> str | None:
    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target:
            return value
    return None


def forwarded_headers(
    headers: dict[str, str],
    excluded_headers: set[str],
    client_host: str,
) -> dict[str, str]:
    excluded = HOP_BY_HOP_HEADERS | excluded_headers
    result = {
        key: value
        for key, value in headers.items()
        if key.lower() not in excluded and not key.lower().startswith("x-proxy-")
    }
    prior_xff = case_insensitive_get(headers, "x-forwarded-for")
    chain = (
        f"{prior_xff}, {client_host}"
        if prior_xff and client_host
        else (client_host or prior_xff)
    )
    if chain:
        result["X-Forwarded-For"] = chain
    if client_host:
        result["X-Real-IP"] = client_host
    return result


def response_headers(headers: dict[str, str]) -> dict[str, str]:
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
    }
