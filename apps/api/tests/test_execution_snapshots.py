from uuid import UUID

import pytest

from benchloop_api.configs.models import Config
from benchloop_api.execution.rendering import (
    MissingTemplateVariableError,
    UnsupportedTemplateVariableError,
    UnsupportedWorkflowCombinationError,
)
from benchloop_api.execution.snapshots import ContextSnapshot, build_run_snapshot_bundle
from benchloop_api.test_cases.models import TestCase as BenchloopTestCase


def build_config(
    *,
    workflow_mode: str = "single_shot",
    system_prompt: str | None = "You are a concise assistant.",
    user_prompt_template: str = "Answer the request: {{input}}",
) -> Config:
    return Config(
        id=UUID("f5386bd1-709b-49be-8f76-a95f756859ec"),
        user_id=UUID("4e6e1e8f-9a2f-4c38-8ca3-f5343cf87341"),
        experiment_id=UUID("90bd6a11-e3cc-454b-9fb6-f8d83b28b332"),
        name="Support response",
        version_label="v3",
        description="Primary support response config.",
        provider="openai",
        model="gpt-4.1-mini",
        workflow_mode=workflow_mode,
        system_prompt=system_prompt,
        user_prompt_template=user_prompt_template,
        temperature=0.3,
        max_output_tokens=400,
        top_p=0.8,
        context_bundle_id=UUID("464df2ef-4d04-4cb3-b4f7-e565315b2728"),
        tags=["support", "baseline"],
        is_baseline=True,
    )


def build_test_case() -> BenchloopTestCase:
    return BenchloopTestCase(
        id=UUID("0efcae41-1ef6-48f3-9760-7f47a9cbba73"),
        user_id=UUID("4e6e1e8f-9a2f-4c38-8ca3-f5343cf87341"),
        experiment_id=UUID("90bd6a11-e3cc-454b-9fb6-f8d83b28b332"),
        input_text="Refund the customer for the duplicate charge.",
        expected_output_text="Confirm the refund and share the expected timeline.",
        notes="High-priority billing case.",
        tags=["billing", "priority"],
    )


def test_build_run_snapshot_bundle_captures_rendered_prompt_and_exact_runtime_state() -> None:
    config = build_config(
        workflow_mode="prompt_plus_context",
        system_prompt="Use the supplied knowledge base.",
        user_prompt_template="Input: {{input}}\n\nContext: {{context}}",
    )
    test_case = build_test_case()
    context = ContextSnapshot(
        source="bundle",
        bundle_id=UUID("464df2ef-4d04-4cb3-b4f7-e565315b2728"),
        name="Refund policy",
        content_text="Refunds may be issued within 24 hours for duplicate charges.",
        notes="Latest approved billing guidance.",
    )

    bundle = build_run_snapshot_bundle(
        config=config,
        test_case=test_case,
        context_snapshot=context,
    )

    assert bundle.config_snapshot.model_dump(mode="json") == {
        "config_id": "f5386bd1-709b-49be-8f76-a95f756859ec",
        "name": "Support response",
        "version_label": "v3",
        "description": "Primary support response config.",
        "provider": "openai",
        "model": "gpt-4.1-mini",
        "workflow_mode": "prompt_plus_context",
        "system_prompt_template": "Use the supplied knowledge base.",
        "rendered_system_prompt": "Use the supplied knowledge base.",
        "user_prompt_template": "Input: {{input}}\n\nContext: {{context}}",
        "rendered_user_prompt": (
            "Input: Refund the customer for the duplicate charge.\n\n"
            "Context: Refunds may be issued within 24 hours for duplicate charges."
        ),
        "temperature": 0.3,
        "max_output_tokens": 400,
        "top_p": 0.8,
        "context_bundle_id": "464df2ef-4d04-4cb3-b4f7-e565315b2728",
        "tags": ["support", "baseline"],
        "is_baseline": True,
    }
    assert bundle.input_snapshot.model_dump(mode="json") == {
        "test_case_id": "0efcae41-1ef6-48f3-9760-7f47a9cbba73",
        "input_text": "Refund the customer for the duplicate charge.",
        "expected_output_text": "Confirm the refund and share the expected timeline.",
        "notes": "High-priority billing case.",
        "tags": ["billing", "priority"],
    }
    assert bundle.context_snapshot is context

    config.user_prompt_template = "Mutated template {{input}}"
    test_case.input_text = "Changed later."

    assert bundle.config_snapshot.user_prompt_template == "Input: {{input}}\n\nContext: {{context}}"
    assert bundle.config_snapshot.rendered_user_prompt.startswith("Input: Refund the customer")
    assert bundle.input_snapshot.input_text == "Refund the customer for the duplicate charge."


def test_build_run_snapshot_bundle_is_deterministic_for_the_same_inputs() -> None:
    config = build_config()
    test_case = build_test_case()

    first = build_run_snapshot_bundle(config=config, test_case=test_case)
    second = build_run_snapshot_bundle(config=config, test_case=test_case)

    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_rendering_rejects_unknown_template_variables() -> None:
    config = build_config(user_prompt_template="Answer: {{input}} {{customer_name}}")

    with pytest.raises(UnsupportedTemplateVariableError, match="customer_name"):
        build_run_snapshot_bundle(config=config, test_case=build_test_case())


def test_prompt_plus_context_requires_context_snapshot_when_template_uses_context() -> None:
    config = build_config(
        workflow_mode="prompt_plus_context",
        user_prompt_template="Answer with context: {{input}} / {{context}}",
    )

    with pytest.raises(MissingTemplateVariableError, match="context"):
        build_run_snapshot_bundle(config=config, test_case=build_test_case())


def test_single_shot_rejects_context_and_intermediate_placeholders() -> None:
    context_config = build_config(user_prompt_template="Answer: {{input}} {{context}}")
    intermediate_config = build_config(user_prompt_template="Answer: {{input}} {{intermediate}}")

    with pytest.raises(UnsupportedWorkflowCombinationError, match="single_shot"):
        build_run_snapshot_bundle(config=context_config, test_case=build_test_case())

    with pytest.raises(UnsupportedWorkflowCombinationError, match="single_shot"):
        build_run_snapshot_bundle(config=intermediate_config, test_case=build_test_case())


def test_two_step_chain_requires_intermediate_output_for_final_prompt_rendering() -> None:
    config = build_config(
        workflow_mode="two_step_chain",
        user_prompt_template="Input: {{input}}\nPlan: {{intermediate}}",
    )

    with pytest.raises(MissingTemplateVariableError, match="intermediate"):
        build_run_snapshot_bundle(config=config, test_case=build_test_case())
