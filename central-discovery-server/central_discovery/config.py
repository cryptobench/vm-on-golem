"""
Central Discovery Service Configuration

This module provides configuration settings for the centralized discovery service.
Canonical settings use GOLEM_CENTRAL_DISCOVERY_. Legacy GOLEM_DISCOVERY_ variables
are still accepted for compatibility.

Example:
    To change the port:
    GOLEM_CENTRAL_DISCOVERY_PORT=8000

    To enable debug mode:
    GOLEM_CENTRAL_DISCOVERY_DEBUG=true
"""

from pydantic import BaseSettings, validator
from typing import Optional
import secrets
from pathlib import Path
import os


_SETTING_NAMES = (
    "API_V1_PREFIX",
    "PROJECT_NAME",
    "DEBUG",
    "HOST",
    "PORT",
    "DATABASE_DIR",
    "DATABASE_NAME",
    "DATABASE_URL",
    "SECRET_KEY",
    "PROVIDER_AUTH_HEADER",
    "PROVIDER_SIGNATURE_HEADER",
    "RATE_LIMIT_PER_MINUTE",
    "ADVERTISEMENT_EXPIRY_MINUTES",
    "CLEANUP_INTERVAL_SECONDS",
)


def _copy_legacy_env() -> None:
    """Accept old GOLEM_DISCOVERY_* variables without making them canonical."""
    for name in _SETTING_NAMES:
        canonical = f"GOLEM_CENTRAL_DISCOVERY_{name}"
        legacy = f"GOLEM_DISCOVERY_{name}"
        if canonical not in os.environ and legacy in os.environ:
            os.environ[canonical] = os.environ[legacy]


_copy_legacy_env()


class Settings(BaseSettings):
    """
    Configuration settings with built-in defaults.
    Prefer GOLEM_CENTRAL_DISCOVERY_ variables; GOLEM_DISCOVERY_ remains supported.
    """

    # API Settings
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "VM on Golem Central Discovery Service"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"  # Listen on all interfaces by default
    PORT: int = 9001  # Default Golem Discovery port

    # Database Settings - SQLite by default in ~/.golem/central-discovery
    DATABASE_DIR: str = str(Path.home() / ".golem" / "central-discovery")
    DATABASE_NAME: str = "central-discovery.db"
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
    ADVERTISEMENT_EXPIRY_MINUTES: int = 5  # Providers must refresh every 5 minutes
    CLEANUP_INTERVAL_SECONDS: int = 60  # Clean expired entries every minute

    class Config:
        """Pydantic configuration"""

        case_sensitive = True
        env_prefix = "GOLEM_CENTRAL_DISCOVERY_"


# Global settings instance with defaults, can be overridden by environment variables
settings = Settings()
