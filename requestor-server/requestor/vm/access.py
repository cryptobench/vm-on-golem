from collections.abc import Mapping
from typing import Any

from requestor.errors import VMError


def require_ssh_user(access_info: Mapping[str, Any]) -> str:
    """Return provider-reported SSH user or fail without guessing."""
    ssh_user = access_info.get("ssh_user")
    if not isinstance(ssh_user, str) or not ssh_user.strip():
        raise VMError("Provider did not return SSH login user for VM access")
    return ssh_user
