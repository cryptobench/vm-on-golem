import click
import asyncio
from typing import Optional
from pathlib import Path
import subprocess
import aiohttp
from tabulate import tabulate

from ..config import config
from ..provider.client import ProviderClient
from ..ssh.manager import SSHKeyManager
from ..db.sqlite import Database
from ..errors import RequestorError
from ..utils.logging import setup_logger
from ..utils.spinner import step

# Initialize logger
logger = setup_logger('golem.requestor')

# Initialize components
db = Database(config.db_path)


def async_command(f):
    """Decorator to run async commands."""
    async def wrapper(*args, **kwargs):
        # Initialize database
        await db.init()
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
        
        params = {
            k: v for k, v in {
                'cpu': cpu,
                'memory': memory,
                'storage': storage,
                'country': country
            }.items() if v is not None
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{config.discovery_url}/api/v1/advertisements",
                params=params
            ) as response:
                if not response.ok:
                    raise RequestorError("Failed to query discovery service")
                providers = await response.json()

        if not providers:
            logger.warning("No providers found matching criteria")
            return

        # Format provider information
        headers = ["Provider ID", "IP Address", "Country",
                   "CPU", "Memory (GB)", "Storage (GB)", "Updated"]
        rows = []
        for p in providers:
            # Get provider IP based on environment
            provider_ip = 'localhost' if config.environment == "development" else p.get(
                'ip_address')
            if not provider_ip and config.environment == "production":
                logger.warning(f"Provider {p['provider_id']} has no IP address")
                provider_ip = 'N/A'
            rows.append([
                p['provider_id'],
                provider_ip,
                p['country'],
                p['resources']['cpu'],
                p['resources']['memory'],
                p['resources']['storage'],
                p['updated_at']
            ])

        # Show fancy header
        click.echo("\n" + "─" * 60)
        click.echo(click.style(f"  🌍 Available Providers ({len(providers)} total)", fg="blue", bold=True))
        click.echo("─" * 60)

        # Add color and formatting to columns
        for row in rows:
            # Format Provider ID to be more readable
            row[0] = click.style(row[0], fg="yellow")  # Provider ID
            
            # Format resources with icons and colors
            row[3] = click.style(f"💻 {row[3]}", fg="cyan", bold=True)  # CPU
            row[4] = click.style(f"🧠 {row[4]}", fg="cyan", bold=True)  # Memory
            row[5] = click.style(f"💾 {row[5]}", fg="cyan", bold=True)  # Storage
            
            # Format location info
            row[2] = click.style(f"🌍 {row[2]}", fg="green", bold=True)  # Country

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


# Helper functions for VM creation with spinners
@step("Checking VM name availability")
async def check_vm_name(db, name):
    existing_vm = await db.get_vm(name)
    if existing_vm:
        raise RequestorError(f"VM with name '{name}' already exists")

@step("Locating provider")
async def find_provider(discovery_url, provider_id):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{discovery_url}/api/v1/advertisements") as response:
            if not response.ok:
                raise RequestorError("Failed to query discovery service")
            providers = await response.json()
    
    provider = next((p for p in providers if p['provider_id'] == provider_id), None)
    if not provider:
        raise RequestorError(f"Provider {provider_id} not found")
    return provider

@step("Verifying resource availability")
async def verify_resources(provider, cpu, memory, storage):
    if (cpu > provider['resources']['cpu'] or
        memory > provider['resources']['memory'] or
            storage > provider['resources']['storage']):
        raise RequestorError("Requested resources exceed provider capacity")

@step("Setting up SSH access")
async def setup_ssh(ssh_manager):
    return await ssh_manager.get_key_pair()

@step("Deploying VM on provider")
async def deploy_vm(client, name, cpu, memory, storage, ssh_key):
    return await client.create_vm(
        name=name,
        cpu=cpu,
        memory=memory,
        storage=storage,
        ssh_key=ssh_key
    )

@step("Configuring VM access")
async def get_vm_access(client, vm_id):
    return await client.get_vm_access(vm_id)

@step("Saving VM configuration")
async def save_vm_config(db, name, provider_ip, vm_id, config):
    await db.save_vm(
        name=name,
        provider_ip=provider_ip,
        vm_id=vm_id,
        config=config
    )

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
        logger.command(f"🚀 Creating VM '{name}'")
        logger.detail(f"Provider: {provider_id}")
        logger.detail(f"Resources: {cpu} CPU, {memory}GB RAM, {storage}GB Storage")

        # Check VM name
        await check_vm_name(db, name)

        # Find and verify provider
        provider = await find_provider(config.discovery_url, provider_id)
        await verify_resources(provider, cpu, memory, storage)

        # Setup SSH
        ssh_manager = SSHKeyManager(config.ssh_key_dir)
        key_pair = await setup_ssh(ssh_manager)

        # Get provider IP
        provider_ip = 'localhost' if config.environment == "development" else provider.get('ip_address')
        if not provider_ip and config.environment == "production":
            raise RequestorError("Provider IP address not found in advertisement")

        # Create and configure VM
        provider_url = config.get_provider_url(provider_ip)
        async with ProviderClient(provider_url) as client:
            # Create VM and get full VM ID
            vm = await deploy_vm(client, name, cpu, memory, storage, key_pair.public_key_content)
            access_info = await get_vm_access(client, vm['id'])
            
            # Store the full VM ID from access info
            full_vm_id = access_info['vm_id']
            
            await save_vm_config(
                db, name, provider_ip, full_vm_id,
                {
                    'cpu': cpu,
                    'memory': memory,
                    'storage': storage,
                    'ssh_port': access_info['ssh_port']
                }
            )

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
        click.echo(f"  🔌 Port       : {click.style(str(access_info['ssh_port']), fg='cyan')}")
        
        # Quick Connect Section
        click.echo("\n" + click.style("  Quick Connect", fg="blue", bold=True))
        click.echo("  " + "┈" * 25)
        ssh_command = f"ssh -i {key_pair.private_key.absolute()} -p {access_info['ssh_port']} ubuntu@{provider_ip}"
        click.echo(f"  🔑 SSH Command : {click.style(ssh_command, fg='yellow')}")
        
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


@vm.command(name='ssh')
@click.argument('name')
@async_command
async def ssh_vm(name: str):
    """SSH into a VM."""
    try:
        logger.command(f"🔌 Connecting to VM '{name}'")
        
        # Get VM details
        logger.process("Retrieving VM details")
        vm = await db.get_vm(name)
        if not vm:
            raise click.BadParameter(f"VM '{name}' not found")

        # Get SSH key
        logger.process("Loading SSH credentials")
        ssh_manager = SSHKeyManager(config.ssh_key_dir)
        key_pair = await ssh_manager.get_key_pair()

        # Get VM access info
        logger.process("Fetching connection details")
        provider_url = config.get_provider_url(vm['provider_ip'])
        async with ProviderClient(provider_url) as client:
            access_info = await client.get_vm_access(vm['vm_id'])

        # Execute SSH command
        logger.success(f"Connecting to {vm['provider_ip']}:{access_info['ssh_port']}")
        cmd = [
            "ssh",
            "-i", str(key_pair.private_key.absolute()),
            "-p", str(access_info['ssh_port']),
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            f"ubuntu@{vm['provider_ip']}"
        ]
        subprocess.run(cmd)

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

        # Get VM details
        logger.process("Retrieving VM details")
        vm = await db.get_vm(name)
        if not vm:
            raise click.BadParameter(f"VM '{name}' not found")

        try:
            # Connect to provider using full VM ID
            logger.process("Requesting VM termination")
            provider_url = config.get_provider_url(vm['provider_ip'])
            async with ProviderClient(provider_url) as client:
                await client.destroy_vm(vm['vm_id'])
                logger.success("VM terminated on provider")
        except Exception as e:
            error_msg = str(e)
            if "Not Found" in error_msg:
                logger.warning("VM already removed from provider")
            else:
                raise

        # Always remove from database
        logger.process("Cleaning up VM records")
        await db.delete_vm(name)
        
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
        
        # Get all VMs
        logger.process("Retrieving all VM details")
        vms = await db.list_vms()
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
                
                try:
                    # Try to destroy on provider using full VM ID
                    provider_url = config.get_provider_url(vm['provider_ip'])
                    async with ProviderClient(provider_url) as client:
                        # Get latest VM access info to ensure we have the correct ID
                        try:
                            access_info = await client.get_vm_access(vm['vm_id'])
                            full_vm_id = access_info['vm_id']
                        except Exception:
                            # If we can't get access info, use stored VM ID
                            full_vm_id = vm['vm_id']
                        
                        await client.destroy_vm(full_vm_id)
                    results['success'].append((vm['name'], 'Destroyed successfully'))
                except Exception as e:
                    error_msg = str(e)
                    if "Not Found" in error_msg:
                        results['success'].append((vm['name'], 'Already removed from provider'))
                    else:
                        if not force:
                            raise
                        results['failed'].append((vm['name'], f"Provider error: {error_msg}"))

                # Always remove from local database
                await db.delete_vm(vm['name'])
                
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

        # Get VM details
        logger.process("Retrieving VM details")
        vm = await db.get_vm(name)
        if not vm:
            raise click.BadParameter(f"VM '{name}' not found")

        # Connect to provider
        logger.process("Powering up VM")
        provider_url = config.get_provider_url(vm['provider_ip'])
        async with ProviderClient(provider_url) as client:
            await client.start_vm(vm['vm_id'])
            await db.update_vm_status(name, "running")

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

        # Get VM details
        logger.process("Retrieving VM details")
        vm = await db.get_vm(name)
        if not vm:
            raise click.BadParameter(f"VM '{name}' not found")

        # Connect to provider
        logger.process("Shutting down VM")
        provider_url = config.get_provider_url(vm['provider_ip'])
        async with ProviderClient(provider_url) as client:
            await client.stop_vm(vm['vm_id'])
            await db.update_vm_status(name, "stopped")

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


@vm.command(name='list')
@async_command
async def list_vms():
    """List all VMs."""
    try:
        logger.command("📋 Listing your VMs")
        logger.process("Fetching VM details")
        
        vms = await db.list_vms()
        if not vms:
            logger.warning("No VMs found")
            return

        headers = ["Name", "Status", "IP Address", "SSH Port",
                   "CPU", "Memory (GB)", "Storage (GB)", "Created"]
        rows = []
        for vm in vms:
            rows.append([
                vm['name'],
                vm['status'],
                vm['provider_ip'],
                vm['config'].get('ssh_port', 'N/A'),
                vm['config']['cpu'],
                vm['config']['memory'],
                vm['config']['storage'],
                vm['created_at']
            ])

        # Show fancy header
        click.echo("\n" + "─" * 60)
        click.echo(click.style(f"  📋 Your VMs ({len(vms)} total)", fg="blue", bold=True))
        click.echo("─" * 60)
        
        # Add color to status column (index 1)
        for i, row in enumerate(rows):
            status = row[1]
            if status == "running":
                rows[i][1] = click.style("● " + status, fg="green", bold=True)
            elif status == "stopped":
                rows[i][1] = click.style("● " + status, fg="yellow", bold=True)
            else:
                rows[i][1] = click.style("● " + status, fg="red", bold=True)
        
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
