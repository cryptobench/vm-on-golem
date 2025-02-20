"""SSH key management for VM on Golem requestor."""
import os
import asyncio
import logging
import sys
from pathlib import Path
from typing import Tuple, Optional, Union, NamedTuple
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

# Configure basic logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

class KeyPair(NamedTuple):
    """Represents an SSH key pair with both private and public keys.
    
    Attributes:
        private_key: Path to the private key file
        public_key: Path to the public key file
        private_key_content: Content of the private key file
        public_key_content: Content of the public key file
    """
    private_key: Path
    public_key: Path
    private_key_content: str
    public_key_content: str

class SSHKeyManager:
    """Manages SSH keys for VM connections."""
    
    def __init__(self, golem_dir: Union[str, Path] = None):
        if golem_dir is None:
            from ..config import config
            self.ssh_dir = config.ssh_key_dir
        elif isinstance(golem_dir, str):
            self.ssh_dir = Path(golem_dir)
        else:
            self.ssh_dir = golem_dir
            
        self.system_key_path = Path.home() / '.ssh' / 'id_rsa'
        self.golem_key_path = self.ssh_dir / 'id_rsa'
        
        # Create golem ssh directory if it doesn't exist
        self.ssh_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.ssh_dir, 0o700)  # Secure directory permissions

    async def get_key_pair(self, force_golem_key: bool = False) -> KeyPair:
        """Get the SSH key pair paths and contents, using system key if available or Golem key.
        
        Args:
            force_golem_key: If True, always use Golem key even if system key exists
        """
        if not force_golem_key:
            logger.debug("Checking for system SSH key at %s", self.system_key_path)
            if self.system_key_path.exists() and (self.system_key_path.parent / 'id_rsa.pub').exists():
                logger.info("Using existing system SSH key")
                private_key = self.system_key_path
                public_key = self.system_key_path.parent / 'id_rsa.pub'
                return KeyPair(
                    private_key=private_key,
                    public_key=public_key,
                    private_key_content=private_key.read_text().strip(),
                    public_key_content=public_key.read_text().strip()
                )
            
        logger.debug("Using Golem SSH key at %s", self.golem_key_path)
        if not self.golem_key_path.exists():
            logger.info("No existing Golem SSH key found, generating new key pair")
            await self._generate_key_pair()
            
        private_key = self.golem_key_path
        public_key = self.golem_key_path.parent / 'id_rsa.pub'
        return KeyPair(
            private_key=private_key,
            public_key=public_key,
            private_key_content=private_key.read_text().strip(),
            public_key_content=public_key.read_text().strip()
        )

    async def get_public_key_content(self, force_golem_key: bool = False) -> str:
        """Get the content of the public key file."""
        key_pair = await self.get_key_pair(force_golem_key)
        return key_pair.public_key_content

    async def get_key_content(self, force_golem_key: bool = False) -> KeyPair:
        """Get both the paths and contents of the key pair."""
        print("DEBUG: Getting key content")  # Direct print for visibility
        logger.debug("Getting key content")
        key_pair = await self.get_key_pair(force_golem_key)
        print(f"DEBUG: Got key pair with paths: private={key_pair.private_key}, public={key_pair.public_key}")
        logger.debug("Got key pair with paths: private=%s, public=%s", key_pair.private_key, key_pair.public_key)
        return key_pair

    @classmethod
    async def generate_key_pair(cls, golem_dir: Union[str, Path] = None) -> KeyPair:
        """Generate a new RSA key pair for Golem VMs and return their contents."""
        print(f"DEBUG: Generating new SSH key pair with golem_dir={golem_dir}")  # Direct print
        logger.info("Generating new SSH key pair")
        logger.debug("Creating SSHKeyManager with golem_dir=%s", golem_dir)
        manager = cls(golem_dir)
        await manager._generate_key_pair()
        print("DEBUG: Key pair generated, getting content")  # Direct print
        logger.debug("Key pair generated, getting content")
        content = await manager.get_key_content(force_golem_key=True)
        print("DEBUG: Successfully generated and retrieved key pair content")  # Direct print
        logger.info("Successfully generated and retrieved key pair content")
        return content

    async def _generate_key_pair(self):
        """Generate a new RSA key pair for Golem VMs."""
        logger.debug("Generating new RSA key pair")
        try:
            # Generate private key
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend()
            )
            logger.debug("Generated private key")

            # Save private key
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            logger.debug("Saving private key to %s", self.golem_key_path)
            self.golem_key_path.write_bytes(private_pem)
            os.chmod(self.golem_key_path, 0o600)  # Secure key permissions

            # Save public key
            logger.debug("Generating public key")
            public_key = private_key.public_key()
            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.OpenSSH,
                format=serialization.PublicFormat.OpenSSH
            )
            pub_key_path = self.golem_key_path.parent / 'id_rsa.pub'
            logger.debug("Saving public key to %s", pub_key_path)
            pub_key_path.write_bytes(public_pem)
            os.chmod(pub_key_path, 0o644)  # Public key can be readable
            logger.info("Successfully generated and saved SSH key pair")
        except Exception as e:
            logger.error("Failed to generate key pair: %s", str(e))
            raise

    async def get_private_key_content(self, force_golem_key: bool = False) -> Optional[str]:
        """Get the content of the private key file."""
        key_pair = await self.get_key_pair(force_golem_key)
        return key_pair.private_key_content
