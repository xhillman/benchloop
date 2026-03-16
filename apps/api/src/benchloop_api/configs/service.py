from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from benchloop_api.configs.models import Config
from benchloop_api.configs.repository import ConfigRepository
from benchloop_api.context_bundles.repository import ContextBundleRepository
from benchloop_api.experiments.repository import ExperimentRepository
from benchloop_api.experiments.service import normalize_tags
from benchloop_api.ownership.service import UserOwnedResourceNotFoundError

WORKFLOW_MODES = {
    "prompt_plus_context",
    "single_shot",
    "two_step_chain",
}


class InvalidWorkflowModeError(ValueError):
    def __init__(self, workflow_mode: str) -> None:
        self.workflow_mode = workflow_mode
        super().__init__(f"Workflow mode '{workflow_mode}' is not supported.")


def normalize_workflow_mode(workflow_mode: str) -> str:
    normalized_workflow_mode = workflow_mode.strip().lower()
    if normalized_workflow_mode not in WORKFLOW_MODES:
        raise InvalidWorkflowModeError(normalized_workflow_mode)
    return normalized_workflow_mode


class ConfigService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._experiment_repository = ExperimentRepository(session)
        self._context_bundle_repository = ContextBundleRepository(session)
        self._repository = ConfigRepository(session)

    def list(
        self,
        *,
        user_id: UUID,
        experiment_id: UUID,
    ) -> list[Config]:
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
        version_label: str,
        description: str | None,
        provider: str,
        model: str,
        workflow_mode: str,
        system_prompt: str | None,
        user_prompt_template: str,
        temperature: float,
        max_output_tokens: int,
        top_p: float | None,
        context_bundle_id: UUID | None,
        tags: Sequence[str],
        is_baseline: bool,
    ) -> Config:
        self._get_experiment_or_raise(user_id=user_id, experiment_id=experiment_id)
        self._validate_context_bundle(
            user_id=user_id,
            experiment_id=experiment_id,
            context_bundle_id=context_bundle_id,
        )

        config = self._repository.add(
            Config(
                user_id=user_id,
                experiment_id=experiment_id,
                name=name,
                version_label=version_label,
                description=description,
                provider=provider,
                model=model,
                workflow_mode=normalize_workflow_mode(workflow_mode),
                system_prompt=system_prompt,
                user_prompt_template=user_prompt_template,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                top_p=top_p,
                context_bundle_id=context_bundle_id,
                tags=normalize_tags(tags),
                is_baseline=False,
            )
        )
        self._session.flush()

        if is_baseline:
            self._set_baseline_for_experiment(
                user_id=user_id,
                experiment_id=experiment_id,
                baseline_config_id=config.id,
            )

        self._session.refresh(config)
        return config

    def update(
        self,
        *,
        user_id: UUID,
        experiment_id: UUID,
        config_id: UUID,
        name: str,
        version_label: str,
        description: str | None,
        provider: str,
        model: str,
        workflow_mode: str,
        system_prompt: str | None,
        user_prompt_template: str,
        temperature: float,
        max_output_tokens: int,
        top_p: float | None,
        context_bundle_id: UUID | None,
        tags: Sequence[str],
        is_baseline: bool,
    ) -> Config:
        self._get_experiment_or_raise(user_id=user_id, experiment_id=experiment_id)
        self._validate_context_bundle(
            user_id=user_id,
            experiment_id=experiment_id,
            context_bundle_id=context_bundle_id,
        )
        config = self._read_in_experiment(
            user_id=user_id,
            experiment_id=experiment_id,
            config_id=config_id,
        )
        config.name = name
        config.version_label = version_label
        config.description = description
        config.provider = provider
        config.model = model
        config.workflow_mode = normalize_workflow_mode(workflow_mode)
        config.system_prompt = system_prompt
        config.user_prompt_template = user_prompt_template
        config.temperature = temperature
        config.max_output_tokens = max_output_tokens
        config.top_p = top_p
        config.context_bundle_id = context_bundle_id
        config.tags = normalize_tags(tags)
        config.is_baseline = False if is_baseline else config.is_baseline

        self._session.flush()

        if is_baseline:
            self._set_baseline_for_experiment(
                user_id=user_id,
                experiment_id=experiment_id,
                baseline_config_id=config.id,
            )
        else:
            config.is_baseline = False
            self._session.flush()

        self._session.refresh(config)
        return config

    def clone(
        self,
        *,
        user_id: UUID,
        experiment_id: UUID,
        config_id: UUID,
    ) -> Config:
        self._get_experiment_or_raise(user_id=user_id, experiment_id=experiment_id)
        source = self._read_in_experiment(
            user_id=user_id,
            experiment_id=experiment_id,
            config_id=config_id,
        )
        version_label = self._build_clone_version_label(
            experiment_id=experiment_id,
            source_version_label=source.version_label,
            user_id=user_id,
        )
        cloned_config = self._repository.add(
            Config(
                user_id=user_id,
                experiment_id=experiment_id,
                name=source.name,
                version_label=version_label,
                description=source.description,
                provider=source.provider,
                model=source.model,
                workflow_mode=source.workflow_mode,
                system_prompt=source.system_prompt,
                user_prompt_template=source.user_prompt_template,
                temperature=source.temperature,
                max_output_tokens=source.max_output_tokens,
                top_p=source.top_p,
                context_bundle_id=source.context_bundle_id,
                tags=list(source.tags),
                is_baseline=False,
            )
        )
        self._session.flush()
        self._session.refresh(cloned_config)
        return cloned_config

    def mark_baseline(
        self,
        *,
        user_id: UUID,
        experiment_id: UUID,
        config_id: UUID,
    ) -> Config:
        self._get_experiment_or_raise(user_id=user_id, experiment_id=experiment_id)
        config = self._read_in_experiment(
            user_id=user_id,
            experiment_id=experiment_id,
            config_id=config_id,
        )
        self._set_baseline_for_experiment(
            user_id=user_id,
            experiment_id=experiment_id,
            baseline_config_id=config.id,
        )
        self._session.refresh(config)
        return config

    def delete(
        self,
        *,
        user_id: UUID,
        experiment_id: UUID,
        config_id: UUID,
    ) -> None:
        self._get_experiment_or_raise(user_id=user_id, experiment_id=experiment_id)
        config = self._read_in_experiment(
            user_id=user_id,
            experiment_id=experiment_id,
            config_id=config_id,
        )
        self._session.delete(config)
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
        config_id: UUID,
    ) -> Config:
        config = self._repository.get_owned_for_experiment(
            user_id=user_id,
            experiment_id=experiment_id,
            config_id=config_id,
        )
        if config is None:
            raise UserOwnedResourceNotFoundError(
                resource_name="Config",
                resource_id=config_id,
                user_id=user_id,
            )
        return config

    def _set_baseline_for_experiment(
        self,
        *,
        user_id: UUID,
        experiment_id: UUID,
        baseline_config_id: UUID,
    ) -> None:
        configs = self._repository.list_for_experiment(
            user_id=user_id,
            experiment_id=experiment_id,
        )
        for config in configs:
            config.is_baseline = config.id == baseline_config_id
        self._session.flush()

    def _build_clone_version_label(
        self,
        *,
        user_id: UUID,
        experiment_id: UUID,
        source_version_label: str,
    ) -> str:
        existing_labels = {
            config.version_label.lower()
            for config in self._repository.list_for_experiment(
                user_id=user_id,
                experiment_id=experiment_id,
            )
        }
        base_label = f"{source_version_label}-copy"
        if base_label.lower() not in existing_labels:
            return base_label

        suffix = 2
        while f"{base_label}-{suffix}".lower() in existing_labels:
            suffix += 1

        return f"{base_label}-{suffix}"

    def _validate_context_bundle(
        self,
        *,
        user_id: UUID,
        experiment_id: UUID,
        context_bundle_id: UUID | None,
    ) -> None:
        if context_bundle_id is None:
            return

        context_bundle = self._context_bundle_repository.get_owned_for_experiment(
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
