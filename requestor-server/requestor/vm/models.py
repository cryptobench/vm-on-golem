from sqlalchemy import Column, DateTime, String, Text, func

from requestor.db.base import Base


class VMModel(Base):
    __tablename__ = "vms"

    name = Column(String, primary_key=True)
    provider_ip = Column(String, nullable=False)
    vm_id = Column(String, nullable=False)
    config = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="running")
    created_at = Column(DateTime, server_default=func.current_timestamp())
