from __future__ import annotations

from typing import Optional, List, Tuple

from web3 import Web3
from golem_faucet import PowFaucetClient
from ..utils.logging import setup_logger

logger = setup_logger(__name__)


class L2FaucetService:
    """Request native ETH on the L2 payments chain via PoW faucet.

    Uses provider settings for RPC and faucet endpoints.
    """

    def __init__(self, config):
        # Config is expected to expose POLYGON_RPC_URL, L2_* faucet fields
        self.cfg = config
        self.web3 = Web3(Web3.HTTPProvider(config.POLYGON_RPC_URL))
        self.client = PowFaucetClient(
            faucet_url=getattr(config, "L2_FAUCET_URL", "https://l2.holesky.golemdb.io/faucet"),
            captcha_base_url=getattr(config, "L2_CAPTCHA_URL", "https://cap.gobas.me"),
            captcha_api_key=getattr(config, "L2_CAPTCHA_API_KEY", "05381a2cef5e"),
        )

    def _balance_eth(self, address: str) -> float:
        try:
            wei = self.web3.eth.get_balance(Web3.to_checksum_address(address))
            return float(self.web3.from_wei(wei, "ether"))
        except Exception as e:
            logger.warning(f"L2 balance check failed: {e}")
            return 0.0

    async def request_funds(self, address: str) -> Optional[str]:
        """Ensure some native ETH on L2; if low, solve PoW and request faucet payout.

        Returns tx hash string on payout, or None if skipped/failed.
        """
        # Respect profile gating only if explicitly present and false
        if hasattr(self.cfg, "FAUCET_ENABLED") and not bool(getattr(self.cfg, "FAUCET_ENABLED")):
            logger.info("Faucet disabled for current payments network; skipping.")
            return None
        bal = self._balance_eth(address)
        if bal > 0.01:
            logger.info(f"Sufficient L2 funds ({bal} ETH), skipping faucet.")
            return None
        chall = await self.client.get_challenge()
        if not chall:
            logger.error("could not fetch faucet challenge")
            return None
        token = chall.get("token")
        challenge_list = chall.get("challenge") or []
        solutions: List[Tuple[str, str, int]] = []
        for salt, target in challenge_list:
            nonce = PowFaucetClient.solve_challenge(salt, target)
            solutions.append((salt, target, nonce))
        redeemed = await self.client.redeem(token, solutions)
        if not redeemed:
            logger.error("failed to redeem challenge")
            return None
        tx = await self.client.request_funds(address, redeemed)
        if tx:
            logger.success(f"L2 faucet sent tx: {tx}")
        return tx
