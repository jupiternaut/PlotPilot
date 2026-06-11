#!/usr/bin/env python3
"""Polish a PlotPilot chapter with the HumanizerService.

Examples:
  python scripts/humanize_chapter.py --input ~/Desktop/chapter.md --output ~/Desktop/chapter.humanized.md
  python scripts/humanize_chapter.py --novel-id novel-id --chapter-number 13 --update-db --output ~/Desktop/ch13.humanized.md
"""
from __future__ import annotations

import argparse
import asyncio
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from application.engine.services.humanizer_service import HumanizerService
from infrastructure.ai.config.settings import Settings
from infrastructure.ai.providers.codex_app_server_provider import CodexAppServerProvider


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def _read_db_chapter(db_path: Path, novel_id: str, chapter_number: int) -> tuple[str, str]:
    with _connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT title, content
            FROM chapters
            WHERE novel_id = ? AND number = ?
            """,
            (novel_id, chapter_number),
        ).fetchone()
    if not row:
        raise SystemExit(f"未找到章节：novel_id={novel_id} number={chapter_number}")
    return str(row["title"] or ""), str(row["content"] or "")


def _read_character_context(db_path: Path, novel_id: str, limit: int = 12) -> str:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM bible_characters
            WHERE novel_id = ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (novel_id, limit),
        ).fetchall()
    lines: list[str] = []
    for row in rows:
        keys = set(row.keys())
        name = str(row["name"] or "").strip() if "name" in keys else ""
        description = str(row["description"] or "").strip() if "description" in keys else ""
        public_profile = str(row["public_profile"] or "").strip() if "public_profile" in keys else ""
        verbal_tic = str(row["verbal_tic"] or "").strip() if "verbal_tic" in keys else ""
        mental_state = str(row["mental_state"] or "").strip() if "mental_state" in keys else ""
        parts = [description or public_profile]
        if verbal_tic:
            parts.append(f"口癖：{verbal_tic}")
        if mental_state and mental_state.upper() != "NORMAL":
            parts.append(f"当前心理：{mental_state}")
        desc = "；".join(p for p in parts if p)
        lines.append(f"- {name}：{desc}" if desc else f"- {name}")
    return "\n".join(line for line in lines if line.strip() != "-")


def _update_db_chapter(db_path: Path, novel_id: str, chapter_number: int, content: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = db_path.with_name(f"{db_path.name}.backup-humanizer-{stamp}")
    shutil.copy2(db_path, backup)
    now = datetime.now().isoformat()
    with _connect(db_path) as conn:
        conn.execute(
            """
            UPDATE chapters
            SET content = ?, word_count = ?, updated_at = ?
            WHERE novel_id = ? AND number = ?
            """,
            (content, len(content), now, novel_id, chapter_number),
        )
        conn.commit()
    return backup


def _default_output_path(input_path: Optional[Path], chapter_number: Optional[int]) -> Path:
    if input_path:
        return input_path.with_name(f"{input_path.stem}.humanized{input_path.suffix}")
    suffix = f"第{chapter_number}章" if chapter_number else "chapter"
    return Path.home() / "Desktop" / f"PlotPilot-{suffix}.humanized.md"


def _build_provider(provider: str, timeout: int, model: str):
    if provider == "active":
        from infrastructure.ai.provider_factory import DynamicLLMService

        return DynamicLLMService()
    return CodexAppServerProvider(
        Settings(
            default_model=model,
            default_temperature=0.65,
            default_max_tokens=12000,
            timeout_seconds=timeout,
            protocol="codex",
            provider_name="Codex Humanizer",
        )
    )


def _read_revision_note(args: argparse.Namespace) -> str:
    parts: list[str] = []
    if args.revision_note_file:
        parts.append(Path(args.revision_note_file).expanduser().read_text(encoding="utf-8"))
    if args.revision_note:
        parts.append(args.revision_note)
    return "\n\n".join(p.strip() for p in parts if p and p.strip())


async def _run(args: argparse.Namespace) -> None:
    db_path = Path(args.db).expanduser()
    input_path = Path(args.input).expanduser() if args.input else None
    output_path = Path(args.output).expanduser() if args.output else _default_output_path(
        input_path,
        args.chapter_number,
    )

    title = ""
    if input_path:
        content = input_path.read_text(encoding="utf-8")
    else:
        if not args.novel_id or args.chapter_number is None:
            raise SystemExit("请提供 --input，或同时提供 --novel-id 与 --chapter-number")
        title, content = _read_db_chapter(db_path, args.novel_id, args.chapter_number)

    character_context = args.character_context or ""
    if not character_context and args.novel_id and db_path.exists():
        character_context = _read_character_context(db_path, args.novel_id)

    provider = _build_provider(args.provider, args.timeout, args.model)
    try:
        service = HumanizerService(provider)
        rewritten = await service.humanize_chapter(
            content,
            character_context=character_context,
            novel_id=args.novel_id or (input_path.stem if input_path else ""),
            chapter_num=args.chapter_number or 0,
            revision_note=_read_revision_note(args),
            max_tokens=args.max_tokens,
            temperature=args.temperature,
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        if title and not rewritten.lstrip().startswith("#"):
            output_path.write_text(f"# {title}\n\n{rewritten}\n", encoding="utf-8")
        else:
            output_path.write_text(rewritten + "\n", encoding="utf-8")

        backup = None
        if args.update_db:
            if not args.novel_id or args.chapter_number is None:
                raise SystemExit("--update-db 需要同时提供 --novel-id 与 --chapter-number")
            backup = _update_db_chapter(db_path, args.novel_id, args.chapter_number, rewritten)

        print(f"润色完成：{len(content)} -> {len(rewritten)} 字")
        print(f"输出文件：{output_path}")
        if backup:
            print(f"数据库备份：{backup}")
    finally:
        close = getattr(provider, "aclose", None)
        if close is not None:
            await close()


def main() -> None:
    parser = argparse.ArgumentParser(description="PlotPilot 章节润色器")
    parser.add_argument("--input", help="输入 Markdown/TXT 文件")
    parser.add_argument("--output", help="输出文件")
    parser.add_argument("--db", default=str(ROOT / "data" / "plotpilot.db"), help="PlotPilot SQLite DB")
    parser.add_argument("--novel-id", help="PLM 小说 ID")
    parser.add_argument("--chapter-number", type=int, help="章节号")
    parser.add_argument("--update-db", action="store_true", help="把润色结果写回 chapters 表")
    parser.add_argument("--provider", choices=["codex", "active"], default="codex")
    parser.add_argument("--model", default="", help="Codex 模型名，留空使用默认")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--max-tokens", type=int)
    parser.add_argument("--temperature", type=float, default=0.65)
    parser.add_argument("--character-context", default="")
    parser.add_argument("--revision-note", default="", help="本轮专项修订要求")
    parser.add_argument("--revision-note-file", help="从文件读取本轮专项修订要求")
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
