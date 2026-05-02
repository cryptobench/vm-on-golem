import json
from collections.abc import Callable

from sqlalchemy.orm import Session

from requestor.db.base import Base
from requestor.errors import NotFoundError

from .domain import VMRecord
from .models import VMModel


class VMRepository:
    """All VM persistence for the requestor service."""

    def __init__(self, session_factory: Callable[[], Session]):
        self.session_factory = session_factory

    def init_schema(self) -> None:
        with self.session_factory() as session:
            Base.metadata.create_all(session.get_bind())

    def save(
        self,
        name: str,
        provider_ip: str,
        vm_id: str,
        config: dict,
        status: str = "running",
    ) -> None:
        with self.session_factory() as session:
            session.add(
                VMModel(
                    name=name,
                    provider_ip=provider_ip,
                    vm_id=vm_id,
                    config=json.dumps(config),
                    status=status,
                )
            )
            session.commit()

    def get(self, name: str) -> VMRecord | None:
        with self.session_factory() as session:
            model = session.get(VMModel, name)
            return self._to_record(model) if model else None

    def require(self, name: str) -> VMRecord:
        record = self.get(name)
        if record is None:
            raise NotFoundError(f"VM '{name}' not found")
        return record

    def list(self) -> list[VMRecord]:
        with self.session_factory() as session:
            models = session.query(VMModel).order_by(VMModel.created_at).all()
            return [self._to_record(model) for model in models]

    def update_status(self, name: str, status: str) -> None:
        with self.session_factory() as session:
            model = session.get(VMModel, name)
            if model is None:
                raise NotFoundError(f"VM '{name}' not found")
            model.status = status
            session.commit()

    def delete(self, name: str) -> None:
        with self.session_factory() as session:
            model = session.get(VMModel, name)
            if model is None:
                raise NotFoundError(f"VM '{name}' not found")
            session.delete(model)
            session.commit()

    @staticmethod
    def _to_record(model: VMModel) -> VMRecord:
        created_at = model.created_at.isoformat() if model.created_at else None
        return VMRecord(
            name=model.name,
            provider_ip=model.provider_ip,
            vm_id=model.vm_id,
            config=json.loads(model.config),
            status=model.status,
            created_at=created_at,
        )
