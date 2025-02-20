"""
Discovery Service Configuration

This module provides configuration settings for the Discovery Service with sensible defaults.
All settings can be overridden using environment variables with the prefix GOLEM_DISCOVERY_.

Example:
    To change the port:
    GOLEM_DISCOVERY_PORT=8000

    To enable debug mode:
    GOLEM_DISCOVERY_DEBUG=true
"""

from pydantic import BaseSettings, validator
from typing import Optional
import secrets
from pathlib import Path

class Settings(BaseSettings):
    """
    Configuration settings with built-in defaults.
    All settings can be overridden using environment variables with GOLEM_DISCOVERY_ prefix.
    """
    
    # API Settings
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "VM on Golem Discovery Service"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"  # Listen on all interfaces by default
    PORT: int = 7465       # Default Golem Discovery port
    
    # Database Settings - SQLite by default in ~/.golem/discovery
    DATABASE_DIR: str = str(Path.home() / ".golem" / "discovery")
    DATABASE_NAME: str = "discovery.db"
    DATABASE_URL: Optional[str] = None  # Will be auto-generated if not provided

    @validator("DATABASE_URL", pre=True)
    def assemble_db_url(cls, v: Optional[str], values: dict) -> str:
        """Generate SQLite database URL if not provided."""
        if v:
            return v
        db_path = Path(values["DATABASE_DIR"]) / values["DATABASE_NAME"]
        # Ensure directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite+aiosqlite:///{db_path}"

    # Security Settings
    SECRET_KEY: str = secrets.token_urlsafe(32)  # Auto-generated secure key
    PROVIDER_AUTH_HEADER: str = "X-Provider-ID"
    PROVIDER_SIGNATURE_HEADER: str = "X-Provider-Signature"
    
    # Rate Limiting - Protect against abuse
    RATE_LIMIT_PER_MINUTE: int = 100  # 100 requests per minute per IP
    
    # Advertisement Settings
    ADVERTISEMENT_EXPIRY_MINUTES: int = 5    # Providers must refresh every 5 minutes
    CLEANUP_INTERVAL_SECONDS: int = 60       # Clean expired entries every minute

    class Config:
        """Pydantic configuration"""
        case_sensitive = True
        env_prefix = "GOLEM_DISCOVERY_"  # All env vars must start with GOLEM_DISCOVERY_

# Global settings instance with defaults, can be overridden by environment variables
settings = Settings()
