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
            click.echo("No providers found matching criteria")
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
                click.echo(
                    f"Warning: Provider {p['provider_id']} has no IP address", err=True)
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

        click.echo("\nAvailable Providers:")
        click.echo(tabulate(rows, headers=headers, tablefmt="grid"))

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
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
        # Check if VM with this name already exists
        existing_vm = await db.get_vm(name)
        if existing_vm:
            raise RequestorError(f"VM with name '{name}' already exists")

        # Find provider
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{config.discovery_url}/api/v1/advertisements"
            ) as response:
                if not response.ok:
                    raise RequestorError("Failed to query discovery service")
                providers = await response.json()

        provider = next(
            (p for p in providers if p['provider_id'] == provider_id), None)
        if not provider:
            raise RequestorError(f"Provider {provider_id} not found")

        # Verify resources
        if (cpu > provider['resources']['cpu'] or
            memory > provider['resources']['memory'] or
                storage > provider['resources']['storage']):
            raise RequestorError(
                "Requested resources exceed provider capacity")

        # Get SSH key pair
        ssh_manager = SSHKeyManager(config.ssh_key_dir)
        key_pair = await ssh_manager.get_key_pair()

        # Get provider IP based on environment
        provider_ip = 'localhost' if config.environment == "development" else provider.get(
            'ip_address')
        if not provider_ip and config.environment == "production":
            raise RequestorError(
                "Provider IP address not found in advertisement")

        # Create VM
        provider_url = config.get_provider_url(provider_ip)
        async with ProviderClient(provider_url) as client:
            # Create VM with SSH key
            vm = await client.create_vm(
                name=name,
                cpu=cpu,
                memory=memory,
                storage=storage,
                ssh_key=key_pair.public_key_content
            )

            # Get VM access info
            access_info = await client.get_vm_access(vm['id'])

            # Save VM details
            await db.save_vm(
                name=name,
                provider_ip=provider_ip,
                vm_id=vm['id'],
                config={
                    'cpu': cpu,
                    'memory': memory,
                    'storage': storage,
                    'ssh_port': access_info['ssh_port']
                }
            )

        click.echo(f"""
✅ VM '{name}' created successfully!
-------------------------------------------------------------
SSH Access       : ssh -i {key_pair.private_key.absolute()} -p {access_info['ssh_port']} ubuntu@{provider_ip}
IP Address      : {provider_ip}
Port            : {access_info['ssh_port']}
VM Status       : running
Resources       : {cpu} CPU, {memory}GB RAM, {storage}GB Storage
-------------------------------------------------------------
Note: Remember to change your SSH password upon first login.
        """)

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        raise click.Abort()


@vm.command(name='ssh')
@click.argument('name')
@async_command
async def ssh_vm(name: str):
    """SSH into a VM."""
    try:
        # Get VM details
        vm = await db.get_vm(name)
        if not vm:
            raise click.BadParameter(f"VM '{name}' not found")

        # Get SSH key
        ssh_manager = SSHKeyManager(config.ssh_key_dir)
        key_pair = await ssh_manager.get_key_pair()

        # Get VM access info
        provider_url = config.get_provider_url(vm['provider_ip'])
        async with ProviderClient(provider_url) as client:
            access_info = await client.get_vm_access(vm['vm_id'])

        # Execute SSH command
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
        click.echo(f"Error: {str(e)}", err=True)
        raise click.Abort()


@vm.command(name='destroy')
@click.argument('name')
@async_command
async def destroy_vm(name: str):
    """Destroy a VM."""
    try:
        # Get VM details
        vm = await db.get_vm(name)
        if not vm:
            raise click.BadParameter(f"VM '{name}' not found")

        # Connect to provider
        provider_url = config.get_provider_url(vm['provider_ip'])
        async with ProviderClient(provider_url) as client:
            await client.destroy_vm(vm['vm_id'])

        # Remove from database
        await db.delete_vm(name)
        click.echo(f"VM '{name}' destroyed successfully")

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        raise click.Abort()


@vm.command(name='start')
@click.argument('name')
@async_command
async def start_vm(name: str):
    """Start a VM."""
    try:
        # Get VM details
        vm = await db.get_vm(name)
        if not vm:
            raise click.BadParameter(f"VM '{name}' not found")

        # Connect to provider
        provider_url = config.get_provider_url(vm['provider_ip'])
        async with ProviderClient(provider_url) as client:
            await client.start_vm(vm['vm_id'])
            await db.update_vm_status(name, "running")

        click.echo(f"VM '{name}' started successfully")

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        raise click.Abort()


@vm.command(name='stop')
@click.argument('name')
@async_command
async def stop_vm(name: str):
    """Stop a VM."""
    try:
        # Get VM details
        vm = await db.get_vm(name)
        if not vm:
            raise click.BadParameter(f"VM '{name}' not found")

        # Connect to provider
        provider_url = config.get_provider_url(vm['provider_ip'])
        async with ProviderClient(provider_url) as client:
            await client.stop_vm(vm['vm_id'])
            await db.update_vm_status(name, "stopped")

        click.echo(f"VM '{name}' stopped successfully")

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        raise click.Abort()


@vm.command(name='list')
@async_command
async def list_vms():
    """List all VMs."""
    try:
        vms = await db.list_vms()
        if not vms:
            click.echo("No VMs found")
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

        click.echo("\nYour VMs:")
        click.echo(tabulate(rows, headers=headers, tablefmt="grid"))

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        raise click.Abort()


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == '__main__':
    main()
