"""
Central Discovery Service Configuration.

Only GOLEM_CENTRAL_DISCOVERY_* settings are accepted. Discovery data flows over
websockets and is kept in memory while provider sockets are connected.
"""

import secrets

from pydantic import BaseSettings


class Settings(BaseSettings):
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "VM on Golem Central Discovery Service"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 9001
    SECRET_KEY: str = secrets.token_urlsafe(32)
    RATE_LIMIT_PER_MINUTE: int = 100

    class Config:
        case_sensitive = True
        env_prefix = "GOLEM_CENTRAL_DISCOVERY_"


settings = Settings()
