from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field, field_validator, model_validator
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

    port_check_retries: int = Field(default=1, validation_alias="PORT_CHECK_RETRIES")
    port_check_retry_delay: float = Field(
        default=0.25, validation_alias="PORT_CHECK_RETRY_DELAY"
    )
    port_check_timeout: float = Field(
        default=3.0, validation_alias="PORT_CHECK_TIMEOUT"
    )

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
