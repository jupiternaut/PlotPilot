# WritingSpec

WritingSpec 是 PLM 的轻量写作契约层，用来在文本写入前检查“是否仍然是同一篇文章”。

当前 4.6 移植版本提供基础验证能力：

- `required`：必须出现的主题、写意、历史锚点。
- `meaning.argument_steps`：必须出现的论证骨架，不再只看关键词。
- `reader.requirements`：必须给外行读者入口和解释台阶，防止概念直接砸脸。
- `forbidden`：明确禁止的偏题方向、俗套写法、错误体裁。
- `metrics` / `style.metrics` / `reader.metrics`：段落、短句、句长、碎句比例、连续碎句、主题词密度、术语密度等指标。
- `meaning_contract`：可渲染为运行时写作合同，防止“文风像但意思变了”。
- `examples.negative`：反例样本库；生成稿与反例过像会直接失败。
- `judge`：可选 LLM 评审配置；CLI 默认只做确定性规则与 ExampleBank 检查。

PLM 里的 WritingSpec v2 结构：

```text
WritingSpec
  ├─ MeaningSpec：这篇文章到底在写什么，要求论证骨架和事实承重
  ├─ StyleSpec：句法、节奏、隐喻、语气，限制碎句口号和主题词刷分
  ├─ ReaderSpec：外行入口、解释台阶、术语密度和信息坡度
  ├─ AntiSpec：禁止写成什么
  ├─ ExampleBank：正例/反例
  ├─ Verifier：规则检查 + 可选 LLM 评审 + 反例相似度
  └─ Gate：不通过就不应进入正文保存或发布
```

内置规格：

| spec_id | 用途 |
| --- | --- |
| `open-source-past` | 《开源往事》通用外篇，约束代码文明史主轴、平台俘获、外行阅读坡度。 |
| `open-source-past-huggingface` | 《开源往事》Hugging Face 外篇，要求 Transformers / Hub / model cards / 开源权重生态的事实链，并拦截口语科普稿。 |

运行示例：

```bash
python scripts/writing_spec.py validate \
  --spec writing_specs/open_source_past.yaml \
  --input /Users/gengrf/Desktop/开源往事·外篇-被俘获的胜利.md
```

如果返回 `FAIL`，文本不应写入 PLM 正文区，应先重写或人工确认。

说明：本次 4.6 移植没有接入生成链路、章节保存接口、Autopilot 或 Humanizer；这些链路需要后续在各自模块中显式接入后才会自动执行 WritingSpec。
