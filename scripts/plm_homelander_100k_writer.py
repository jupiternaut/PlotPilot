#!/usr/bin/env python3
"""Generate a 100k-char PLM novel draft through the local Codex provider.

The script is intentionally resumable. It creates/updates a PlotPilot book in
SQLite, generates chapter prose through the PLM Codex app-server provider, saves
each chapter immediately, and refreshes a desktop Markdown manuscript.
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from domain.ai.services.llm_service import GenerationConfig
from domain.ai.value_objects.prompt import Prompt
from infrastructure.ai.config.settings import Settings
from infrastructure.ai.providers.codex_app_server_provider import CodexAppServerProvider

NOVEL_ID = "novel-homelander-lost-power-100k"
TITLE = "穿越成了失去能力的祖国人，发誓夺回属于自己的一切"
AUTHOR = "gengrf"
TARGET_CHARS = 100_000
TARGET_CHARS_PER_CHAPTER = 3_400
DESKTOP_MANUSCRIPT = Path.home() / "Desktop" / "穿越成了失去能力的祖国人-十万字草稿.md"

PREMISE = """同人爽文/黑暗逃生改写。祖国人被喜梅子夺取超级能力后没有立刻下线。
他没有杀死爆竹女，而是逼她用“爱”证明忠诚，替自己阻挡黑袍小队，自己从白宫秘密通道逃到外围。
逃出白宫后，他伪装成普通路人，却不断遭遇白眼、殴打、饥饿、寒冷、羞辱和媒体清算。
他反复说自己是祖国人，但人人喊打；他没了超能力，连普通人都打不过。
电视里黑袍小队宣布祖国人是暴君，超级英雄统治被推翻。祖国人不得不隐姓埋名。
第一卷的主体是三万字以上的窝囊逃生：他被打、被抢、被利用、被迫低头，慢慢接受自己只是普通人。
结尾他受到刺激，看见有人占据他的符号和位置，于是发誓把失去的一切夺回来。
后续方向：他给其他七人组残党画饼，靠阴险狡诈复苏士兵男孩，最终去找初代五号化合物，变成超级单体。"""

STYLE_RULES = """写作规则：
- 直接写正文，不要输出解释、提纲、标题之外的说明。
- 近距离第三人称，核心视角贴着祖国人；可以写他的羞耻、暴怒和自我欺骗。
- 重点写“失去能力后的窝囊事”：疼痛、饥饿、恐惧、钱、证件、气味、衣服、伤口、被人当成垃圾。
- 祖国人不是突然变善；他只是在普通身体里学会更阴险地活。
- 对话要短、狠、口语化，不要所有人一个腔调。
- 不要复述原剧台词，不写官方剧情摘抄；只沿用本设定继续写新情节。
- 不要让他太快翻盘。第一卷必须压低他、羞辱他、让他连续失败。
- 暴力可以写，但不要沉迷血浆；重点是权力坠落和心理折磨。
- 每章结尾留一个推进钩子。"""

CHAPTER_PLAN: list[tuple[str, str]] = [
    ("爆竹女的证明", "白宫内清算开始，祖国人让爆竹女替自己挡住黑袍小队，从密道逃走；他第一次发现连推开画像密门都费力。"),
    ("白宫外的耳光", "祖国人逃到外围维护楼，试图抢流浪汉外套，被流浪汉扇耳光并打退；他第一次用脚逃跑。"),
    ("我是祖国人", "他在便利店暴露身份，想靠名号拿食物和衣服，结果被顾客围殴、偷拍视频、狼狈逃走。"),
    ("三美元热狗", "饥饿压垮尊严，他在街头为一根热狗低头；电视第一次宣布暴君祖国人倒台。"),
    ("暴君已死", "黑袍小队通过媒体宣布超级英雄统治终结，民众狂欢；祖国人在旅馆大厅看见自己被公开审判。"),
    ("假名约翰", "他剪掉金发，用偷来的旧衣服和假名住进廉价旅馆；他发现没人害怕约翰。"),
    ("押金不退", "旅馆老板、清洁工、小混混轮番羞辱他；他试图发火，却被一句报警吓住。"),
    ("伤口发炎", "密道里摔伤的膝盖感染，他在公共厕所里发烧，第一次害怕自己会普通地死掉。"),
    ("旧粉丝", "一个认出他的狂热粉丝没有救他，而是想把他绑起来直播换钱；祖国人靠撒谎脱身。"),
    ("无能的威胁", "他试图威胁地下诊所医生，医生看穿他没有能力，反过来勒索他。"),
    ("地铁里的神", "他被迫混进地铁睡觉，被醉汉、学生、保安嘲笑；他听见路人讨论他像讨论死狗。"),
    ("爆竹女的新闻", "媒体播放爆竹女被抓或战死的消息，祖国人短暂动摇，却很快把她的牺牲重新包装成自己的资产。"),
    ("第一场雨", "他在雨里丢掉最后一点现金，被外卖员撞倒；普通城市的冷漠比黑袍小队更折磨他。"),
    ("租来的名字", "他买到低级假证，化名住进郊区地下室；房东太太把他当逃犯看。"),
    ("白眼的一周", "用组章写法压缩一周窝囊生活：找工失败、排队领救济、被孩子认出、被警察盘问。"),
    ("屏幕里的审判", "电视台连续播出祖国人罪行专题，黑袍小队掌握叙事权；他发现符号正在被夺走。"),
    ("新英雄试镜", "沃特残余和政府推出新的国家英雄候选，披风和微笑都像在复制他。"),
    ("老海报", "他在旧影院后巷看见自己的巨幅海报被撕下，拾荒者用它垫垃圾车。"),
    ("一份脏工作", "他为活下去接了底层黑活，搬运、看门、恐吓债务人，却被真正的地头蛇羞辱。"),
    ("低头吃饭", "他被迫和流浪汉、失业者、瘾君子排在同一条救济队伍里，第一次学会观察普通人的弱点。"),
    ("残党的试探", "一个七人组边缘残党找到他，确认他是否真的失能；祖国人用话术让对方不敢立刻动手。"),
    ("画饼", "祖国人给残党描绘未来：只要救他，就能重新分配超级英雄时代的权力。"),
    ("黑袍的通缉令", "黑袍小队发布更高规格通缉，普通人开始把举报祖国人当成暴富机会。"),
    ("被孩子追打", "一群青少年认出他并追打、拍摄，祖国人躲进垃圾房；这成为他最低谷的羞辱。"),
    ("接受命运", "他短暂接受自己可能只能做普通人，甚至尝试在洗车场工作。"),
    ("洗车场的王", "他在洗车场靠操控同事和老板重建微型权力，发现自己即使没有能力也能统治小群体。"),
    ("替代者登场", "电视上新的国家英雄正式登场，穿着改良披风，宣布祖国人时代结束。"),
    ("神像复燃", "替代者的一句话刺激祖国人，他砸碎电视，决定不再逃避。"),
    ("名单", "祖国人开始列出可利用的人：深海、残党、旧粉丝、黑市医生、士兵男孩线索。"),
    ("父亲的冷冻柜", "他听到士兵男孩可能还活着或被转移的消息，意识到自己能用父子关系打开旧时代武器库。"),
    ("初代化合物", "黑市医生提到初代五号化合物不是传说，祖国人明白恢复原状不够，他要更高阶的东西。"),
    ("夺回一切", "第一卷收束：祖国人站在雨夜广告屏下，看着新英雄取代自己，发誓夺回名字、披风、力量和恐惧。"),
]


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def now() -> str:
    return datetime.now().isoformat()


def ensure_project(conn: sqlite3.Connection) -> None:
    timestamp = now()
    conn.execute(
        """
        INSERT INTO novels (
            id, title, slug, author, target_chapters, premise, autopilot_status,
            auto_approve_mode, current_stage, current_act, current_chapter_in_act,
            max_auto_chapters, current_auto_chapters, consecutive_error_count,
            target_words_per_chapter, generation_prefs_json, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, 'stopped', 0, 'writing', 1, 1, ?, 0, 0, ?, '{}', ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title = excluded.title,
            premise = excluded.premise,
            target_chapters = excluded.target_chapters,
            target_words_per_chapter = excluded.target_words_per_chapter,
            current_stage = 'writing',
            updated_at = excluded.updated_at
        """,
        (
            NOVEL_ID,
            TITLE,
            NOVEL_ID,
            AUTHOR,
            len(CHAPTER_PLAN),
            PREMISE,
            len(CHAPTER_PLAN),
            TARGET_CHARS_PER_CHAPTER,
            timestamp,
            timestamp,
        ),
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO bibles (id, novel_id, schema_version, extensions, created_at, updated_at)
        VALUES (?, ?, 1, '{}', ?, ?)
        """,
        (f"bible-{NOVEL_ID}", NOVEL_ID, timestamp, timestamp),
    )
    characters = [
        ("祖国人/约翰", "失去超能力后的祖国人，仍保留暴君人格、表演本能和统治欲；最怕被普通人看见自己的脆弱。", "笑一下，压低声音说话，把命令说成恩赐"),
        ("爆竹女", "祖国人狂热崇拜者，被他要求用爱证明忠诚，成为第一章牺牲和负罪感来源。", "把崇拜说成信仰"),
        ("喜梅子", "夺走祖国人能力的人，是整卷的压迫性阴影，不常出场但决定祖国人命运。", "沉默比语言更有压迫感"),
        ("黑袍小队", "通过媒体宣布暴君倒台，成为新秩序的叙事中心，也让祖国人成为全民猎物。", "直接、粗粝、带胜利者的厌恶"),
        ("士兵男孩", "祖国人后续要复苏的旧时代武器和父亲幽灵，第一卷只作为线索出现。", "旧时代粗暴口吻"),
    ]
    for idx, (name, desc, tic) in enumerate(characters, start=1):
        conn.execute(
            """
            INSERT INTO bible_characters (
                id, novel_id, name, description, mental_state, verbal_tic,
                idle_behavior, core_belief, moral_taboos_json, voice_profile_json,
                active_wounds_json, public_profile, hidden_profile, reveal_chapter,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 'NORMAL', ?, '', '', '[]', '{}', '[]', ?, '', ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                description = excluded.description,
                verbal_tic = excluded.verbal_tic,
                public_profile = excluded.public_profile,
                updated_at = excluded.updated_at
            """,
            (
                f"char-{NOVEL_ID}-{idx}",
                NOVEL_ID,
                name,
                desc,
                tic,
                desc,
                idx,
                timestamp,
                timestamp,
            ),
        )
    conn.execute(
        """
        INSERT OR IGNORE INTO story_nodes (
            id, novel_id, parent_id, node_type, number, title, description,
            order_index, planning_status, planning_source, chapter_start, chapter_end,
            chapter_count, suggested_chapter_count, content, outline, word_count,
            status, metadata, created_at, updated_at
        )
        VALUES (?, ?, NULL, 'act', 1, '第一卷：神像倒在白宫外', ?, 1, 'approved',
                'manual', 1, ?, ?, ?, '', ?, 0, 'draft', '{}', ?, ?)
        """,
        (
            f"act-{NOVEL_ID}-1",
            NOVEL_ID,
            PREMISE,
            len(CHAPTER_PLAN),
            len(CHAPTER_PLAN),
            len(CHAPTER_PLAN),
            PREMISE,
            timestamp,
            timestamp,
        ),
    )
    for number, (title, outline) in enumerate(CHAPTER_PLAN, start=1):
        chapter_id = f"chapter-{NOVEL_ID}-{number}"
        conn.execute(
            """
            INSERT INTO chapters (
                id, novel_id, number, title, content, outline, status,
                tension_score, plot_tension, emotional_tension, pacing_tension,
                word_count, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, '', ?, 'draft', 50, 50, 50, 50, 0, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                outline = excluded.outline,
                updated_at = excluded.updated_at
            """,
            (chapter_id, NOVEL_ID, number, f"第{number}章：{title}", outline, timestamp, timestamp),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO story_nodes (
                id, novel_id, parent_id, node_type, number, title, description,
                order_index, planning_status, planning_source, chapter_start, chapter_end,
                chapter_count, suggested_chapter_count, content, outline, word_count,
                status, metadata, created_at, updated_at
            )
            VALUES (?, ?, ?, 'chapter', ?, ?, ?, ?, 'approved', 'manual',
                    ?, ?, 1, 1, '', ?, 0, 'draft', '{}', ?, ?)
            """,
            (
                f"node-{NOVEL_ID}-{number}",
                NOVEL_ID,
                f"act-{NOVEL_ID}-1",
                number,
                f"第{number}章：{title}",
                outline,
                number,
                number,
                number,
                outline,
                timestamp,
                timestamp,
            ),
        )
    conn.commit()


def chapter_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT number, title, outline, content
            FROM chapters
            WHERE novel_id = ?
            ORDER BY number ASC
            """,
            (NOVEL_ID,),
        )
    )


def total_chars(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT SUM(LENGTH(COALESCE(content,''))) AS total FROM chapters WHERE novel_id = ?",
        (NOVEL_ID,),
    ).fetchone()
    return int(row["total"] or 0)


def recent_context(conn: sqlite3.Connection, chapter_number: int) -> str:
    rows = list(
        conn.execute(
            """
            SELECT number, title, content
            FROM chapters
            WHERE novel_id = ? AND number < ? AND LENGTH(COALESCE(content,'')) > 100
            ORDER BY number DESC
            LIMIT 3
            """,
            (NOVEL_ID, chapter_number),
        )
    )
    rows.reverse()
    parts: list[str] = []
    for row in rows:
        content = str(row["content"] or "")
        head = content[:320].replace("\n", " ")
        tail = content[-520:].replace("\n", " ")
        parts.append(f"第{row['number']}章《{row['title']}》开头：{head}\n结尾：{tail}")
    return "\n\n".join(parts) if parts else "这是第一章，没有前文。"


def all_plan_text() -> str:
    return "\n".join(
        f"{idx}. {title}：{outline}"
        for idx, (title, outline) in enumerate(CHAPTER_PLAN, start=1)
    )


def clean_content(raw: str, title: str) -> str:
    text = (raw or "").strip()
    text = re.sub(r"^```(?:\w+)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = re.sub(r"^#+\s*.*\n+", "", text)
    text = text.replace("【本章正文】", "").strip()
    text = re.sub(r"^\s*(?:正文|章节正文)\s*[:：]\s*", "", text)
    if title in text[:80]:
        text = re.sub(rf"^\s*{re.escape(title)}\s*", "", text).strip()
    return text


def write_manuscript(conn: sqlite3.Connection, path: Path) -> None:
    rows = chapter_rows(conn)
    completed = [r for r in rows if str(r["content"] or "").strip()]
    parts = [
        f"# {TITLE}",
        "",
        f"PLM 项目 ID：`{NOVEL_ID}`",
        "",
        f"当前已生成：{len(completed)}/{len(CHAPTER_PLAN)} 章，约 {total_chars(conn)} 字。",
        "",
    ]
    for row in rows:
        content = str(row["content"] or "").strip()
        if not content:
            continue
        parts.append(f"## {row['title']}")
        parts.append("")
        parts.append(content)
        parts.append("")
    path.write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")


def save_chapter(conn: sqlite3.Connection, number: int, content: str) -> None:
    timestamp = now()
    conn.execute(
        """
        UPDATE chapters
        SET content = ?, word_count = ?, status = 'draft', updated_at = ?
        WHERE novel_id = ? AND number = ?
        """,
        (content, len(content), timestamp, NOVEL_ID, number),
    )
    completed = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM chapters
        WHERE novel_id = ? AND LENGTH(COALESCE(content,'')) > 100
        """,
        (NOVEL_ID,),
    ).fetchone()["c"]
    conn.execute(
        """
        UPDATE novels
        SET current_auto_chapters = ?, updated_at = ?
        WHERE id = ?
        """,
        (int(completed), timestamp, NOVEL_ID),
    )
    conn.commit()


async def generate_one(provider: CodexAppServerProvider, conn: sqlite3.Connection, row: sqlite3.Row) -> str:
    number = int(row["number"])
    title = str(row["title"])
    outline = str(row["outline"] or "")
    prompt = Prompt(
        system=(
            "你是 PLM 本地写作引擎，正在为用户生成私人阅读用长篇小说草稿。"
            "严格按设定和章节任务写正文，不要审查式说教，不要替换角色名。"
            "\n\n"
            f"{STYLE_RULES}"
        ),
        user=(
            f"书名：{TITLE}\n\n"
            f"全书核心设定：\n{PREMISE}\n\n"
            f"第一卷章节规划：\n{all_plan_text()}\n\n"
            f"已生成前文摘要/片段：\n{recent_context(conn, number)}\n\n"
            f"现在撰写：{title}\n"
            f"本章任务：{outline}\n"
            f"目标长度：约 {TARGET_CHARS_PER_CHAPTER} 个中文字符。\n\n"
            "只输出本章正文，不要输出章节标题、分析、提纲或说明。"
        ),
    )
    config = GenerationConfig(max_tokens=9_000, temperature=0.74)
    result = await provider.generate(prompt, config)
    return clean_content(result.content, title)


async def run(args: argparse.Namespace) -> None:
    db_path = Path(args.db).expanduser()
    manuscript_path = Path(args.output).expanduser()
    log_prefix = "[homelander-100k]"
    provider = CodexAppServerProvider(
        Settings(
            default_model=args.model,
            default_temperature=0.74,
            default_max_tokens=9_000,
            timeout_seconds=args.timeout,
            protocol="codex",
            provider_name="PLM Homelander 100k Writer",
        )
    )
    with connect(db_path) as conn:
        ensure_project(conn)
        write_manuscript(conn, manuscript_path)
        rows = chapter_rows(conn)
        for row in rows:
            number = int(row["number"])
            if number < args.start or number > args.end:
                continue
            existing = str(row["content"] or "").strip()
            if existing and len(existing) >= args.skip_chars and not args.force:
                print(f"{log_prefix} skip chapter={number} chars={len(existing)}", flush=True)
                continue
            if total_chars(conn) >= args.target_total and not args.force:
                print(f"{log_prefix} target reached chars={total_chars(conn)}", flush=True)
                break

            print(f"{log_prefix} generating chapter={number} title={row['title']}", flush=True)
            content = await generate_one(provider, conn, row)
            if len(content) < 800:
                raise RuntimeError(f"chapter {number} output too short: {len(content)} chars")
            save_chapter(conn, number, content)
            write_manuscript(conn, manuscript_path)
            print(
                f"{log_prefix} saved chapter={number} chars={len(content)} total={total_chars(conn)} output={manuscript_path}",
                flush=True,
            )


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PLM Codex 10 万字长篇写作 worker")
    parser.add_argument("--db", default=str(ROOT / "data" / "plotpilot.db"))
    parser.add_argument("--output", default=str(DESKTOP_MANUSCRIPT))
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int, default=len(CHAPTER_PLAN))
    parser.add_argument("--target-total", type=int, default=TARGET_CHARS)
    parser.add_argument("--skip-chars", type=int, default=800)
    parser.add_argument("--timeout", type=int, default=1200)
    parser.add_argument("--model", default="")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(list(argv))


def main() -> None:
    asyncio.run(run(parse_args(sys.argv[1:])))


if __name__ == "__main__":
    main()
