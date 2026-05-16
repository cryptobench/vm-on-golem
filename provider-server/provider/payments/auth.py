import hashlib
import json
import time
from typing import Any

from eth_account import Account
from eth_account.messages import encode_typed_data
from fastapi import Header, Request

from provider.errors import ValidationError


ACTION_DOMAIN_NAME = "GolemProviderAction"
ACTION_DOMAIN_VERSION = "2"
_seen_nonces: dict[tuple[str, str], int] = {}


async def requestor_action_signer(
    request: Request,
    x_golem_requestor: str | None = Header(default=None),
    x_golem_signature: str | None = Header(default=None),
    x_golem_nonce: str | None = Header(default=None),
    x_golem_deadline: str | None = Header(default=None),
) -> str | None:
    """Recover the requestor signer for a provider VM action.

    Missing headers return None so services can decide whether a signature is
    required for the operation. Malformed or mismatched headers fail closed.
    """

    if not any([x_golem_requestor, x_golem_signature, x_golem_nonce, x_golem_deadline]):
        return None
    if not all([x_golem_requestor, x_golem_signature, x_golem_nonce, x_golem_deadline]):
        raise ValidationError("incomplete requestor action signature headers")

    deadline = int(str(x_golem_deadline))
    now = int(time.time())
    if deadline < now:
        raise ValidationError("requestor action signature expired")

    body = await request.body()
    body_hash = "0x" + hashlib.sha256(body or b"").hexdigest()
    message = {
        "requestor": x_golem_requestor,
        "method": request.method.upper(),
        "path": request.url.path,
        "bodyHash": body_hash,
        "nonce": str(x_golem_nonce),
        "deadline": deadline,
    }
    signable = encode_typed_data(
        domain_data={
            "name": ACTION_DOMAIN_NAME,
            "version": ACTION_DOMAIN_VERSION,
        },
        message_types={
            "ProviderAction": [
                {"name": "requestor", "type": "address"},
                {"name": "method", "type": "string"},
                {"name": "path", "type": "string"},
                {"name": "bodyHash", "type": "bytes32"},
                {"name": "nonce", "type": "string"},
                {"name": "deadline", "type": "uint256"},
            ]
        },
        message_data=message,
    )
    recovered = Account.recover_message(signable, signature=str(x_golem_signature))
    if recovered.lower() != str(x_golem_requestor).lower():
        raise ValidationError("requestor action signature mismatch")
    _purge_expired_nonces(now)
    nonce_key = (recovered.lower(), str(x_golem_nonce))
    if nonce_key in _seen_nonces:
        raise ValidationError("requestor action signature nonce already used")
    _seen_nonces[nonce_key] = deadline
    return recovered


def canonical_body_hash(body: dict[str, Any]) -> str:
    payload = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return "0x" + hashlib.sha256(payload).hexdigest()


def _purge_expired_nonces(now: int) -> None:
    for key, deadline in list(_seen_nonces.items()):
        if deadline < now:
            del _seen_nonces[key]
