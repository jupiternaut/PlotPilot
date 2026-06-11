from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from application.writing_spec import (
    WritingSpecValidator,
    apply_writing_spec_to_prompt,
    apply_writing_spec_to_snapshot,
    load_writing_spec,
    render_report_for_repair,
    render_writing_spec_contract,
    resolve_writing_spec_id,
    validate_writing_spec_with_judge,
)
from domain.ai.value_objects.prompt import Prompt


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "writing_specs/open_source_past.yaml"


@dataclass(frozen=True)
class _PromptSnapshot:
    prompt: Prompt
    rendered_prompt_hash: str
    diagnostics: tuple[str, ...] = ()


def _passing_open_source_past_text() -> str:
    paragraphs = [
        "# 外篇：被俘获的胜利",
        "开源赢了，但胜利并不等于自由。源代码从黑盒中流亡，又在漫长归乡后被新的城墙围住；Stallman、GNU、Linux 与 Apache 点燃的火种，后来穿过 GitHub 和 Hugging Face 这样的广场。问题在于，广场一旦成为唯一入口，就开始拥有城墙的功能。",
        "这不是因为开放失败，而是因为权力学会了不反对开放。IBM、MIT、PDP-10、Usenet 和 GPL 所代表的早期历史，说明封闭曾经依靠合同、律师、授权和金库；到了云厂商时代，封闭不再总是藏起代码，而是控制托管服务、分发入口、账号体系、默认选项和排名。",
        "于是，公司和商业平台可以同时赞美开源、吸收开源、重新包装开源。服务器、数据库、容器、控制台、账单、API、搜索排序、企业采购、用户关系和网络效应，构成新的制度现场。一旦这些现场被云和平台接管，开放代码仍然开放，使用道路却可能封闭。",
        "这就是被俘获的胜利。帝国不必宣布开源违法，也不必重新把共享知识锁回黑盒；它只要让离开变得昂贵，让重建变得困难，让每一次部署都经过同一个控制台和同一套账号。权力回来了，不是以禁令的形式，而是以方便的形式。",
        "这样的变化必须落在制度细节里看。早期软件行业把授权写进合同，把源代码放在只有雇员能够进入的实验室和机房里；后来的平台时代，则把协作、身份、发布、支付、企业采购和搜索排序做成一整套服务。用户得到的不是单一程序，而是一条被精心铺好的路径。",
        "路径越顺滑，选择越难被察觉。开发者当然还能下载源码，也当然还能自建服务器；可是数据库迁移、容器镜像、API 兼容、团队权限、审计日志和账单系统会一层层抬高离开的成本。这里的关键不是某家公司善恶如何，而是便利如何成为新的治理技术。",
        "所以这段历史仍然未完成。自由不是许可证上的一句话，也不是仓库里的星数，而是活人能否继续选择、复制、离开和重建。每一个人仍然要保存火种，因为归乡不是一次抵达，而是一代又一代人继续拆墙的劳动。",
    ]
    return "\n\n".join(paragraphs)


@dataclass
class _JudgeResult:
    content: str


class RejectingJudge:
    def __init__(self):
        self.prompts = []
        self.configs = []

    async def generate(self, prompt, config):
        self.prompts.append(prompt)
        self.configs.append(config)
        return _JudgeResult('{"passed": false, "score": 40, "reasons": ["只有主题词，没有历史因果链"]}')


def test_resolve_writing_spec_id_from_metadata_context_aliases_and_snapshot_items():
    assert resolve_writing_spec_id(metadata={"writing_spec_id": "open-source-past"}) == "open-source-past"
    assert resolve_writing_spec_id(context={"writing_style": "WritingSpec: open-source-past"}) == "open-source-past"
    assert resolve_writing_spec_id(aliases={"writingSpecId": "open-source-past-huggingface"}) == (
        "open-source-past-huggingface"
    )
    assert resolve_writing_spec_id(
        snapshot_items=(
            {"variable_key": "novel.writing_style", "value": "写作规格：open-source-past"},
        )
    ) == "open-source-past"


def test_render_contract_and_repair_prompt_include_reader_spec_and_findings():
    spec = load_writing_spec(SPEC_PATH)
    failed_report = WritingSpecValidator(spec).validate(
        "AI 编程助手生成了 commit message，云端 IDE 让一切都更快。本文认为 API 调用值得关注。"
    )

    contract = render_writing_spec_contract(spec)
    assert "reader_requirements:" in contract
    assert "reader_metrics:" in contract
    assert "reader-ai-war-jargon-density-limit" in contract
    assert "negative-default-entrance-generated" in contract

    repair = render_report_for_repair(failed_report)
    assert "失败规格: open-source-past" in repair
    assert "exile-and-return-axis" in repair

    prompt = Prompt(system="你是严肃史论作者。", user="续写《开源往事》。")
    patched = apply_writing_spec_to_prompt(
        prompt,
        spec,
        previous_content="失败稿正文",
        previous_report=failed_report,
    )
    assert "WritingSpec 固化合同" in patched.system
    assert "WritingSpec 自动返工" in patched.user
    assert "失败稿正文" in patched.user


def test_apply_writing_spec_to_snapshot_updates_prompt_hash_and_diagnostics():
    spec = load_writing_spec(SPEC_PATH)
    prompt = Prompt(system="你是严肃史论作者。", user="续写《开源往事》。")
    snapshot = _PromptSnapshot(
        prompt=prompt,
        rendered_prompt_hash="old-hash",
    )

    patched = apply_writing_spec_to_snapshot(snapshot, spec)

    assert patched.rendered_prompt_hash != snapshot.rendered_prompt_hash
    assert patched.diagnostics == ("WritingSpec active: open-source-past@0.3",)
    assert "WritingSpec 固化合同" in patched.prompt.system


def test_validate_writing_spec_with_judge_rejects_when_judge_fails():
    spec = load_writing_spec(SPEC_PATH)
    judge = RejectingJudge()

    report = asyncio.run(validate_writing_spec_with_judge(spec, _passing_open_source_past_text(), judge))

    assert report.passed is False
    assert any(finding.rule_id == "open-source-past-llm-judge" for finding in report.findings)
    assert len(judge.prompts) == 1
    assert "WritingSpec LLM Judge" in judge.prompts[0].system
    assert judge.configs[0].temperature == 0.0
