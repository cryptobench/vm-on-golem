"""CLI interface for VM on Golem."""
import asyncio
from functools import wraps
from typing import Optional
from pathlib import Path
import subprocess
import json
import aiohttp
from tabulate import tabulate
import uvicorn
import click
import typer
try:
    from importlib import metadata
except ImportError:
    # Python < 3.8
    import importlib_metadata as metadata

from ..config import config
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
    @wraps(f)
    def wrapper(*args, **kwargs):
        async def run():
            await db_service.init()
            return await f(*args, **kwargs)
        return asyncio.run(run())
    return wrapper


def print_version(value: bool):
    if not value:
        return
    try:
        version = metadata.version('request-vm-on-golem')
    except metadata.PackageNotFoundError:
        version = 'unknown'
    typer.echo(f'Requestor VM on Golem CLI version {version}')
    raise typer.Exit()


cli = typer.Typer()
vm = typer.Typer()
server = typer.Typer()

cli.add_typer(vm, name="vm")
cli.add_typer(server, name="server")


@cli.callback()
def main(version: bool = typer.Option(False, "--version", callback=print_version, is_eager=True, help="Show the version and exit.")):
    """VM on Golem management CLI"""
    pass


@vm.command(name='providers')
@async_command
async def list_providers(
    cpu: Optional[int] = typer.Option(None, "--cpu", help="Minimum CPU cores required"),
    memory: Optional[int] = typer.Option(None, "--memory", help="Minimum memory (GB) required"),
    storage: Optional[int] = typer.Option(None, "--storage", help="Minimum storage (GB) required"),
    country: Optional[str] = typer.Option(None, "--country", help="Preferred provider country"),
    driver: Optional[str] = typer.Option(None, "--driver", help="Discovery driver to use"),
):
    """List available providers matching requirements."""
    try:
        # Log search criteria if any
        if any([cpu, memory, storage, country]):
            logger.command("🔍 Searching for providers with criteria:")
            if cpu:
                logger.detail(f"CPU Cores: {cpu}+")
            if memory:
                logger.detail(f"Memory: {memory}GB+")
            if storage:
                logger.detail(f"Storage: {storage}GB+")
            if country:
                logger.detail(f"Country: {country}")
        
        # Determine the discovery driver being used
        discovery_driver = driver or config.discovery_driver
        logger.process(f"Querying discovery service via {discovery_driver}")
        
        # Initialize provider service
        provider_service = ProviderService()
        async with provider_service:
            providers = await provider_service.find_providers(
                cpu=cpu,
                memory=memory,
                storage=storage,
                country=country,
                driver=driver
            )

        if not providers:
            logger.warning("No providers found matching criteria")
            return

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

    except Exception as e:
        logger.error(f"Failed to list providers: {str(e)}")
        raise typer.Exit(code=1)


@vm.command(name='create')
@async_command
async def create_vm(
    name: str = typer.Argument(...),
    provider_id: str = typer.Option(..., '--provider-id', help='Provider ID to use'),
    cpu: int = typer.Option(..., '--cpu', help='Number of CPU cores'),
    memory: int = typer.Option(..., '--memory', help='Memory in GB'),
    storage: int = typer.Option(..., '--storage', help='Storage in GB'),
):
    """Create a new VM on a specific provider."""
    try:
        # Show configuration details
        click.echo("\n" + "─" * 60)
        click.echo(click.style("  VM Configuration", fg="blue", bold=True))
        click.echo("─" * 60)
        click.echo(f"  Provider   : {click.style(provider_id, fg='cyan')}")
        click.echo(f"  Resources  : {click.style(f'{cpu} CPU, {memory}GB RAM, {storage}GB Storage', fg='cyan')}")
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

                # Setup SSH
                ssh_service = SSHService(config.ssh_key_dir)
                key_pair = await ssh_service.get_key_pair()

                # Initialize VM service
                provider_url = config.get_provider_url(provider_ip)
                async with ProviderClient(provider_url) as client:
                    vm_service = VMService(db_service, ssh_service, client)
                    
                    # Create VM
                    vm = await vm_service.create_vm(
                        name=name,
                        cpu=cpu,
                        memory=memory,
                        storage=storage,
                        provider_ip=provider_ip,
                        ssh_key=key_pair.public_key_content
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
        click.echo(f"  💻 Resources  : {click.style(f'{cpu} CPU, {memory}GB RAM, {storage}GB Storage', fg='cyan')}")
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
        raise typer.Exit(code=1)


@vm.command(name='ssh')
@async_command
async def ssh_vm(name: str = typer.Argument(...)):
    """SSH into a VM."""
    try:
        logger.command(f"🔌 Connecting to VM '{name}'")
        
        # Initialize services
        ssh_service = SSHService(config.ssh_key_dir)
        
        # Get VM details using database service
        logger.process("Retrieving VM details")
        vm = await db_service.get_vm(name)
        if not vm:
            raise typer.BadParameter(f"VM '{name}' not found")

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
        raise typer.Exit(code=1)


@vm.command(name='info')
@async_command
async def info_vm(
    name: str = typer.Argument(...),
    json_output: bool = typer.Option(
        False, "--json", help="Output VM information in JSON format"
    ),
):
    """Show information about a VM."""
    try:
        logger.command(f"ℹ️  Getting info for VM '{name}'")

        # Initialize VM service
        ssh_service = SSHService(config.ssh_key_dir)
        vm_service = VMService(db_service, ssh_service)

        # Retrieve VM details
        vm = await vm_service.get_vm(name)
        if not vm:
            raise typer.BadParameter(f"VM '{name}' not found")

        if json_output:
            typer.echo(json.dumps(vm))
            return

        headers = [
            "Status",
            "IP Address",
            "SSH Port",
            "CPU",
            "Memory (GB)",
            "Storage (GB)",
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

    except Exception as e:
        logger.error(f"Failed to get VM info: {str(e)}")
        raise typer.Exit(code=1)


@vm.command(name='destroy')
@async_command
async def destroy_vm(name: str = typer.Argument(...)):
    """Destroy a VM."""
    try:
        logger.command(f"💥 Destroying VM '{name}'")

        # Get VM details using database service
        logger.process("Retrieving VM details")
        vm = await db_service.get_vm(name)
        if not vm:
            raise typer.BadParameter(f"VM '{name}' not found")

        # Initialize VM service
        provider_url = config.get_provider_url(vm['provider_ip'])
        async with ProviderClient(provider_url) as client:
            vm_service = VMService(db_service, SSHService(config.ssh_key_dir), client)
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
        raise typer.Exit(code=1)


@vm.command(name='purge')
@async_command
async def purge_vms(
    force: bool = typer.Option(False, "--force", help="Force purge even if other errors occur"),
):
    """Purge all VMs and clean up local database."""
    if not typer.confirm('Are you sure you want to purge all VMs?'):
        raise typer.Abort()
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
                    vm_service = VMService(db_service, SSHService(config.ssh_key_dir), client)
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
        raise typer.Exit(code=1)


@vm.command(name='start')
@async_command
async def start_vm(name: str = typer.Argument(...)):
    """Start a VM."""
    try:
        logger.command(f"🟢 Starting VM '{name}'")

        # Get VM details using database service
        logger.process("Retrieving VM details")
        vm = await db_service.get_vm(name)
        if not vm:
            raise typer.BadParameter(f"VM '{name}' not found")

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
        raise typer.Exit(code=1)


@vm.command(name='stop')
@async_command
async def stop_vm(name: str = typer.Argument(...)):
    """Stop a VM."""
    try:
        logger.command(f"🔴 Stopping VM '{name}'")

        # Get VM details using database service
        logger.process("Retrieving VM details")
        vm = await db_service.get_vm(name)
        if not vm:
            raise typer.BadParameter(f"VM '{name}' not found")

        # Initialize VM service
        provider_url = config.get_provider_url(vm['provider_ip'])
        async with ProviderClient(provider_url) as client:
            vm_service = VMService(db_service, SSHService(config.ssh_key_dir), client)
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
        raise typer.Exit(code=1)


@server.command(name='api')
def run_api_server(
    host: str = typer.Option('127.0.0.1', '--host', help='Host to bind the API server to.'),
    port: int = typer.Option(8000, '--port', help='Port to run the API server on.'),
    reload: bool = typer.Option(False, '--reload', help='Enable auto-reload for development.'),
):
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
        raise typer.Exit(code=1)

    uvicorn.run(
        "requestor.api.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info" # Or adjust as needed
    )


@vm.command(name='list')
@async_command
async def list_vms():
    """List all VMs."""
    try:
        logger.command("📋 Listing your VMs")
        logger.process("Fetching VM details")
        
        # Initialize VM service with temporary client (not needed for listing)
        ssh_service = SSHService(config.ssh_key_dir)
        vm_service = VMService(db_service, ssh_service, None)
        vms = await vm_service.list_vms()
        if not vms:
            logger.warning("No VMs found")
            return

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

    except Exception as e:
        error_msg = str(e)
        if "database" in error_msg.lower():
            error_msg = "Failed to access local database (try running the command again)"
        logger.error(f"Failed to list VMs: {error_msg}")
        raise typer.Exit(code=1)


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == '__main__':
    main()


@vm.command(name='stats')
@async_command
async def vm_stats(name: str = typer.Argument(...)):
    """Display live resource usage statistics for a VM."""
    try:
        # Initialize services
        ssh_service = SSHService(config.ssh_key_dir)
        vm_service = VMService(db_service, ssh_service)

        # Get VM details
        vm = await vm_service.get_vm(name)
        if not vm:
            raise typer.BadParameter(f"VM '{name}' not found")

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
        raise typer.Exit(code=1)
