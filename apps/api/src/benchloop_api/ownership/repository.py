from collections.abc import Sequence
from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from benchloop_api.ownership.models import UserOwnedMixin

ModelT = TypeVar("ModelT", bound=UserOwnedMixin)


class UserOwnedRepository(Generic[ModelT]):
    def __init__(self, session: Session, model_type: type[ModelT]) -> None:
        self._session = session
        self._model_type = model_type

    def list_owned(self, *, user_id: UUID) -> Sequence[ModelT]:
        statement = self._owned_statement(user_id=user_id)
        return self._session.scalars(statement).all()

    def get_owned(self, *, user_id: UUID, resource_id: UUID) -> ModelT | None:
        statement = self._owned_statement(user_id=user_id).where(
            self._model_type.id == resource_id,
        )
        return self._session.scalar(statement)

    def add(self, resource: ModelT) -> ModelT:
        self._session.add(resource)
        return resource

    def delete_owned(self, *, user_id: UUID, resource_id: UUID) -> bool:
        resource = self.get_owned(user_id=user_id, resource_id=resource_id)
        if resource is None:
            return False

        self._session.delete(resource)
        return True

    def _owned_statement(self, *, user_id: UUID):
        return select(self._model_type).where(self._model_type.user_id == user_id)
