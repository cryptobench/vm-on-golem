#!/usr/bin/env python3
import asyncio
import aiohttp
import sys
import json
from typing import List

async def check_ports(ip: str, ports: List[int], server_url: str = "http://localhost:7466"):
    """Check port accessibility using the port checker service.
    
    Args:
        ip: IP address to check
        ports: List of ports to check
        server_url: URL of the port checker service
    """
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{server_url}/check-ports",
                json={
                    "provider_ip": ip,
                    "ports": ports
                }
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    print("\nPort Check Results:")
                    print("-" * 50)
                    print(f"Provider IP: {ip}")
                    print(f"Status: {'✅ Success' if result['success'] else '❌ Failed'}")
                    print("\nPort Details:")
                    for port, status in result["results"].items():
                        icon = "✅" if status["accessible"] else "❌"
                        error = f" ({status['error']})" if status["error"] else ""
                        print(f"{icon} Port {port}: {'Accessible' if status['accessible'] else 'Not accessible'}{error}")
                    print(f"\nSummary: {result['message']}")
                else:
                    print(f"Error: Server returned status {response.status}")
                    print(await response.text())
        except aiohttp.ClientError as e:
            print(f"Error connecting to port checker service: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")

def print_usage():
    """Print script usage instructions."""
    print("Usage: python check_ports.py <ip_address> [port1 port2 ...]")
    print("Example: python check_ports.py 192.168.1.100 7466 50800 50801")

async def main():
    """Main entry point."""
    if len(sys.argv) < 3:
        print_usage()
        sys.exit(1)
        
    ip = sys.argv[1]
    try:
        ports = [int(p) for p in sys.argv[2:]]
    except ValueError:
        print("Error: Ports must be valid numbers")
        print_usage()
        sys.exit(1)
        
    await check_ports(ip, ports)

if __name__ == "__main__":
    asyncio.run(main())
