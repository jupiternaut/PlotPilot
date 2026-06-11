from types import SimpleNamespace

import pytest

from application.engine.services import humanizer_service
from application.engine.services.humanizer_service import (
    HUMANIZER_SYSTEM_PROMPT,
    HumanizerService,
)
from domain.ai.services.llm_service import GenerationConfig
from domain.ai.value_objects.prompt import Prompt


ORIGINAL = (
    "林默站在雨棚下，看着对街的灯一盏盏灭掉。"
    "他没有立刻回头，只把伞柄攥得更紧。"
    "身后的脚步声停在三步之外，像是在等他先开口。"
    "雨水从棚沿落下来，砸在铁皮桶里，一声比一声空。"
) * 2

REWRITTEN = (
    "林默站在雨棚下。对街的灯灭了一盏，又一盏。"
    "他没回头，只把伞柄攥紧。"
    "身后的脚步停在三步外，没人催他。"
    "雨从棚沿砸进铁皮桶里，响得发空。"
) * 2


class _FakeLLM:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls = []

    async def generate(self, prompt: Prompt, config: GenerationConfig) -> SimpleNamespace:
        self.calls.append((prompt, config))
        return SimpleNamespace(content=self.content)


def test_humanizer_service_imports() -> None:
    assert HumanizerService
    assert "只输出润色后的完整正文" in HUMANIZER_SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_humanize_skips_short_content_without_llm() -> None:
    llm = _FakeLLM(REWRITTEN)
    service = HumanizerService(llm)

    content = "太短的一章。"
    result = await service.humanize_chapter(content, novel_id="novel-1", chapter_num=1)

    assert result == content
    assert llm.calls == []


@pytest.mark.asyncio
async def test_humanize_builds_prompt_and_writes_diff_log(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(humanizer_service, "_DIFF_LOG_DIR", str(tmp_path))
    llm = _FakeLLM(f"\n{REWRITTEN}\n")
    service = HumanizerService(llm)

    result = await service.humanize_chapter(
        f"\n{ORIGINAL}\n",
        character_context="林默：说话短，习惯先停顿。",
        novel_id="novel-1",
        chapter_num=7,
        revision_note="减少论文腔。",
        max_tokens=5000,
        temperature=0.4,
    )

    assert result == REWRITTEN
    assert len(llm.calls) == 1
    prompt, config = llm.calls[0]
    assert "减少论文腔" in prompt.user
    assert "林默：说话短" in prompt.user
    assert ORIGINAL in prompt.user
    assert config.temperature == 0.4

    log_text = (tmp_path / "humanizer_diff.log").read_text(encoding="utf-8")
    assert "novel-1 chapter=7" in log_text
    assert ORIGINAL in log_text
    assert REWRITTEN in log_text


@pytest.mark.asyncio
async def test_humanize_keeps_original_when_output_outside_length_bounds(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(humanizer_service, "_DIFF_LOG_DIR", str(tmp_path))

    for rewritten in ("太短。", ORIGINAL * 2):
        llm = _FakeLLM(rewritten)
        service = HumanizerService(llm)

        result = await service.humanize_chapter(ORIGINAL, novel_id="novel-1", chapter_num=8)

        assert result == ORIGINAL
        assert len(llm.calls) == 1

    assert not (tmp_path / "humanizer_diff.log").exists()
