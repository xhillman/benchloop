from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from benchloop_api.ownership.repository import UserOwnedRepository
from benchloop_api.runs.models import Run, RunEvaluation


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


class RunEvaluationRepository(UserOwnedRepository[RunEvaluation]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, RunEvaluation)

    def get_for_run(self, *, user_id: UUID, run_id: UUID) -> RunEvaluation | None:
        statement = self._owned_statement(user_id=user_id).where(RunEvaluation.run_id == run_id)
        return self._session.scalar(statement)

    def list_for_runs(
        self,
        *,
        user_id: UUID,
        run_ids: Sequence[UUID],
    ) -> dict[UUID, RunEvaluation]:
        if not run_ids:
            return {}

        statement = self._owned_statement(user_id=user_id).where(RunEvaluation.run_id.in_(run_ids))
        evaluations = self._session.scalars(statement).all()
        return {evaluation.run_id: evaluation for evaluation in evaluations}

    def delete_for_run(self, *, user_id: UUID, run_id: UUID) -> bool:
        evaluation = self.get_for_run(user_id=user_id, run_id=run_id)
        if evaluation is None:
            return False

        self._session.delete(evaluation)
        return True
