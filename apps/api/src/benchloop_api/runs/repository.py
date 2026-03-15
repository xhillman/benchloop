from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from benchloop_api.ownership.repository import UserOwnedRepository
from benchloop_api.runs.models import Run


class RunRepository(UserOwnedRepository[Run]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Run)

    def list_for_user(self, *, user_id: UUID) -> Sequence[Run]:
        statement = (
            select(Run)
            .where(Run.user_id == user_id)
            .order_by(Run.created_at.desc(), Run.id.desc())
        )
        return self._session.scalars(statement).all()
