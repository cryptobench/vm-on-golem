from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()

class Advertisement(Base):
    """Provider advertisement model."""
    __tablename__ = "advertisements"

    provider_id = Column(String, primary_key=True)
    ip_address = Column(String, nullable=False)
    country = Column(String(2), nullable=False)  # ISO 3166-1 alpha-2
    resources = Column(JSON, nullable=False)  # CPU, memory, storage
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Advertisement(provider_id={self.provider_id}, ip={self.ip_address})>"

    @property
    def is_expired(self) -> bool:
        """Check if advertisement has expired (older than 5 minutes)."""
        if not self.updated_at:
            return True
        age = datetime.utcnow() - self.updated_at
        return age.total_seconds() > 300  # 5 minutes
