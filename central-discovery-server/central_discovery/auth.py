from datetime import timedelta

from eth_account import Account
from eth_account.messages import encode_defunct

from central_discovery.domain import ProviderAuthenticateMessage, UnauthorizedError
from central_discovery.time import utc_now

AUTH_TIMESTAMP_TOLERANCE_SECONDS = 300


def provider_auth_message(provider_id: str, nonce: str, timestamp: str) -> str:
    return f"central-discovery-auth:{provider_id}:{nonce}:{timestamp}"


def verify_provider_auth(
    message: ProviderAuthenticateMessage, expected_nonce: str
) -> str:
    if message.nonce != expected_nonce:
        raise UnauthorizedError("provider auth nonce mismatch")

    now = utc_now()
    age = abs(now - message.timestamp)
    if age > timedelta(seconds=AUTH_TIMESTAMP_TOLERANCE_SECONDS):
        raise UnauthorizedError("provider auth timestamp expired")

    signed_text = provider_auth_message(
        message.provider_id,
        message.nonce,
        message.timestamp.isoformat(),
    )
    try:
        recovered = Account.recover_message(
            encode_defunct(text=signed_text), signature=message.signature
        )
    except Exception as exc:
        raise UnauthorizedError("provider auth signature invalid") from exc
    if recovered.lower() != message.provider_id.lower():
        raise UnauthorizedError("provider auth signature mismatch")
    return recovered
