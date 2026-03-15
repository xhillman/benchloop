from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from benchloop_api.experiments.repository import ExperimentRepository
from benchloop_api.experiments.service import normalize_tags
from benchloop_api.ownership.service import UserOwnedResourceNotFoundError, UserOwnedService
from benchloop_api.test_cases.models import TestCase
from benchloop_api.test_cases.repository import TestCaseRepository


class TestCaseService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._experiment_repository = ExperimentRepository(session)
        self._repository = TestCaseRepository(session)
        self._owned_service = UserOwnedService(
            self._repository,
            resource_name="Test case",
        )

    def list(
        self,
        *,
        user_id: UUID,
        experiment_id: UUID,
    ) -> list[TestCase]:
        self._get_experiment_or_raise(user_id=user_id, experiment_id=experiment_id)
        return list(
            self._repository.list_for_experiment(
                user_id=user_id,
                experiment_id=experiment_id,
            )
        )

    def create(
        self,
        *,
        user_id: UUID,
        experiment_id: UUID,
        input_text: str,
        expected_output_text: str | None,
        notes: str | None,
        tags: Sequence[str],
    ) -> TestCase:
        self._get_experiment_or_raise(user_id=user_id, experiment_id=experiment_id)

        test_case = self._repository.add(
            TestCase(
                user_id=user_id,
                experiment_id=experiment_id,
                input_text=input_text,
                expected_output_text=expected_output_text,
                notes=notes,
                tags=normalize_tags(tags),
            )
        )
        self._session.flush()
        self._session.refresh(test_case)
        return test_case

    def update(
        self,
        *,
        user_id: UUID,
        experiment_id: UUID,
        test_case_id: UUID,
        input_text: str,
        expected_output_text: str | None,
        notes: str | None,
        tags: Sequence[str],
    ) -> TestCase:
        self._get_experiment_or_raise(user_id=user_id, experiment_id=experiment_id)
        test_case = self._read_in_experiment(
            user_id=user_id,
            experiment_id=experiment_id,
            test_case_id=test_case_id,
        )
        test_case.input_text = input_text
        test_case.expected_output_text = expected_output_text
        test_case.notes = notes
        test_case.tags = normalize_tags(tags)
        self._session.flush()
        self._session.refresh(test_case)
        return test_case

    def duplicate(
        self,
        *,
        user_id: UUID,
        experiment_id: UUID,
        test_case_id: UUID,
    ) -> TestCase:
        self._get_experiment_or_raise(user_id=user_id, experiment_id=experiment_id)
        source = self._read_in_experiment(
            user_id=user_id,
            experiment_id=experiment_id,
            test_case_id=test_case_id,
        )
        duplicated_test_case = self._repository.add(
            TestCase(
                user_id=user_id,
                experiment_id=experiment_id,
                input_text=source.input_text,
                expected_output_text=source.expected_output_text,
                notes=source.notes,
                tags=list(source.tags),
            )
        )
        self._session.flush()
        self._session.refresh(duplicated_test_case)
        return duplicated_test_case

    def delete(
        self,
        *,
        user_id: UUID,
        experiment_id: UUID,
        test_case_id: UUID,
    ) -> None:
        self._get_experiment_or_raise(user_id=user_id, experiment_id=experiment_id)
        test_case = self._read_in_experiment(
            user_id=user_id,
            experiment_id=experiment_id,
            test_case_id=test_case_id,
        )
        self._session.delete(test_case)
        self._session.flush()

    def _get_experiment_or_raise(self, *, user_id: UUID, experiment_id: UUID) -> None:
        experiment = self._experiment_repository.get_owned(
            user_id=user_id,
            resource_id=experiment_id,
        )
        if experiment is None:
            raise UserOwnedResourceNotFoundError(
                resource_name="Experiment",
                resource_id=experiment_id,
                user_id=user_id,
            )

    def _read_in_experiment(
        self,
        *,
        user_id: UUID,
        experiment_id: UUID,
        test_case_id: UUID,
    ) -> TestCase:
        test_case = self._repository.get_owned_for_experiment(
            user_id=user_id,
            experiment_id=experiment_id,
            test_case_id=test_case_id,
        )
        if test_case is None:
            raise UserOwnedResourceNotFoundError(
                resource_name="Test case",
                resource_id=test_case_id,
                user_id=user_id,
            )
        return test_case
