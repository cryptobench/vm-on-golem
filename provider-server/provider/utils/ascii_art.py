from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.style import Style
import time
import asyncio

# Initialize Rich console
console = Console()

# ASCII Art Logo
LOGO = """
[bold cyan] _    ____  __  __[/bold cyan]
[bold cyan]| |  / /  |/  / /___ _____[/bold cyan]
[bold cyan]| | / / /|_/ / __/ // / _ \\[/bold cyan]
[bold cyan]| |/ / /  / / /_/ _  /  __/[/bold cyan]
[bold cyan]|___/_/  /_/\\__/_//_/\\___/[/bold cyan]
[bold magenta]   ____  _   __[/bold magenta]   [bold yellow]______[/bold yellow]    [bold green]____  __    ________  ___ [/bold green]
[bold magenta]  / __ \\/ | / /[/bold magenta]  [bold yellow]/ ____/[/bold yellow]   [bold green]/ __ \\/ /   / ____/  |/  /[/bold green]
[bold magenta] / / / /  |/ /[/bold magenta]  [bold yellow]/ / __[/bold yellow]    [bold green]/ / / / /   / __/ / /|_/ / [/bold green]
[bold magenta]/ /_/ / /|  /[/bold magenta]  [bold yellow]/ /_/ /[/bold yellow]   [bold green]/ /_/ / /___/ /___/ /  / /  [/bold green]
[bold magenta]\\____/_/ |_/[/bold magenta]   [bold yellow]\\____/[/bold yellow]   [bold green]/_____/_____/_____/_/  /_/   [/bold green]
"""

# Spinner frames (reduced for faster animation)
SPINNER_FRAMES = ["⠋", "⠙", "⠸", "⠴"]

def display_logo():
    """Display the VM on Golem logo."""
    console.print(LOGO)
    console.print()

async def startup_animation():
    """Display startup animation."""
    display_logo()
    
    with Live(refresh_per_second=8) as live:
        # Startup message
        live.console.print("\n[bold yellow]🚀 Initializing VM on Golem Provider...[/bold yellow]")
        await asyncio.sleep(0.1)
        
        # Components check animation (reduced)
        components = [
            "Loading configuration",
            "Starting provider services",
            "Connecting to network"
        ]
        
        for component in components:
            for frame in SPINNER_FRAMES:
                live.update(f"[bold blue]{frame}[/bold blue] {component}...")
                await asyncio.sleep(0.1)
            live.console.print(f"[bold green]✓[/bold green] {component} [dim]complete[/dim]")
        
        # Final ready message
        live.console.print("\n[bold green]✨ VM on Golem Provider is ready![/bold green]")
        live.console.print("[bold cyan]🌐 Listening for incoming requests on port 7466[/bold cyan]")
        live.console.print("[dim]Press Ctrl+C to stop the server[/dim]")

async def vm_creation_animation(vm_name: str):
    """Display VM creation success message.
    
    Args:
        vm_name: Name of the VM being created
    """
    console.print(f"[bold green]✨ VM '{vm_name}' is now being rented. Access information has been forwarded to the requestor.[/bold green]")

def vm_status_change(vm_id: str, status: str, details: str = ""):
    """Display VM status change.
    
    Args:
        vm_id: VM identifier
        status: New status
        details: Additional details (optional)
    """
    # Only show final status
    if status.lower() == "running":
        console.print(f"[green]✓[/green] VM {vm_id} is {status.lower()}")
