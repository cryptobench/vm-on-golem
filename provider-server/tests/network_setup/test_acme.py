import base64
import json

import pytest
from aiohttp import web

import provider.network_setup.acme as acme_module
from provider.network_setup.acme import (
    ACME_JWS_CONTENT_TYPE,
    PEM_CERTIFICATE_CHAIN_CONTENT_TYPE,
    AcmeRequestError,
    NativeAcmeClient,
)


class FakeChallengeServer:
    def __init__(self):
        self.tokens = {}

    def set_token(self, token: str, key_authorization: str) -> None:
        self.tokens[token] = key_authorization


def _decode_b64url(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))


def _decode_payload(jws: dict) -> dict | None:
    if jws["payload"] == "":
        return None
    return json.loads(_decode_b64url(jws["payload"]))


async def _start_fake_acme_server(profiles: dict[str, str] | None = None):
    app = web.Application()
    records = []
    challenge_acked = False
    nonce_counter = 0

    async def directory(request):
        base_url = f"{request.scheme}://{request.host}"
        return web.json_response(
            {
                "newNonce": f"{base_url}/new-nonce",
                "newAccount": f"{base_url}/new-account",
                "newOrder": f"{base_url}/new-order",
                "meta": {"profiles": profiles or {"shortlived": "test profile"}},
            }
        )

    async def new_nonce(_request):
        nonlocal nonce_counter
        nonce_counter += 1
        return web.Response(headers={"Replay-Nonce": f"nonce-{nonce_counter}"})

    async def signed(request):
        nonlocal challenge_acked
        if request.content_type != ACME_JWS_CONTENT_TYPE:
            return web.json_response(
                {"detail": f"bad content type {request.content_type}"},
                status=400,
            )
        if request.path == "/certificate/1":
            accept = request.headers.get("Accept")
            if accept != PEM_CERTIFICATE_CHAIN_CONTENT_TYPE:
                return web.json_response(
                    {"detail": f"bad accept {accept}"},
                    status=406,
                )
        body = await request.json()
        payload = _decode_payload(body)
        records.append(
            {
                "path": request.path,
                "content_type": request.content_type,
                "accept": request.headers.get("Accept"),
                "payload": payload,
                "jws_payload": body["payload"],
            }
        )
        base_url = f"{request.scheme}://{request.host}"

        if request.path == "/new-account":
            return web.json_response(
                {"status": "valid"},
                headers={"Location": f"{base_url}/account/1"},
            )
        if request.path == "/new-order":
            return web.json_response(
                {
                    "status": "pending",
                    "authorizations": [f"{base_url}/authz/1"],
                    "finalize": f"{base_url}/finalize/1",
                },
                headers={"Location": f"{base_url}/order/1"},
            )
        if request.path == "/authz/1":
            status = "valid" if challenge_acked else "pending"
            return web.json_response(
                {
                    "status": status,
                    "challenges": [
                        {
                            "type": "http-01",
                            "url": f"{base_url}/challenge/1",
                            "token": "token-1",
                        }
                    ],
                }
            )
        if request.path == "/challenge/1":
            challenge_acked = True
            return web.json_response({"status": "processing"})
        if request.path == "/finalize/1":
            return web.json_response({"status": "processing"})
        if request.path == "/order/1":
            return web.json_response(
                {"status": "valid", "certificate": f"{base_url}/certificate/1"}
            )
        if request.path == "/certificate/1":
            return web.Response(
                text=(
                    "-----BEGIN CERTIFICATE-----\n"
                    "MIIBfake\n"
                    "-----END CERTIFICATE-----\n"
                ),
                content_type=PEM_CERTIFICATE_CHAIN_CONTENT_TYPE,
            )
        return web.Response(status=404)

    app.router.add_get("/directory", directory)
    app.router.add_head("/new-nonce", new_nonce)
    for path in (
        "/new-account",
        "/new-order",
        "/authz/1",
        "/challenge/1",
        "/finalize/1",
        "/order/1",
        "/certificate/1",
    ):
        app.router.add_post(path, signed)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    sockets = site._server.sockets
    assert sockets
    port = sockets[0].getsockname()[1]
    return runner, f"http://127.0.0.1:{port}/directory", records


@pytest.mark.asyncio
async def test_native_acme_client_sends_rfc8555_signed_posts(tmp_path, monkeypatch):
    async def fast_sleep(_seconds):
        return None

    monkeypatch.setattr(acme_module.asyncio, "sleep", fast_sleep)
    runner, directory_url, records = await _start_fake_acme_server()
    client = NativeAcmeClient(
        directory_url=directory_url,
        account_key_path=tmp_path / "acme-account.key",
        cert_key_path=tmp_path / "provider-ip.key",
        certificate_path=tmp_path / "provider-ip.crt",
        profile="shortlived",
    )
    challenge_server = FakeChallengeServer()

    try:
        await client.issue_ip_certificate("127.0.0.1", challenge_server)
    finally:
        await runner.cleanup()

    assert [record["path"] for record in records] == [
        "/new-account",
        "/new-order",
        "/authz/1",
        "/challenge/1",
        "/authz/1",
        "/finalize/1",
        "/order/1",
        "/certificate/1",
    ]
    assert all(record["content_type"] == ACME_JWS_CONTENT_TYPE for record in records)
    assert records[1]["payload"] == {
        "identifiers": [{"type": "ip", "value": "127.0.0.1"}],
        "profile": "shortlived",
    }
    assert records[2]["payload"] is None
    assert records[2]["jws_payload"] == ""
    assert records[7]["accept"] == PEM_CERTIFICATE_CHAIN_CONTENT_TYPE
    assert "token-1" in challenge_server.tokens
    assert (
        (tmp_path / "provider-ip.crt")
        .read_text()
        .startswith("-----BEGIN CERTIFICATE-----")
    )


@pytest.mark.asyncio
async def test_native_acme_client_rejects_unadvertised_profile(tmp_path):
    runner, directory_url, _records = await _start_fake_acme_server(
        profiles={"classic": "classic profile"}
    )
    client = NativeAcmeClient(
        directory_url=directory_url,
        account_key_path=tmp_path / "acme-account.key",
        cert_key_path=tmp_path / "provider-ip.key",
        certificate_path=tmp_path / "provider-ip.crt",
        profile="shortlived",
    )

    try:
        with pytest.raises(AcmeRequestError, match="shortlived"):
            await client.issue_ip_certificate("127.0.0.1", FakeChallengeServer())
    finally:
        await runner.cleanup()
