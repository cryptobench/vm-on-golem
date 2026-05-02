import pytest

from port_checker.config import Settings
from port_checker.errors import ConfigurationError, ValidationError
from port_checker.proxy.policy import (
    forwarded_headers,
    forwarded_query,
    is_allowed_port,
    is_public_ip,
    normalize_proxy_source,
    parse_allowed_ports,
)


def test_parse_allowed_ports_basic_and_wildcard():
    ranges = parse_allowed_ports("80,443,1000-1005, 65535")

    assert (80, 80) in ranges
    assert (443, 443) in ranges
    assert (1000, 1005) in ranges
    assert (65535, 65535) in ranges
    assert parse_allowed_ports("*") == [(1, 65535)]


def test_parse_allowed_ports_invalid_tokens_raise():
    with pytest.raises(ConfigurationError):
        parse_allowed_ports("80,abc-def,443")

    with pytest.raises(ConfigurationError):
        parse_allowed_ports("")


def test_is_allowed_port_range_and_exact():
    ranges = parse_allowed_ports("80,443,1024-65535")

    assert is_allowed_port(80, ranges)
    assert is_allowed_port(443, ranges)
    assert is_allowed_port(2048, ranges)
    assert not is_allowed_port(81, parse_allowed_ports("80"))


def test_is_public_ip_recognizes_private_public_and_invalid():
    assert is_public_ip("127.0.0.1") is False
    assert is_public_ip("10.0.0.1") is False
    assert is_public_ip("192.168.1.10") is False
    assert is_public_ip("not.an.ip") is False
    assert is_public_ip("1.1.1.1") is True


def test_proxy_source_is_arkiv_or_central_only():
    assert normalize_proxy_source(None) == "arkiv"
    assert normalize_proxy_source("arkiv") == "arkiv"
    assert normalize_proxy_source("central") == "central"

    with pytest.raises(ValidationError):
        normalize_proxy_source("legacy")


def test_forwarded_query_removes_control_params():
    assert forwarded_query("port=8080&foo=bar&empty=", {"port"}) == "foo=bar&empty="
    assert forwarded_query("target=1.1.1.1%3A80&foo=bar", {"target"}) == "foo=bar"


def test_forwarded_headers_strip_proxy_controls_and_append_client_ip():
    headers = {
        "Host": "proxy.local",
        "X-Proxy-Token": "secret",
        "X-Proxy-Source": "arkiv",
        "X-Forwarded-For": "1.2.3.4",
        "User-Agent": "client",
    }

    forwarded = forwarded_headers(
        headers,
        {"x-proxy-token", "x-proxy-source"},
        "5.6.7.8",
    )

    assert "Host" not in forwarded
    assert "X-Proxy-Token" not in forwarded
    assert forwarded["User-Agent"] == "client"
    assert forwarded["X-Forwarded-For"] == "1.2.3.4, 5.6.7.8"
    assert forwarded["X-Real-IP"] == "5.6.7.8"


def test_settings_use_arkiv_names_only(monkeypatch):
    monkeypatch.setenv("GOLEM_ENVIRONMENT", "development")
    monkeypatch.setenv("ARKIV_RPC_URL", "http://rpc")
    monkeypatch.setenv("ARKIV_WS_URL", "ws://ws")

    settings = Settings()

    assert settings.arkiv_rpc_url == "http://rpc"
    assert settings.arkiv_ws_url == "ws://ws"
    assert settings.expected_network == "development"
    assert settings.effective_allow_local_ips is True
