#!/usr/bin/env python3
"""Build chapter prompts for the Star Restart PLM project package.

This is a safe project entry point: it reads Markdown source files under
projects/star_restart and writes a prompt file under that package's runtime
directory. It does not call an LLM and does not modify PlotPilot's database.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT / "projects" / "star_restart"
RUNTIME_DIR = PROJECT_DIR / "runtime"

SOURCE_FILES = {
    "bible": PROJECT_DIR / "project_bible.md",
    "plan": PROJECT_DIR / "chapter_plan_1_20.md",
    "style": PROJECT_DIR / "style_guide.md",
    "anchor": PROJECT_DIR / "target_style_anchor.md",
    "prison_economy": PROJECT_DIR / "world_ai_prison_economy.md",
    "audit": PROJECT_DIR / "motif_audit.md",
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def extract_chapter(plan_text: str, chapter_number: int) -> str:
    pattern = rf"^## 第{chapter_number}章：.*?(?=^## 第\d+章：|\Z)"
    match = re.search(pattern, plan_text, flags=re.M | re.S)
    if not match:
        raise ValueError(f"chapter {chapter_number} not found in {SOURCE_FILES['plan']}")
    return match.group(0).strip()


def build_prompt(chapter_number: int) -> str:
    bible = read_text(SOURCE_FILES["bible"])
    plan = read_text(SOURCE_FILES["plan"])
    style = read_text(SOURCE_FILES["style"])
    anchor = read_text(SOURCE_FILES["anchor"])
    prison_economy = read_text(SOURCE_FILES["prison_economy"])
    audit = read_text(SOURCE_FILES["audit"])
    chapter_plan = extract_chapter(plan, chapter_number)

    return f"""# 《星河重启》第 {chapter_number} 章 PLM 生成提示

## System

你是 PLM 本地小说写作引擎。请严格服务《星河重启》项目，不要把它写成首富爽文、豪门爽文或名校天才爽文。

写作目标：

- 直接输出章节正文，不输出解释、提纲、分析、道歉或系统说明。
- 默认第三人称近距离，贴顾临川。
- 保留黑色幽默，让读者先笑出来，再感到荒诞背后的冷。
- 贫穷、高淳、老师、书店、夜场、Dota1 和未来 AI 圈地记忆都要通过具体生活细节出现。
- 不要使用禁用 AI 腔，不要写成社论，不要用大段技术论文替代剧情。

## Project Bible

{bible}

## Style Guide

{style}

## Target Style Anchor

{anchor}

## Future World: AI Prison Economy

{prison_economy}

## Chapter Task

{chapter_plan}

## Audit Checklist

写完后自查以下要求，但不要把自查过程输出给用户：

{audit}

## Output

只输出第 {chapter_number} 章正文。不要输出章节标题之外的说明；如果输出标题，只能使用章节规划中的标题。
"""


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Star Restart chapter prompt files.")
    parser.add_argument("--chapter", type=int, required=True, help="Chapter number in chapter_plan_1_20.md")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Prompt output path. Defaults to projects/star_restart/runtime/chapter_XX_prompt.md",
    )
    parser.add_argument("--print", action="store_true", help="Also print the prompt to stdout")
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.chapter < 1 or args.chapter > 20:
        raise SystemExit("--chapter must be between 1 and 20 for the current package")

    prompt = build_prompt(args.chapter)
    output = args.output or RUNTIME_DIR / f"chapter_{args.chapter:02d}_prompt.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(prompt.rstrip() + "\n", encoding="utf-8")
    if args.print:
        print(prompt)
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
