import asyncio
import hashlib
import httpx
from typing import Optional

from golem_base_sdk import GolemBaseClient
from provider.utils.logging import setup_logger

logger = setup_logger(__name__)


class FaucetClient:
    """A client for interacting with a Proof of Work-protected faucet."""

    def __init__(self, faucet_url: str, captcha_url: str, captcha_api_key: str):
        self.faucet_url = faucet_url
        self.captcha_url = captcha_url
        self.captcha_api_key = captcha_api_key
        self.api_endpoint = f"{faucet_url}/api"
        self.client: Optional[GolemBaseClient] = None

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
            async with httpx.AsyncClient(timeout=60.0) as client:
                url = f"{self.captcha_url}/{self.captcha_api_key}/api/challenge"
                response = await client.post(url)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to get PoW challenge: {e.response.text}")
            return None

    def _solve_challenge(self, salt: str, target: str) -> int:
        """Solve the PoW challenge."""
        target_hash = bytes.fromhex(target)
        nonce = 0
        while True:
            hasher = hashlib.sha256()
            hasher.update(f"{salt}{nonce}".encode())
            if hasher.digest().startswith(target_hash):
                return nonce
            nonce += 1

    async def _redeem_solution(self, token: str, solutions: list) -> Optional[str]:
        """Redeem the PoW solution to get a CAPTCHA token."""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                url = f"{self.captcha_url}/{self.captcha_api_key}/api/redeem"
                response = await client.post(
                    url,
                    json={"token": token, "solutions": solutions}
                )
                response.raise_for_status()
                return response.json().get("token")
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to redeem PoW solution: {e.response.text}")
            return None

    async def _request_faucet(self, address: str, token: str) -> Optional[str]:
        """Request funds from the faucet with the CAPTCHA token."""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.api_endpoint}/faucet",
                    json={"address": address, "captchaToken": token}
                )
                response.raise_for_status()
                return response.json().get("txHash")
        except httpx.HTTPStatusError as e:
            logger.error(f"Faucet request failed: {e.response.text}")
            return None