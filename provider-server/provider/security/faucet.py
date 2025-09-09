import asyncio
from typing import Optional, List, Tuple

from golem_base_sdk import GolemBaseClient
from provider.utils.logging import setup_logger
from golem_faucet import PowFaucetClient

logger = setup_logger(__name__)


class FaucetClient:
    """A client for interacting with a Proof of Work-protected faucet."""

    def __init__(self, faucet_url: str, captcha_url: str, captcha_api_key: str):
        self.faucet_url = faucet_url.rstrip("/")
        self.captcha_url = captcha_url.rstrip("/")
        self.captcha_api_key = captcha_api_key
        self.api_endpoint = f"{self.faucet_url}/api"
        self.client: Optional[GolemBaseClient] = None
        self._pow = PowFaucetClient(self.faucet_url, self.captcha_url, self.captcha_api_key)

    async def _ensure_client(self):
        if not self.client:
            from ..config import settings
            private_key_hex = settings.ETHEREUM_PRIVATE_KEY.replace("0x", "")
            private_key_bytes = bytes.fromhex(private_key_hex)
            self.client = await GolemBaseClient.create_ro_client(
                rpc_url=settings.GOLEM_BASE_RPC_URL,
                ws_url=settings.GOLEM_BASE_WS_URL,
            )

    async def check_balance(self, address: str) -> Optional[float]:
        """Check the balance of the given address."""
        await self._ensure_client()
        try:
            balance_wei = await self.client.http_client().eth.get_balance(address)
            balance_eth = self.client.http_client().from_wei(balance_wei, 'ether')
            return float(balance_eth)
        except Exception as e:
            logger.error(f"Failed to check balance: {e}")
            return None

    async def get_funds(self, address: str) -> Optional[str]:
        """Request funds from the faucet for the given address."""
        try:
            balance = await self.check_balance(address)
            if balance is not None and balance > 0.01:
                logger.info(f"Sufficient funds ({balance} ETH), skipping faucet request.")
                return None

            logger.info("Requesting funds from faucet...")
            challenge_data = await self._get_challenge()
            if not challenge_data:
                return None

            challenge_list = challenge_data.get("challenge")
            token = challenge_data.get("token")

            if not challenge_list or not token:
                logger.error(f"Invalid challenge data received: {challenge_data}")
                return None

            solutions = []
            for salt, target in challenge_list:
                nonce = self._solve_challenge(salt, target)
                solutions.append([salt, target, nonce])

            redeemed_token = await self._redeem_solution(token, solutions)
            if not redeemed_token:
                return None

            tx_hash = await self._request_faucet(address, redeemed_token)
            if tx_hash:
                logger.success(f"Successfully requested funds. Transaction hash: {tx_hash}")
            return tx_hash
        except Exception as e:
            import traceback
            logger.error(f"Failed to get funds from faucet: {e}")
            logger.error(traceback.format_exc())
            return None

    async def _get_challenge(self) -> Optional[dict]:
        """Get a PoW challenge from the faucet."""
        try:
            return await self._pow.get_challenge()
        except Exception as e:
            logger.error(f"Failed to get PoW challenge: {e}")
            return None

    def _solve_challenge(self, salt: str, target: str) -> int:
        """Solve the PoW challenge."""
        return PowFaucetClient.solve_challenge(salt, target)

    async def _redeem_solution(self, token: str, solutions: list) -> Optional[str]:
        """Redeem the PoW solution to get a CAPTCHA token."""
        try:
            return await self._pow.redeem(token, solutions)
        except Exception as e:
            logger.error(f"Failed to redeem PoW solution: {e}")
            return None

    async def _request_faucet(self, address: str, token: str) -> Optional[str]:
        """Request funds from the faucet with the CAPTCHA token."""
        try:
            return await self._pow.request_funds(address, token)
        except Exception as e:
            logger.error(f"Faucet request failed: {e}")
            return None
