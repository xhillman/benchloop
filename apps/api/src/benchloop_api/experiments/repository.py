from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from benchloop_api.experiments.models import Experiment
from benchloop_api.ownership.repository import UserOwnedRepository


class ExperimentRepository(UserOwnedRepository[Experiment]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Experiment)

    def list_for_user(
        self,
        *,
        user_id: UUID,
        include_archived: bool,
    ) -> Sequence[Experiment]:
        statement = self._owned_statement(user_id=user_id).order_by(
            Experiment.updated_at.desc(),
            Experiment.created_at.desc(),
            Experiment.name.asc(),
        )
        if not include_archived:
            statement = statement.where(Experiment.is_archived.is_(False))
        return self._session.scalars(statement).all()
