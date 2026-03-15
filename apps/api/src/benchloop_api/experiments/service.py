from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from benchloop_api.experiments.models import Experiment
from benchloop_api.experiments.repository import ExperimentRepository
from benchloop_api.ownership.service import UserOwnedService


def normalize_tags(tags: Sequence[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()

    for raw_tag in tags:
        tag = raw_tag.strip().lower()
        if not tag or tag in seen:
            continue
        seen.add(tag)
        normalized.append(tag)

    return normalized


class ExperimentService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repository = ExperimentRepository(session)
        self._owned_service = UserOwnedService(
            self._repository,
            resource_name="Experiment",
        )

    def list(
        self,
        *,
        user_id: UUID,
        search: str | None,
        tags: Sequence[str],
        include_archived: bool,
    ) -> list[Experiment]:
        normalized_search = (search or "").strip().lower()
        normalized_tags = normalize_tags(tags)

        experiments = self._repository.list_for_user(
            user_id=user_id,
            include_archived=include_archived,
        )

        return [
            experiment
            for experiment in experiments
            if self._matches_search(experiment=experiment, search=normalized_search)
            and self._matches_tags(experiment=experiment, tags=normalized_tags)
        ]

    def create(
        self,
        *,
        user_id: UUID,
        name: str,
        description: str | None,
        tags: Sequence[str],
    ) -> Experiment:
        experiment = self._repository.add(
            Experiment(
                user_id=user_id,
                name=name,
                description=description,
                tags=normalize_tags(tags),
            )
        )
        self._session.flush()
        self._session.refresh(experiment)
        return experiment

    def read(self, *, user_id: UUID, experiment_id: UUID) -> Experiment:
        return self._owned_service.get_owned_or_raise(
            user_id=user_id,
            resource_id=experiment_id,
        )

    def update(
        self,
        *,
        user_id: UUID,
        experiment_id: UUID,
        name: str,
        description: str | None,
        tags: Sequence[str],
        is_archived: bool,
    ) -> Experiment:
        experiment = self.read(user_id=user_id, experiment_id=experiment_id)
        experiment.name = name
        experiment.description = description
        experiment.tags = normalize_tags(tags)
        experiment.is_archived = is_archived
        self._session.flush()
        self._session.refresh(experiment)
        return experiment

    def delete(self, *, user_id: UUID, experiment_id: UUID) -> None:
        self._owned_service.delete_owned_or_raise(
            user_id=user_id,
            resource_id=experiment_id,
        )
        self._session.flush()

    @staticmethod
    def _matches_search(*, experiment: Experiment, search: str) -> bool:
        if not search:
            return True
        return search in experiment.name.lower()

    @staticmethod
    def _matches_tags(*, experiment: Experiment, tags: Sequence[str]) -> bool:
        if not tags:
            return True

        experiment_tags = {tag.lower() for tag in experiment.tags}
        return any(tag in experiment_tags for tag in tags)
