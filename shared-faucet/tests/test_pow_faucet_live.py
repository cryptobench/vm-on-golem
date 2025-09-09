import os
import pytest

from golem_faucet import PowFaucetClient


CAPTCHA_BASE = os.getenv("CAPTCHA_BASE", "https://cap.gobas.me")
CAPTCHA_KEY = os.getenv("CAPTCHA_API_KEY", "05381a2cef5e")
L2_FAUCET = os.getenv("L2_FAUCET_URL", "https://l2.holesky.golemdb.io/faucet")


@pytest.mark.asyncio
async def test_live_challenge_and_redeem():
    pf = PowFaucetClient(L2_FAUCET, CAPTCHA_BASE, CAPTCHA_KEY)
    chall = await pf.get_challenge()
    if not chall:
        pytest.skip("challenge endpoint unavailable")
    token = chall.get("token")
    challenges = chall.get("challenge") or []
    assert token and isinstance(challenges, list)
    # Solve full challenge set
    sols = [(salt, target, PowFaucetClient.solve_challenge(salt, target)) for salt, target in challenges]
    redeemed = await pf.redeem(token, sols)
    assert redeemed, "expected a redeemed token"


@pytest.mark.asyncio
async def test_live_request_funds_optional():
    addr = os.getenv("L2_FAUCET_TEST_ADDRESS")
    if not addr or not os.getenv("RUN_LIVE_FAUCET_PAYOUT"):
        pytest.skip("Set L2_FAUCET_TEST_ADDRESS and RUN_LIVE_FAUCET_PAYOUT=1 to run")
    pf = PowFaucetClient(L2_FAUCET, CAPTCHA_BASE, CAPTCHA_KEY)
    chall = await pf.get_challenge()
    assert chall and chall.get("challenge")
    sols = []
    for salt, target in chall["challenge"]:
        sols.append((salt, target, PowFaucetClient.solve_challenge(salt, target)))
    redeemed = await pf.redeem(chall["token"], sols)
    assert redeemed
    tx = await pf.request_funds(addr, redeemed)
    assert tx, "expected faucet to return a tx hash"
