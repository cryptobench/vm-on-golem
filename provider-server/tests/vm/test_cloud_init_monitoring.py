from pathlib import Path

import yaml

from provider.vm.cloud_init import cleanup_cloud_init, generate_cloud_init
from provider.vm.models import MULTIPASS_SSH_USER


def test_cloud_init_installs_push_only_monitoring_agent():
    path, config_id = generate_cloud_init(
        hostname="test-vm",
        ssh_key="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITestKeyForCloudInitOnly",
        monitoring_vm_id="test-vm",
        monitoring_token="token-123",
    )
    try:
        content = Path(path).read_text()
        config = yaml.safe_load(content)
        agent_file = next(
            item
            for item in config["write_files"]
            if item["path"] == "/usr/local/bin/golem-metrics-agent"
        )
        agent_content = agent_file["content"]

        assert "/usr/local/bin/golem-metrics-agent" in content
        assert "golem-metrics-agent.service" in content
        assert "token-123" in content
        assert "urllib.request" in agent_content
        assert '"agent_ready": True' in agent_content
        assert '"sshd_ready": _sshd_ready()' in agent_content
        assert '"hardening_applied": _hardening_applied()' in agent_content
        assert "AllowUsers {REQUESTOR_SSH_USER}" in agent_content
        assert "multipass exec" not in content
        assert "ssh " not in agent_content
        assert "except Exception as exc:" in agent_content
        assert "failed to publish sample" in agent_content
        assert "endpoint unavailable" in agent_content
        assert "except Exception:\n        pass" not in agent_content
    finally:
        cleanup_cloud_init(path, config_id)


def test_cloud_init_grants_requestor_only_ssh_with_passwordless_sudo():
    ssh_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITestKeyForCloudInitOnly"
    path, config_id = generate_cloud_init(hostname="test-vm", ssh_key=ssh_key)
    try:
        content = Path(path).read_text()
        config = yaml.safe_load(content)
        users = config["users"]
        requestor_user = users[0]

        assert "ssh_authorized_keys" not in config
        assert config["ssh_pwauth"] is False
        assert config["disable_root"] is True
        assert len(users) == 1
        assert requestor_user == {
            "name": MULTIPASS_SSH_USER,
            "gecos": "Golem Requestor",
            "groups": ["adm", "sudo"],
            "shell": "/bin/bash",
            "sudo": "ALL=(ALL) NOPASSWD:ALL",
            "lock_passwd": True,
            "ssh_authorized_keys": [ssh_key],
        }
        assert {"name": "root", "ssh_authorized_keys": [ssh_key]} not in users
        assert {"name": "ubuntu", "ssh_authorized_keys": [ssh_key]} not in users
    finally:
        cleanup_cloud_init(path, config_id)


def test_cloud_init_disables_password_and_root_ssh_login():
    ssh_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITestKeyForCloudInitOnly"
    path, config_id = generate_cloud_init(hostname="test-vm", ssh_key=ssh_key)
    try:
        config = yaml.safe_load(Path(path).read_text())
        hardening_file = next(
            item
            for item in config["write_files"]
            if item["path"] == "/etc/ssh/sshd_config.d/99-golem-requestor-only.conf"
        )
        sshd_config = hardening_file["content"]

        assert hardening_file["owner"] == "root:root"
        assert hardening_file["permissions"] == "0644"
        assert "PasswordAuthentication no" in sshd_config
        assert "KbdInteractiveAuthentication no" in sshd_config
        assert "ChallengeResponseAuthentication no" in sshd_config
        assert "PermitRootLogin no" in sshd_config
        assert "DenyUsers ubuntu" in sshd_config
        assert "PubkeyAuthentication yes" in sshd_config
        assert "AuthenticationMethods publickey" in sshd_config
        assert f"AllowUsers {MULTIPASS_SSH_USER}" in sshd_config
        assert "AllowUsers ubuntu" not in sshd_config
        assert (
            "if id ubuntu >/dev/null 2>&1; then passwd -l ubuntu && "
            "usermod --shell /usr/sbin/nologin ubuntu && "
            "rm -rf /home/ubuntu/.ssh; fi"
        ) in config["runcmd"]
        assert "systemctl restart ssh || systemctl restart sshd" in config["runcmd"]
    finally:
        cleanup_cloud_init(path, config_id)
