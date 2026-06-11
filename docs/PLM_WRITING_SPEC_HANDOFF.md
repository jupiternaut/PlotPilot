# PLM WritingSpec Handoff

更新时间：2026-06-11

源分支：`plm-v4.5.1-port`

当前移植分支：`plm-v4.6-port`，底座为官方 `v4.6.0`。本分支已将 WritingSpec 运行时、Codex OAuth provider、Humanizer 服务/脚本、PLM 项目包和章节提示脚本迁入 4.6 结构；提交时注意 `docs/` 被 `.gitignore` 忽略，需要用 `git add -f docs/PLM_WRITING_SPEC_HANDOFF.md` 纳入版本库。

目标：把 PLM 从“能调用模型写文”推进到“按 WritingSpec 生产、校验、返工和保存文本”的写作 CI。当前已经有可运行的 WritingSpec/ReaderSpec 基础设施，但还没有覆盖所有生成、润色、导出和事实校验路径。

## 当前状态

PLM 已经具备以下能力：

- `WritingSpec` 可以从 YAML 加载 `required`、`meaning.argument_steps`、`reader.requirements`、`forbidden`、`metrics`、`reader.metrics`、`examples` 和 `judge`。
- `AttemptService` 在 AI Invocation 生成前注入 WritingSpec 合同，生成后执行确定性校验和可选 LLM Judge。
- 生成失败时最多自动返工 2 次，最终失败会抛出 `WritingSpecGateError`。
- Streaming 生成在启用 WritingSpec 时会先内部生成和校验，通过后才把内容一次性推给前端，避免失败稿露出。
- 章节保存接口支持 `writing_spec_id` 或项目绑定的 `novel.writing_spec_id`，不通过时返回 `422`，不会写入章节正文。
- 验收报告会写入 Variable Hub：`chapter.writing_spec.report` 和 `chapter.writing_spec.status`。

当前内置规格：

| spec_id | 用途 |
| --- | --- |
| `open-source-past` | 《开源往事》通用外篇规格，约束代码文明史主轴、平台俘获、ReaderSpec 外行阅读坡度。 |
| `open-source-past-huggingface` | 《开源往事》Hugging Face 外篇规格，要求 Transformers / Hub / model cards / 开源权重生态事实链，并拦截口语科普稿。 |

## 本轮新增

新增 `writing_specs/open_source_past_huggingface.yaml`：

- 专门约束 Hugging Face 外篇，而不是污染通用 `open-source-past`。
- 要求文本先建立 Hugging Face / Transformers / Hub / model cards / dataset cards 的历史事实链。
- 要求把模型生态放进 Stable Diffusion / LLaMA / Mistral / Qwen / DeepSeek 等开源权重传播背景。
- 要求解释模型不同于传统代码：权重、训练数据、许可证、算力、推理服务和可见性共同构成新的权力边界。
- 禁止把章节写成口语科普、功能说明文、虚构平台案例或二元对照式行业评论。

新增 `writing_specs/examples/open_source_past_huggingface/negative_plain_explainer.md`：

- 固化此前失败模式：文本更好读，但缺少历史事实链、原文庄重叙事和《开源往事》的文明史骨架。
- 后续生成稿与该反例过像时，会触发 `negative-huggingface-plain-explainer`。

补充测试：

- `test_open_source_past_huggingface_spec_accepts_historical_narrative_draft`
- `test_open_source_past_huggingface_spec_rejects_plain_explainer_draft`
- `test_open_source_past_spec_rejects_ai_war_jargon_wall_for_lay_reader`

## 仍未闭环

### 1. SourceSpec 未闭环

当前规格能要求出现事实锚点，但不能验证事实真伪、顺序和因果。

缺口：

- 没有事实卡数据结构。
- 没有来源 URL / 文档 / 本地资料到章节论证链的绑定。
- 没有“事实 A 是否真的推出机制 B”的校验。
- 无法拦截看似合理但实际编造的历史链。

建议目标链路：

```text
source material -> fact cards -> source spec -> generated prose -> fact validation report
```

### 2. StyleProfile 未闭环

当前 StyleSpec 主要靠人工规则，如段落长度、短句比例、禁用口语科普腔。它还没有从原文自动提取文法画像。

缺口：

- 未从《开源往事(1).md》提取段落长度分布。
- 未提取短句位置和短句用途。
- 未提取长短句组合、章节开头模式、结尾收束模式。
- 未提取原文核心意象系统，如黑盒、火种、教堂、市场、广场、城墙。
- 规格仍然偏关键词和人工阈值，不是统计基线。

建议目标链路：

```text
source essay -> style profile extraction -> style metrics baseline -> generation prompt -> style gate
```

### 3. InferenceSpec / PoliticalLogicSpec 未闭环

当前 MeaningSpec 还是关键词命中型，可以要求“论证骨架出现”，但不能验证推理链是否成立。

典型失败：

```text
这不是悖论。
这是商业模式。
```

这类句子可能有判断，但缺少中间推理：事实是什么、谁被保护、谁定义安全/法律、结构性利益如何服务结论。

建议新增结构：

```yaml
inference:
  chains:
    - id: platform-capture-chain
      steps:
        - fact
        - actor
        - power_relation
        - mechanism
        - consequence
        - final_judgment
```

### 4. Humanizer 未闭环

Humanizer 当前是后处理润色器，主要减少 AI 腔、论文腔、节奏均匀感和对白假。它不理解 WritingSpec，也不会天然保证润色后仍符合规格。

风险：

- 能把生涩文本改顺。
- 也可能把史论庄重感改成口语说明文。
- 也可能删除必要事实锚点。

建议目标链路：

```text
generate -> writing spec gate -> humanizer -> writing spec gate again -> save
```

### 5. Autopilot 端到端绑定未闭环

`AttemptService` 已支持 WritingSpec，但需要用真实书籍跑完整 Autopilot 验证。

待验证：

- Autopilot 章节生成是否稳定带上 `novel.writing_spec_id`。
- StoryPipeline 的所有正文生成节点是否都走 AI Invocation。
- 自动驾驶失败后，前端是否能展示 WritingSpec 失败项和返工轮次。
- 审阅、after-chapter extraction、Humanizer 是否有绕过 gate 的路径。

### 6. 保存和导出路径未统一

正式章节保存接口有门禁，但以下路径可能绕过：

- 直接编辑 Markdown。
- 桌面导出脚本。
- 单独运行 `scripts/humanize_chapter.py`。
- 部分数据库脚本直接写 `chapters.content`。
- 非 AI Invocation 的临时生成脚本。

目标是所有正文出口都经过统一入口：

```text
prose output -> WritingSpec gate -> persistence/export
```

### 7. LLM Judge 还不够独立

当前 LLM Judge 是可选项，且通常复用同一个 LLM 服务。它能补确定性规则的语义盲区，但还不是强隔离评审。

缺口：

- 缺少独立 judge profile。
- 缺少 judge 结果的可视化。
- 缺少 judge prompt 版本追踪。
- 缺少多 judge 投票或冲突处理。

### 8. UI 还不是完整产品体验

后端已有绑定 API：

```http
PUT /api/v1/novels/{novel_id}/writing-spec
Content-Type: application/json

{"writing_spec_id":"open-source-past-huggingface"}
```

但前端还需要明确显示：

- 当前项目绑定的 `spec_id`。
- 本章 WritingSpec 状态。
- 失败项、证据、扣分。
- 自动返工轮次。
- Humanizer 后是否二次通过。
- 最终写入内容对应的 spec report。

## 推荐下一步

优先级 1：让 Humanizer spec-aware

- Humanizer 接收 active WritingSpec。
- 润色前后都运行 `validate_writing_spec_with_judge`。
- 润色后失败则保留原文或进入专项返工。
- 把 Humanizer 的 diff 和 spec report 绑定到同一章。

优先级 2：做 StyleProfile 提取器

- 输入原文 Markdown。
- 输出 `style_profiles/open_source_past.json`。
- 指标包括段落长度分布、短句比例、短段落连续度、术语密度、核心意象密度、章节开头/结尾模式。
- WritingSpec YAML 引用该 profile，而不是手写所有阈值。

优先级 3：做 SourceSpec / FactCard

- 为 Hugging Face 外篇建立事实卡。
- 事实卡至少包含 `claim`、`source`、`date`、`actors`、`allowed_use`。
- 生成稿必须引用或覆盖必需 fact cards。
- 保存前检查事实覆盖率和未支撑判断。

优先级 4：跑 Autopilot e2e

- 创建测试书籍。
- 绑定 `open-source-past-huggingface`。
- 使用 Codex profile 生成一章。
- 验证失败稿不会写入。
- 验证通过稿写入后能看到 `chapter.writing_spec.report`。

## 验收命令

当前目标单测：

```bash
uv run --python /opt/homebrew/bin/python3.14 --with pytest --with pyyaml pytest tests/unit/test_writing_spec.py -q
```

反例 CLI 验证：

```bash
uv run --python /opt/homebrew/bin/python3.14 --with pyyaml python scripts/writing_spec.py validate \
  --spec writing_specs/open_source_past_huggingface.yaml \
  --input writing_specs/examples/open_source_past_huggingface/negative_plain_explainer.md
```

预期：CLI 返回 `FAIL`，并命中：

- `huggingface-plain-explainer-register`
- `fictional-platform-case`
- `negative-huggingface-plain-explainer`

## 当前风险

- 新的 Hugging Face 规格仍依赖关键词和人工阈值，不能替代事实校验。
- 好稿样本是测试内联文本，不是来自真实生成链路。
- LLM Judge 在单元测试里不实际调用在线模型。
- 若用户直接编辑文件或绕过 AI Invocation，WritingSpec 不会执行。
- `.venv/` 是测试时临时创建的环境，已清理；如需复跑测试可继续使用 `uv run`。

## 文件范围

本轮相关文件：

- `application/writing_spec/models.py`
- `application/writing_spec/runtime.py`
- `application/writing_spec/validator.py`
- `tests/unit/test_writing_spec.py`
- `writing_specs/README.md`
- `writing_specs/open_source_past.yaml`
- `writing_specs/open_source_past_huggingface.yaml`
- `writing_specs/examples/open_source_past_huggingface/negative_plain_explainer.md`
- `docs/PLM_WRITING_SPEC_HANDOFF.md`

## 交接判断

PLM 现在不是“没有 spec”，而是已经有 WritingSpec Gate 的基础设施，但还不是完整写作 CI。

下一阶段的工程判断：

```text
不要继续只加 prompt。
要把 SourceSpec、StyleProfile、Humanizer 二次门禁和 Autopilot e2e 串起来。
```

做到这一步后，PLM 才会从“能检查文章”变成“能按规格稳定生产文章”。
