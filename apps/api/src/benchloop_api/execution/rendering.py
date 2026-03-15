import re
from collections.abc import Mapping

SUPPORTED_TEMPLATE_VARIABLES = frozenset({"context", "input", "intermediate"})
WORKFLOW_ALLOWED_VARIABLES = {
    "single_shot": frozenset({"input"}),
    "prompt_plus_context": frozenset({"context", "input"}),
    "two_step_chain": frozenset({"input", "intermediate"}),
}
TEMPLATE_VARIABLE_PATTERN = re.compile(r"{{\s*([a-z_]+)\s*}}")


class PromptRenderingError(ValueError):
    """Base error for prompt rendering and validation failures."""


class UnsupportedTemplateVariableError(PromptRenderingError):
    def __init__(self, *, variable_name: str, field_name: str) -> None:
        self.variable_name = variable_name
        self.field_name = field_name
        super().__init__(
            f"Template field '{field_name}' references unsupported variable '{variable_name}'."
        )


class MissingTemplateVariableError(PromptRenderingError):
    def __init__(self, *, variable_name: str, field_name: str) -> None:
        self.variable_name = variable_name
        self.field_name = field_name
        super().__init__(
            f"Template field '{field_name}' requires variable '{variable_name}' but no runtime value was provided."
        )


class UnsupportedWorkflowCombinationError(PromptRenderingError):
    def __init__(self, *, workflow_mode: str, variable_name: str) -> None:
        self.workflow_mode = workflow_mode
        self.variable_name = variable_name
        super().__init__(
            f"Workflow mode '{workflow_mode}' does not support template variable '{variable_name}'."
        )


def extract_template_variables(template: str | None) -> set[str]:
    if not template:
        return set()
    return set(TEMPLATE_VARIABLE_PATTERN.findall(template))


def render_prompt_template(
    *,
    template: str | None,
    workflow_mode: str,
    field_name: str,
    values: Mapping[str, str | None],
) -> str | None:
    if template is None:
        return None

    _validate_template_variables(
        template=template,
        workflow_mode=workflow_mode,
        field_name=field_name,
    )

    def replace(match: re.Match[str]) -> str:
        variable_name = match.group(1)
        value = values.get(variable_name)
        if value is None:
            raise MissingTemplateVariableError(
                variable_name=variable_name,
                field_name=field_name,
            )
        return value

    return TEMPLATE_VARIABLE_PATTERN.sub(replace, template)


def _validate_template_variables(
    *,
    template: str,
    workflow_mode: str,
    field_name: str,
) -> None:
    variables = extract_template_variables(template)

    for variable_name in sorted(variables):
        if variable_name not in SUPPORTED_TEMPLATE_VARIABLES:
            raise UnsupportedTemplateVariableError(
                variable_name=variable_name,
                field_name=field_name,
            )

    allowed_variables = WORKFLOW_ALLOWED_VARIABLES.get(workflow_mode)
    if allowed_variables is None:
        raise UnsupportedWorkflowCombinationError(
            workflow_mode=workflow_mode,
            variable_name="unknown",
        )

    for variable_name in sorted(variables - allowed_variables):
        raise UnsupportedWorkflowCombinationError(
            workflow_mode=workflow_mode,
            variable_name=variable_name,
        )
