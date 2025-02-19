from pydantic import BaseSettings, validator
from typing import Optional
import secrets
from pathlib import Path

class Settings(BaseSettings):
    # API Settings
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "VM on Golem Discovery Service"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 7465

    # Database Settings
    DATABASE_DIR: str = str(Path.home() / ".golem" / "discovery")
    DATABASE_NAME: str = "discovery.db"
    DATABASE_URL: Optional[str] = None

    @validator("DATABASE_URL", pre=True)
    def assemble_db_url(cls, v: Optional[str], values: dict) -> str:
        if v:
            return v
        db_path = Path(values["DATABASE_DIR"]) / values["DATABASE_NAME"]
        # Ensure directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite+aiosqlite:///{db_path}"

    # Security Settings
    SECRET_KEY: str = secrets.token_urlsafe(32)
    PROVIDER_AUTH_HEADER: str = "X-Provider-ID"
    PROVIDER_SIGNATURE_HEADER: str = "X-Provider-Signature"
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 100
    
    # Advertisement Settings
    ADVERTISEMENT_EXPIRY_MINUTES: int = 5
    CLEANUP_INTERVAL_SECONDS: int = 60

    class Config:
        case_sensitive = True
        env_prefix = "GOLEM_DISCOVERY_"

settings = Settings()
