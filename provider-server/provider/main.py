import asyncio
import os
import socket
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

from .config import settings, ensure_config
from .utils.logging import setup_logger
from .utils.ascii_art import startup_animation
from .discovery.resource_tracker import ResourceTracker
from .discovery.advertiser import DiscoveryServerAdvertiser
from .container import Container
from .service import ProviderService


logger = setup_logger(__name__)

app = FastAPI(title="VM on Golem Provider")
container = Container()
# Load configuration using a dict to avoid version-specific adapters
try:
    container.config.from_dict(settings.model_dump())
except Exception:
    # Fallback for environments without pydantic v2 model_dump
    container.config.from_pydantic(settings)
app.container = container
container.wire(modules=[".api.routes"])

from .vm.models import VMNotFoundError
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(VMNotFoundError)
async def vm_not_found_exception_handler(request: Request, exc: VMNotFoundError):
    return JSONResponse(
        status_code=404,
        content={"message": str(exc)},
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"message": "An unexpected error occurred"},
    )

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

@app.on_event("startup")
async def startup_event():
    """Handle application startup."""
    provider_service = container.provider_service()
    await provider_service.setup(app)


@app.on_event("shutdown")
async def shutdown_event():
    """Handle application shutdown."""
    provider_service = container.provider_service()
    await provider_service.cleanup()

# Import routes after app creation to avoid circular imports
from .api import routes
app.include_router(routes.router, prefix="/api/v1")

# Export app for uvicorn
__all__ = ["app", "start"]


def check_requirements():
    """Check if all requirements are met."""
    try:
        # Import settings to trigger validation
        from .config import settings
        return True
    except Exception as e:
        logger.error(f"Requirements check failed: {e}")
        return False


async def verify_provider_port(port: int) -> bool:
    """Verify that the provider port is available for binding.

    Args:
        port: The port to verify

    Returns:
        bool: True if the port is available, False otherwise
    """
    try:
        # Try to create a temporary listener
        server = await asyncio.start_server(
            lambda r, w: None,  # Empty callback
            '0.0.0.0',
            port
        )
        server.close()
        await server.wait_closed()
        logger.info(f"✅ Provider port {port} is available")
        return True
    except Exception as e:
        logger.error(f"❌ Provider port {port} is not available: {e}")
        logger.error("Please ensure:")
        logger.error(f"1. Port {port} is not in use by another application")
        logger.error("2. You have permission to bind to this port")
        logger.error("3. Your firewall allows binding to this port")
        return False


# The get_local_ip function has been removed as this logic is now handled in config.py


import typer
try:
    from importlib import metadata
except ImportError:
    # Python < 3.8
    import importlib_metadata as metadata

cli = typer.Typer()
pricing_app = typer.Typer(help="Configure USD pricing; auto-converts to GLM.")
wallet_app = typer.Typer(help="Wallet utilities (funding, balance)")
streams_app = typer.Typer(help="Inspect payment streams")
cli.add_typer(pricing_app, name="pricing")
cli.add_typer(wallet_app, name="wallet")
cli.add_typer(streams_app, name="streams")
config_app = typer.Typer(help="Configure stream monitoring and withdrawals")
cli.add_typer(config_app, name="config")

@cli.callback()
def main():
    """VM on Golem Provider CLI"""
    ensure_config()
    # No-op callback to initialize config; avoid custom --version flag to keep help stable
    return


@wallet_app.command("faucet-l2")
def wallet_faucet_l2():
    """Request L2 faucet funds for the provider's payment address (native ETH)."""
    from .config import settings
    from .security.l2_faucet import L2FaucetService
    try:
        addr = settings.PROVIDER_ID
        async def _run():
            svc = L2FaucetService(settings)
            tx = await svc.request_funds(addr)
            if tx:
                print(f"Faucet tx: {tx}")
            else:
                # Either skipped due to sufficient balance or failed
                pass
        asyncio.run(_run())
    except Exception as e:
        print(f"Error: {e}")
        raise typer.Exit(code=1)


@streams_app.command("list")
def streams_list(json_out: bool = typer.Option(False, "--json", help="Output in JSON")):
    """List all mapped streams with computed status."""
    from .container import Container
    from .config import settings
    from .payments.blockchain_service import StreamPaymentReader
    from .utils.pricing import fetch_glm_usd_price, fetch_eth_usd_price
    from decimal import Decimal
    from web3 import Web3
    import json as _json
    try:
        if not settings.STREAM_PAYMENT_ADDRESS or settings.STREAM_PAYMENT_ADDRESS == "0x0000000000000000000000000000000000000000":
            print("Streaming payments are disabled on this provider.")
            raise typer.Exit(code=1)
        c = Container()
        c.config.from_pydantic(settings)
        stream_map = c.stream_map()
        reader = StreamPaymentReader(settings.POLYGON_RPC_URL, settings.STREAM_PAYMENT_ADDRESS)
        items = asyncio.run(stream_map.all_items())
        now = int(reader.web3.eth.get_block("latest")["timestamp"]) if items else 0
        rows = []
        for vm_id, stream_id in items.items():
            try:
                s = reader.get_stream(int(stream_id))
                vested = max(min(now, int(s["stopTime"])) - int(s["startTime"]), 0) * int(s["ratePerSecond"])  # type: ignore
                withdrawable = max(int(vested) - int(s["withdrawn"]), 0)
                remaining = max(int(s["stopTime"]) - now, 0)
                ok, reason = reader.verify_stream(int(stream_id), settings.PROVIDER_ID)
                rows.append({
                    "vm_id": vm_id,
                    "stream_id": int(stream_id),
                    "token": str(s.get("token")),
                    "recipient": s["recipient"],
                    "start": int(s["startTime"]),
                    "stop": int(s["stopTime"]),
                    "rate": int(s["ratePerSecond"]),
                    "deposit": int(s["deposit"]),
                    "withdrawn": int(s["withdrawn"]),
                    "remaining": remaining,
                    "verified": bool(ok),
                    "reason": reason,
                    "withdrawable": int(withdrawable),
                })
            except Exception as e:
                rows.append({"vm_id": vm_id, "stream_id": int(stream_id), "error": str(e)})
        if json_out:
            print(_json.dumps({"streams": rows}, indent=2))
            return
        if not rows:
            print("No streams mapped.")
            return
        # Prepare human-friendly display (ETH/GLM + USD)
        ZERO = "0x0000000000000000000000000000000000000000"
        # Cache prices so we don't query per-row
        price_cache: dict[str, Optional[Decimal]] = {"ETH": None, "GLM": None}
        # Determine which symbols are present
        symbols_present = set()
        for r in rows:
            if "error" in r:
                continue
            token_addr = (r.get("token") or "").lower()
            sym = "ETH" if token_addr == ZERO.lower() else "GLM"
            symbols_present.add(sym)
        if "ETH" in symbols_present:
            price_cache["ETH"] = fetch_eth_usd_price()
        if "GLM" in symbols_present:
            price_cache["GLM"] = fetch_glm_usd_price()

        # Build table rows
        table_rows = []
        for r in rows:
            if "error" in r:
                table_rows.append([r["vm_id"], str(r["stream_id"]), "—", "ERROR", r.get("error", ""), "—"])
                continue
            token_addr = (r.get("token") or "").lower()
            sym = "ETH" if token_addr == ZERO.lower() else "GLM"
            withdrawable_eth = Decimal(str(Web3.from_wei(int(r["withdrawable"]), "ether")))
            withdrawable_str = f"{withdrawable_eth:.6f} {sym}"
            price = price_cache.get(sym)
            usd_str = "—"
            if price is not None:
                try:
                    usd_val = (withdrawable_eth * price).quantize(Decimal("0.01"))
                    usd_str = f"${usd_val}"
                except Exception:
                    usd_str = "—"
            table_rows.append([
                r["vm_id"],
                str(r["stream_id"]),
                f"{int(r['remaining'])}s",
                "yes" if r["verified"] else "no",
                withdrawable_str,
                usd_str,
            ])

        headers = ["VM", "Stream", "Remaining", "Verified", "Withdrawable", "USD"]
        # Compute column widths
        cols = len(headers)
        col_widths = [len(h) for h in headers]
        for row in table_rows:
            for i in range(cols):
                col_widths[i] = max(col_widths[i], len(str(row[i])))

        def fmt_row(values: list[str]) -> str:
            return "  ".join(str(values[i]).ljust(col_widths[i]) for i in range(cols))

        print("\nStreams")
        print(fmt_row(headers))
        print("  ".join("-" * w for w in col_widths))
        for row in table_rows:
            print(fmt_row(row))
    except Exception as e:
        print(f"Error: {e}")
        raise typer.Exit(code=1)


@streams_app.command("show")
def streams_show(vm_id: str = typer.Argument(..., help="VM id (requestor_name)"), json_out: bool = typer.Option(False, "--json")):
    """Show a single VM's stream status."""
    from .container import Container
    from .config import settings
    from .payments.blockchain_service import StreamPaymentReader
    from .utils.pricing import fetch_glm_usd_price, fetch_eth_usd_price
    from decimal import Decimal
    from web3 import Web3
    import json as _json
    try:
        c = Container()
        c.config.from_pydantic(settings)
        stream_map = c.stream_map()
        sid = asyncio.run(stream_map.get(vm_id))
        if sid is None:
            print("No stream mapped for this VM.")
            raise typer.Exit(code=1)
        reader = StreamPaymentReader(settings.POLYGON_RPC_URL, settings.STREAM_PAYMENT_ADDRESS)
        s = reader.get_stream(int(sid))
        now = int(reader.web3.eth.get_block("latest")["timestamp"])  # type: ignore
        vested = max(min(now, int(s["stopTime"])) - int(s["startTime"]), 0) * int(s["ratePerSecond"])  # type: ignore
        withdrawable = max(int(vested) - int(s["withdrawn"]), 0)
        remaining = max(int(s["stopTime"]) - now, 0)
        ok, reason = reader.verify_stream(int(sid), settings.PROVIDER_ID)
        out = {
            "vm_id": vm_id,
            "stream_id": int(sid),
            "chain": s,
            "computed": {
                "now": now,
                "remaining_seconds": remaining,
                "vested_wei": int(vested),
                "withdrawable_wei": int(withdrawable),
            },
            "verified": bool(ok),
            "reason": reason,
        }
        if json_out:
            print(_json.dumps(out, indent=2))
        else:
            ZERO = "0x0000000000000000000000000000000000000000"
            token_addr = (s.get("token") or "").lower()
            sym = "ETH" if token_addr == ZERO.lower() else "GLM"
            nat = Decimal(str(Web3.from_wei(int(withdrawable), "ether")))
            price = fetch_eth_usd_price() if sym == "ETH" else fetch_glm_usd_price()
            usd_str = "—"
            if price is not None:
                try:
                    usd_val = (nat * price).quantize(Decimal("0.01"))
                    usd_str = f"${usd_val}"
                except Exception:
                    usd_str = "—"
            def _fmt_seconds(sec: int) -> str:
                m, s2 = divmod(int(sec), 60)
                h, m = divmod(m, 60)
                d, h = divmod(h, 24)
                parts = []
                if d: parts.append(f"{d}d")
                if h: parts.append(f"{h}h")
                if m and not d: parts.append(f"{m}m")
                if s2 and not d and not h and not m: parts.append(f"{s2}s")
                return " ".join(parts) or "0s"
            # Pretty single-record display
            print("\nStream Details")
            headers = ["VM", "Stream", "Remaining", "Verified", "Withdrawable", "USD"]
            cols = [
                vm_id,
                str(sid),
                _fmt_seconds(remaining),
                "yes" if ok else "no",
                f"{nat:.6f} {sym}",
                usd_str,
            ]
            w = [max(len(headers[i]), len(str(cols[i]))) for i in range(len(headers))]
            print("  ".join(headers[i].ljust(w[i]) for i in range(len(w))))
            print("  ".join("-" * wi for wi in w))
            print("  ".join(str(cols[i]).ljust(w[i]) for i in range(len(w))))
    except Exception as e:
        print(f"Error: {e}")
        raise typer.Exit(code=1)

@streams_app.command("earnings")
def streams_earnings(json_out: bool = typer.Option(False, "--json", help="Output in JSON")):
    """Summarize provider earnings: vested, withdrawn, and withdrawable totals."""
    from .container import Container
    from .config import settings
    from .payments.blockchain_service import StreamPaymentReader
    from .utils.pricing import fetch_glm_usd_price, fetch_eth_usd_price
    from decimal import Decimal
    from web3 import Web3
    import json as _json
    try:
        c = Container()
        c.config.from_pydantic(settings)
        stream_map = c.stream_map()
        reader = StreamPaymentReader(settings.POLYGON_RPC_URL, settings.STREAM_PAYMENT_ADDRESS)
        items = asyncio.run(stream_map.all_items())
        now = int(reader.web3.eth.get_block("latest")["timestamp"]) if items else 0
        rows = []
        total_vested = 0
        total_withdrawn = 0
        total_withdrawable = 0
        ZERO = "0x0000000000000000000000000000000000000000"
        sums_native: dict[str, Decimal] = {"ETH": Decimal("0"), "GLM": Decimal("0")}
        for vm_id, stream_id in items.items():
            try:
                s = reader.get_stream(int(stream_id))
                vested = max(min(now, int(s["stopTime"])) - int(s["startTime"]), 0) * int(s["ratePerSecond"])  # type: ignore
                withdrawable = max(int(vested) - int(s["withdrawn"]), 0)
                total_vested += int(vested)
                total_withdrawn += int(s["withdrawn"])  # type: ignore
                total_withdrawable += int(withdrawable)
                sym = "ETH" if (s.get("token") or "").lower() == ZERO.lower() else "GLM"
                sums_native[sym] += Decimal(str(Web3.from_wei(int(withdrawable), "ether")))
                rows.append({
                    "vm_id": vm_id,
                    "stream_id": int(stream_id),
                    "token": str(s.get("token")),
                    "vested": int(vested),
                    "withdrawn": int(s["withdrawn"]),
                    "withdrawable": int(withdrawable),
                })
            except Exception as e:
                rows.append({"vm_id": vm_id, "stream_id": int(stream_id), "error": str(e)})
        out = {
            "streams": rows,
            "totals": {
                "vested": int(total_vested),
                "withdrawn": int(total_withdrawn),
                "withdrawable": int(total_withdrawable),
            }
        }
        if json_out:
            print(_json.dumps(out, indent=2))
            return
        # Human summary by token with USD
        price_eth = fetch_eth_usd_price()
        price_glm = fetch_glm_usd_price()
        def _fmt_usd(amount_native: Decimal, price: Optional[Decimal]) -> str:
            if price is None:
                return "—"
            try:
                return f"${(amount_native * price).quantize(Decimal('0.01'))}"
            except Exception:
                return "—"
        print("\nEarnings Summary")
        headers = ["Token", "Withdrawable", "USD"]
        data_rows = [
            ["ETH", f"{sums_native['ETH']:.6f} ETH", _fmt_usd(sums_native["ETH"], price_eth)],
            ["GLM", f"{sums_native['GLM']:.6f} GLM", _fmt_usd(sums_native["GLM"], price_glm)],
        ]
        # Table widths
        w = [len(h) for h in headers]
        for r in data_rows:
            for i in range(3):
                w[i] = max(w[i], len(str(r[i])))
        print("  ".join(headers[i].ljust(w[i]) for i in range(3)))
        print("  ".join("-" * wi for wi in w))
        for r in data_rows:
            print("  ".join(str(r[i]).ljust(w[i]) for i in range(3)))
        # Per stream table
        if rows:
            table = []
            for r in rows:
                if "error" in r:
                    table.append([r["vm_id"], str(r["stream_id"]), "ERROR", r.get("error", "")])
                    continue
                sym = "ETH" if (r.get("token") or "").lower() == ZERO.lower() else "GLM"
                nat = Decimal(str(Web3.from_wei(int(r["withdrawable"]), "ether")))
                price = price_eth if sym == "ETH" else price_glm
                usd = _fmt_usd(nat, price)
                table.append([r["vm_id"], str(r["stream_id"]), f"{nat:.6f} {sym}", usd])
            h2 = ["VM", "Stream", "Withdrawable", "USD"]
            w2 = [len(x) for x in h2]
            for row in table:
                for i in range(4):
                    w2[i] = max(w2[i], len(str(row[i])))
            print("\nPer Stream")
            print("  ".join(h2[i].ljust(w2[i]) for i in range(4)))
            print("  ".join("-" * wi for wi in w2))
            for row in table:
                print("  ".join(str(row[i]).ljust(w2[i]) for i in range(4)))
    except Exception as e:
        print(f"Error: {e}")
        raise typer.Exit(code=1)


@streams_app.command("withdraw")
def streams_withdraw(
    vm_id: str = typer.Option(None, "--vm-id", help="Withdraw for a single VM id"),
    all_streams: bool = typer.Option(False, "--all", help="Withdraw for all mapped streams"),
):
    """Withdraw vested funds for one or all streams."""
    from .container import Container
    from .config import settings
    from .security.l2_faucet import L2FaucetService
    try:
        if not vm_id and not all_streams:
            print("Specify --vm-id or --all")
            raise typer.Exit(code=1)
        c = Container()
        c.config.from_pydantic(settings)
        stream_map = c.stream_map()
        client = c.stream_client()
        # Ensure we have L2 gas for withdrawals (testnets)
        try:
            asyncio.run(L2FaucetService(settings).request_funds(settings.PROVIDER_ID))
        except Exception:
            # Non-fatal; proceed with withdraw attempt
            pass
        targets = []
        if all_streams:
            items = asyncio.run(stream_map.all_items())
            for vid, sid in items.items():
                targets.append((vid, int(sid)))
        else:
            sid = asyncio.run(stream_map.get(vm_id))
            if sid is None:
                print("No stream mapped for this VM.")
                raise typer.Exit(code=1)
            targets.append((vm_id, int(sid)))
        results = []
        for vid, sid in targets:
            try:
                tx = client.withdraw(int(sid))
                results.append((vid, sid, tx))
                print(f"Withdrew stream {sid} for VM {vid}: tx={tx}")
            except Exception as e:
                print(f"Failed to withdraw stream {sid} for VM {vid}: {e}")
        # no JSON aggregation here; use earnings for structured output
    except Exception as e:
        print(f"Error: {e}")
        raise typer.Exit(code=1)

@cli.command()
def start(
    no_verify_port: bool = typer.Option(False, "--no-verify-port", help="Skip provider port verification."),
    network: str = typer.Option(None, "--network", help="Target network: 'testnet' or 'mainnet' (overrides env)")
):
    """Start the provider server."""
    run_server(dev_mode=False, no_verify_port=no_verify_port, network=network)

# Removed separate 'dev' command; use environment GOLEM_PROVIDER_ENVIRONMENT=development instead.

def _env_path_for(dev_mode: Optional[bool]) -> str:
    from pathlib import Path
    env_file = ".env.dev" if dev_mode else ".env"
    return str(Path(__file__).parent.parent / env_file)

def _write_env_vars(path: str, updates: dict):
    # Simple .env updater: preserves other lines, replaces/append updated keys
    import re
    import io
    try:
        with open(path, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        lines = []

    kv = {**updates}
    pattern = re.compile(r"^(?P<k>[A-Z0-9_]+)=.*$")
    out = []
    seen = set()
    for line in lines:
        m = pattern.match(line.strip())
        if not m:
            out.append(line)
            continue
        k = m.group("k")
        if k in kv:
            out.append(f"{k}={kv[k]}\n")
            seen.add(k)
        else:
            out.append(line)
    for k, v in kv.items():
        if k not in seen:
            out.append(f"{k}={v}\n")

    with open(path, "w") as f:
        f.writelines(out)


@config_app.command("withdraw")
def config_withdraw(
    enable: bool = typer.Option(None, "--enable", help="Enable/disable auto-withdraw (true/false)"),
    interval: int = typer.Option(None, "--interval", help="Withdraw interval in seconds (e.g., 1800)"),
    min_wei: int = typer.Option(None, "--min-wei", help="Only withdraw when >= this wei amount"),
    dev: bool = typer.Option(False, "--dev", help="Write to .env.dev instead of .env"),
):
    """Configure provider auto-withdraw settings and persist to .env(.dev)."""
    from .config import settings
    env_path = _env_path_for(dev)
    updates = {}
    if enable is not None:
        updates["GOLEM_PROVIDER_STREAM_WITHDRAW_ENABLED"] = str(enable).lower()
        settings.STREAM_WITHDRAW_ENABLED = bool(enable)
    if interval is not None:
        if interval < 0:
            raise typer.BadParameter("--interval must be >= 0")
        updates["GOLEM_PROVIDER_STREAM_WITHDRAW_INTERVAL_SECONDS"] = int(interval)
        try:
            settings.STREAM_WITHDRAW_INTERVAL_SECONDS = int(interval)
        except Exception:
            pass
    if min_wei is not None:
        if min_wei < 0:
            raise typer.BadParameter("--min-wei must be >= 0")
        updates["GOLEM_PROVIDER_STREAM_MIN_WITHDRAW_WEI"] = int(min_wei)
        try:
            settings.STREAM_MIN_WITHDRAW_WEI = int(min_wei)
        except Exception:
            pass
    if not updates:
        print("No changes (use --enable/--interval/--min-wei)")
        raise typer.Exit(code=0)
    _write_env_vars(env_path, updates)
    print(f"Updated withdraw settings in {env_path}")


@config_app.command("monitor")
def config_monitor(
    enable: bool = typer.Option(None, "--enable", help="Enable/disable stream monitor (true/false)"),
    interval: int = typer.Option(None, "--interval", help="Monitor interval in seconds (e.g., 30)"),
    min_remaining: int = typer.Option(None, "--min-remaining", help="Minimum remaining runway to keep VM running (seconds)"),
    dev: bool = typer.Option(False, "--dev", help="Write to .env.dev instead of .env"),
):
    """Configure provider stream monitor and persist to .env(.dev)."""
    from .config import settings
    env_path = _env_path_for(dev)
    updates = {}
    if enable is not None:
        updates["GOLEM_PROVIDER_STREAM_MONITOR_ENABLED"] = str(enable).lower()
        settings.STREAM_MONITOR_ENABLED = bool(enable)
    if interval is not None:
        if interval < 0:
            raise typer.BadParameter("--interval must be >= 0")
        updates["GOLEM_PROVIDER_STREAM_MONITOR_INTERVAL_SECONDS"] = int(interval)
        try:
            settings.STREAM_MONITOR_INTERVAL_SECONDS = int(interval)
        except Exception:
            pass
    if min_remaining is not None:
        if min_remaining < 0:
            raise typer.BadParameter("--min-remaining must be >= 0")
        updates["GOLEM_PROVIDER_STREAM_MIN_REMAINING_SECONDS"] = int(min_remaining)
        try:
            settings.STREAM_MIN_REMAINING_SECONDS = int(min_remaining)
        except Exception:
            pass
    if not updates:
        print("No changes (use --enable/--interval/--min-remaining)")
        raise typer.Exit(code=0)
    _write_env_vars(env_path, updates)
    print(f"Updated monitor settings in {env_path}")

def _print_pricing_examples(glm_usd):
    from decimal import Decimal
    from .utils.pricing import calculate_monthly_cost, calculate_monthly_cost_usd
    from .vm.models import VMResources
    examples = [
        ("Small", VMResources(cpu=1, memory=1, storage=10)),
        ("Medium", VMResources(cpu=2, memory=4, storage=20)),
        ("Example 2c/2g/10g", VMResources(cpu=2, memory=2, storage=10)),
    ]
    # Maintain legacy header for tests while adding a clearer caption
    print("\nExample monthly costs with current settings:")
    print("(Estimated monthly earnings with your current pricing)")
    for name, res in examples:
        glm = calculate_monthly_cost(res)
        usd = calculate_monthly_cost_usd(res, glm_usd)
        usd_str = f"${usd:.2f}" if usd is not None else "—"
        glm_str = f"{glm:.4f} GLM"
        print(
            f"- {name} ({res.cpu}C, {res.memory}GB RAM, {res.storage}GB Disk): ~{usd_str} per month (~{glm_str})"
        )

def run_server(dev_mode: bool | None = None, no_verify_port: bool = False, network: str | None = None):
    """Helper to run the uvicorn server."""
    import sys
    from pathlib import Path
    from dotenv import load_dotenv
    import uvicorn
    # Decide dev mode from explicit arg or environment
    if dev_mode is None:
        dev_mode = os.environ.get("GOLEM_PROVIDER_ENVIRONMENT", "").lower() == "development"

    # Load appropriate .env file based on mode
    env_file = ".env.dev" if dev_mode else ".env"
    env_path = Path(__file__).parent.parent / env_file
    load_dotenv(dotenv_path=env_path)

    # Apply network override early (affects settings and annotations)
    if network:
        os.environ["GOLEM_PROVIDER_NETWORK"] = network
    
    # The logic for setting the public IP in dev mode is now handled in config.py
    # The following lines are no longer needed and have been removed.

    # Import settings after loading env
    from .config import settings
    if network:
        try:
            settings.NETWORK = network
        except Exception:
            pass

    # Configure logging with debug mode
    logger = setup_logger(__name__, debug=dev_mode)

    try:
        # Log environment variables
        logger.info("Environment variables:")
        for key, value in os.environ.items():
            if key.startswith('GOLEM_PROVIDER_'):
                logger.info(f"{key}={value}")
        if network:
            logger.info(f"Overridden network: {network}")

        # Check requirements
        if not check_requirements():
            logger.error("Requirements check failed")
            sys.exit(1)

        # Verify provider port is available
        if not no_verify_port and not asyncio.run(verify_provider_port(settings.PORT)):
            logger.error(f"Provider port {settings.PORT} is not available")
            sys.exit(1)

        # Configure uvicorn logging
        log_config = uvicorn.config.LOGGING_CONFIG
        log_config["formatters"]["access"]["fmt"] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

        # Run server
        logger.process(
            f"🚀 Starting provider server on {settings.HOST}:{settings.PORT}")
        uvicorn.run(
            "provider:app",
            host=settings.HOST,
            port=settings.PORT,
            reload=dev_mode,
            log_level="debug" if dev_mode else "info",
            log_config=log_config,
            timeout_keep_alive=60,  # Increase keep-alive timeout
            limit_concurrency=100,  # Limit concurrent connections
        )
    except Exception as e:
        logger.error(f"Failed to start provider server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    cli()


@pricing_app.command("show")
def pricing_show():
    """Show current USD and GLM per-unit monthly prices and examples."""
    from decimal import Decimal
    from .utils.pricing import fetch_glm_usd_price, update_glm_unit_prices_from_usd

    print("Current pricing (per month):")
    print(
        f"  - USD per unit: CPU ${settings.PRICE_USD_PER_CORE_MONTH}/core, RAM ${settings.PRICE_USD_PER_GB_RAM_MONTH}/GB, Disk ${settings.PRICE_USD_PER_GB_STORAGE_MONTH}/GB"
    )
    glm_usd = fetch_glm_usd_price()
    if not glm_usd:
        print("Error: Could not fetch GLM/USD price. Please try again later.")
        raise typer.Exit(code=1)
    # Coerce to Decimal for calculations if needed
    from decimal import Decimal
    if not isinstance(glm_usd, Decimal):
        glm_usd = Decimal(str(glm_usd))
    update_glm_unit_prices_from_usd(glm_usd)
    print(f"  - GLM price: ${glm_usd} per GLM")
    print(f"  - Rate: {glm_usd} USD/GLM")
    print(
        f"  - GLM per unit: CPU {round(float(settings.PRICE_GLM_PER_CORE_MONTH), 6)} GLM/core, RAM {round(float(settings.PRICE_GLM_PER_GB_RAM_MONTH), 6)} GLM/GB, Disk {round(float(settings.PRICE_GLM_PER_GB_STORAGE_MONTH), 6)} GLM/GB"
    )
    _print_pricing_examples(glm_usd)


@pricing_app.command("set")
def pricing_set(
    usd_per_core: float = typer.Option(
        ..., "--usd-per-core", "--core-usd", help="USD per CPU core per month"
    ),
    usd_per_mem: float = typer.Option(
        ..., "--usd-per-mem", "--ram-usd", help="USD per GB of RAM per month"
    ),
    usd_per_disk: float = typer.Option(
        ..., "--usd-per-disk", "--usd-per-storage", "--storage-usd", help="USD per GB of disk per month"
    ),
    dev: bool = typer.Option(False, "--dev", help="Write to .env.dev instead of .env"),
):
    """Set USD pricing; GLM rates auto-update via CoinGecko in background."""
    if usd_per_core < 0 or usd_per_mem < 0 or usd_per_disk < 0:
        raise typer.BadParameter("All pricing values must be >= 0")
    env_path = _env_path_for(dev)
    updates = {
        "GOLEM_PROVIDER_PRICE_USD_PER_CORE_MONTH": usd_per_core,
        "GOLEM_PROVIDER_PRICE_USD_PER_GB_RAM_MONTH": usd_per_mem,
        "GOLEM_PROVIDER_PRICE_USD_PER_GB_STORAGE_MONTH": usd_per_disk,
    }
    _write_env_vars(env_path, updates)
    print(f"Updated pricing in {env_path}")
    # Immediately reflect in current process settings as well
    settings.PRICE_USD_PER_CORE_MONTH = usd_per_core
    settings.PRICE_USD_PER_GB_RAM_MONTH = usd_per_mem
    settings.PRICE_USD_PER_GB_STORAGE_MONTH = usd_per_disk

    from .utils.pricing import fetch_glm_usd_price, update_glm_unit_prices_from_usd
    glm_usd = fetch_glm_usd_price()
    if glm_usd:
        # Coerce to Decimal for calculations if needed
        from decimal import Decimal
        if not isinstance(glm_usd, Decimal):
            glm_usd = Decimal(str(glm_usd))
        update_glm_unit_prices_from_usd(glm_usd)
        print("Recalculated GLM prices due to updated USD configuration.")
        _print_pricing_examples(glm_usd)
    else:
        print("Warning: could not fetch GLM/USD; GLM unit prices not recalculated.")
        print("Tip: run 'golem-provider pricing show' when online to verify pricing with USD examples.")
