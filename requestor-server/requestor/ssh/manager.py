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
        """Initialize SSH key manager.
        
        Args:
            golem_dir: Optional custom directory for Golem SSH keys. If None, uses default from config.
        """
        # Set up Golem SSH directory
        if golem_dir is None:
            from ..config import config
            self.golem_dir = Path(config.ssh_key_dir)
        else:
            self.golem_dir = Path(golem_dir)

        # Define key paths
        self.system_key_path = Path.home() / '.ssh' / 'id_rsa'
        self.golem_key_path = self.golem_dir / 'golem_id_rsa'  # Single reusable key
        
        # Create Golem directory if needed
        self.golem_dir.mkdir(parents=True, exist_ok=True)
        # Secure directory permissions (on Unix-like systems). If the directory
        # is a system path (e.g., "/tmp") or not owned/permission-changeable
        # by the current user, ignore the error to avoid test and runtime failures.
        if os.name == 'posix':
            try:
                os.chmod(self.golem_dir, 0o700)
            except PermissionError:
                logger.warning(
                    "Could not set permissions on %s; continuing without chmod",
                    self.golem_dir,
                )

    async def get_key_pair(self) -> KeyPair:
        """Get the SSH key pair to use.
        
        Returns system SSH key if available, otherwise returns/creates Golem key.
        """
        # Try to use system SSH key first
        logger.debug("Checking for system SSH key at %s", self.system_key_path)
        system_pub_key = self.system_key_path.parent / 'id_rsa.pub'
        
        if self.system_key_path.exists() and system_pub_key.exists():
            logger.info("Using existing system SSH key")
            try:
                return KeyPair(
                    private_key=self.system_key_path,
                    public_key=system_pub_key,
                    private_key_content=self.system_key_path.read_text().strip(),
                    public_key_content=system_pub_key.read_text().strip()
                )
            except (PermissionError, OSError) as e:
                logger.warning("Could not read system SSH key: %s", e)
                # Fall through to use Golem key
        
        # Use/create Golem key if system key unavailable
        logger.debug("Using Golem SSH key at %s", self.golem_key_path)
        if not self.golem_key_path.exists():
            logger.info("No existing Golem SSH key found, generating new key pair")
            await self._generate_key_pair()
        
        golem_pub_key = Path(str(self.golem_key_path) + '.pub')
        return KeyPair(
            private_key=self.golem_key_path,
            public_key=golem_pub_key,
            private_key_content=self.golem_key_path.read_text().strip(),
            public_key_content=golem_pub_key.read_text().strip()
        )

    def get_key_pair_sync(self) -> KeyPair:
        """Get the SSH key pair to use (synchronous version)."""
        logger.debug("Checking for system SSH key at %s", self.system_key_path)
        system_pub_key = self.system_key_path.parent / 'id_rsa.pub'
        
        if self.system_key_path.exists() and system_pub_key.exists():
            logger.info("Using existing system SSH key")
            try:
                return KeyPair(
                    private_key=self.system_key_path,
                    public_key=system_pub_key,
                    private_key_content=self.system_key_path.read_text().strip(),
                    public_key_content=system_pub_key.read_text().strip()
                )
            except (PermissionError, OSError) as e:
                logger.warning("Could not read system SSH key: %s", e)
        
        logger.debug("Using Golem SSH key at %s", self.golem_key_path)
        if not self.golem_key_path.exists():
            logger.info("No existing Golem SSH key found, generating new key pair")
            self._generate_key_pair_sync()
        
        golem_pub_key = Path(str(self.golem_key_path) + '.pub')
        return KeyPair(
            private_key=self.golem_key_path,
            public_key=golem_pub_key,
            private_key_content=self.golem_key_path.read_text().strip(),
            public_key_content=golem_pub_key.read_text().strip()
        )

    async def get_public_key_content(self) -> str:
        """Get the content of the public key file."""
        key_pair = await self.get_key_pair()
        return key_pair.public_key_content

    async def get_key_content(self) -> KeyPair:
        """Get both the paths and contents of the key pair."""
        logger.debug("Getting key content")
        key_pair = await self.get_key_pair()
        logger.debug("Got key pair with paths: private=%s, public=%s", 
                    key_pair.private_key, key_pair.public_key)
        return key_pair

    @classmethod
    async def generate_key_pair(cls) -> KeyPair:
        """Generate a new RSA key pair for Golem VMs and return their contents."""
        logger.info("Generating new SSH key pair")
        manager = cls()
        await manager._generate_key_pair()
        logger.debug("Key pair generated, getting content")
        return await manager.get_key_content()

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
            if os.name == 'posix':
                os.chmod(self.golem_key_path, 0o600)  # Secure key permissions on Unix-like systems

            # Save public key
            logger.debug("Generating public key")
            public_key = private_key.public_key()
            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.OpenSSH,
                format=serialization.PublicFormat.OpenSSH
            )
            pub_key_path = Path(str(self.golem_key_path) + '.pub')
            logger.debug("Saving public key to %s", pub_key_path)
            pub_key_path.write_bytes(public_pem)
            if os.name == 'posix':
                os.chmod(pub_key_path, 0o644)  # Public key can be readable on Unix-like systems
            logger.info("Successfully generated and saved SSH key pair")
        except Exception as e:
            logger.error("Failed to generate key pair: %s", str(e))
            raise

    def _generate_key_pair_sync(self):
        """Generate a new RSA key pair for Golem VMs (synchronous version)."""
        logger.debug("Generating new RSA key pair")
        try:
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend()
            )
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            self.golem_key_path.write_bytes(private_pem)
            if os.name == 'posix':
                os.chmod(self.golem_key_path, 0o600)

            public_key = private_key.public_key()
            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.OpenSSH,
                format=serialization.PublicFormat.OpenSSH
            )
            pub_key_path = Path(str(self.golem_key_path) + '.pub')
            pub_key_path.write_bytes(public_pem)
            if os.name == 'posix':
                os.chmod(pub_key_path, 0o644)
            logger.info("Successfully generated and saved SSH key pair")
        except Exception as e:
            logger.error("Failed to generate key pair: %s", str(e))
            raise

    async def get_private_key_content(self, force_golem_key: bool = False) -> Optional[str]:
        """Get the content of the private key file."""
        key_pair = await self.get_key_pair(force_golem_key)
        return key_pair.private_key_content
