"""Optional Humanizer post-processing for chapter prose invocation."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping

from application.ai_invocation.variable_hub import VariableHubRepository, VariableWrite
from application.engine.services.humanizer_service import HumanizerService
from application.writing_spec import (
    WritingSpec,
    WritingSpecGateError,
    validate_writing_spec_with_judge,
)

logger = logging.getLogger(__name__)

HUMANIZER_ENABLED_KEY = "novel.humanizer.enabled"
HUMANIZER_REVISION_NOTE_KEY = "novel.humanizer.revision_note"
HUMANIZER_FAILURE_POLICY_KEY = "novel.humanizer.failure_policy"
HUMANIZER_TEMPERATURE_KEY = "novel.humanizer.temperature"
HUMANIZER_MAX_TOKENS_KEY = "novel.humanizer.max_tokens"

HUMANIZER_REPORT_KEY = "chapter.humanizer.report"
HUMANIZER_STATUS_KEY = "chapter.humanizer.status"

_CHAPTER_PROSE_OPERATIONS = {
    "chapter.generate",
    "chapter.generate.prose",
    "autopilot.chapter.prose",
}


@dataclass(frozen=True)
class HumanizerSettings:
    enabled: bool = False
    revision_note: str = ""
    failure_policy: str = "fallback_original"
    temperature: float = 0.65
    max_tokens: int | None = None


@dataclass(frozen=True)
class HumanizerResult:
    content: str
    status: str = "disabled"
    changed: bool = False


def load_session_humanizer_settings(
    session: Any,
    variable_hub_repository: VariableHubRepository | None = None,
) -> HumanizerSettings:
    """Resolve per-novel Humanizer settings for chapter prose only."""

    if str(getattr(session, "operation", "") or "") not in _CHAPTER_PROSE_OPERATIONS:
        return HumanizerSettings()

    raw: dict[str, Any] = {}
    variable_plan = getattr(session, "variable_plan", None)
    for source in (
        getattr(session, "metadata", None) or {},
        getattr(session, "context", None) or {},
        getattr(variable_plan, "aliases", None) or {},
    ):
        _merge_humanizer_values(raw, source)
    for item in getattr(variable_plan, "snapshot_items", None) or ():
        key = str(item.get("variable_key") or item.get("key") or "")
        if key:
            _merge_humanizer_values(raw, {key: item.get("value")})

    novel_id = str((getattr(session, "context", None) or {}).get("novel_id") or "").strip()
    if novel_id and variable_hub_repository is not None:
        context_key = _novel_context_key(novel_id)
        for key in (
            HUMANIZER_ENABLED_KEY,
            HUMANIZER_REVISION_NOTE_KEY,
            HUMANIZER_FAILURE_POLICY_KEY,
            HUMANIZER_TEMPERATURE_KEY,
            HUMANIZER_MAX_TOKENS_KEY,
        ):
            value = variable_hub_repository.get_value(key, context_key)
            if value is not None:
                raw[key] = value.value
    elif novel_id:
        raw.update(_load_humanizer_values_from_default_repo(novel_id))

    enabled = _as_bool(raw.get(HUMANIZER_ENABLED_KEY) or raw.get("humanizer_enabled"))
    failure_policy = str(
        raw.get(HUMANIZER_FAILURE_POLICY_KEY)
        or raw.get("humanizer_failure_policy")
        or "fallback_original"
    ).strip()
    if failure_policy not in {"fallback_original", "fail"}:
        failure_policy = "fallback_original"

    return HumanizerSettings(
        enabled=enabled,
        revision_note=str(
            raw.get(HUMANIZER_REVISION_NOTE_KEY)
            or raw.get("humanizer_revision_note")
            or ""
        ).strip(),
        failure_policy=failure_policy,
        temperature=_as_float(
            raw.get(HUMANIZER_TEMPERATURE_KEY) or raw.get("humanizer_temperature"),
            default=0.65,
        ),
        max_tokens=_as_optional_int(raw.get(HUMANIZER_MAX_TOKENS_KEY) or raw.get("humanizer_max_tokens")),
    )


async def maybe_humanize_content(
    *,
    session: Any,
    content: str,
    llm_service: Any,
    writing_spec: WritingSpec | None = None,
    attempt_id: str = "",
    settings: HumanizerSettings | None = None,
    variable_hub_repository: VariableHubRepository | None = None,
) -> HumanizerResult:
    """Run Humanizer after generation and before adoption/save when enabled."""

    active = settings or load_session_humanizer_settings(session, variable_hub_repository)
    if not active.enabled:
        return HumanizerResult(content=content)

    novel_id = str((getattr(session, "context", None) or {}).get("novel_id") or "").strip()
    chapter_number = _as_optional_int((getattr(session, "context", None) or {}).get("chapter_number")) or 0
    original = str(content or "")
    try:
        rewritten = await HumanizerService(llm_service).humanize_chapter(
            original,
            character_context=_character_context_from_session(session),
            novel_id=novel_id,
            chapter_num=chapter_number,
            revision_note=active.revision_note,
            max_tokens=active.max_tokens,
            temperature=active.temperature,
        )
    except Exception as exc:
        _persist_humanizer_report(
            session=session,
            attempt_id=attempt_id,
            settings=active,
            status="failed_exception",
            original=original,
            rewritten=original,
            error=str(exc),
            variable_hub_repository=variable_hub_repository,
        )
        if active.failure_policy == "fail":
            raise
        return HumanizerResult(content=original, status="failed_exception", changed=False)

    changed = rewritten.strip() != original.strip()
    if not changed:
        _persist_humanizer_report(
            session=session,
            attempt_id=attempt_id,
            settings=active,
            status="unchanged_or_skipped",
            original=original,
            rewritten=rewritten,
            variable_hub_repository=variable_hub_repository,
        )
        return HumanizerResult(content=original, status="unchanged_or_skipped", changed=False)

    if writing_spec is not None:
        report = await validate_writing_spec_with_judge(writing_spec, rewritten, llm_service)
        if not report.passed:
            _persist_humanizer_report(
                session=session,
                attempt_id=attempt_id,
                settings=active,
                status="failed_writing_spec_fallback_original"
                if active.failure_policy != "fail"
                else "failed_writing_spec",
                original=original,
                rewritten=rewritten,
                post_writing_spec_report=report.to_dict(),
                variable_hub_repository=variable_hub_repository,
            )
            if active.failure_policy == "fail":
                raise WritingSpecGateError(report)
            return HumanizerResult(
                content=original,
                status="failed_writing_spec_fallback_original",
                changed=False,
            )

        _persist_humanizer_report(
            session=session,
            attempt_id=attempt_id,
            settings=active,
            status="humanized_passed_writing_spec",
            original=original,
            rewritten=rewritten,
            post_writing_spec_report=report.to_dict(),
            variable_hub_repository=variable_hub_repository,
        )
        return HumanizerResult(content=rewritten, status="humanized_passed_writing_spec", changed=True)

    _persist_humanizer_report(
        session=session,
        attempt_id=attempt_id,
        settings=active,
        status="humanized",
        original=original,
        rewritten=rewritten,
        variable_hub_repository=variable_hub_repository,
    )
    return HumanizerResult(content=rewritten, status="humanized", changed=True)


def _merge_humanizer_values(target: dict[str, Any], source: Mapping[str, Any]) -> None:
    for key, value in source.items():
        normalized = str(key or "").strip()
        if normalized in {
            HUMANIZER_ENABLED_KEY,
            HUMANIZER_REVISION_NOTE_KEY,
            HUMANIZER_FAILURE_POLICY_KEY,
            HUMANIZER_TEMPERATURE_KEY,
            HUMANIZER_MAX_TOKENS_KEY,
            "humanizer_enabled",
            "humanizer_revision_note",
            "humanizer_failure_policy",
            "humanizer_temperature",
            "humanizer_max_tokens",
        }:
            target[normalized] = value


def _load_humanizer_values_from_default_repo(novel_id: str) -> dict[str, Any]:
    try:
        from infrastructure.persistence.database.connection import get_database
        from infrastructure.persistence.database.sqlite_ai_invocation_repository import SqliteVariableHubRepository
    except Exception:
        return {}

    repo = SqliteVariableHubRepository(get_database())
    context_key = _novel_context_key(novel_id)
    values: dict[str, Any] = {}
    for key in (
        HUMANIZER_ENABLED_KEY,
        HUMANIZER_REVISION_NOTE_KEY,
        HUMANIZER_FAILURE_POLICY_KEY,
        HUMANIZER_TEMPERATURE_KEY,
        HUMANIZER_MAX_TOKENS_KEY,
    ):
        value = repo.get_value(key, context_key)
        if value is not None:
            values[key] = value.value
    return values


def _persist_humanizer_report(
    *,
    session: Any,
    attempt_id: str,
    settings: HumanizerSettings,
    status: str,
    original: str,
    rewritten: str,
    error: str = "",
    post_writing_spec_report: Mapping[str, Any] | None = None,
    variable_hub_repository: VariableHubRepository | None = None,
) -> None:
    repo = variable_hub_repository or _default_variable_repo()
    if repo is None:
        return

    context_key = _chapter_context_key(getattr(session, "context", None) or {})
    payload = {
        "status": status,
        "attempt_id": attempt_id,
        "operation": getattr(session, "operation", ""),
        "node_key": getattr(session, "node_key", ""),
        "original_length": len(original),
        "rewritten_length": len(rewritten),
        "changed": original.strip() != rewritten.strip(),
        "failure_policy": settings.failure_policy,
        "error": error,
    }
    if post_writing_spec_report is not None:
        payload["post_writing_spec_report"] = dict(post_writing_spec_report)
    try:
        repo.set_value(
            VariableWrite(
                key=HUMANIZER_REPORT_KEY,
                value=payload,
                context_key=context_key,
                source_session_id=getattr(session, "id", ""),
                source_attempt_id=attempt_id,
                source_node_key=getattr(session, "node_key", ""),
                value_type="object",
                display_name="Humanizer 润色报告",
                scope="chapter" if "chapter_number:" in context_key else "novel",
                stage="review",
            )
        )
        repo.set_value(
            VariableWrite(
                key=HUMANIZER_STATUS_KEY,
                value=status,
                context_key=context_key,
                source_session_id=getattr(session, "id", ""),
                source_attempt_id=attempt_id,
                source_node_key=getattr(session, "node_key", ""),
                value_type="string",
                display_name="Humanizer 润色状态",
                scope="chapter" if "chapter_number:" in context_key else "novel",
                stage="review",
            )
        )
    except Exception:
        logger.warning("failed to persist Humanizer report", exc_info=True)


def _default_variable_repo() -> VariableHubRepository | None:
    try:
        from infrastructure.persistence.database.connection import get_database
        from infrastructure.persistence.database.sqlite_ai_invocation_repository import SqliteVariableHubRepository
    except Exception:
        return None
    return SqliteVariableHubRepository(get_database())


def _character_context_from_session(session: Any) -> str:
    variable_plan = getattr(session, "variable_plan", None)
    lines: list[str] = []
    for item in getattr(variable_plan, "snapshot_items", None) or ():
        key = str(item.get("variable_key") or item.get("key") or "").lower()
        if "character" not in key and "角色" not in key:
            continue
        value = item.get("value")
        if value in (None, "", [], {}):
            continue
        lines.append(f"- {item.get('display_name') or item.get('key') or key}: {value}")
    return "\n".join(lines)[:4000]


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on", "enabled", "开启", "是"}


def _as_float(value: Any, *, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return min(2.0, max(0.0, parsed))


def _as_optional_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _novel_context_key(novel_id: str) -> str:
    return f"novel_id:{novel_id}"


def _chapter_context_key(context: Mapping[str, Any]) -> str:
    novel_id = str(context.get("novel_id") or "").strip()
    chapter_number = context.get("chapter_number")
    if novel_id and chapter_number not in (None, ""):
        return f"novel_id:{novel_id}|chapter_number:{chapter_number}"
    if novel_id:
        return _novel_context_key(novel_id)
    return "global"
