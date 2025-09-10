"""CLI interface for VM on Golem."""
import click
import asyncio
import json
from typing import Optional
from pathlib import Path
import subprocess
import os
import aiohttp
from tabulate import tabulate
import uvicorn
try:
    from importlib import metadata
except ImportError:
    # Python < 3.8
    import importlib_metadata as metadata

from ..config import config

# `ensure_config` is responsible for creating default configuration
# files and directories on first run.  Some unit tests replace the
# entire `requestor.config` module with a lightweight stub that only
# provides a `config` object.  Importing `ensure_config` in such
# scenarios would raise an ``ImportError`` which prevents the CLI
# module from being imported at all.  To make the CLI resilient during
# tests we try to import ``ensure_config`` but fall back to a no-op
# when it isn't available.
try:
    from ..config import ensure_config  # type: ignore
except Exception:  # pragma: no cover - used only when tests stub the module
    def ensure_config() -> None:
        """Fallback ``ensure_config`` used in tests.

        When the real configuration module is replaced with a stub the
        CLI should still be importable.  The stub simply does nothing
        which is sufficient for the unit tests exercising the CLI
        command mappings.
        """
        pass
from ..provider.client import ProviderClient
from ..errors import RequestorError
from ..utils.logging import setup_logger
from ..utils.spinner import step, Spinner
from ..services.vm_service import VMService
from ..services.provider_service import ProviderService
from ..services.ssh_service import SSHService
from ..services.database_service import DatabaseService

# Initialize logger
logger = setup_logger('golem.requestor')

# Initialize services
db_service = DatabaseService(config.db_path)


def async_command(f):
    """Decorator to run async commands."""
    async def wrapper(*args, **kwargs):
        # Initialize database
        await db_service.init()
        return await f(*args, **kwargs)
    return lambda *args, **kwargs: asyncio.run(wrapper(*args, **kwargs))


def print_version(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return
    try:
        version = metadata.version('request-vm-on-golem')
    except metadata.PackageNotFoundError:
        version = 'unknown'
    click.echo(f'Requestor VM on Golem CLI version {version}')
    ctx.exit()


@click.group()
@click.option('--version', is_flag=True, callback=print_version,
              expose_value=False, is_eager=True, help="Show the version and exit.")
@click.option('--network', type=click.Choice(['testnet', 'mainnet']), default=None,
              help="Override network for discovery filtering ('testnet' or 'mainnet')")
def cli(network: str | None):
    """VM on Golem management CLI"""
    ensure_config()
    # Allow on-demand override without touching env
    if network:
        try:
            config.network = network
        except Exception:
            pass
    pass


@cli.command(name="version")
def version_cmd():
    """Show installed and latest versions from PyPI."""
    pkg = "request-vm-on-golem"
    try:
        current = metadata.version(pkg)
    except Exception:
        current = "unknown"
    latest = None
    # Avoid network during pytest
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        try:
            import json as _json
            from urllib.request import urlopen
            with urlopen(f"https://pypi.org/pypi/{pkg}/json", timeout=5) as resp:
                data = _json.loads(resp.read().decode("utf-8"))
                latest = data.get("info", {}).get("version")
        except Exception:
            latest = None

    if latest and latest != current:
        click.echo(f"Requestor CLI: {current} (update available: {latest})")
        click.echo("Update: pip install -U request-vm-on-golem")
    else:
        click.echo(f"Requestor CLI: {current} (up-to-date)" if latest else f"Requestor CLI: {current}")


@cli.group()
def vm():
    """VM management commands"""
    pass


@vm.command(name='providers')
@click.option('--cpu', type=int, help='Minimum CPU cores required')
@click.option('--memory', type=int, help='Minimum memory (GB) required')
@click.option('--storage', type=int, help='Minimum disk (GB) required')
@click.option('--country', help='Preferred provider country')
@click.option('--driver', type=click.Choice(['central', 'golem-base']), default=None, help='Discovery driver to use')
@click.option('--payments-network', type=str, default=None, help='Filter by payments network profile (default: current config)')
@click.option('--all-payments', is_flag=True, help='Do not filter by payments network (show all)')
@click.option('--json', 'as_json', is_flag=True, help='Output in JSON format')
@click.option('--network', type=click.Choice(['testnet', 'mainnet']), default=None,
              help='Override network filter for this command')
@async_command
async def list_providers(cpu: Optional[int], memory: Optional[int], storage: Optional[int], country: Optional[str], driver: Optional[str], payments_network: Optional[str] = None, all_payments: bool = False, as_json: bool = False, network: Optional[str] = None):
    """List available providers matching requirements."""
    try:
        if as_json:
            os.environ["GOLEM_SILENCE_LOGS"] = "1"
        if network:
            config.network = network
        # Log search criteria if any
        if any([cpu, memory, storage, country]):
            logger.command("🔍 Searching for providers with criteria:")
            if cpu:
                logger.detail(f"CPU Cores: {cpu}+")
            if memory:
                logger.detail(f"Memory: {memory}GB+")
            if storage:
                logger.detail(f"Disk: {storage}GB+")
            if country:
                logger.detail(f"Country: {country}")

        # Determine the discovery driver being used
        discovery_driver = driver or config.discovery_driver
        eff_pn = payments_network if payments_network is not None else getattr(config, 'payments_network', None)
        logger.process(f"Querying discovery via {discovery_driver} (network={config.network}, payments={eff_pn if not all_payments else 'ALL'})")

        # Initialize provider service
        provider_service = ProviderService()
        async with provider_service:
            # If a full spec is provided, enable per-provider estimate display
            if cpu and memory and storage:
                provider_service.estimate_spec = (cpu, memory, storage)
            try:
                providers = await provider_service.find_providers(
                    cpu=cpu,
                    memory=memory,
                    storage=storage,
                    country=country,
                    driver=driver,
                    payments_network=eff_pn,
                    include_all_payments=bool(all_payments),
                )
            except TypeError:
                # Backward compatibility with older/dummy service stubs in tests
                providers = await provider_service.find_providers(
                    cpu=cpu, memory=memory, storage=storage, country=country, driver=driver
                )

        if not providers:
            logger.warning("No providers found matching criteria")
            result = {"providers": []}
            if as_json:
                click.echo(json.dumps(result, indent=2))
            return result

        # If JSON requested and full spec provided, include estimates per provider
        if as_json and cpu and memory and storage:
            for p in providers:
                est = provider_service.compute_estimate(p, (cpu, memory, storage))
                if est is not None:
                    p['estimate'] = est
        result = {"providers": providers}

        if as_json:
            click.echo(json.dumps(result, indent=2))
        else:
            # Format provider information using service with colors
            headers = provider_service.provider_headers
            rows = await asyncio.gather(*(provider_service.format_provider_row(p, colorize=True) for p in providers))

            # Show fancy header
            click.echo("\n" + "─" * 80)
            click.echo(click.style(f"  🌍 Available Providers ({len(providers)} total)", fg="blue", bold=True))
            click.echo("─" * 80)

            # Show table with colored headers
            click.echo("\n" + tabulate(
                rows,
                headers=[click.style(h, bold=True) for h in headers],
                tablefmt="grid"
            ))
            click.echo("\n" + "─" * 80)

        return result

    except Exception as e:
        logger.error(f"Failed to list providers: {str(e)}")
        raise click.Abort()
    finally:
        if as_json:
            try:
                del os.environ["GOLEM_SILENCE_LOGS"]
            except Exception:
                pass


@vm.command(name='create')
@click.argument('name')
@click.option('--provider-id', required=True, help='Provider ID to use')
@click.option('--cpu', type=int, required=True, help='Number of CPU cores')
@click.option('--memory', type=int, required=True, help='Memory in GB')
@click.option('--storage', type=int, required=True, help='Disk in GB')
@click.option('--stream-id', type=int, default=None, help='Optional StreamPayment stream id to fund this VM')
@click.option('--hours', type=int, default=1, help='If no stream-id is provided and payments are enabled, open a stream with this many hours of deposit (default 1)')
@click.option('--yes', is_flag=True, help='Do not prompt for confirmation')
@click.option('--network', type=click.Choice(['testnet', 'mainnet']), default=None, help='Override network for discovery during creation')
@async_command
async def create_vm(name: str, provider_id: str, cpu: int, memory: int, storage: int, stream_id: int | None, hours: int, yes: bool, network: Optional[str] = None):
    """Create a new VM on a specific provider."""
    try:
        if network:
            config.network = network
        # Show configuration details
        click.echo("\n" + "─" * 60)
        click.echo(click.style("  VM Configuration", fg="blue", bold=True))
        click.echo("─" * 60)
        click.echo(f"  Provider   : {click.style(provider_id, fg='cyan')}")
        click.echo(f"  Resources  : {click.style(f'{cpu} CPU, {memory}GB RAM, {storage}GB Disk', fg='cyan')}")
        click.echo("─" * 60 + "\n")

        # Now start the deployment with spinner
        with Spinner("Deploying VM..."):
            # Initialize services
            provider_service = ProviderService()
            async with provider_service:
                # Verify provider and resources
                provider = await provider_service.verify_provider(provider_id)
                if not await provider_service.check_resource_availability(provider_id, cpu, memory, storage):
                    raise RequestorError("Provider doesn't have enough resources available")

                # Get provider IP
                provider_ip = 'localhost' if config.environment == "development" else provider.get('ip_address')
                if not provider_ip and config.environment == "production":
                    raise RequestorError("Provider IP address not found in advertisement")

                # Before proceeding, show estimated monthly price and confirm
                provider_service.estimate_spec = (cpu, memory, storage)
                est_row = await provider_service.format_provider_row(provider, colorize=False)
                # Columns: ... [7]=USD/core/mo, [8]=USD/GB RAM/mo, [9]=USD/GB Disk/mo, [10]=Est. $/mo, [11]=Est. GLM/mo
                est_usd = est_row[10]
                est_glm = est_row[11]
                price_str = f"~${est_usd}/mo" if est_usd != '—' else "(no USD pricing)"
                if est_glm != '—':
                    price_str += f" (~{est_glm} GLM/mo)"
                click.echo(click.style(f"  💵 Estimated Monthly Cost: {price_str}", fg='yellow', bold=True))
                # For streamlined UX, proceed without an interactive confirmation

                # Setup SSH
                ssh_service = SSHService(config.ssh_key_dir)
                key_pair = await ssh_service.get_key_pair()

                # Initialize VM service
                provider_url = config.get_provider_url(provider_ip)
                async with ProviderClient(provider_url) as client:
                    # Fetch provider info if available (for preferred contract addresses); proceed regardless
                    info = None
                    try:
                        info = await client.get_provider_info()
                    except Exception:
                        info = None
                    # Always auto-open a stream when none provided (assume streaming required by default)
                    if stream_id is None:
                        # Compute rate from provider pricing
                        est = provider_service.compute_estimate(provider, (cpu, memory, storage))
                        if not est or est.get('glm_per_month') is None:
                            raise RequestorError('Provider requires streaming but does not advertise GLM pricing; cannot compute ratePerSecond')
                        glm_month = est['glm_per_month']
                        glm_per_second = float(glm_month) / (730.0 * 3600.0)
                        rate_per_second_wei = int(glm_per_second * (10**18))
                        deposit_wei = rate_per_second_wei * int(hours) * 3600
                        # Auto-fund via faucet if needed (testnets), then create stream
                        try:
                            from eth_account import Account
                            from ..security.faucet import L2FaucetService
                            acct = Account.from_key(config.ethereum_private_key)
                            faucet = L2FaucetService(config)
                            await faucet.request_funds(acct.address)
                        except Exception:
                            # Non-fatal; stream creation may still succeed if already funded
                            pass
                        # Open stream on-chain
                        from ..payments.blockchain_service import StreamPaymentClient, StreamPaymentConfig
                        spc = StreamPaymentConfig(
                            rpc_url=config.polygon_rpc_url,
                            contract_address=(info.get('stream_payment_address') if info else None) or config.stream_payment_address,
                            glm_token_address=(info.get('glm_token_address') if info else None) or config.glm_token_address,
                            private_key=config.ethereum_private_key,
                        )
                        sp_client = StreamPaymentClient(spc)
                        recipient = (info.get('provider_id') if info else None) or provider_id
                        stream_id = sp_client.create_stream(recipient, int(deposit_wei), int(rate_per_second_wei))
                        logger.success(f"Opened stream id={stream_id} (hours={hours})")

                    vm_service = VMService(db_service, ssh_service, client)
                    # Create VM
                    vm = await vm_service.create_vm(
                        name=name,
                        cpu=cpu,
                        memory=memory,
                        storage=storage,
                        provider_ip=provider_ip,
                        ssh_key=key_pair.public_key_content,
                        stream_id=stream_id
                    )

                    # Get access info from config
                    ssh_port = vm['config']['ssh_port']

        # Create a visually appealing success message
        click.echo("\n" + "─" * 60)
        click.echo(click.style("  🎉 VM Deployed Successfully!", fg="green", bold=True))
        click.echo("─" * 60 + "\n")

        # VM Details Section
        click.echo(click.style("  VM Details", fg="blue", bold=True))
        click.echo("  " + "┈" * 25)
        click.echo(f"  🏷️  Name      : {click.style(name, fg='cyan')}")
        click.echo(f"  💻 Resources  : {click.style(f'{cpu} CPU, {memory}GB RAM, {storage}GB Disk', fg='cyan')}")
        click.echo(f"  🟢 Status     : {click.style('running', fg='green')}")
        
        # Connection Details Section
        click.echo("\n" + click.style("  Connection Details", fg="blue", bold=True))
        click.echo("  " + "┈" * 25)
        click.echo(f"  🌐 IP Address : {click.style(provider_ip, fg='cyan')}")
        click.echo(f"  🔌 Port       : {click.style(str(ssh_port), fg='cyan')}")
        
        # Quick Connect Section
        click.echo("\n" + click.style("  Quick Connect", fg="blue", bold=True))
        click.echo("  " + "┈" * 25)
        ssh_command = ssh_service.format_ssh_command(
            host=provider_ip,
            port=ssh_port,
            private_key_path=key_pair.private_key.absolute(),
            colorize=True
        )
        click.echo(f"  🔑 SSH Command : {ssh_command}")
        
        click.echo("\n" + "─" * 60)

    except Exception as e:
        error_msg = str(e)
        if "Failed to query discovery service" in error_msg:
            error_msg = "Unable to reach discovery service (check your internet connection)"
        elif "Provider" in error_msg and "not found" in error_msg:
            error_msg = "Provider is no longer available (they may have gone offline)"
        elif "capacity" in error_msg:
            error_msg = "Provider doesn't have enough resources available"
        logger.error(f"Failed to create VM: {error_msg}")
        raise click.Abort()


@vm.group(name='stream')
def vm_stream():
    """Streaming payments helpers"""
    pass


@vm_stream.command('list')
@click.option('--json', 'as_json', is_flag=True, help='Output in JSON format')
@async_command
async def stream_list(as_json: bool):
    """List payment stream status for all known VMs."""
    try:
        if as_json:
            os.environ["GOLEM_SILENCE_LOGS"] = "1"
        vms = await db_service.list_vms()
        if not vms:
            logger.warning("No VMs found in local database")
            click.echo(json.dumps({"streams": []}, indent=2) if as_json else "No VMs found.")
            return {"streams": []}

        results = []
        for vm in vms:
            item: dict = {
                "name": vm.get("name"),
                "provider_ip": vm.get("provider_ip"),
                "stream_id": None,
                "verified": False,
                "reason": None,
                "computed": {},
                "error": None,
            }
            try:
                provider_url = config.get_provider_url(vm['provider_ip'])
                async with ProviderClient(provider_url) as client:
                    status = await client.get_vm_stream_status(vm['vm_id'])
                item.update({
                    "stream_id": status.get("stream_id"),
                    "verified": bool(status.get("verified")),
                    "reason": status.get("reason"),
                    "computed": status.get("computed", {}),
                })
            except Exception as e:
                msg = str(e)
                # Normalize common provider errors
                if "no stream mapped" in msg.lower():
                    item.update({
                        "stream_id": None,
                        "verified": False,
                        "reason": "unmapped",
                    })
                else:
                    item["error"] = msg
            results.append(item)

        out = {"streams": results}

        if as_json:
            click.echo(json.dumps(out, indent=2))
        else:
            # Render a concise table
            headers = [
                "VM",
                "Stream ID",
                "Verified",
                "Reason",
                "Remaining (s)",
                "Withdrawable (wei)",
            ]
            rows = []
            for r in results:
                comp = r.get("computed") or {}
                rows.append([
                    r.get("name"),
                    r.get("stream_id") if r.get("stream_id") is not None else "—",
                    "✔" if r.get("verified") else "✖",
                    r.get("reason") or ("error: " + r.get("error") if r.get("error") else ""),
                    comp.get("remaining_seconds", ""),
                    comp.get("withdrawable_wei", ""),
                ])
            click.echo("\n" + "─" * 60)
            click.echo(click.style(f"  💸 Streams ({len(results)} VMs)", fg="blue", bold=True))
            click.echo("─" * 60)
            click.echo("\n" + tabulate(rows, headers=[click.style(h, bold=True) for h in headers], tablefmt="grid"))
            click.echo("\n" + "─" * 60)

        return out

    except Exception as e:
        logger.error(f"Failed to list streams: {e}")
        raise click.Abort()
    finally:
        if as_json:
            try:
                del os.environ["GOLEM_SILENCE_LOGS"]
            except Exception:
                pass


@vm_stream.command('open')
@click.option('--provider-id', required=True, help='Provider ID to use')
@click.option('--cpu', type=int, required=True, help='CPU cores for rate calc')
@click.option('--memory', type=int, required=True, help='Memory (GB) for rate calc')
@click.option('--storage', type=int, required=True, help='Storage (GB) for rate calc')
@click.option('--hours', type=int, default=1, help='Deposit coverage in hours (default 1)')
@click.option('--network', type=click.Choice(['testnet', 'mainnet']), default=None, help='Override network for discovery during stream open')
@async_command
async def stream_open(provider_id: str, cpu: int, memory: int, storage: int, hours: int, network: Optional[str] = None):
    """Create a GLM stream for a planned VM rental."""
    from ..payments.blockchain_service import StreamPaymentClient, StreamPaymentConfig
    try:
        if network:
            config.network = network
        provider_service = ProviderService()
        async with provider_service:
            provider = await provider_service.verify_provider(provider_id)
            est = provider_service.compute_estimate(provider, (cpu, memory, storage))
            if not est or est.get('glm_per_month') is None:
                raise RequestorError('Provider does not advertise GLM pricing; cannot compute ratePerSecond')
            glm_month = est['glm_per_month']
            glm_per_second = float(glm_month) / (730.0 * 3600.0)
            rate_per_second_wei = int(glm_per_second * (10**18))

            provider_ip = 'localhost' if config.environment == "development" else provider.get('ip_address')
            if not provider_ip and config.environment == "production":
                raise RequestorError("Provider IP address not found in advertisement")
            provider_url = config.get_provider_url(provider_ip)
            async with ProviderClient(provider_url) as client:
                info = await client.get_provider_info()
                recipient = info['provider_id']

            deposit_wei = rate_per_second_wei * int(hours) * 3600
            # Prefer provider-advertised contract addresses to avoid mismatches
            spc = StreamPaymentConfig(
                rpc_url=config.polygon_rpc_url,
                contract_address=info.get('stream_payment_address') or config.stream_payment_address,
                glm_token_address=info.get('glm_token_address') or config.glm_token_address,
                private_key=config.ethereum_private_key,
            )
            sp = StreamPaymentClient(spc)
            stream_id = sp.create_stream(recipient, deposit_wei, rate_per_second_wei)
            click.echo(json.dumps({"stream_id": stream_id, "rate_per_second_wei": rate_per_second_wei, "deposit_wei": deposit_wei}, indent=2))
    except Exception as e:
        logger.error(f"Failed to open stream: {e}")
        raise click.Abort()


@vm_stream.command('topup')
@click.option('--stream-id', type=int, required=True)
@click.option('--glm', type=float, required=False, help='GLM amount to add')
@click.option('--hours', type=int, required=False, help='Hours of coverage to add at prior rate')
@async_command
async def stream_topup(stream_id: int, glm: float | None, hours: int | None):
    """Top up a stream. Provide either --glm or --hours (using prior rate)."""
    from ..payments.blockchain_service import StreamPaymentClient, StreamPaymentConfig
    try:
        spc = StreamPaymentConfig(
            rpc_url=config.polygon_rpc_url,
            contract_address=config.stream_payment_address,
            glm_token_address=config.glm_token_address,
            private_key=config.ethereum_private_key,
        )
        sp = StreamPaymentClient(spc)
        add_wei: int
        if glm is not None:
            add_wei = int(float(glm) * (10**18))
        elif hours is not None:
            # naive: use last known rate by reading on-chain stream
            rate = sp.contract.functions.streams(int(stream_id)).call()[5]  # ratePerSecond
            add_wei = int(rate) * int(hours) * 3600
        else:
            raise RequestorError('Provide either --glm or --hours')
        tx = sp.top_up(stream_id, add_wei)
        click.echo(json.dumps({"stream_id": stream_id, "topped_up_wei": add_wei, "tx": tx}, indent=2))
    except Exception as e:
        logger.error(f"Failed to top up stream: {e}")
        raise click.Abort()


@vm_stream.command('status')
@click.argument('name')
@click.option('--json', 'as_json', is_flag=True, help='Output in JSON format')
@async_command
async def stream_status(name: str, as_json: bool):
    """Show the payment stream status for a VM by name."""
    try:
        if as_json:
            os.environ["GOLEM_SILENCE_LOGS"] = "1"
        # Resolve VM and provider
        vm = await db_service.get_vm(name)
        if not vm:
            raise RequestorError(f"VM '{name}' not found in local DB")
        provider_url = config.get_provider_url(vm['provider_ip'])
        async with ProviderClient(provider_url) as client:
            status = await client.get_vm_stream_status(vm['vm_id'])
        if as_json:
            click.echo(json.dumps(status, indent=2))
            return
        # Pretty print
        c = status.get('chain', {})
        comp = status.get('computed', {})
        click.echo("\n" + "─" * 60)
        click.echo(click.style(f"  💸 Stream Status for VM: {name}", fg="blue", bold=True))
        click.echo("─" * 60)
        click.echo(f"  Stream ID     : {click.style(str(status.get('stream_id')), fg='cyan')}")
        click.echo(f"  Verified      : {click.style(str(status.get('verified')), fg='green' if status.get('verified') else 'yellow')}")
        click.echo(f"  Reason        : {status.get('reason')}")
        click.echo("  On-chain      :")
        click.echo(f"    recipient   : {c.get('recipient')} ")
        click.echo(f"    startTime   : {c.get('startTime')}  stopTime: {c.get('stopTime')}")
        click.echo(f"    rate/second : {c.get('ratePerSecond')}  deposit: {c.get('deposit')}  withdrawn: {c.get('withdrawn')}  halted: {c.get('halted')}")
        click.echo("  Computed      :")
        click.echo(f"    now         : {comp.get('now')}  remaining: {comp.get('remaining_seconds')}s")
        click.echo(f"    vested      : {comp.get('vested_wei')}  withdrawable: {comp.get('withdrawable_wei')}")
        click.echo("─" * 60)
    except Exception as e:
        logger.error(f"Failed to fetch stream status: {e}")
        raise click.Abort()
    finally:
        if as_json:
            try:
                del os.environ["GOLEM_SILENCE_LOGS"]
            except Exception:
                pass


@vm_stream.command('inspect')
@click.option('--stream-id', type=int, required=True)
@click.option('--json', 'as_json', is_flag=True, help='Output in JSON format')
@async_command
async def stream_inspect(stream_id: int, as_json: bool):
    """Inspect a stream directly on-chain (no provider required)."""
    try:
        if as_json:
            os.environ["GOLEM_SILENCE_LOGS"] = "1"
        from web3 import Web3
        from golem_streaming_abi import STREAM_PAYMENT_ABI
        w3 = Web3(Web3.HTTPProvider(config.polygon_rpc_url))
        contract = w3.eth.contract(address=Web3.to_checksum_address(config.stream_payment_address), abi=STREAM_PAYMENT_ABI)
        token, sender, recipient, startTime, stopTime, ratePerSecond, deposit, withdrawn, halted = contract.functions.streams(int(stream_id)).call()
        now = int(w3.eth.get_block('latest')['timestamp'])
        vested = max(min(now, int(stopTime)) - int(startTime), 0) * int(ratePerSecond)
        withdrawable = max(int(vested) - int(withdrawn), 0)
        remaining = max(int(stopTime) - now, 0)
        out = {
            "stream_id": int(stream_id),
            "chain": {
                "token": token,
                "sender": sender,
                "recipient": recipient,
                "startTime": int(startTime),
                "stopTime": int(stopTime),
                "ratePerSecond": int(ratePerSecond),
                "deposit": int(deposit),
                "withdrawn": int(withdrawn),
                "halted": bool(halted),
            },
            "computed": {
                "now": now,
                "remaining_seconds": remaining,
                "vested_wei": int(vested),
                "withdrawable_wei": int(withdrawable),
            }
        }
        if as_json:
            click.echo(json.dumps(out, indent=2))
        else:
            click.echo("\n" + "─" * 60)
            click.echo(click.style(f"  🔎 On-chain Stream Inspect: {stream_id}", fg="blue", bold=True))
            click.echo("─" * 60)
            click.echo(f"  recipient     : {recipient}")
            click.echo(f"  startTime     : {int(startTime)}  stopTime: {int(stopTime)}  now: {now}  remaining: {remaining}s")
            click.echo(f"  rate/second   : {int(ratePerSecond)}  deposit: {int(deposit)}  withdrawn: {int(withdrawn)}  halted: {bool(halted)}")
            click.echo(f"  vested        : {int(vested)}  withdrawable: {int(withdrawable)}")
            click.echo("─" * 60)
    except Exception as e:
        logger.error(f"Failed to inspect stream: {e}")
        raise click.Abort()
    finally:
        if as_json:
            try:
                del os.environ["GOLEM_SILENCE_LOGS"]
            except Exception:
                pass


@cli.group()
def wallet():
    """Wallet utilities (funding, balance)."""
    pass


@wallet.command('faucet')
@async_command
async def wallet_faucet():
    """Request L2 faucet funds for the requestor's payment address."""
    try:
        if not getattr(config, 'faucet_enabled', False):
            logger.warning("Faucet is disabled for the current payments network.")
            click.echo(json.dumps({"error": "faucet_disabled", "network": getattr(config, 'payments_network', None)}, indent=2))
            return
        from ..security.faucet import L2FaucetService
        from eth_account import Account
        acct = Account.from_key(config.ethereum_private_key)
        service = L2FaucetService(config)
        tx = await service.request_funds(acct.address)
        if tx:
            click.echo(json.dumps({"address": acct.address, "tx": tx}, indent=2))
        else:
            click.echo(json.dumps({"address": acct.address, "tx": None}, indent=2))
    except Exception as e:
        logger.error(f"Faucet request failed: {e}")
        raise click.Abort()


@vm.command(name='ssh')
@click.argument('name')
@async_command
async def ssh_vm(name: str):
    """SSH into a VM (alias: connect)."""
    try:
        logger.command(f"🔌 Connecting to VM '{name}'")
        
        # Initialize services
        ssh_service = SSHService(config.ssh_key_dir)
        
        # Get VM details using database service
        logger.process("Retrieving VM details")
        vm = await db_service.get_vm(name)
        if not vm:
            raise click.BadParameter(f"VM '{name}' not found")

        # Get SSH key
        logger.process("Loading SSH credentials")
        key_pair = await ssh_service.get_key_pair()

        # Get VM access info using service
        logger.process("Fetching connection details")
        provider_url = config.get_provider_url(vm['provider_ip'])
        async with ProviderClient(provider_url) as client:
            vm_service = VMService(db_service, ssh_service, client)
            vm = await vm_service.get_vm(name)  # Get fresh VM info
            ssh_port = vm['config']['ssh_port']

        # Execute SSH command
        logger.success(f"Connecting to {vm['provider_ip']}:{ssh_port}")
        ssh_service.connect_to_vm(
            host=vm['provider_ip'],
            port=ssh_port,
            private_key_path=key_pair.private_key.absolute()
        )

    except Exception as e:
        error_msg = str(e)
        if "VM 'test-vm' not found" in error_msg:
            error_msg = "VM not found in local database"
        elif "Not Found" in error_msg:
            error_msg = "VM not found on provider (it may have been manually removed)"
        elif "Connection refused" in error_msg:
            error_msg = "Unable to establish SSH connection (VM may be starting up)"
        logger.error(f"Failed to connect: {error_msg}")
        raise click.Abort()


@vm.command(name="connect")
@click.argument("name")
def connect_vm(name: str):
    """Connect to a VM via SSH (alias of ssh)."""
    return ssh_vm.callback(name)


@vm.command(name='info')
@click.argument('name')
@click.option('--json', 'as_json', is_flag=True, help='Output in JSON format')
@async_command
async def info_vm(name: str, as_json: bool):
    """Show information about a VM."""
    try:
        if as_json:
            os.environ["GOLEM_SILENCE_LOGS"] = "1"
        logger.command(f"ℹ️  Getting info for VM '{name}'")

        # Initialize VM service
        ssh_service = SSHService(config.ssh_key_dir)
        vm_service = VMService(db_service, ssh_service)

        # Retrieve VM details
        vm = await vm_service.get_vm(name)
        if not vm:
            raise click.BadParameter(f"VM '{name}' not found")

        result = vm

        if as_json:
            click.echo(json.dumps(result, indent=2))
        else:
            headers = [
                "Status",
                "IP Address",
                "SSH Port",
                "CPU",
                "Memory (GB)",
                "Disk (GB)",
            ]

            row = [
                vm.get("status", "unknown"),
                vm["provider_ip"],
                vm["config"].get("ssh_port", "N/A"),
                vm["config"]["cpu"],
                vm["config"]["memory"],
                vm["config"]["storage"],
            ]

            click.echo("\n" + tabulate([row], headers=headers, tablefmt="grid"))

        return result

    except Exception as e:
        logger.error(f"Failed to get VM info: {str(e)}")
        raise click.Abort()
    finally:
        if as_json:
            try:
                del os.environ["GOLEM_SILENCE_LOGS"]
            except Exception:
                pass


@vm.command(name='destroy')
@click.argument('name')
@async_command
async def destroy_vm(name: str):
    """Destroy a VM (alias: delete)."""
    try:
        logger.command(f"💥 Destroying VM '{name}'")

        # Get VM details using database service
        logger.process("Retrieving VM details")
        vm = await db_service.get_vm(name)
        if not vm:
            raise click.BadParameter(f"VM '{name}' not found")

        # Initialize VM service
        provider_url = config.get_provider_url(vm['provider_ip'])
        async with ProviderClient(provider_url) as client:
            # Initialize blockchain client for stream termination on destroy
            from ..payments.blockchain_service import StreamPaymentClient, StreamPaymentConfig
            spc = StreamPaymentConfig(
                rpc_url=config.polygon_rpc_url,
                contract_address=config.stream_payment_address,
                glm_token_address=config.glm_token_address,
                private_key=config.ethereum_private_key,
            )
            sp_client = StreamPaymentClient(spc)
            vm_service = VMService(db_service, SSHService(config.ssh_key_dir), client, sp_client)
            await vm_service.destroy_vm(name)
        
        # Show fancy success message
        click.echo("\n" + "─" * 60)
        click.echo(click.style("  💥 VM Destroyed Successfully!", fg="red", bold=True))
        click.echo("─" * 60 + "\n")
        
        click.echo(click.style("  Summary", fg="blue", bold=True))
        click.echo("  " + "┈" * 25)
        click.echo(f"  🏷️  Name      : {click.style(name, fg='cyan')}")
        click.echo(f"  🗑️  Status     : {click.style('destroyed', fg='red')}")
        click.echo(f"  ⏱️  Time       : {click.style('just now', fg='cyan')}")
        
        click.echo("\n" + "─" * 60)

    except Exception as e:
        error_msg = str(e)
        if "VM 'test-vm' not found" in error_msg:
            error_msg = "VM not found in local database"
        elif "Not Found" in error_msg:
            error_msg = "VM not found on provider (it may have been manually removed)"
        logger.error(f"Failed to destroy VM: {error_msg}")
        raise click.Abort()


@vm.command(name="delete")
@click.argument("name")
def delete_vm(name: str):
    """Delete a VM (alias of destroy)."""
    return destroy_vm.callback(name)


@vm.command(name='purge')
@click.option('--force', is_flag=True, help='Force purge even if other errors occur')
@click.confirmation_option(prompt='Are you sure you want to purge all VMs?')
@async_command
async def purge_vms(force: bool):
    """Purge all VMs and clean up local database."""
    try:
        logger.command("🌪️  Purging all VMs")
        
        vms = await db_service.list_vms()
        if not vms:
            logger.warning("No VMs found to purge")
            return

        results = {'success': [], 'failed': []}

        for vm in vms:
            try:
                logger.process(f"Purging VM '{vm['name']}'")
                provider_url = config.get_provider_url(vm['provider_ip'])
                
                async with ProviderClient(provider_url) as client:
                    # Initialize blockchain client for stream termination on purge
                    from ..payments.blockchain_service import StreamPaymentClient, StreamPaymentConfig
                    spc = StreamPaymentConfig(
                        rpc_url=config.polygon_rpc_url,
                        contract_address=config.stream_payment_address,
                        glm_token_address=config.glm_token_address,
                        private_key=config.ethereum_private_key,
                    )
                    sp_client = StreamPaymentClient(spc)
                    vm_service = VMService(db_service, SSHService(config.ssh_key_dir), client, sp_client)
                    await vm_service.destroy_vm(vm['name'])
                    results['success'].append((vm['name'], 'Destroyed successfully'))

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                await db_service.delete_vm(vm['name'])
                msg = f"Could not connect to provider ({e}). Removed from local DB. Please destroy manually."
                results['failed'].append((vm['name'], msg))
            
            except Exception as e:
                if "Cannot connect to host" in str(e):
                    await db_service.delete_vm(vm['name'])
                    msg = f"Could not connect to provider ({e}). Removed from local DB. Please destroy manually."
                    results['failed'].append((vm['name'], msg))
                elif "not found in multipass" in str(e).lower():
                    await db_service.delete_vm(vm['name'])
                    msg = "VM not found on provider. Removed from local DB."
                    results['success'].append((vm['name'], msg))
                elif not force:
                    logger.error(f"Failed to purge VM '{vm['name']}'. Use --force to ignore errors and continue.")
                    raise
                else:
                    results['failed'].append((vm['name'], str(e)))

        # Show results
        click.echo("\n" + "─" * 60)
        click.echo(click.style("  🌪️  VM Purge Complete", fg="blue", bold=True))
        click.echo("─" * 60 + "\n")

        if results['success']:
            click.echo(click.style("  ✅ Successfully Purged", fg="green", bold=True))
            click.echo("  " + "┈" * 25)
            for name, msg in results['success']:
                click.echo(f"  • {click.style(name, fg='cyan')}: {click.style(msg, fg='green')}")
            click.echo()

        if results['failed']:
            click.echo(click.style("  ❌ Failed to Purge", fg="red", bold=True))
            click.echo("  " + "┈" * 25)
            for name, error in results['failed']:
                click.echo(f"  • {click.style(name, fg='cyan')}: {click.style(error, fg='red')}")
            click.echo()

        total = len(results['success']) + len(results['failed'])
        success_rate = (len(results['success']) / total) * 100 if total > 0 else 0
        
        click.echo(click.style("  📊 Summary", fg="blue", bold=True))
        click.echo("  " + "┈" * 25)
        click.echo(f"  📈 Success Rate : {click.style(f'{success_rate:.1f}%', fg='cyan')}")
        click.echo(f"  ✅ Successful   : {click.style(str(len(results['success'])), fg='green')}")
        click.echo(f"  ❌ Failed       : {click.style(str(len(results['failed'])), fg='red')}")
        click.echo(f"  📋 Total VMs    : {click.style(str(total), fg='cyan')}")
        
        click.echo("\n" + "─" * 60)

    except Exception as e:
        logger.error(f"Purge operation failed: {str(e)}")
        raise click.Abort()


@vm.command(name='start')
@click.argument('name')
@async_command
async def start_vm(name: str):
    """Start a VM."""
    try:
        logger.command(f"🟢 Starting VM '{name}'")

        # Get VM details using database service
        logger.process("Retrieving VM details")
        vm = await db_service.get_vm(name)
        if not vm:
            raise click.BadParameter(f"VM '{name}' not found")

        # Initialize VM service
        provider_url = config.get_provider_url(vm['provider_ip'])
        async with ProviderClient(provider_url) as client:
            vm_service = VMService(db_service, SSHService(config.ssh_key_dir), client)
            await vm_service.start_vm(name)

        # Show fancy success message
        click.echo("\n" + "─" * 60)
        click.echo(click.style("  🟢 VM Started Successfully!", fg="green", bold=True))
        click.echo("─" * 60 + "\n")
        
        click.echo(click.style("  VM Status", fg="blue", bold=True))
        click.echo("  " + "┈" * 25)
        click.echo(f"  🏷️  Name      : {click.style(name, fg='cyan')}")
        click.echo(f"  💫 Status     : {click.style('running', fg='green')}")
        click.echo(f"  🌐 IP Address : {click.style(vm['provider_ip'], fg='cyan')}")
        click.echo(f"  🔌 Port       : {click.style(str(vm['config']['ssh_port']), fg='cyan')}")
        
        click.echo("\n" + "─" * 60)

    except Exception as e:
        error_msg = str(e)
        if "VM 'test-vm' not found" in error_msg:
            error_msg = "VM not found in local database"
        elif "Not Found" in error_msg:
            error_msg = "VM not found on provider (it may have been manually removed)"
        elif "already running" in error_msg.lower():
            error_msg = "VM is already running"
        logger.error(f"Failed to start VM: {error_msg}")
        raise click.Abort()


@vm.command(name='stop')
@click.argument('name')
@async_command
async def stop_vm(name: str):
    """Stop a VM."""
    try:
        logger.command(f"🔴 Stopping VM '{name}'")

        # Get VM details using database service
        logger.process("Retrieving VM details")
        vm = await db_service.get_vm(name)
        if not vm:
            raise click.BadParameter(f"VM '{name}' not found")

        # Initialize VM service
        provider_url = config.get_provider_url(vm['provider_ip'])
        async with ProviderClient(provider_url) as client:
            # Initialize blockchain client for stream termination on stop
            from ..payments.blockchain_service import StreamPaymentClient, StreamPaymentConfig
            spc = StreamPaymentConfig(
                rpc_url=config.polygon_rpc_url,
                contract_address=config.stream_payment_address,
                glm_token_address=config.glm_token_address,
                private_key=config.ethereum_private_key,
            )
            sp_client = StreamPaymentClient(spc)
            vm_service = VMService(db_service, SSHService(config.ssh_key_dir), client, sp_client)
            await vm_service.stop_vm(name)

        # Show fancy success message
        click.echo("\n" + "─" * 60)
        click.echo(click.style("  🔴 VM Stopped Successfully!", fg="yellow", bold=True))
        click.echo("─" * 60 + "\n")

        click.echo(click.style("  VM Status", fg="blue", bold=True))
        click.echo("  " + "┈" * 25)
        click.echo(f"  🏷️  Name      : {click.style(name, fg='cyan')}")
        click.echo(f"  💫 Status     : {click.style('stopped', fg='yellow')}")
        click.echo(f"  💾 Resources  : {click.style('preserved', fg='cyan')}")

        click.echo("\n" + "─" * 60)

    except Exception as e:
        error_msg = str(e)
        if "Not Found" in error_msg:
            error_msg = "VM not found on provider (it may have been manually removed)"
        logger.error(f"Failed to stop VM: {error_msg}")
        raise click.Abort()


@cli.group()
def server():
    """Server management commands"""
    pass


@server.command(name='api')
@click.option('--host', default='127.0.0.1', help='Host to bind the API server to.')
@click.option('--port', default=8000, type=int, help='Port to run the API server on.')
@click.option('--reload', is_flag=True, help='Enable auto-reload for development.')
def run_api_server(host: str, port: int, reload: bool):
    """Run the Requestor API server."""
    logger.command(f"🚀 Starting Requestor API server on {host}:{port}")
    if reload:
        logger.warning("Auto-reload enabled (for development)")

    # Ensure the database directory exists before starting uvicorn
    try:
        config.db_path.parent.mkdir(parents=True, exist_ok=True)
        logger.detail(f"Ensured database directory exists: {config.db_path.parent}")
    except Exception as e:
        logger.error(f"Failed to create database directory {config.db_path.parent}: {e}")
        raise click.Abort()

    uvicorn.run(
        "requestor.api.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info" # Or adjust as needed
    )


@vm.command(name='list')
@click.option('--json', 'as_json', is_flag=True, help='Output in JSON format')
@async_command
async def list_vms(as_json: bool):
    """List all VMs."""
    try:
        if as_json:
            os.environ["GOLEM_SILENCE_LOGS"] = "1"
        logger.command("📋 Listing your VMs")
        logger.process("Fetching VM details")

        # Initialize VM service with temporary client (not needed for listing)
        ssh_service = SSHService(config.ssh_key_dir)
        vm_service = VMService(db_service, ssh_service, None)
        vms = await vm_service.list_vms()
        if not vms:
            logger.warning("No VMs found")
            return {"vms": []}

        result = {"vms": vms}

        if as_json:
            click.echo(json.dumps(result, indent=2))
        else:
            # Format VM information using service
            headers = vm_service.vm_headers
            rows = [vm_service.format_vm_row(vm, colorize=True) for vm in vms]

            # Show fancy header
            click.echo("\n" + "─" * 60)
            click.echo(click.style(f"  📋 Your VMs ({len(vms)} total)", fg="blue", bold=True))
            click.echo("─" * 60)

            # Show table with colored status
            click.echo("\n" + tabulate(
                rows,
                headers=[click.style(h, bold=True) for h in headers],
                tablefmt="grid"
            ))
            click.echo("\n" + "─" * 60)
        return result

    except Exception as e:
        error_msg = str(e)
        if "database" in error_msg.lower():
            error_msg = "Failed to access local database (try running the command again)"
        logger.error(f"Failed to list VMs: {error_msg}")
        raise click.Abort()

    finally:
        if as_json:
            try:
                del os.environ["GOLEM_SILENCE_LOGS"]
            except Exception:
                pass


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == '__main__':
    main()


@vm.command(name='stats')
@click.argument('name')
@async_command
async def vm_stats(name: str):
    """Display live resource usage statistics for a VM."""
    try:
        # Initialize services
        ssh_service = SSHService(config.ssh_key_dir)
        vm_service = VMService(db_service, ssh_service)

        # Get VM details
        vm = await vm_service.get_vm(name)
        if not vm:
            raise click.BadParameter(f"VM '{name}' not found")

        # Loop to fetch and display stats continuously
        while True:
            stats = await vm_service.get_vm_stats(name)
            
            click.clear()
            click.echo("\n" + "─" * 60)
            click.echo(click.style(f"  📊 Live Stats for VM: {name} (Press Ctrl+C to exit)", fg="blue", bold=True))
            click.echo("─" * 60)
            
            if 'cpu' in stats and 'usage' in stats['cpu']:
                click.echo(f"  💻 CPU Usage : {click.style(stats['cpu']['usage'], fg='cyan')}")
            if 'memory' in stats and 'used' in stats['memory']:
                click.echo(f"  🧠 Memory    : {click.style(stats['memory']['used'], fg='cyan')} / {click.style(stats['memory']['total'], fg='cyan')}")
            if 'disk' in stats and 'used' in stats['disk']:
                click.echo(f"  💾 Disk      : {click.style(stats['disk']['used'], fg='cyan')} / {click.style(stats['disk']['total'], fg='cyan')}")
            
            click.echo("─" * 60)
            
            await asyncio.sleep(2)  # Update every 2 seconds

    except Exception as e:
        logger.error(f"Failed to get VM stats: {str(e)}")
        raise click.Abort()
