from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import replace
from typing import Any, Mapping

from domain.ai.services.llm_service import GenerationConfig
from domain.ai.value_objects.prompt import Prompt

from .models import LLMJudgeRule, WritingSpec, WritingSpecFinding, WritingSpecReport
from .validator import WritingSpecValidator, load_writing_spec_by_id

logger = logging.getLogger(__name__)

_SPEC_ID_RE = re.compile(r"(?:writing[_ -]?spec|WritingSpec|写作规格|文风规格)\s*[:：=]\s*([A-Za-z0-9_-]{1,120})")
_DIRECT_SPEC_KEYS = (
    "writing_spec_id",
    "writing_spec",
    "novel.writing_spec_id",
    "project.writing_spec_id",
    "writingSpecId",
)
_TEXT_SPEC_KEYS = (
    "writing_style",
    "novel.writing_style",
    "special_requirements",
    "novel.special_requirements",
)


class WritingSpecGateError(RuntimeError):
    """Raised when generated text still violates the active WritingSpec."""

    def __init__(self, report: WritingSpecReport):
        self.report = report
        super().__init__(
            f"WritingSpec validation failed: {report.spec_id} "
            f"score={report.score:.2f}/{report.threshold}"
        )


def resolve_writing_spec_id(
    *,
    context: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
    aliases: Mapping[str, Any] | None = None,
    snapshot_items: tuple[Mapping[str, Any], ...] | None = None,
) -> str:
    """Resolve a project-bound WritingSpec id from invocation state."""

    for source in (metadata or {}, context or {}, aliases or {}):
        found = _resolve_from_mapping(source)
        if found:
            return found

    for item in snapshot_items or ():
        variable_key = str(item.get("variable_key") or item.get("key") or "")
        value = item.get("value")
        if variable_key in _DIRECT_SPEC_KEYS and isinstance(value, str) and value.strip():
            return value.strip()
        if variable_key in _TEXT_SPEC_KEYS and isinstance(value, str):
            found = _resolve_from_text(value)
            if found:
                return found
    return ""


def load_session_writing_spec(session: Any) -> WritingSpec | None:
    variable_plan = session.variable_plan
    spec_id = resolve_writing_spec_id(
        context=session.context,
        metadata=session.metadata,
        aliases=variable_plan.aliases if variable_plan else {},
        snapshot_items=variable_plan.snapshot_items if variable_plan else (),
    )
    if not spec_id:
        return None
    return load_writing_spec_by_id(spec_id)


def load_project_writing_spec(novel_id: str, chapter_number: int | None = None) -> WritingSpec | None:
    """Load the novel-bound WritingSpec from Variable Hub, if any."""

    novel = str(novel_id or "").strip()
    if not novel:
        return None
    context_key = f"novel_id:{novel}"
    if chapter_number:
        context_key = f"{context_key}|chapter_number:{int(chapter_number)}"
    try:
        from infrastructure.persistence.database.connection import get_database
        from infrastructure.persistence.database.sqlite_ai_invocation_repository import SqliteVariableHubRepository
    except Exception:
        return None
    value = SqliteVariableHubRepository(get_database()).get_value(
        "novel.writing_spec_id",
        context_key,
    )
    spec_id = str(value.value or "").strip() if value is not None else ""
    if not spec_id:
        return None
    return load_writing_spec_by_id(spec_id)


def apply_writing_spec_to_snapshot(
    snapshot: Any,
    spec: WritingSpec,
    *,
    previous_content: str = "",
    previous_report: WritingSpecReport | None = None,
) -> Any:
    prompt = apply_writing_spec_to_prompt(
        snapshot.prompt,
        spec,
        previous_content=previous_content,
        previous_report=previous_report,
    )
    diagnostics = list(snapshot.diagnostics or ())
    marker = f"WritingSpec active: {spec.id}@{spec.version}"
    if marker not in diagnostics:
        diagnostics.append(marker)
    return replace(
        snapshot,
        prompt=prompt,
        rendered_prompt_hash=_prompt_hash(prompt),
        diagnostics=tuple(diagnostics),
    )


def apply_writing_spec_to_prompt(
    prompt: Prompt,
    spec: WritingSpec,
    *,
    previous_content: str = "",
    previous_report: WritingSpecReport | None = None,
) -> Prompt:
    contract = render_writing_spec_contract(spec)
    system = f"{prompt.system.rstrip()}\n\n{contract}".strip()
    if previous_report is None:
        user_suffix = (
            "\n\n[WritingSpec 执行要求]\n"
            f"本次输出必须满足 WritingSpec `{spec.id}`。只输出正文，不解释规格，不输出自评。"
        )
    else:
        user_suffix = (
            "\n\n[WritingSpec 自动返工]\n"
            "上一版没有通过项目写作规格。请基于原任务重写，而不是补丁式修几句。\n"
            f"{render_report_for_repair(previous_report)}\n\n"
            "[上一版失败稿]\n"
            f"{previous_content[:6000]}"
        )
    return Prompt(system=system, user=f"{prompt.user.rstrip()}{user_suffix}")


def validate_writing_spec(spec: WritingSpec, content: str) -> WritingSpecReport:
    return WritingSpecValidator(spec).validate(content)


async def validate_writing_spec_with_judge(
    spec: WritingSpec,
    content: str,
    llm_service: Any,
) -> WritingSpecReport:
    """Run deterministic checks first, then optional LLM judge checks."""

    report = validate_writing_spec(spec, content)
    if not report.passed or not spec.judges:
        return report

    findings = list(report.findings)
    score = report.score
    for judge in spec.judges:
        finding = await _run_llm_judge(judge, spec, content, llm_service)
        if finding is None:
            continue
        findings.append(finding)
        score -= finding.deduction

    score = max(0.0, min(100.0, score))
    has_error = any(finding.severity == "error" for finding in findings)
    return WritingSpecReport(
        spec_id=report.spec_id,
        passed=score >= report.threshold and not has_error,
        score=score,
        threshold=report.threshold,
        findings=tuple(findings),
        metrics=report.metrics,
    )


def persist_writing_spec_report(
    *,
    session: Any,
    report: WritingSpecReport,
    attempt_id: str = "",
    status: str = "",
) -> None:
    """Best-effort persistence of the last WritingSpec report into Variable Hub."""

    try:
        from application.ai_invocation.variable_hub import VariableWrite
        from infrastructure.persistence.database.connection import get_database
        from infrastructure.persistence.database.sqlite_ai_invocation_repository import SqliteVariableHubRepository
    except Exception:
        return

    context_key = _context_key_for_report(session.context)
    payload = {
        "status": status or ("passed" if report.passed else "failed"),
        "attempt_id": attempt_id,
        "operation": session.operation,
        "node_key": session.node_key,
        "report": report.to_dict(),
    }
    try:
        repo = SqliteVariableHubRepository(get_database())
        repo.set_value(
            VariableWrite(
                key="chapter.writing_spec.report",
                value=payload,
                context_key=context_key,
                source_session_id=session.id,
                source_attempt_id=attempt_id,
                source_node_key=session.node_key,
                value_type="object",
                display_name="WritingSpec 验收报告",
                scope="chapter" if "chapter_number:" in context_key else "novel",
                stage="review",
            )
        )
        repo.set_value(
            VariableWrite(
                key="chapter.writing_spec.status",
                value=payload["status"],
                context_key=context_key,
                source_session_id=session.id,
                source_attempt_id=attempt_id,
                source_node_key=session.node_key,
                value_type="string",
                display_name="WritingSpec 验收状态",
                scope="chapter" if "chapter_number:" in context_key else "novel",
                stage="review",
            )
        )
    except Exception:
        logger.warning("failed to persist WritingSpec report", exc_info=True)


def render_writing_spec_contract(spec: WritingSpec) -> str:
    parts = [
        "[WritingSpec 固化合同]",
        f"spec_id: {spec.id}",
        f"version: {spec.version}",
        f"title: {spec.title}",
    ]
    if spec.core_question:
        parts.append(f"core_question: {spec.core_question}")
    if spec.meaning_contract:
        parts.append(f"meaning_contract: {spec.meaning_contract}")
    elif spec.description:
        parts.append(f"description: {spec.description}")

    if spec.required:
        parts.append("required_anchors:")
        for item in spec.required:
            terms = " / ".join(item.terms[:8])
            parts.append(f"- {item.id}: {item.description}; 至少命中 {item.min_hits}; 关键词: {terms}")

    if spec.meaning:
        parts.append("meaning_argument_steps:")
        for item in spec.meaning:
            terms = " / ".join(item.terms[:10])
            parts.append(f"- {item.id}: {item.description}; 至少命中 {item.min_hits}; 证据词: {terms}")

    if spec.reader:
        parts.append("reader_requirements:")
        for item in spec.reader:
            terms = " / ".join(item.terms[:10])
            parts.append(f"- {item.id}: {item.description}; 至少命中 {item.min_hits}; 台阶词: {terms}")

    if spec.forbidden:
        parts.append("forbidden_drifts:")
        for item in spec.forbidden:
            patterns = " / ".join(item.patterns[:8])
            parts.append(f"- {item.id}: {item.description}; severity={item.severity}; 禁止: {patterns}")

    if spec.metrics:
        parts.append("style_metrics:")
        for item in spec.metrics:
            bounds = []
            if item.min_value is not None:
                bounds.append(f">={item.min_value:g}")
            if item.max_value is not None:
                bounds.append(f"<={item.max_value:g}")
            term_hint = f"; terms={' / '.join(item.terms[:8])}" if item.terms else ""
            parts.append(f"- {item.id}: {item.description}; {item.metric} {' and '.join(bounds)}{term_hint}")

    if spec.reader_metrics:
        parts.append("reader_metrics:")
        for item in spec.reader_metrics:
            bounds = []
            if item.min_value is not None:
                bounds.append(f">={item.min_value:g}")
            if item.max_value is not None:
                bounds.append(f"<={item.max_value:g}")
            term_hint = f"; terms={' / '.join(item.terms[:8])}" if item.terms else ""
            parts.append(f"- {item.id}: {item.description}; {item.metric} {' and '.join(bounds)}{term_hint}")

    negative_examples = [item for item in spec.examples if item.label == "negative"]
    if negative_examples:
        parts.append("negative_examples:")
        for item in negative_examples[:5]:
            parts.append(f"- {item.id}: {item.description}; 不要生成与此反例相同的碎句/口号/空泛论证模式")

    if spec.judges:
        parts.append("llm_judge:")
        for item in spec.judges:
            checks = " / ".join(item.checklist[:8])
            parts.append(
                f"- {item.id}: {item.description}; min_score={item.min_score:g}; "
                f"checklist={checks}"
            )

    parts.append("execution: 以本 WritingSpec 为硬约束。必须写出论证骨架和事实承重，不得用主题词刷分；锋利表达必须给外行读者留下解释台阶。")
    return "\n".join(parts)


def render_report_for_repair(report: WritingSpecReport) -> str:
    lines = [
        f"失败规格: {report.spec_id}",
        f"得分: {report.score:.2f}/{report.threshold}",
        "必须修复的失败项:",
    ]
    for finding in report.findings[:10]:
        evidence = f"; evidence={', '.join(finding.evidence[:6])}" if finding.evidence else ""
        lines.append(f"- {finding.rule_id} [{finding.severity}]: {finding.message}{evidence}")
    return "\n".join(lines)


def _resolve_from_mapping(source: Mapping[str, Any]) -> str:
    for key in _DIRECT_SPEC_KEYS:
        value = source.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for key in _TEXT_SPEC_KEYS:
        value = source.get(key)
        if isinstance(value, str):
            found = _resolve_from_text(value)
            if found:
                return found
    return ""


def _resolve_from_text(text: str) -> str:
    match = _SPEC_ID_RE.search(text or "")
    return match.group(1).strip() if match else ""


def _context_key_for_report(context: Mapping[str, Any]) -> str:
    novel_id = str(context.get("novel_id") or "").strip()
    chapter_number = context.get("chapter_number")
    if novel_id and chapter_number not in (None, ""):
        return f"novel_id:{novel_id}|chapter_number:{chapter_number}"
    if novel_id:
        return f"novel_id:{novel_id}"
    return "global"


async def _run_llm_judge(
    judge: LLMJudgeRule,
    spec: WritingSpec,
    content: str,
    llm_service: Any,
) -> WritingSpecFinding | None:
    prompt = _build_judge_prompt(judge, spec, content)
    try:
        result = await llm_service.generate(
            prompt,
            GenerationConfig(
                temperature=0.0,
                max_tokens=1200,
                response_format={"type": "json_object"},
            ),
        )
        payload = _parse_judge_response(result.content)
    except Exception as exc:
        deduction = judge.weight if judge.severity == "error" else judge.weight * 0.5
        return WritingSpecFinding(
            rule_id=judge.id,
            severity=judge.severity,
            message=f"LLM 评审不可用：{judge.description}",
            evidence=(str(exc)[:240],),
            deduction=deduction,
        )

    judge_score = float(payload.get("score", 0.0))
    passed = bool(payload.get("passed", False)) and judge_score >= judge.min_score
    if passed:
        return None

    deduction = judge.weight if judge.severity == "error" else judge.weight * 0.5
    reasons = payload.get("reasons") or payload.get("reason") or ()
    if isinstance(reasons, str):
        evidence = (reasons,)
    elif isinstance(reasons, list):
        evidence = tuple(str(item) for item in reasons[:6])
    else:
        evidence = ()
    return WritingSpecFinding(
        rule_id=judge.id,
        severity=judge.severity,
        message=(
            f"LLM 评审未通过：{judge.description}; "
            f"score={judge_score:.1f}, expected >= {judge.min_score:g}"
        ),
        evidence=evidence,
        deduction=deduction,
    )


def _build_judge_prompt(judge: LLMJudgeRule, spec: WritingSpec, content: str) -> Prompt:
    checklist = "\n".join(f"- {item}" for item in judge.checklist)
    system = (
        "你是 WritingSpec LLM Judge。你的任务是审查候选文本是否仍然满足写作规格，"
        "不是润色文本，也不是替作者辩护。只输出 JSON。"
    )
    user = (
        f"[spec_id]\n{spec.id}@{spec.version}\n\n"
        f"[core_question]\n{spec.core_question}\n\n"
        f"[meaning_contract]\n{spec.meaning_contract or spec.description}\n\n"
        f"[judge_description]\n{judge.description}\n\n"
        f"[checklist]\n{checklist}\n\n"
        "[output_json_schema]\n"
        '{"passed": boolean, "score": number, "reasons": string[]}\n\n'
        "[candidate_text]\n"
        f"{content[:12000]}"
    )
    return Prompt(system=system, user=user)


def _parse_judge_response(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        raw = raw[start:end + 1]
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("LLM judge response must be a JSON object")
    verdict = str(payload.get("verdict") or "").strip().lower()
    if "passed" not in payload and verdict:
        payload["passed"] = verdict in {"pass", "passed", "ok", "true"}
    if "score" not in payload:
        payload["score"] = 100 if payload.get("passed") else 0
    return payload


def _prompt_hash(prompt: Prompt) -> str:
    payload = json.dumps(
        {"system": prompt.system, "user": prompt.user},
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
