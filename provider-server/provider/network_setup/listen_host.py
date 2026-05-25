import ipaddress


def is_ipv4_address(value: str) -> bool:
    try:
        return isinstance(ipaddress.ip_address(value), ipaddress.IPv4Address)
    except ValueError:
        return False


def is_ipv6_address(value: str) -> bool:
    try:
        return isinstance(ipaddress.ip_address(value), ipaddress.IPv6Address)
    except ValueError:
        return False


def listen_host_for_public_ip(configured_host: str, public_ip: str) -> str:
    host = str(configured_host or "").strip()
    if is_ipv6_address(public_ip) and host in {"", "0.0.0.0"}:
        return "::"
    if is_ipv4_address(public_ip) and host in {"", "::"}:
        return "0.0.0.0"
    return host
