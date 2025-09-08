from pathlib import Path

import pytest

import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))

from requestor.ssh.manager import SSHKeyManager


@pytest.mark.asyncio
async def test_generate_key_pair(tmp_path):
    mgr = SSHKeyManager(tmp_path)
    pair = await mgr.get_key_pair()
    assert pair.private_key.exists()
    assert pair.public_key.exists()


def test_get_key_pair_sync(tmp_path):
    mgr = SSHKeyManager(tmp_path)
    pair = mgr.get_key_pair_sync()
    assert pair.private_key.exists()
    assert pair.public_key.exists()


@pytest.mark.asyncio
async def test_get_public_key_content(tmp_path):
    mgr = SSHKeyManager(tmp_path)
    content = await mgr.get_public_key_content()
    assert "ssh-rsa" in content
