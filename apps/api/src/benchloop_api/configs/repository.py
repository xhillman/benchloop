from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from benchloop_api.configs.models import Config
from benchloop_api.ownership.repository import UserOwnedRepository


class ConfigRepository(UserOwnedRepository[Config]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Config)

    def list_for_experiment(
        self,
        *,
        user_id: UUID,
        experiment_id: UUID,
    ) -> Sequence[Config]:
        statement = self._owned_statement(user_id=user_id).where(
            Config.experiment_id == experiment_id,
        ).order_by(
            Config.is_baseline.desc(),
            Config.updated_at.desc(),
            Config.created_at.desc(),
            Config.name.asc(),
            Config.version_label.asc(),
        )
        return self._session.scalars(statement).all()

    def get_owned_for_experiment(
        self,
        *,
        user_id: UUID,
        experiment_id: UUID,
        config_id: UUID,
    ) -> Config | None:
        statement = self._owned_statement(user_id=user_id).where(
            Config.experiment_id == experiment_id,
            Config.id == config_id,
        )
        return self._session.scalar(statement)
