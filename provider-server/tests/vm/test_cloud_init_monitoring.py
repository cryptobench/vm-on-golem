from pathlib import Path

from provider.vm.cloud_init import cleanup_cloud_init, generate_cloud_init


def test_cloud_init_installs_push_only_monitoring_agent():
    path, config_id = generate_cloud_init(
        hostname="test-vm",
        ssh_key="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITestKeyForCloudInitOnly",
        monitoring_vm_id="test-vm",
        monitoring_token="token-123",
    )
    try:
        content = Path(path).read_text()
        assert "/usr/local/bin/golem-metrics-agent" in content
        assert "golem-metrics-agent.service" in content
        assert "token-123" in content
        assert "urllib.request" in content
        assert "multipass exec" not in content
        assert "ssh " not in content
    finally:
        cleanup_cloud_init(path, config_id)
