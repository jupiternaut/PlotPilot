"""Chapter humanizer service.

This conservative rewrite pass keeps plot facts unchanged while reducing
essay-like connective tissue, uniform rhythm, and generic AI prose.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime

from domain.ai.services.llm_service import GenerationConfig, LLMService
from domain.ai.value_objects.prompt import Prompt

logger = logging.getLogger(__name__)

_DIFF_LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "logs")


HUMANIZER_SYSTEM_PROMPT = """你是一位小说终稿编辑，任务是把已经生成的章节润色成更像真人写作的中文小说。

核心目标：
1. 保留原章节的剧情、人物关系、事件顺序、悬念和结尾钩子，不新增重大情节。
2. 优先修改对话：让人物说话更口语、更短、更有各自习惯；允许停顿、打断、省略和重复。
3. 删除 AI 腔和论文腔：不要出现“值得注意的是、与此同时、不言而喻、彰显、凸显、赋能、综上所述、由此可见”等套话。
4. 打破均匀感：段落长短、句子长度、信息密度和叙事速度都要有变化。
5. 情绪用动作、物件、停顿和场面反应表现，不要直说“复杂情绪涌上心头”“空气中弥漫着微妙气氛”。
6. 保持原文体量，允许在原文长度的 80% 到 120% 间浮动。
7. 宁可保留一点真实的粗糙，也不要改成过分精致、过分工整、过分像范文。

禁止：
- 不要输出解释、点评、标题、修改说明或列表。
- 不要把严肃段落强行改成段子。
- 不要改变人物名字、地点、道具、时间线和超自然规则。
- 不要把原本含蓄的关系直接说破。

只输出润色后的完整正文。"""


HUMANIZER_USER_TEMPLATE = """请按上述规则润色下面这一章。

{revision_note}
{character_context}
【原章节正文】
{content}

请直接输出润色后的完整正文。"""


def _write_diff_log(novel_id: str, chapter_num: int, original: str, rewritten: str) -> str:
    log_dir = os.path.normpath(_DIFF_LOG_DIR)
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "humanizer_diff.log")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sep = "=" * 80
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n{sep}\n")
        f.write(f"[{ts}] {novel_id or '-'} chapter={chapter_num or '-'}\n")
        f.write(f"original {len(original)} chars -> rewritten {len(rewritten)} chars\n")
        f.write(f"{sep}\n")
        f.write(f"【原文】\n{original}\n\n")
        f.write(f"【润色后】\n{rewritten}\n\n")
    return log_path


class HumanizerService:
    """LLM-backed chapter polishing service."""

    def __init__(self, llm_service: LLMService) -> None:
        self.llm_service = llm_service

    async def humanize_chapter(
        self,
        content: str,
        character_context: str = "",
        novel_id: str = "",
        chapter_num: int = 0,
        *,
        revision_note: str = "",
        max_tokens: int | None = None,
        temperature: float = 0.65,
    ) -> str:
        stripped = (content or "").strip()
        if len(stripped) < 100:
            logger.info("[%s] chapter %s too short, skip humanizer", novel_id, chapter_num)
            return content

        user_msg = HUMANIZER_USER_TEMPLATE.format(
            revision_note=(
                f"【本轮专项修订要求】\n{revision_note.strip()}\n\n"
                if revision_note and revision_note.strip()
                else ""
            ),
            character_context=(
                f"【人物声线参考】\n{character_context}\n\n" if character_context else ""
            ),
            content=stripped,
        )
        prompt = Prompt(system=HUMANIZER_SYSTEM_PROMPT, user=user_msg)
        token_budget = max_tokens or max(4096, int(len(stripped) * 2.2))
        config = GenerationConfig(max_tokens=token_budget, temperature=temperature)

        logger.info("[%s] humanizer start chapter=%s chars=%s", novel_id, chapter_num, len(stripped))
        result = await self.llm_service.generate(prompt, config)
        rewritten = (result.content or "").strip()

        min_len = int(len(stripped) * 0.55)
        max_len = int(len(stripped) * 1.45)
        if not rewritten or len(rewritten) < min_len:
            logger.warning(
                "[%s] humanizer output too short chapter=%s original=%s rewritten=%s; keep original",
                novel_id,
                chapter_num,
                len(stripped),
                len(rewritten),
            )
            return content
        if len(rewritten) > max_len:
            logger.warning(
                "[%s] humanizer output too long chapter=%s original=%s rewritten=%s; keep original",
                novel_id,
                chapter_num,
                len(stripped),
                len(rewritten),
            )
            return content

        try:
            _write_diff_log(novel_id, chapter_num, stripped, rewritten)
        except Exception as exc:
            logger.debug("humanizer diff log failed: %s", exc)

        logger.info("[%s] humanizer done chapter=%s chars=%s->%s", novel_id, chapter_num, len(stripped), len(rewritten))
        return rewritten
