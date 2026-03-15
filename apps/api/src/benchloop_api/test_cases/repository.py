from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from benchloop_api.ownership.repository import UserOwnedRepository
from benchloop_api.test_cases.models import TestCase


class TestCaseRepository(UserOwnedRepository[TestCase]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, TestCase)

    def list_for_experiment(
        self,
        *,
        user_id: UUID,
        experiment_id: UUID,
    ) -> Sequence[TestCase]:
        statement = self._owned_statement(user_id=user_id).where(
            TestCase.experiment_id == experiment_id,
        ).order_by(
            TestCase.updated_at.desc(),
            TestCase.created_at.desc(),
            TestCase.id.asc(),
        )
        return self._session.scalars(statement).all()

    def get_owned_for_experiment(
        self,
        *,
        user_id: UUID,
        experiment_id: UUID,
        test_case_id: UUID,
    ) -> TestCase | None:
        statement = self._owned_statement(user_id=user_id).where(
            TestCase.experiment_id == experiment_id,
            TestCase.id == test_case_id,
        )
        return self._session.scalar(statement)
