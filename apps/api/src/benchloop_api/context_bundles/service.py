from uuid import UUID

from sqlalchemy.orm import Session

from benchloop_api.configs.repository import ConfigRepository
from benchloop_api.context_bundles.models import ContextBundle
from benchloop_api.context_bundles.repository import ContextBundleRepository
from benchloop_api.experiments.repository import ExperimentRepository
from benchloop_api.ownership.service import UserOwnedResourceNotFoundError


class ContextBundleService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._config_repository = ConfigRepository(session)
        self._experiment_repository = ExperimentRepository(session)
        self._repository = ContextBundleRepository(session)

    def list(
        self,
        *,
        user_id: UUID,
        experiment_id: UUID,
    ) -> list[ContextBundle]:
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
        name: str,
        content_text: str,
        notes: str | None,
    ) -> ContextBundle:
        self._get_experiment_or_raise(user_id=user_id, experiment_id=experiment_id)
        context_bundle = self._repository.add(
            ContextBundle(
                user_id=user_id,
                experiment_id=experiment_id,
                name=name,
                content_text=content_text,
                notes=notes,
            )
        )
        self._session.flush()
        self._session.refresh(context_bundle)
        return context_bundle

    def update(
        self,
        *,
        user_id: UUID,
        experiment_id: UUID,
        context_bundle_id: UUID,
        name: str,
        content_text: str,
        notes: str | None,
    ) -> ContextBundle:
        self._get_experiment_or_raise(user_id=user_id, experiment_id=experiment_id)
        context_bundle = self.read(
            user_id=user_id,
            experiment_id=experiment_id,
            context_bundle_id=context_bundle_id,
        )
        context_bundle.name = name
        context_bundle.content_text = content_text
        context_bundle.notes = notes
        self._session.flush()
        self._session.refresh(context_bundle)
        return context_bundle

    def read(
        self,
        *,
        user_id: UUID,
        experiment_id: UUID,
        context_bundle_id: UUID,
    ) -> ContextBundle:
        self._get_experiment_or_raise(user_id=user_id, experiment_id=experiment_id)
        context_bundle = self._repository.get_owned_for_experiment(
            user_id=user_id,
            experiment_id=experiment_id,
            context_bundle_id=context_bundle_id,
        )
        if context_bundle is None:
            raise UserOwnedResourceNotFoundError(
                resource_name="Context bundle",
                resource_id=context_bundle_id,
                user_id=user_id,
            )
        return context_bundle

    def delete(
        self,
        *,
        user_id: UUID,
        experiment_id: UUID,
        context_bundle_id: UUID,
    ) -> None:
        context_bundle = self.read(
            user_id=user_id,
            experiment_id=experiment_id,
            context_bundle_id=context_bundle_id,
        )
        for config in self._config_repository.list_for_experiment(
            user_id=user_id,
            experiment_id=experiment_id,
        ):
            if config.context_bundle_id == context_bundle.id:
                config.context_bundle_id = None
        self._session.delete(context_bundle)
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
