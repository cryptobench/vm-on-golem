from pathlib import Path

from dotenv import load_dotenv
from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def load_environment() -> None:
    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=True,
        extra="ignore",
        populate_by_name=True,
    )

    host: str = Field(default="0.0.0.0", validation_alias="PORT_CHECKER_HOST")
    port: int = Field(default=9000, validation_alias="PORT_CHECKER_PORT")
    debug: bool = Field(default=False, validation_alias="PORT_CHECKER_DEBUG")
    environment: str = Field(default="", validation_alias="GOLEM_ENVIRONMENT")

    cors_origins: list[str] = Field(
        default_factory=lambda: ["*"], validation_alias="PORT_CHECKER_CORS_ORIGINS"
    )

    port_check_retries: int = Field(default=3, validation_alias="PORT_CHECK_RETRIES")
    port_check_retry_delay: float = Field(
        default=1.0, validation_alias="PORT_CHECK_RETRY_DELAY"
    )
    port_check_timeout: float = Field(
        default=5.0, validation_alias="PORT_CHECK_TIMEOUT"
    )

    proxy_enabled: bool = Field(
        default=True, validation_alias="PORT_CHECKER_PROXY_ENABLED"
    )
    proxy_allow_direct_ip: bool = Field(
        default=False, validation_alias="PORT_CHECKER_PROXY_ALLOW_DIRECT_IP"
    )
    proxy_allowed_ports: str = Field(
        default="80,443,1024-65535",
        validation_alias="PORT_CHECKER_PROXY_ALLOWED_PORTS",
    )
    proxy_max_body_bytes: int = Field(
        default=2 * 1024 * 1024,
        validation_alias="PORT_CHECKER_PROXY_MAX_BODY_BYTES",
    )
    proxy_connect_timeout: float = Field(
        default=5.0, validation_alias="PORT_CHECKER_PROXY_CONNECT_TIMEOUT"
    )
    proxy_read_timeout: float = Field(
        default=10.0, validation_alias="PORT_CHECKER_PROXY_READ_TIMEOUT"
    )
    proxy_token: str = Field(default="", validation_alias="PORT_CHECKER_PROXY_TOKEN")
    allow_local_ips: bool = Field(
        default=False, validation_alias="PORT_CHECKER_ALLOW_LOCAL_IPS"
    )

    central_discovery_api_url: str = Field(
        default="http://localhost:9001/api/v1",
        validation_alias=AliasChoices(
            "CENTRAL_DISCOVERY_API_URL",
            "DISCOVERY_API_URL",
        ),
    )
    arkiv_rpc_url: str = Field(default="", validation_alias="ARKIV_RPC_URL")
    arkiv_ws_url: str = Field(default="", validation_alias="ARKIV_WS_URL")
    expected_network: str = Field(
        default="", validation_alias="PORT_CHECKER_EXPECTED_NETWORK"
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            origins = [origin.strip() for origin in value.split(",")]
            return [origin for origin in origins if origin]
        return value

    @model_validator(mode="after")
    def resolve_expected_network(self) -> "Settings":
        if self.expected_network.strip():
            self.expected_network = self.expected_network.strip()
            return self
        self.expected_network = "development" if self.is_development else "mainnet"
        return self

    @property
    def is_development(self) -> bool:
        return self.environment.lower() == "development"

    @property
    def effective_allow_local_ips(self) -> bool:
        return self.allow_local_ips or self.is_development
