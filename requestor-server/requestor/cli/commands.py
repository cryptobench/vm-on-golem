"""CLI interface for VM on Golem."""
import click
import asyncio
from typing import Optional
from pathlib import Path
import subprocess
import aiohttp
from tabulate import tabulate
import uvicorn

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
    async def wrapper(*args, **kwargs):
        # Initialize database
        await db_service.init()
        return await f(*args, **kwargs)
    return lambda *args, **kwargs: asyncio.run(wrapper(*args, **kwargs))


@click.group()
def cli():
    """VM on Golem management CLI"""
    pass


@cli.group()
def vm():
    """VM management commands"""
    pass


@vm.command(name='providers')
@click.option('--cpu', type=int, help='Minimum CPU cores required')
@click.option('--memory', type=int, help='Minimum memory (GB) required')
@click.option('--storage', type=int, help='Minimum storage (GB) required')
@click.option('--country', help='Preferred provider country')
@async_command
async def list_providers(cpu: Optional[int], memory: Optional[int], storage: Optional[int], country: Optional[str]):
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
        
        logger.process("Querying discovery service")
        
        # Initialize provider service
        provider_service = ProviderService(config.discovery_url)
        async with provider_service:
            providers = await provider_service.find_providers(
                cpu=cpu,
                memory=memory,
                storage=storage,
                country=country
            )

        if not providers:
            logger.warning("No providers found matching criteria")
            return

        # Format provider information using service with colors
        headers = provider_service.provider_headers
        rows = [provider_service.format_provider_row(p, colorize=True) for p in providers]

        # Show fancy header
        click.echo("\n" + "─" * 60)
        click.echo(click.style(f"  🌍 Available Providers ({len(providers)} total)", fg="blue", bold=True))
        click.echo("─" * 60)

        # Show table with colored headers
        click.echo("\n" + tabulate(
            rows,
            headers=[click.style(h, bold=True) for h in headers],
            tablefmt="grid"
        ))
        click.echo("\n" + "─" * 60)

    except Exception as e:
        logger.error(f"Failed to list providers: {str(e)}")
        raise click.Abort()


@vm.command(name='create')
@click.argument('name')
@click.option('--provider-id', required=True, help='Provider ID to use')
@click.option('--cpu', type=int, required=True, help='Number of CPU cores')
@click.option('--memory', type=int, required=True, help='Memory in GB')
@click.option('--storage', type=int, required=True, help='Storage in GB')
@async_command
async def create_vm(name: str, provider_id: str, cpu: int, memory: int, storage: int):
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
            provider_service = ProviderService(config.discovery_url)
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
                    vm_service = VMService(db_service, client)
                    
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
        raise click.Abort()
@vm.command(name='list')
@async_command
async def list_vms():
    """List all managed VMs."""
    try:
        logger.command("📋 Listing all managed VMs")

        # Get VMs using database service
        logger.process("Retrieving VM list from database")
        vms = await db_service.list_vms()

        if not vms:
            logger.warning("No VMs found in the database.")
            click.echo("\nNo VMs currently managed.")
            return

        # Format VM information
        headers = ["Name", "Status", "Provider IP", "SSH Port", "CPU", "Memory (GB)", "Storage (GB)"]
        rows = []
        for vm in vms:
            # Safely access config details
            config_data = vm.get('config', {})
            rows.append([
                vm.get('name', 'N/A'),
                vm.get('status', 'N/A'),
                vm.get('provider_ip', 'N/A'),
                config_data.get('ssh_port', 'N/A'),
                config_data.get('cpu', 'N/A'),
                config_data.get('memory', 'N/A'),
                config_data.get('storage', 'N/A'),
            ])

        # Show fancy header
        click.echo("\n" + "─" * 80)
        click.echo(click.style(f"  🖥️  Managed VMs ({len(vms)} total)", fg="blue", bold=True))
        click.echo("─" * 80)

        # Show table with colored headers
        click.echo("\n" + tabulate(
            rows,
            headers=[click.style(h, bold=True) for h in headers],
            tablefmt="grid"
        ))
        click.echo("\n" + "─" * 80)

    except Exception as e:
        logger.error(f"Failed to list VMs: {str(e)}")
        raise click.Abort()


@vm.command(name='ssh')
@click.argument('name')
@async_command
async def ssh_vm(name: str):
    """SSH into a VM."""
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
            vm_service = VMService(db_service, client)
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


@vm.command(name='destroy')
@click.argument('name')
@async_command
async def destroy_vm(name: str):
    """Destroy a VM."""
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
            vm_service = VMService(db_service, client)
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


@vm.command(name='purge')
@click.option('--force', is_flag=True, help='Force purge even if errors occur')
@click.confirmation_option(prompt='Are you sure you want to purge all VMs?')
@async_command
async def purge_vms(force: bool):
    """Purge all VMs and clean up local database."""
    try:
        logger.command("🌪️  Purging all VMs")
        
        # Get all VMs using database service
        logger.process("Retrieving all VM details")
        vms = await db_service.list_vms()
        if not vms:
            logger.warning("No VMs found to purge")
            return

        # Track results
        results = {
            'success': [],
            'failed': []
        }

        # Process each VM
        for vm in vms:
            try:
                logger.process(f"Purging VM '{vm['name']}'")
                
                # Initialize VM service
                provider_url = config.get_provider_url(vm['provider_ip'])
                async with ProviderClient(provider_url) as client:
                    vm_service = VMService(db_service, client)
                    try:
                        await vm_service.destroy_vm(vm['name'])
                        results['success'].append((vm['name'], 'Destroyed successfully'))
                    except Exception as e:
                        error_msg = str(e)
                        if "Not Found" in error_msg:
                            results['success'].append((vm['name'], 'Already removed from provider'))
                            # Still need to clean up database
                            await db_service.delete_vm(vm['name'])
                        else:
                            if not force:
                                raise
                            results['failed'].append((vm['name'], f"Provider error: {error_msg}"))
                
            except Exception as e:
                if not force:
                    raise
                results['failed'].append((vm['name'], str(e)))

        # Show results
        click.echo("\n" + "─" * 60)
        click.echo(click.style("  🌪️  VM Purge Complete", fg="blue", bold=True))
        click.echo("─" * 60 + "\n")

        # Success section
        if results['success']:
            click.echo(click.style("  ✅ Successfully Purged", fg="green", bold=True))
            click.echo("  " + "┈" * 25)
            for name, msg in results['success']:
                click.echo(f"  • {click.style(name, fg='cyan')}: {click.style(msg, fg='green')}")
            click.echo()

        # Failures section
        if results['failed']:
            click.echo(click.style("  ❌ Failed to Purge", fg="red", bold=True))
            click.echo("  " + "┈" * 25)
            for name, error in results['failed']:
                click.echo(f"  • {click.style(name, fg='cyan')}: {click.style(error, fg='red')}")
            click.echo()

        # Summary
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
        error_msg = str(e)
        if "database" in error_msg.lower():
            error_msg = "Failed to access local database"
        logger.error(f"Purge operation failed: {error_msg}")
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
            vm_service = VMService(db_service, client)
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
            vm_service = VMService(db_service, client)
            await vm_service.stop_vm(name)

        # Show fancy success message
        click.echo("\n" + "─" * 60)
        click.echo(click.style("  🔴 VM Stopped Successfully!", fg="yellow", bold=True))
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


@vm.command(name='list')
@async_command
async def list_vms():
    """List all VMs."""
    try:
        logger.command("📋 Listing your VMs")
        logger.process("Fetching VM details")
        
        # Initialize VM service with temporary client (not needed for listing)
        vm_service = VMService(db_service, None)
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
        raise click.Abort()


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == '__main__':
    main()
