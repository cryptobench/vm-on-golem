"""Port verification display utilities."""
import time
import sys
import asyncio
from typing import Dict, List, Optional
from ..network.port_verifier import PortVerificationResult

class PortVerificationDisplay:
    """Display utilities for port verification status."""
    
    SPINNER_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    
    def __init__(self):
        """Initialize the display."""
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
        print("\n📡 Discovery Service (Required)")
        print("--------------------------")
        
        await self.animate_verification("Checking discovery service...")
        
        status_badge = "✅ Running" if result.accessible else "❌ Not Running"
        print(f"[{status_badge}] Port 7466")
        print(f"└─ Status: {'Running' if result.accessible else 'Not Running'}")
        
        # Show external/internal access
        if result.accessible:
            print("└─ Access: External ✓ | Internal ✓")
        else:
            print("└─ Access: External ✗ | Internal ✗")
            
        # Show verification server if successful
        if result.verified_by:
            print(f"└─ Verified By: {result.verified_by}")
            
    async def print_ssh_status(self, results: Dict[int, PortVerificationResult]):
        """Print SSH ports status with progress bar.
        
        Args:
            results: Dictionary mapping ports to their verification results
        """
        print("\n🔒 SSH Access Ports (Required)")
        print("-------------------------")
        
        await self.animate_verification("Scanning SSH ports...")
        
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
            
        print("Required: At least 1 port in range 50800-50900")
        
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
            issues.append(("Discovery port 7466 is not accessible",
                         "This will prevent provider registration",
                         "Configure port forwarding for port 7466"))
            
        # Check SSH ports
        if not any(r.accessible for r in ssh_results.values()):
            issues.append(("No SSH ports are accessible",
                         "This will prevent VM deployments",
                         "Configure port forwarding for range 50800-50900"))
            
        if issues:
            print("\n🚨 Critical Issues")
            print("---------------")
            for i, (issue, impact, action) in enumerate(issues, 1):
                print(f"{i}. {issue}")
                print(f"   ↳ {impact}")
                print(f"   ↳ Action: {action}")
                
    def print_quick_fix(self):
        """Print quick fix guide with tutorials."""
        print("\n💡 Quick Fix Guide")
        print("---------------")
        
        print("1. Check your router's port forwarding settings")
        print("   ↳ Forward ports 50800-50900 to this machine")
        print("   ↳ Tutorial: docs.golem.network/port-forwarding")
        
        print("\n2. Verify firewall rules")
        print("   ↳ Allow incoming TCP connections on ports:")
        print("     • 7466 (Discovery)")
        print("     • 50800-50900 (SSH)")
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
            print("Provider Cannot Start")
            print("└─ Reason: Discovery port 7466 is not accessible")
            print("└─ Impact: Cannot register with network")
            print("└─ Fix: Configure port forwarding for 7466")
            
        elif not accessible_ssh_ports:
            print("Provider Cannot Accept VMs")
            print("└─ Reason: No SSH ports are accessible")
            print("└─ Impact: Cannot deploy any VMs")
            print("└─ Fix: Configure port forwarding for range 50800-50900")
            
        else:
            status = "Provider Ready" if len(accessible_ssh_ports) > 5 else "Provider Ready with Limited Capacity"
            print(status)
            print(f"└─ Available: {len(accessible_ssh_ports)} SSH ports ({', '.join(map(str, sorted(accessible_ssh_ports)[:3]))}{'...' if len(accessible_ssh_ports) > 3 else ''})")
            print(f"└─ Capacity: Can handle up to {len(accessible_ssh_ports)} concurrent VMs")
            if len(accessible_ssh_ports) <= 5:
                print("└─ Recommendation: Open more ports for higher capacity")
