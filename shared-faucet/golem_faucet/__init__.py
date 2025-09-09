from __future__ import annotations

import hashlib
from typing import Optional, List, Tuple

import httpx


class PowFaucetClient:
    def __init__(self, faucet_url: str, captcha_base_url: str, captcha_api_key: str, timeout: float = 60.0):
        self.faucet_url = faucet_url.rstrip("/")
        self.captcha_base_url = captcha_base_url.rstrip("/")
        self.captcha_api_key = captcha_api_key
        self.timeout = timeout

    async def get_challenge(self) -> Optional[dict]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                url = f"{self.captcha_base_url}/{self.captcha_api_key}/api/challenge"
                r = await client.post(url)
                r.raise_for_status()
                return r.json()
        except Exception:
            return None

    @staticmethod
    def solve_challenge(salt: str, target: str) -> int:
        target_bytes = bytes.fromhex(target)
        nonce = 0
        while True:
            hasher = hashlib.sha256()
            hasher.update(f"{salt}{nonce}".encode())
            if hasher.digest().startswith(target_bytes):
                return nonce
            nonce += 1

    async def redeem(self, token: str, solutions: List[Tuple[str, str, int]]) -> Optional[str]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                url = f"{self.captcha_base_url}/{self.captcha_api_key}/api/redeem"
                r = await client.post(url, json={"token": token, "solutions": solutions})
                r.raise_for_status()
                return r.json().get("token")
        except Exception:
            return None

    async def request_funds(self, address: str, captcha_token: str) -> Optional[str]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                url = f"{self.faucet_url}/api/faucet"
                r = await client.post(url, json={"address": address, "captchaToken": captcha_token})
                r.raise_for_status()
                data = r.json()
                return data.get("txHash") or data.get("tx") or data.get("hash")
        except Exception:
            return None
