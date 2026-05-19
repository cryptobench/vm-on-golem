import asyncio
import json
import socket
from unittest.mock import AsyncMock

import pytest

from provider.vm import proxy_manager as proxy_module
from provider.vm.proxy_manager import (
    PythonProxyManager,
    SSHProxyProtocol,
    SSHTargetProtocol,
)


class FakePortManager:
    def __init__(self):
        self.verified_ports = {50800}
        self.deallocated = []

    def allocate_port(self, vm_id):
        return 50800

    def deallocate_port(self, vm_id):
        self.deallocated.append(vm_id)

    def get_port(self, vm_id):
        return 50800


class FakeProxyServer:
    def __init__(self, listen_port, target_host, target_port=22, counters=None):
        self.listen_port = listen_port
        self.target_host = target_host
        self.target_port = target_port
        self.counters = counters
        self.server = None

    async def start(self):
        self.server = object()

    async def stop(self):
        self.server = None


class FakeSocket:
    def __init__(self):
        self.options = []

    def setsockopt(self, level, option, value):
        self.options.append((level, option, value))


class FakeTransport:
    def __init__(self):
        self.socket = FakeSocket()

    def get_extra_info(self, name):
        if name == "socket":
            return self.socket
        return None


@pytest.mark.asyncio
async def test_proxy_client_socket_disables_nagle_buffering():
    transport = FakeTransport()
    protocol = SSHProxyProtocol("192.168.2.4", 22, {})

    async def noop_connect():
        return None

    protocol.connect_to_target = noop_connect
    protocol.connection_made(transport)
    await asyncio.sleep(0)

    assert (
        socket.IPPROTO_TCP,
        socket.TCP_NODELAY,
        1,
    ) in transport.socket.options


def test_proxy_target_socket_disables_nagle_buffering():
    transport = FakeTransport()
    client_protocol = SSHProxyProtocol("192.168.2.4", 22, {})
    target_protocol = SSHTargetProtocol(client_protocol)

    target_protocol.connection_made(transport)

    assert (
        socket.IPPROTO_TCP,
        socket.TCP_NODELAY,
        1,
    ) in transport.socket.options


@pytest.mark.asyncio
async def test_initialize_restores_persisted_proxy(tmp_path, monkeypatch):
    monkeypatch.setattr(proxy_module, "ProxyServer", FakeProxyServer)
    state_file = tmp_path / "proxy_state.json"
    state_file.write_text(
        json.dumps(
            {
                "version": 1,
                "proxies": {"vm-ed1d": {"port": 50800, "target": "192.168.2.4"}},
            }
        )
    )
    name_mapper = AsyncMock()
    name_mapper.get_multipass_name = AsyncMock(
        return_value="golem-e518aa54-4744-4e2b-a187-60f271ca50f6"
    )

    manager = PythonProxyManager(
        FakePortManager(),
        name_mapper,
        state_file=str(state_file),
    )

    await manager.initialize()

    assert manager.get_port("golem-e518aa54-4744-4e2b-a187-60f271ca50f6") == 50800


def test_get_port_does_not_expose_stale_port_allocation(tmp_path):
    manager = PythonProxyManager(
        FakePortManager(),
        AsyncMock(),
        state_file=str(tmp_path / "proxy_state.json"),
    )

    assert manager.get_port("golem-e518aa54-4744-4e2b-a187-60f271ca50f6") is None


@pytest.mark.asyncio
async def test_remove_vm_deallocates_stale_proxy_state(tmp_path):
    port_manager = FakePortManager()
    manager = PythonProxyManager(
        port_manager,
        AsyncMock(),
        state_file=str(tmp_path / "proxy_state.json"),
    )
    manager._active_ports["golem-vm"] = 50800

    await manager.remove_vm("golem-vm")

    assert port_manager.deallocated == ["golem-vm"]
    assert manager.get_port("golem-vm") is None
