from __future__ import annotations

import pytest

from application.ai_invocation.dtos import (
    InvocationPolicy,
    InvocationSession,
    PromptSnapshot,
    VariablePlan,
    prompt_hash,
    stable_hash,
)
from application.ai_invocation.humanizer_runtime import (
    HUMANIZER_STATUS_KEY,
    HumanizerSettings,
    load_session_humanizer_settings,
)
from application.ai_invocation.services import AttemptService
from application.ai_invocation.variable_hub import InMemoryVariableHubRepository, VariableWrite
from domain.ai.services.llm_service import GenerationResult
from domain.ai.value_objects.prompt import Prompt
from domain.ai.value_objects.token_usage import TokenUsage


ORIGINAL = (
    "林默站在旧书店门口，雨水从招牌边缘落下来。"
    "他没有急着进去，只看着玻璃里自己的影子。"
    "柜台后的老人抬了抬眼，像是早就知道他会回来。"
    "街上的车灯一闪一闪，把地面的积水照得发白。"
) * 2

REWRITTEN = (
    "林默站在旧书店门口。雨从招牌边缘往下滴。"
    "他没急着进去，只盯着玻璃里的自己看。"
    "柜台后的老人抬了下眼，像早知道他会回来。"
    "车灯从街面扫过去，积水白了一瞬。"
) * 2


class FakeLLM:
    def __init__(self) -> None:
        self.generate_prompts = []

    async def generate(self, prompt, config):
        self.generate_prompts.append(prompt)
        content = REWRITTEN if "【原章节正文】" in prompt.user else ORIGINAL
        return GenerationResult(
            content=content,
            token_usage=TokenUsage(input_tokens=1, output_tokens=1),
        )

    async def stream_generate(self, prompt, config):
        midpoint = len(ORIGINAL) // 2
        yield ORIGINAL[:midpoint]
        yield ORIGINAL[midpoint:]


def _snapshot() -> PromptSnapshot:
    prompt = Prompt(system="你是小说作者。", user="写一章。")
    return PromptSnapshot(
        prompt=prompt,
        node_key="chapter-prose-generation",
        node_version_id="v1",
        asset_link_set_id="",
        input_binding_set_id="",
        output_binding_set_id="",
        variable_snapshot_hash="",
        template_hash=stable_hash({"template": "test"}),
        composition_hash=stable_hash({"composition": "test"}),
        rendered_prompt_hash=prompt_hash(prompt),
    )


def _session(operation: str = "chapter.generate.prose") -> InvocationSession:
    session = InvocationSession(
        id="session-1",
        operation=operation,
        node_key="chapter-prose-generation",
        policy=InvocationPolicy.DIRECT,
        context={"novel_id": "novel-1", "chapter_number": 3},
    )
    session.variable_plan = VariablePlan(aliases={})
    return session


def _repo_with_humanizer_enabled() -> InMemoryVariableHubRepository:
    repo = InMemoryVariableHubRepository()
    context_key = "novel_id:novel-1"
    repo.set_value(VariableWrite(key="novel.humanizer.enabled", value=True, context_key=context_key))
    repo.set_value(
        VariableWrite(
            key="novel.humanizer.revision_note",
            value="减少 AI 腔，保留物件细节。",
            context_key=context_key,
        )
    )
    return repo


def test_humanizer_settings_only_enable_for_chapter_prose_operations():
    repo = _repo_with_humanizer_enabled()

    enabled = load_session_humanizer_settings(_session(), repo)
    disabled = load_session_humanizer_settings(_session(operation="bible.setup.characters"), repo)

    assert enabled.enabled is True
    assert "减少 AI 腔" in enabled.revision_note
    assert disabled == HumanizerSettings()


@pytest.mark.asyncio
async def test_attempt_service_humanizes_generated_chapter_before_success():
    repo = _repo_with_humanizer_enabled()
    llm = FakeLLM()
    service = AttemptService(llm, variable_hub_repository=repo)

    attempt = await service.generate(
        session=_session(),
        prompt_snapshot=_snapshot(),
    )

    assert attempt.content == REWRITTEN
    assert attempt.status.value == "succeeded"
    assert len(llm.generate_prompts) == 2
    status = repo.get_value(HUMANIZER_STATUS_KEY, "novel_id:novel-1|chapter_number:3")
    assert status is not None
    assert status.value == "humanized"


@pytest.mark.asyncio
async def test_streaming_humanizer_hides_raw_chunks_until_final_text():
    repo = _repo_with_humanizer_enabled()
    llm = FakeLLM()
    service = AttemptService(llm, variable_hub_repository=repo)
    chunks: list[str] = []

    attempt = await service.generate_streaming(
        session=_session(),
        prompt_snapshot=_snapshot(),
        on_chunk=lambda chunk, _content: chunks.append(chunk),
    )

    assert attempt.content == REWRITTEN
    assert chunks == [REWRITTEN]
