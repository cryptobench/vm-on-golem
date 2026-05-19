from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class PortCheckRequest(BaseModel):
    provider_ip: str = Field(..., description="Provider's public IP address")
    ports: List[int] = Field(..., description="List of ports to check")

    @field_validator("ports")
    @classmethod
    def validate_ports(cls, ports: list[int]) -> list[int]:
        for port in ports:
            if not 1 <= port <= 65535:
                raise ValueError(f"Invalid port number: {port}")
        return ports


class PortStatus(BaseModel):
    accessible: bool = Field(..., description="Whether the port is accessible")
    error: Optional[str] = Field(
        None, description="Error message if port is not accessible"
    )


class PortCheckResponse(BaseModel):
    success: bool = Field(..., description="Overall success status")
    results: Dict[int, PortStatus] = Field(..., description="Results for each port")
    message: str = Field(..., description="Summary message")


class HealthResponse(BaseModel):
    status: str


class TlsCheckRequest(BaseModel):
    host: str = Field(..., description="Provider host or IP to check")
    port: int = Field(..., ge=1, le=65535, description="TLS port to check")
    expected_ip: str | None = Field(
        None, description="IP address expected in the certificate SAN"
    )


class TlsCheckResponse(BaseModel):
    valid: bool
    error: str | None = None
    peer: str
    not_after: str | None = None
