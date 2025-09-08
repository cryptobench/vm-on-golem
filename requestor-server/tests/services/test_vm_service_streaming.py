import types
import pytest

from requestor.services.vm_service import VMService


class DummyDB:
    def __init__(self):
        self.vms = {}
    async def get_vm(self, name):
        return self.vms.get(name)
    async def save_vm(self, name, provider_ip, vm_id, config, status='running'):
        self.vms[name] = {
            'name': name,
            'provider_ip': provider_ip,
            'vm_id': vm_id,
            'config': config,
            'status': status,
            'created_at': 'now',
        }
    async def update_vm_status(self, name, status):
        self.vms[name]['status'] = status
    async def delete_vm(self, name):
        self.vms.pop(name, None)


class DummySSH:
    def get_key_pair_sync(self):
        return types.SimpleNamespace(private_key=types.SimpleNamespace(absolute=lambda: "/dev/null"))
    async def get_key_pair(self):
        return types.SimpleNamespace(private_key="/dev/null")


class DummyProvider:
    async def create_vm(self, **kwargs):
        return {'id': 'vm-1'}
    async def get_vm_access(self, vm_id):
        return {'vm_id': vm_id, 'ssh_port': 2222}
    async def destroy_vm(self, vm_id):
        return None
    async def stop_vm(self, vm_id):
        return None


class DummyChain:
    def __init__(self):
        self.created = []
        self.withdrawn = []
        self.terminated = []
    def create_stream(self, provider, deposit, rate):
        self.created.append((provider, deposit, rate))
        return 42
    def withdraw(self, sid):
        self.withdrawn.append(sid)
    def terminate(self, sid):
        self.terminated.append(sid)


@pytest.mark.asyncio
async def test_create_vm_stores_stream_id(monkeypatch):
    # Force config values for streaming
    from requestor import config as cfgmod
    cfgmod.config.stream_payment_address = "0x1111111111111111111111111111111111111111"
    cfgmod.config.glm_token_address = "0x2222222222222222222222222222222222222222"
    cfgmod.config.provider_eth_address = "0x3333333333333333333333333333333333333333"

    db = DummyDB()
    chain = DummyChain()
    svc = VMService(db, DummySSH(), DummyProvider(), blockchain_client=chain)

    vm = await svc.create_vm("n", 1, 1, 1, "127.0.0.1", "ssh-key")
    assert vm['config']['stream_id'] == 42

    # stop should withdraw
    await svc.stop_vm("n")
    assert chain.withdrawn == [42]

    # destroy should terminate
    await svc.destroy_vm("n")
    assert chain.terminated == [42]

