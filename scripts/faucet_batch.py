#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import os
import sys
from typing import Optional, List, Tuple
import concurrent.futures

try:
    # Provided by shared-faucet package installed via Poetry
    from golem_faucet import PowFaucetClient
except Exception as e:
    print("error: missing dependency golem_faucet. Run 'make install' first.")
    sys.exit(2)


async def _solve_single(executor: concurrent.futures.ProcessPoolExecutor, salt: str, target: str) -> Tuple[str, str, int]:
    loop = asyncio.get_running_loop()
    # Use a process pool to bypass the GIL and fully utilize CPU cores
    nonce = await loop.run_in_executor(executor, PowFaucetClient.solve_challenge, salt, target)
    return (salt, target, nonce)


async def run_once(client: PowFaucetClient, address: str, executor: concurrent.futures.ProcessPoolExecutor) -> Optional[str]:
    chall = await client.get_challenge()
    if not chall or not chall.get("challenge") or not chall.get("token"):
        return None
    # Solve PoW challenges in parallel on a thread pool
    sols: List[Tuple[str, str, int]] = await asyncio.gather(
        *(_solve_single(executor, salt, target) for salt, target in chall["challenge"])  # type: ignore[index]
    )
    redeemed = await client.redeem(chall["token"], sols)
    if not redeemed:
        return None
    return await client.request_funds(address, redeemed)


async def amain() -> int:
    addr = os.getenv("FUND_ADDR") or (sys.argv[1] if len(sys.argv) > 1 else None)
    if not addr:
        print("usage: FUND_ADDR=0x... python scripts/faucet_batch.py [FUND_ADDR]")
        return 2

    count = int(os.getenv("COUNT", "20"))
    concurrency = int(os.getenv("CONCURRENCY", str(min(8, max(1, os.cpu_count() or 4)))))
    solver_procs = int(os.getenv("SOLVER_PROCESSES", str(max(1, os.cpu_count() or 4))))

    faucet_url = os.getenv("L2_FAUCET_URL", "https://l2.holesky.golemdb.io/faucet")
    captcha_base = os.getenv("CAPTCHA_BASE", "https://cap.gobas.me")
    captcha_api_key = os.getenv("CAPTCHA_API_KEY", "05381a2cef5e")

    client = PowFaucetClient(
        faucet_url=faucet_url,
        captcha_base_url=captcha_base,
        captcha_api_key=captcha_api_key,
        timeout=90.0,
    )

    print(f"Requesting faucet funds {count} times (concurrency={concurrency}, solver_procs={solver_procs}) for {addr}")
    print(f"- faucet:  {faucet_url}")
    print(f"- captcha: {captcha_base} (key: {captcha_api_key[:4]}…)")

    sem = asyncio.Semaphore(concurrency)

    executor = concurrent.futures.ProcessPoolExecutor(max_workers=solver_procs)

    async def _task(i: int) -> bool:
        async with sem:
            tx = await run_once(client, addr, executor)
            if tx:
                print(f"[{i}/{count}] ok   tx={tx}")
                return True
            else:
                print(f"[{i}/{count}] fail")
                return False

    try:
        results = await asyncio.gather(*(_task(i) for i in range(1, count + 1)))
    finally:
        executor.shutdown(cancel_futures=True)
    successes = sum(1 for r in results if r)

    print(f"done: {successes}/{count} successful requests")
    return 0 if successes > 0 else 1


def main() -> None:
    raise SystemExit(asyncio.run(amain()))


if __name__ == "__main__":
    main()
