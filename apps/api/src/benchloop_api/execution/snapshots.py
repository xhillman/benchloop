from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from benchloop_api.configs.models import Config
from benchloop_api.execution.rendering import (
    UnsupportedWorkflowCombinationError,
    render_prompt_template,
)
from benchloop_api.test_cases.models import TestCase


class SnapshotModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ContextSnapshot(SnapshotModel):
    source: Literal["bundle", "inline"]
    bundle_id: UUID | None = None
    name: str | None = None
    content_text: str
    notes: str | None = None

    @model_validator(mode="after")
    def validate_bundle_source(self) -> "ContextSnapshot":
        if self.source == "bundle" and self.bundle_id is None:
            raise ValueError("Bundle-backed context snapshots require a bundle_id.")
        if self.source == "inline" and self.bundle_id is not None:
            raise ValueError("Inline context snapshots cannot include a bundle_id.")
        return self


class InputSnapshot(SnapshotModel):
    test_case_id: UUID
    input_text: str
    expected_output_text: str | None = None
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)


class ConfigSnapshot(SnapshotModel):
    config_id: UUID
    name: str
    version_label: str
    description: str | None = None
    provider: str
    model: str
    workflow_mode: str
    system_prompt_template: str | None = None
    rendered_system_prompt: str | None = None
    user_prompt_template: str
    rendered_user_prompt: str
    temperature: float
    max_output_tokens: int
    top_p: float | None = None
    context_bundle_id: UUID | None = None
    tags: list[str] = Field(default_factory=list)
    is_baseline: bool


class RunSnapshotBundle(SnapshotModel):
    config_snapshot: ConfigSnapshot
    input_snapshot: InputSnapshot
    context_snapshot: ContextSnapshot | None = None


def build_run_snapshot_bundle(
    *,
    config: Config,
    test_case: TestCase,
    context_snapshot: ContextSnapshot | None = None,
    intermediate_output: str | None = None,
) -> RunSnapshotBundle:
    if context_snapshot is not None and config.workflow_mode != "prompt_plus_context":
        raise UnsupportedWorkflowCombinationError(
            workflow_mode=config.workflow_mode,
            variable_name="context",
        )

    if intermediate_output is not None and config.workflow_mode != "two_step_chain":
        raise UnsupportedWorkflowCombinationError(
            workflow_mode=config.workflow_mode,
            variable_name="intermediate",
        )

    template_values = {
        "input": test_case.input_text,
        "context": context_snapshot.content_text if context_snapshot is not None else None,
        "intermediate": intermediate_output,
    }
    rendered_system_prompt = render_prompt_template(
        template=config.system_prompt,
        workflow_mode=config.workflow_mode,
        field_name="system_prompt",
        values=template_values,
    )
    rendered_user_prompt = render_prompt_template(
        template=config.user_prompt_template,
        workflow_mode=config.workflow_mode,
        field_name="user_prompt_template",
        values=template_values,
    )
    if rendered_user_prompt is None:
        raise ValueError("User prompt template rendering unexpectedly returned no prompt text.")

    return RunSnapshotBundle(
        config_snapshot=ConfigSnapshot(
            config_id=config.id,
            name=config.name,
            version_label=config.version_label,
            description=config.description,
            provider=config.provider,
            model=config.model,
            workflow_mode=config.workflow_mode,
            system_prompt_template=config.system_prompt,
            rendered_system_prompt=rendered_system_prompt,
            user_prompt_template=config.user_prompt_template,
            rendered_user_prompt=rendered_user_prompt,
            temperature=config.temperature,
            max_output_tokens=config.max_output_tokens,
            top_p=config.top_p,
            context_bundle_id=config.context_bundle_id,
            tags=list(config.tags),
            is_baseline=config.is_baseline,
        ),
        input_snapshot=InputSnapshot(
            test_case_id=test_case.id,
            input_text=test_case.input_text,
            expected_output_text=test_case.expected_output_text,
            notes=test_case.notes,
            tags=list(test_case.tags),
        ),
        context_snapshot=context_snapshot,
    )
