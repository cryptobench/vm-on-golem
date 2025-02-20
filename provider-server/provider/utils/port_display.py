"""Port verification display utilities."""

class PortVerificationDisplay:
    """Display utilities for port verification status."""
    
    def print_header(self):
        """Print the verification status header."""
        print("\n🔍 Port Verification Status")
        print("=" * 50)
        
    def print_port_status(self, port: int, status: str, error: str = None, server: str = None, attempts=None):
        """Print status for a single port.
        
        Args:
            port: Port number
            status: Status string ('success' or 'failed')
            error: Optional error message
            server: Optional server that verified the port
            attempts: Optional list of server attempts
        """
        icon = "✅" if status == "success" else "❌"
        status_text = "SUCCESS" if status == "success" else "FAILED"
        print(f"{icon} Port {port}: {status_text}")
        
        # Show verification attempts
        if attempts:
            print("   Verification Attempts:")
            for attempt in attempts:
                attempt_icon = "✅" if attempt.success else "❌"
                print(f"   {attempt_icon} {attempt.server}")
                if attempt.error:
                    print(f"      ⮑ {attempt.error}")
        elif error:
            print(f"   ⮑ Error: {error}")
            
        if server:
            print(f"   ⮑ Verified by: {server}")
            
    def print_section(self, title: str):
        """Print a section header.
        
        Args:
            title: Section title
        """
        print(f"\n📋 {title}")
        print("-" * 50)
        
    def print_summary(self, total: int, success: int):
        """Print verification summary.
        
        Args:
            total: Total number of ports checked
            success: Number of successfully verified ports
        """
        print("\n📊 Summary")
        print("-" * 50)
        print(f"Total Ports Checked: {total}")
        print(f"Successfully Verified: {success}")
        print(f"Failed: {total - success}")
        
        # Add recommendation if no ports were verified
        if success == 0:
            print("\n⚠️  Recommendations:")
            print("1. Check if your firewall allows incoming connections")
            print("2. Verify port forwarding is configured on your router")
            print("3. Ensure no other services are using these ports")
            print("4. Try manually testing ports with netcat or telnet")
