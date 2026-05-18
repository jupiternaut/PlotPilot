import pytest
import uuid
import time
from datetime import datetime
from domain.novel.entities.novel import Novel, AutopilotStatus, NovelStage
from domain.novel.value_objects.novel_id import NovelId
from domain.novel.value_objects.generation_preferences import GenerationPreferences
from infrastructure.persistence.database.connection import get_database
from infrastructure.persistence.database.sqlite_novel_repository import SqliteNovelRepository
from infrastructure.persistence.database.sqlite_chapter_repository import SqliteChapterRepository
from application.core.services.novel_service import NovelService

def test_novel_duplication_and_resets():
    db = get_database()
    novel_repo = SqliteNovelRepository(db)
    chapter_repo = SqliteChapterRepository(db)
    service = NovelService(novel_repo, chapter_repo)

    # 1. 创建原小说
    old_id = f"test-novel-{uuid.uuid4().hex[:8]}"
    novel = Novel(
        id=NovelId(old_id),
        title="测试小说-原版",
        author="测试作者",
        target_chapters=5,
        premise="测试梗概",
        stage=NovelStage.WRITING,
        autopilot_status=AutopilotStatus.STOPPED,
        auto_approve_mode=False,
        generation_prefs=GenerationPreferences()
    )
    novel_repo.save(novel)

    # 插入一些关联记录
    now = datetime.now().isoformat()
    with db.transaction() as conn:
        # 插入章节
        ch_id = f"test-chapter-{uuid.uuid4().hex[:8]}"
        conn.execute(
            """
            INSERT INTO chapters (id, novel_id, number, title, content, outline, status, tension_score, word_count, created_at, updated_at)
            VALUES (?, ?, 1, '第一章', '正文内容', '章节大纲', 'completed', 0.5, 1000, ?, ?)
            """,
            (ch_id, old_id, now, now)
        )
        # 插入大纲树节点
        node_id = f"test-node-{uuid.uuid4().hex[:8]}"
        conn.execute(
            """
            INSERT INTO story_nodes (
                id, novel_id, parent_id, node_type, number, title, description, order_index,
                planning_status, planning_source, chapter_start, chapter_end, chapter_count,
                suggested_chapter_count, content, outline, word_count, status, created_at, updated_at
            ) VALUES (?, ?, NULL, 'chapter', 1, '节点标题', '节点描述', 0, 'draft', 'manual', 1, 1, 1, 1, '正文', '大纲', 1000, 'draft', ?, ?)
            """,
            (node_id, old_id, now, now)
        )
        # 插入世界设定
        conn.execute(
            "INSERT INTO bible_world_settings (id, novel_id, name, description, setting_type, created_at, updated_at) VALUES (?, ?, '设定名', '设定描述', 'magic', ?, ?)",
            (f"ws-{uuid.uuid4().hex[:8]}", old_id, now, now)
        )

    try:
        # 2. 测试克隆
        new_title = "测试小说-副本"
        new_id = service.duplicate_novel(old_id, new_title)
        
        # 验证克隆出来的 novels 数据
        cloned_novel = novel_repo.get_by_id(NovelId(new_id))
        assert cloned_novel is not None
        assert cloned_novel.title == new_title
        assert cloned_novel.novel_id.value == new_id

        # 验证克隆出来的 chapters 与大纲节点
        with db.transaction() as conn:
            ch_rows = conn.execute("SELECT * FROM chapters WHERE novel_id = ?", (new_id,)).fetchall()
            assert len(ch_rows) == 1
            assert ch_rows[0]["title"] == "第一章"
            assert ch_rows[0]["word_count"] == 1000

            node_rows = conn.execute("SELECT * FROM story_nodes WHERE novel_id = ?", (new_id,)).fetchall()
            assert len(node_rows) == 1
            assert node_rows[0]["title"] == "节点标题"

            ws_rows = conn.execute("SELECT * FROM bible_world_settings WHERE novel_id = ?", (new_id,)).fetchall()
            assert len(ws_rows) == 1

        # 3. 测试清空正文 (Choice 1)
        service.clear_novel_drafts(new_id)
        with db.transaction() as conn:
            # 章节正文删除
            ch_rows = conn.execute("SELECT * FROM chapters WHERE novel_id = ?", (new_id,)).fetchall()
            assert len(ch_rows) == 0

            # 节点状态重置
            node_rows = conn.execute("SELECT * FROM story_nodes WHERE novel_id = ?", (new_id,)).fetchall()
            assert len(node_rows) == 1
            assert node_rows[0]["status"] == "draft"
            assert node_rows[0]["word_count"] == 0

        # 4. 测试彻底重置 (Choice 2)
        service.clear_novel_outline(new_id)
        with db.transaction() as conn:
            # 大纲树节点也删除
            node_rows = conn.execute("SELECT * FROM story_nodes WHERE novel_id = ?", (new_id,)).fetchall()
            assert len(node_rows) == 0

            # 小说 stage 重置
            cloned_novel_reset = novel_repo.get_by_id(NovelId(new_id))
            assert cloned_novel_reset.stage == NovelStage.PLANNING

    finally:
        # 清理垃圾数据
        with db.transaction() as conn:
            conn.execute("DELETE FROM novels WHERE id IN (?, ?)", (old_id, new_id))
            conn.execute("DELETE FROM chapters WHERE novel_id IN (?, ?)", (old_id, new_id))
            conn.execute("DELETE FROM story_nodes WHERE novel_id IN (?, ?)", (old_id, new_id))
            conn.execute("DELETE FROM bible_world_settings WHERE novel_id IN (?, ?)", (old_id, new_id))
