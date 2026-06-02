# 《星河重启》PLM 导入包

这是《星河重启》的项目级写作包，用来把 PLM 从通用写作底座收束成这本书的专用生产线。

目标正文样稿：

- `/Users/gengrf/Desktop/工作区/claude/小说/星河重启-首富穿越计划/10-正文前三章正式稿.md`

当前边界：

- 只保存设定、章节规划、风格规则和审稿清单。
- 不直接写入 `data/plotpilot.db`。
- 不复用 `scripts/plm_homelander_100k_writer.py` 的硬编码结构。
- 生成正文前，先用本包生成章节提示，再进入 PLM/Codex/Humanizer 流程。

## 文件说明

| 文件 | 用途 |
| --- | --- |
| `project_bible.md` | 世界观、人物、势力、时间线、讽刺映射边界 |
| `chapter_plan_1_20.md` | 前 20 章长章规划，重点是高淳、高中、Dota1、老师、书店 |
| `style_guide.md` | 文风、对白、黑色幽默、禁用 AI 腔 |
| `target_style_anchor.md` | 从正式稿前三章提炼出的风格锚点 |
| `motif_audit.md` | 每章生成后的母题审稿清单 |
| `runtime/` | 脚本生成的章节提示输出目录 |

## 推荐流程

1. 先生成章节提示。

   ```bash
   .venv/bin/python scripts/plm_star_restart_prompt.py --chapter 1
   ```

2. 把 `projects/star_restart/runtime/chapter_01_prompt.md` 交给 PLM/Codex 生成初稿。

3. 初稿进入 Humanizer 时，带上 `style_guide.md` 和 `motif_audit.md` 里的修订要求。

4. 人工确认通过后，再把正文写回 PLM 数据库或正文文档。

## 生产原则

- 顾临川不是天生首富、豪门继承人或名校怪物。他先是被未来压扁的人，再是回到 2016 年小镇的成年人。
- 第一卷不能急着开挂。前 20 章的主要吸引力来自小镇生活、贫穷细节、甜美恋爱、Dota 圈人情和未来记忆带来的荒诞反差。
- 科技讽刺要好笑，不能只剩冷硬控诉。读者先笑出来，笑完才发现刀口在背后。
- AI 圈地、token 贷、模型霸权、国家资本主义和弱者失语是底层母题，必须让人物和生活细节承载，不要写成论文。
