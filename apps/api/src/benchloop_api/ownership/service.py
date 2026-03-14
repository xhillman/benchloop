from typing import Generic, TypeVar
from uuid import UUID

from benchloop_api.ownership.repository import UserOwnedRepository

ModelT = TypeVar("ModelT")


class UserOwnedResourceNotFoundError(Exception):
    def __init__(self, *, resource_name: str, resource_id: UUID, user_id: UUID) -> None:
        self.resource_name = resource_name
        self.resource_id = resource_id
        self.user_id = user_id
        super().__init__(f"{resource_name} was not found.")


class UserOwnedService(Generic[ModelT]):
    def __init__(
        self,
        repository: UserOwnedRepository[ModelT],
        *,
        resource_name: str,
    ) -> None:
        self._repository = repository
        self._resource_name = resource_name

    def list_owned(self, *, user_id: UUID):
        return self._repository.list_owned(user_id=user_id)

    def get_owned_or_raise(self, *, user_id: UUID, resource_id: UUID) -> ModelT:
        resource = self._repository.get_owned(
            user_id=user_id,
            resource_id=resource_id,
        )
        if resource is None:
            raise UserOwnedResourceNotFoundError(
                resource_name=self._resource_name,
                resource_id=resource_id,
                user_id=user_id,
            )
        return resource

    def delete_owned_or_raise(self, *, user_id: UUID, resource_id: UUID) -> None:
        deleted = self._repository.delete_owned(
            user_id=user_id,
            resource_id=resource_id,
        )
        if not deleted:
            raise UserOwnedResourceNotFoundError(
                resource_name=self._resource_name,
                resource_id=resource_id,
                user_id=user_id,
            )
