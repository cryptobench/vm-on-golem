from eth_account import Account

from requestor.config import RequestorConfig
from requestor.errors import ExternalServiceError, ValidationError
from requestor.security.faucet import L2FaucetService

from .domain import FaucetResult


class WalletService:
    def __init__(self, settings: RequestorConfig):
        self.settings = settings

    async def request_faucet_funds(self) -> FaucetResult:
        if not self.settings.faucet_enabled:
            raise ValidationError("Faucet is not enabled for this payments network")
        account = Account.from_key(self.settings.ethereum_private_key)
        try:
            result = await L2FaucetService(self.settings).request_funds(account.address)
        except Exception as exc:
            raise ExternalServiceError(f"faucet request failed: {exc}") from exc
        tx_hash = result.get("tx_hash") if isinstance(result, dict) else None
        return FaucetResult(
            address=account.address,
            status="requested",
            transaction_hash=tx_hash,
        )
