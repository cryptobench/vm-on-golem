"""Ethereum key management for provider identity."""
import os
from pathlib import Path
from eth_account import Account
import json

class EthereumIdentity:
    """Manage provider's Ethereum identity."""
    
    def __init__(self, key_dir: str = None):
        if key_dir is None:
            key_dir = str(Path.home() / ".golem" / "provider" / "keys")
        self.key_dir = Path(key_dir)
        self.key_file = self.key_dir / "provider_key.json"
        
    def get_or_create_identity(self) -> str:
        """Get existing provider ID or create new one from Ethereum key."""
        # Create directory if it doesn't exist
        self.key_dir.mkdir(parents=True, exist_ok=True)
        self.key_dir.chmod(0o700)  # Secure permissions
        
        # Check for existing key
        if self.key_file.exists():
            with open(self.key_file) as f:
                key_data = json.load(f)
                return key_data["address"]
        
        # Generate new key
        Account.enable_unaudited_hdwallet_features()
        acct = Account.create()
        
        # Save key securely
        key_data = {
            "address": acct.address,
            "private_key": acct.key.hex()
        }
        with open(self.key_file, "w") as f:
            json.dump(key_data, f)
        self.key_file.chmod(0o600)  # Secure permissions
        
        return acct.address
