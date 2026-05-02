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
