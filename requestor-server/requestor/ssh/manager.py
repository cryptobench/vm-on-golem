import asyncio
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
import asyncssh

@dataclass
class SSHKeyPair:
    private_key: Path
    public_key: Path

class SSHKeyManager:
    def __init__(self, keys_dir: Path):
        self.keys_dir = keys_dir
        self.keys_dir.mkdir(parents=True, exist_ok=True)

    async def generate_key_pair(self, name: str) -> SSHKeyPair:
        """Generate new SSH key pair."""
        # Create directory for this VM's keys
        key_dir = self.keys_dir / name
        key_dir.mkdir(parents=True, exist_ok=True)

        private_key_path = key_dir / "id_ed25519"
        public_key_path = key_dir / "id_ed25519.pub"

        # Generate ED25519 key pair
        private_key = asyncssh.generate_private_key('ssh-ed25519')
        
        # Save keys with proper permissions
        private_key.write_private_key(str(private_key_path))
        private_key.write_public_key(str(public_key_path))
        
        # Set proper permissions
        private_key_path.chmod(0o600)
        public_key_path.chmod(0o644)

        return SSHKeyPair(
            private_key=private_key_path,
            public_key=public_key_path
        )

    def get_key_pair(self, name: str) -> Optional[SSHKeyPair]:
        """Get existing SSH key pair."""
        key_dir = self.keys_dir / name
        private_key_path = key_dir / "id_ed25519"
        public_key_path = key_dir / "id_ed25519.pub"

        if private_key_path.exists() and public_key_path.exists():
            return SSHKeyPair(
                private_key=private_key_path,
                public_key=public_key_path
            )
        return None

    def delete_key_pair(self, name: str) -> None:
        """Delete SSH key pair."""
        key_dir = self.keys_dir / name
        if key_dir.exists():
            for key_file in key_dir.iterdir():
                key_file.unlink()
            key_dir.rmdir()
