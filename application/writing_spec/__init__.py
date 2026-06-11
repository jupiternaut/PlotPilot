"""WritingSpec: lightweight writing contract validation."""

from .models import (
    ForbiddenRule,
    LLMJudgeRule,
    MetricRule,
    RequirementGroup,
    WritingSpec,
    WritingSpecFinding,
    WritingSpecReport,
)
from .runtime import (
    WritingSpecGateError,
    apply_writing_spec_to_prompt,
    apply_writing_spec_to_snapshot,
    load_project_writing_spec,
    load_session_writing_spec,
    persist_writing_spec_report,
    render_report_for_repair,
    render_writing_spec_contract,
    resolve_writing_spec_id,
    validate_writing_spec,
    validate_writing_spec_with_judge,
)
from .validator import WritingSpecValidator, load_writing_spec, load_writing_spec_by_id

__all__ = [
    "ForbiddenRule",
    "LLMJudgeRule",
    "MetricRule",
    "RequirementGroup",
    "WritingSpec",
    "WritingSpecGateError",
    "WritingSpecFinding",
    "WritingSpecReport",
    "WritingSpecValidator",
    "apply_writing_spec_to_prompt",
    "apply_writing_spec_to_snapshot",
    "load_project_writing_spec",
    "load_session_writing_spec",
    "load_writing_spec",
    "load_writing_spec_by_id",
    "persist_writing_spec_report",
    "render_report_for_repair",
    "render_writing_spec_contract",
    "resolve_writing_spec_id",
    "validate_writing_spec",
    "validate_writing_spec_with_judge",
]
