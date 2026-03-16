from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from benchloop_api.context_bundles.models import ContextBundle
from benchloop_api.ownership.repository import UserOwnedRepository


class ContextBundleRepository(UserOwnedRepository[ContextBundle]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, ContextBundle)

    def list_for_experiment(
        self,
        *,
        user_id: UUID,
        experiment_id: UUID,
    ) -> Sequence[ContextBundle]:
        statement = self._owned_statement(user_id=user_id).where(
            ContextBundle.experiment_id == experiment_id,
        ).order_by(
            ContextBundle.updated_at.desc(),
            ContextBundle.created_at.desc(),
            ContextBundle.name.asc(),
        )
        return self._session.scalars(statement).all()

    def get_owned_for_experiment(
        self,
        *,
        user_id: UUID,
        experiment_id: UUID,
        context_bundle_id: UUID,
    ) -> ContextBundle | None:
        statement = self._owned_statement(user_id=user_id).where(
            ContextBundle.experiment_id == experiment_id,
            ContextBundle.id == context_bundle_id,
        )
        return self._session.scalar(statement)
