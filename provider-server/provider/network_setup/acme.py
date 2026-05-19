import asyncio
import base64
import hashlib
import json
import time
from pathlib import Path
from typing import Any

import aiohttp
from aiohttp import web
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from .certs import build_ip_csr, load_or_create_rsa_key

ACME_JWS_CONTENT_TYPE = "application/jose+json"
PEM_CERTIFICATE_CHAIN_CONTENT_TYPE = "application/pem-certificate-chain"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


class AcmeRequestError(RuntimeError):
    """Raised when the ACME server rejects a protocol or account request."""


class Http01ChallengeServer:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self._tokens: dict[str, str] = {}
        self._runner: web.AppRunner | None = None

    def set_token(self, token: str, key_authorization: str) -> None:
        self._tokens[token] = key_authorization

    async def start(self) -> None:
        app = web.Application()
        app.router.add_get(
            "/.well-known/acme-challenge/{token}", self._handle_challenge
        )
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()

    async def stop(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None

    async def _handle_challenge(self, request: web.Request) -> web.Response:
        token = request.match_info["token"]
        value = self._tokens.get(token)
        if value is None:
            return web.Response(status=404)
        return web.Response(text=value, content_type="text/plain")


class NativeAcmeClient:
    """Small ACME v2 client for Let's Encrypt IP HTTP-01 certificates."""

    def __init__(
        self,
        directory_url: str,
        account_key_path: Path,
        cert_key_path: Path,
        certificate_path: Path,
        email: str = "",
        profile: str = "shortlived",
        session: aiohttp.ClientSession | None = None,
    ):
        self.directory_url = directory_url
        self.account_key_path = account_key_path
        self.cert_key_path = cert_key_path
        self.certificate_path = certificate_path
        self.email = email
        self.profile = profile
        self.session = session
        self.account_key: rsa.RSAPrivateKey | None = None
        self.cert_key: rsa.RSAPrivateKey | None = None
        self.directory: dict[str, Any] = {}
        self.kid: str | None = None

    async def issue_ip_certificate(
        self,
        ip_address: str,
        challenge_server: Http01ChallengeServer,
    ) -> None:
        owns_session = self.session is None
        session = self.session or aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        )
        try:
            self.session = session
            self.account_key = load_or_create_rsa_key(self.account_key_path)
            self.cert_key = load_or_create_rsa_key(self.cert_key_path)
            self.directory = await self._get_json(self.directory_url)
            self._ensure_profile_available()
            await self._new_account()
            order = await self._new_order(ip_address)
            await self._complete_authorization(
                order["authorizations"][0], challenge_server
            )
            csr_der = build_ip_csr(self.cert_key, ip_address)
            finalized = await self._post(order["finalize"], {"csr": _b64url(csr_der)})
            order = await self._poll_order(
                finalized.get("order_url") or order["order_url"]
            )
            pem = await self._post_as_get_text(order["certificate"])
            self.certificate_path.parent.mkdir(parents=True, exist_ok=True)
            self.certificate_path.write_text(pem)
            self.certificate_path.chmod(0o644)
        finally:
            if owns_session:
                await session.close()
                self.session = None

    async def _get_json(self, url: str) -> dict[str, Any]:
        assert self.session is not None
        async with self.session.get(url) as response:
            response.raise_for_status()
            return await response.json()

    async def _new_account(self) -> None:
        payload: dict[str, Any] = {"termsOfServiceAgreed": True}
        if self.email:
            payload["contact"] = [f"mailto:{self.email}"]
        response = await self._post(
            self.directory["newAccount"],
            payload,
            use_jwk=True,
        )
        self.kid = response["kid"]

    async def _new_order(self, ip_address: str) -> dict[str, Any]:
        payload: dict[str, Any] = {"identifiers": [{"type": "ip", "value": ip_address}]}
        if self.profile:
            payload["profile"] = self.profile
        response = await self._post(self.directory["newOrder"], payload)
        response["order_url"] = response["url"]
        return response

    async def _complete_authorization(
        self,
        authorization_url: str,
        challenge_server: Http01ChallengeServer,
    ) -> None:
        authz = await self._post_as_get(authorization_url)
        challenge = next(
            (
                item
                for item in authz.get("challenges", [])
                if item.get("type") == "http-01"
            ),
            None,
        )
        if challenge is None:
            raise RuntimeError("ACME server did not offer HTTP-01 for IP certificate")
        token = challenge["token"]
        challenge_server.set_token(token, f"{token}.{self._jwk_thumbprint()}")
        await self._post(challenge["url"], {})
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            await asyncio.sleep(2)
            authz = await self._post_as_get(authorization_url)
            status = authz.get("status")
            if status == "valid":
                return
            if status == "invalid":
                raise RuntimeError(f"ACME authorization failed: {authz}")
        raise RuntimeError("Timed out waiting for ACME authorization")

    async def _poll_order(self, order_url: str) -> dict[str, Any]:
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            order = await self._post_as_get(order_url)
            if order.get("status") == "valid" and order.get("certificate"):
                return order
            if order.get("status") == "invalid":
                raise RuntimeError(f"ACME order failed: {order}")
            await asyncio.sleep(2)
        raise RuntimeError("Timed out waiting for ACME certificate")

    async def _post_as_get(self, url: str) -> dict[str, Any]:
        return await self._post(url, None)

    async def _post_as_get_text(self, url: str) -> str:
        _headers, text = await self._post_jws(
            url,
            None,
            accept=PEM_CERTIFICATE_CHAIN_CONTENT_TYPE,
        )
        return text

    async def _post(
        self,
        url: str,
        payload: dict[str, Any] | None,
        use_jwk: bool = False,
    ) -> dict[str, Any]:
        headers, text = await self._post_jws(url, payload, use_jwk=use_jwk)
        data = json.loads(text) if text else {}
        if headers.get("Location"):
            data["url"] = headers["Location"]
        if use_jwk and headers.get("Location"):
            data["kid"] = headers["Location"]
        return data

    async def _post_jws(
        self,
        url: str,
        payload: dict[str, Any] | None,
        use_jwk: bool = False,
        accept: str | None = None,
    ) -> tuple[dict[str, str], str]:
        assert self.session is not None
        body = await self._jws(url, payload, use_jwk=use_jwk)
        headers = {"Content-Type": ACME_JWS_CONTENT_TYPE}
        if accept:
            headers["Accept"] = accept
        async with self.session.post(
            url,
            data=json.dumps(body, separators=(",", ":")).encode("utf-8"),
            headers=headers,
        ) as response:
            text = await response.text()
            if response.status >= 400:
                raise AcmeRequestError(f"ACME request failed {response.status}: {text}")
            return dict(response.headers), text

    async def _jws(
        self,
        url: str,
        payload: dict[str, Any] | None,
        use_jwk: bool = False,
    ) -> dict[str, str]:
        assert self.account_key is not None
        protected: dict[str, Any] = {
            "alg": "RS256",
            "nonce": await self._nonce(),
            "url": url,
        }
        if use_jwk:
            protected["jwk"] = self._jwk()
        else:
            if not self.kid:
                raise RuntimeError("ACME account is not initialized")
            protected["kid"] = self.kid
        protected64 = _b64url(
            json.dumps(protected, separators=(",", ":")).encode("utf-8")
        )
        payload64 = (
            ""
            if payload is None
            else _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        )
        signing_input = f"{protected64}.{payload64}".encode("ascii")
        signature = self.account_key.sign(
            signing_input,
            padding.PKCS1v15(),
            self._hash_algorithm(),
        )
        return {
            "protected": protected64,
            "payload": payload64,
            "signature": _b64url(signature),
        }

    async def _nonce(self) -> str:
        assert self.session is not None
        async with self.session.head(self.directory["newNonce"]) as response:
            response.raise_for_status()
            nonce = response.headers.get("Replay-Nonce")
            if not nonce:
                raise RuntimeError("ACME server did not return a nonce")
            return nonce

    def _jwk(self) -> dict[str, str]:
        assert self.account_key is not None
        numbers = self.account_key.public_key().public_numbers()
        return {
            "kty": "RSA",
            "n": _b64url(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")),
            "e": _b64url(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")),
        }

    def _jwk_thumbprint(self) -> str:
        jwk = self._jwk()
        canonical = json.dumps(
            {"e": jwk["e"], "kty": jwk["kty"], "n": jwk["n"]},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return _b64url(hashlib.sha256(canonical).digest())

    def _ensure_profile_available(self) -> None:
        if not self.profile:
            return
        profiles = self.directory.get("meta", {}).get("profiles")
        if not isinstance(profiles, dict):
            return
        if self.profile in profiles:
            return
        available = ", ".join(sorted(str(profile) for profile in profiles))
        raise AcmeRequestError(
            f"Configured ACME profile '{self.profile}' is not advertised by "
            f"the ACME directory. Available profiles: {available or 'none'}."
        )

    @staticmethod
    def _hash_algorithm():
        from cryptography.hazmat.primitives import hashes

        return hashes.SHA256()
