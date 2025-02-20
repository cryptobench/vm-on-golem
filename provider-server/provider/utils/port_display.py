"""Port verification display utilities."""
import time
import sys
import asyncio
from typing import Dict, List, Optional
from ..network.port_verifier import PortVerificationResult

class PortVerificationDisplay:
    """Display utilities for port verification status."""
    
    SPINNER_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    
    def __init__(self, provider_port: int, port_range_start: int, port_range_end: int):
        """Initialize the display.
        
        Args:
            provider_port: Port used for provider access
            port_range_start: Start of VM access port range
            port_range_end: End of VM access port range
        """
        self.provider_port = provider_port
        self.port_range_start = port_range_start
        self.port_range_end = port_range_end
        self.spinner_idx = 0
    
    def _update_spinner(self):
        """Update and return the next spinner frame."""
        frame = self.SPINNER_FRAMES[self.spinner_idx]
        self.spinner_idx = (self.spinner_idx + 1) % len(self.SPINNER_FRAMES)
        return frame
    
    async def animate_verification(self, text: str, duration: float = 1.0):
        """Show an animated spinner while verifying.
        
        Args:
            text: Text to show with spinner
            duration: How long to show the animation
        """
        start_time = time.time()
        while time.time() - start_time < duration:
            sys.stdout.write(f"\r{self._update_spinner()} {text}")
            sys.stdout.flush()
            await asyncio.sleep(0.1)
        sys.stdout.write("\r" + " " * (len(text) + 2) + "\r")
        sys.stdout.flush()
    
    def print_header(self):
        """Print the verification status header."""
        print("\n🌟 Port Verification Status")
        print("==========================")
        
    async def print_discovery_status(self, result: PortVerificationResult):
        """Print discovery service status with tree structure.
        
        Args:
            result: Verification result for discovery port
        """
        print("\n📡 Provider Accessibility (Required)")
        print("--------------------------------")
        
        await self.animate_verification("Checking provider accessibility...")
        
        status_badge = "✅ Accessible" if result.accessible else "❌ Not Accessible"
        print(f"[{status_badge}] Port {self.provider_port}")
        print(f"└─ Status: {'Accessible' if result.accessible else 'Not Accessible'}")
        
        # Show external/internal access
        if result.accessible:
            print("└─ Access: External ✓ | Internal ✓")
            print("└─ Requestors can discover and connect to your provider")
        else:
            print("└─ Access: External ✗ | Internal ✗")
            print("└─ Requestors cannot discover or connect to your provider")
            
        # Show verification server if successful
        if result.verified_by:
            print(f"└─ Verified By: {result.verified_by}")
            
    async def print_ssh_status(self, results: Dict[int, PortVerificationResult]):
        """Print SSH ports status with progress bar.
        
        Args:
            results: Dictionary mapping ports to their verification results
        """
        print("\n🔒 VM Access Ports (Required)")
        print("-------------------------")
        
        await self.animate_verification("Scanning VM access ports...")
        
        # Calculate progress
        total_ports = len(results)
        accessible_ports = sum(1 for r in results.values() if r.accessible)
        percentage = (accessible_ports / total_ports) * 100 if total_ports > 0 else 0
        
        # Create animated progress bar
        bar_width = 30
        for i in range(bar_width + 1):
            filled = int(i * percentage / 100)
            bar = "█" * filled + "░" * (bar_width - filled)
            sys.stdout.write(f"\r[{bar}] {percentage:.1f}%")
            sys.stdout.flush()
            time.sleep(0.02)
        print()
        
        # List available ports
        available = [port for port, result in results.items() if result.accessible]
        if available:
            print(f"\nAvailable Ports: {', '.join(map(str, sorted(available)))}")
        else:
            print("\nAvailable Ports: None")
            
        print(f"Required: At least 1 port in range {self.port_range_start}-{self.port_range_end}")
        
    def print_critical_issues(self, discovery_result: PortVerificationResult, 
                            ssh_results: Dict[int, PortVerificationResult]):
        """Print critical issues with actionable items.
        
        Args:
            discovery_result: Verification result for discovery port
            ssh_results: Dictionary mapping SSH ports to their verification results
        """
        issues = []
        
        # Check discovery port
        if not discovery_result.accessible:
            issues.append((f"Port {self.provider_port} is not accessible",
                         "Requestors cannot discover or connect to your provider",
                         f"Configure port forwarding for port {self.provider_port}"))
            
        # Check SSH ports
        if not any(r.accessible for r in ssh_results.values()):
            issues.append(("No VM access ports are accessible",
                         "Requestors will not be able to access their rented VMs",
                         f"Configure port forwarding for range {self.port_range_start}-{self.port_range_end}"))
            
        if issues:
            print("\n🚨 Critical Issues")
            print("---------------")
            for i, (issue, impact, action) in enumerate(issues, 1):
                print(f"{i}. {issue}")
                print(f"   ↳ {impact}")
                print(f"   ↳ Action: {action}")
                
    def print_quick_fix(self, discovery_result: PortVerificationResult,
                       ssh_results: Dict[int, PortVerificationResult]):
        """Print quick fix guide only if there are issues.
        
        Args:
            discovery_result: Verification result for discovery port
            ssh_results: Dictionary mapping SSH ports to their verification results
        """
        # Check if we have any issues
        has_issues = (
            not discovery_result.accessible or 
            not any(r.accessible for r in ssh_results.values())
        )
        
        if has_issues:
            print("\n💡 Quick Fix Guide")
            print("---------------")
            
            print("1. Check your router's port forwarding settings")
            print(f"   ↳ Forward ports {self.port_range_start}-{self.port_range_end} to this machine")
            print("   ↳ Tutorial: docs.golem.network/port-forwarding")
            
            print("\n2. Verify firewall rules")
            print("   ↳ Allow incoming TCP connections on ports:")
            print(f"     • {self.provider_port} (Provider Access)")
            print(f"     • {self.port_range_start}-{self.port_range_end} (VM Access)")
            print("   ↳ Tutorial: docs.golem.network/firewall-setup")
            
            print("\nNeed help? Visit our troubleshooting guide: docs.golem.network/ports")
        
    def print_summary(self, discovery_result: PortVerificationResult,
                     ssh_results: Dict[int, PortVerificationResult]):
        """Print a precise, actionable summary of the verification status.
        
        Args:
            discovery_result: Verification result for discovery port
            ssh_results: Dictionary mapping SSH ports to their verification results
        """
        print("\n🎯 Current Status:", end=" ")
        
        accessible_ssh_ports = [port for port, result in ssh_results.items() if result.accessible]
        
        if not discovery_result.accessible:
            print("Provider Not Discoverable")
            print(f"└─ Reason: Port {self.provider_port} is not accessible")
            print("└─ Impact: Requestors cannot find or connect to your provider")
            print(f"└─ Fix: Configure port forwarding for port {self.provider_port}")
            
        elif not accessible_ssh_ports:
            print("VMs Not Accessible")
            print("└─ Reason: No VM access ports are available")
            print("└─ Impact: Requestors will not be able to access their rented VMs")
            print(f"└─ Fix: Configure port forwarding for range {self.port_range_start}-{self.port_range_end}")
            
        else:
            status = "Provider Ready" if len(accessible_ssh_ports) > 5 else "Provider Ready with Limited Capacity"
            print(status)
            print(f"└─ Available: {len(accessible_ssh_ports)} SSH ports ({', '.join(map(str, sorted(accessible_ssh_ports)[:3]))}{'...' if len(accessible_ssh_ports) > 3 else ''})")
            print(f"└─ Capacity: Can handle up to {len(accessible_ssh_ports)} concurrent VMs")
            if len(accessible_ssh_ports) <= 5:
                print("└─ Recommendation: Open more ports for higher capacity")
