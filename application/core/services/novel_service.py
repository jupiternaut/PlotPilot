"""Novel 应用服务"""
import json
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from domain.novel.entities.novel import Novel, NovelStage
from domain.novel.entities.chapter import Chapter
from domain.novel.value_objects.novel_id import NovelId
from domain.novel.value_objects.generation_preferences import GenerationPreferences
from domain.novel.value_objects.word_count import WordCount
from domain.novel.repositories.novel_repository import NovelRepository
from domain.novel.repositories.chapter_repository import ChapterRepository
from domain.shared.exceptions import EntityNotFoundError
from application.core.dtos.novel_dto import NovelDTO
from application.core.chapter_target_limits import clamp_chapter_target_words
from application.core.v1_length_tiers import (
    build_v1_structure_black_box_hint,
    resolve_v1_length_params,
)
from domain.structure.story_node import StoryNode, NodeType, PlanningStatus, PlanningSource
from infrastructure.persistence.database.story_node_repository import StoryNodeRepository


class NovelService:
    """Novel 应用服务

    协调领域对象和基础设施，实现应用用例。
    """

    def __init__(
        self,
        novel_repository: NovelRepository,
        chapter_repository: ChapterRepository,
        story_node_repository: Optional[StoryNodeRepository] = None,
    ):
        """初始化服务

        Args:
            novel_repository: Novel 仓储
            chapter_repository: Chapter 仓储（统计以落盘章节为准）
            story_node_repository: StoryNode 仓储（用于同步叙事结构）
        """
        self.novel_repository = novel_repository
        self.chapter_repository = chapter_repository
        self.story_node_repository = story_node_repository

    def _hydrate_chapters(self, novel: Novel) -> Novel:
        """用 Chapter 仓储补齐 DTO 所需章节列表。"""
        if self.chapter_repository is None:
            return novel
        try:
            chapters = self.chapter_repository.list_by_novel(novel.novel_id)
            if isinstance(chapters, list):
                novel.chapters = chapters
        except Exception:
            pass
        return novel

    def ensure_default_act_for_chapters(self, novel_id: str) -> None:
        """若无任何「幕」节点，创建默认第一幕，以便 add_chapter 能挂接章节到叙事结构树。"""
        if not self.story_node_repository:
            return
        tree = self.story_node_repository.get_tree_sync(novel_id)
        acts = [n for n in tree.nodes if n.node_type == NodeType.ACT]
        if acts:
            return
        act_node = StoryNode(
            id=f"act-{novel_id}-1",
            novel_id=novel_id,
            node_type=NodeType.ACT,
            number=1,
            title="第一幕",
            description="初始规划自动创建，可在结构视图中重命名",
            parent_id=None,
            order_index=0,
            planning_status=PlanningStatus.CONFIRMED,
            planning_source=PlanningSource.AI_MACRO,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        self.story_node_repository.save_sync(act_node)

    @staticmethod
    def _compose_premise_with_presets(
        premise: str,
        genre: str = "",
        world_preset: str = "",
    ) -> str:
        """将赛道/世界观预设与梗概合并，供后续 Bible/全托管链路统一消费（无需额外表字段）。"""
        parts = []
        g = (genre or "").strip()
        w = (world_preset or "").strip()
        if g:
            parts.append(f"类型：{g}")
        if w:
            parts.append(f"世界观基调：{w}")
        body = (premise or "").strip()
        if not parts:
            return body
        return "【" + "；".join(parts) + "】\n\n" + body

    def create_novel(
        self,
        novel_id: str,
        title: str,
        author: str,
        target_chapters: int,
        premise: str = "",
        genre: str = "",
        world_preset: str = "",
        length_tier: Optional[str] = None,
        target_words_per_chapter: Optional[int] = None,
    ) -> NovelDTO:
        """创建新小说

        Args:
            novel_id: 小说 ID
            title: 标题
            author: 作者
            target_chapters: 目标章节数（未使用 V1 体量档时有效）
            premise: 故事梗概/创意
            genre: 赛道/类型（前端下拉预设，写入 premise 前缀）
            world_preset: 世界观基调（前端下拉预设，写入 premise 前缀）
            length_tier: V1 体量档 short|standard|epic；若指定则由服务端推导章数与每章字数
            target_words_per_chapter: 每章目标字数（可选；与体量档或自定义章数搭配）

        Returns:
            NovelDTO
        """
        chapters, wpc, tier_norm = resolve_v1_length_params(
            length_tier, target_chapters, target_words_per_chapter
        )
        structure_hint = build_v1_structure_black_box_hint(tier_norm, chapters, wpc)
        user_block = self._compose_premise_with_presets(premise, genre, world_preset)
        full_premise = f"{structure_hint}\n\n{user_block}"
        novel = Novel(
            id=NovelId(novel_id),
            title=title,
            author=author,
            target_chapters=chapters,
            premise=full_premise,
            stage=NovelStage.PLANNING,
            target_words_per_chapter=wpc,
        )

        self.novel_repository.save(novel)

        return NovelDTO.from_domain(novel)

    def get_novel(self, novel_id: str) -> Optional[NovelDTO]:
        novel = self.novel_repository.get_by_id(NovelId(novel_id))

        if novel is None:
            return None

        dto = NovelDTO.from_domain(self._hydrate_chapters(novel))

        dto.has_bible = self._check_has_bible(novel_id)
        dto.has_outline = self._check_has_outline(novel_id)

        return dto

    def _check_has_bible(self, novel_id: str) -> bool:
        storage = getattr(self.novel_repository, "storage", None)
        if storage is not None and hasattr(storage, "exists"):
            try:
                return bool(storage.exists(f"novels/{novel_id}/bible.json"))
            except Exception:
                pass

        try:
            from infrastructure.persistence.database.sqlite_bible_repository import SqliteBibleRepository
            from infrastructure.persistence.database.connection import get_database
            bible_repo = SqliteBibleRepository(get_database())
            bible = bible_repo.get_by_novel_id(NovelId(novel_id))
            return bible is not None
        except Exception:
            return False

    def _check_has_outline(self, novel_id: str) -> bool:
        if not self.story_node_repository:
            return False
        try:
            tree = self.story_node_repository.get_tree_sync(novel_id)
            act_nodes = [n for n in tree.nodes if n.node_type == NodeType.ACT]
            return len(act_nodes) > 0
        except Exception:
            return False

    def list_novels(self) -> List[NovelDTO]:
        """列出所有小说

        Returns:
            NovelDTO 列表
        """
        novels = self.novel_repository.list_all()
        dtos = []
        for novel in novels:
            dto = NovelDTO.from_domain(self._hydrate_chapters(novel))
            dto.has_bible = self._check_has_bible(novel.novel_id.value)
            dto.has_outline = self._check_has_outline(novel.novel_id.value)
            dtos.append(dto)
        return dtos

    def delete_novel(self, novel_id: str) -> None:
        """删除小说

        Args:
            novel_id: 小说 ID
        """
        self.novel_repository.delete(NovelId(novel_id))

    def add_chapter(
        self,
        novel_id: str,
        chapter_id: str,
        number: int,
        title: str,
        content: str
    ) -> NovelDTO:
        """添加章节

        Args:
            novel_id: 小说 ID
            chapter_id: 章节 ID
            number: 章节编号
            title: 章节标题
            content: 章节内容

        Returns:
            更新后的 NovelDTO

        Raises:
            ValueError: 如果小说不存在或章节号不连续
        """
        novel = self.novel_repository.get_by_id(NovelId(novel_id))

        if novel is None:
            raise ValueError(f"Novel not found: {novel_id}")

        # 查询数据库中实际的章节数
        existing_chapters = self.chapter_repository.list_by_novel(NovelId(novel_id))
        if not isinstance(existing_chapters, list):
            existing_chapters = list(getattr(novel, "chapters", []) or [])
        expected_number = len(existing_chapters) + 1

        # 验证章节号是否连续
        if number != expected_number:
            raise ValueError(f"Chapter number must be {expected_number}, got {number}")

        chapter = Chapter(
            id=chapter_id,
            novel_id=NovelId(novel_id),
            number=number,
            title=title,
            content=content
        )

        # 直接保存章节，不通过Novel实体
        self.chapter_repository.save(chapter)
        if not any(getattr(c, "number", None) == chapter.number for c in novel.chapters):
            novel.chapters.append(chapter)
        self.novel_repository.save(novel)

        # 同步创建 StoryNode 章节节点，并关联到当前活跃的幕
        if self.story_node_repository:
            try:
                # 查找当前活跃的幕（最新的幕）
                tree = self.story_node_repository.get_tree_sync(novel_id)
                acts = [node for node in tree.nodes if node.node_type == NodeType.ACT]

                if acts:
                    # 获取最新的幕
                    current_act = max(acts, key=lambda x: x.number)

                    # 创建章节节点
                    chapter_node = StoryNode(
                        id=f"chapter-{novel_id}-{number}",
                        novel_id=novel_id,
                        node_type=NodeType.CHAPTER,
                        number=number,
                        title=title,
                        description="",
                        parent_id=current_act.id,  # 关联到当前幕
                        order_index=len(tree.nodes),
                        content=content,
                        word_count=len(content),
                        status="draft",
                        created_at=datetime.now(),
                        updated_at=datetime.now()
                    )

                    self.story_node_repository.save_sync(chapter_node)

                    # 更新幕的章节范围
                    children = self.story_node_repository.get_children_sync(current_act.id)
                    chapter_nodes = [node for node in children if node.node_type == NodeType.CHAPTER]
                    if chapter_nodes:
                        chapter_numbers = [node.number for node in chapter_nodes]
                        current_act.chapter_start = min(chapter_numbers)
                        current_act.chapter_end = max(chapter_numbers)
                        current_act.chapter_count = len(chapter_numbers)
                        self.story_node_repository.save_sync(current_act)

            except Exception as e:
                # 如果同步失败，不影响章节创建
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to sync chapter to story structure: {e}")

        # 重新加载Novel以返回最新状态
        novel = self.novel_repository.get_by_id(NovelId(novel_id)) or novel
        return NovelDTO.from_domain(self._hydrate_chapters(novel))

    def update_novel(
        self,
        novel_id: str,
        title: Optional[str] = None,
        author: Optional[str] = None,
        target_chapters: Optional[int] = None,
        premise: Optional[str] = None,
        target_words_per_chapter: Optional[int] = None,
        generation_prefs: Optional[Dict[str, Any]] = None,
    ) -> NovelDTO:
        """更新小说基本信息

        Args:
            novel_id: 小说 ID
            title: 小说标题（可选）
            author: 作者（可选）
            target_chapters: 目标章节数（可选）
            premise: 故事梗概/创意（可选）
            target_words_per_chapter: 每章目标字数（可选，500–20000）
            generation_prefs: 生成偏好（可选；仅更新传入的键）

        Returns:
            更新后的 NovelDTO

        Raises:
            EntityNotFoundError: 如果小说不存在
        """
        novel = self.novel_repository.get_by_id(NovelId(novel_id))
        if novel is None:
            raise EntityNotFoundError("Novel", novel_id)

        # 更新提供的字段
        if title is not None:
            novel.title = title
        if author is not None:
            novel.author = author
        if target_chapters is not None:
            novel.target_chapters = target_chapters
        if premise is not None:
            novel.premise = premise
        if target_words_per_chapter is not None:
            novel.target_words_per_chapter = clamp_chapter_target_words(target_words_per_chapter)
        if generation_prefs is not None:
            novel.generation_prefs = GenerationPreferences.merge_patch(
                novel.generation_prefs, generation_prefs
            )

        # 增量 patch：避免全量 save 把 autopilot_status 等未改字段写回 stopped
        patch_fields: Dict[str, Any] = {}
        if title is not None:
            patch_fields["title"] = title
        if author is not None:
            patch_fields["author"] = author
        if target_chapters is not None:
            patch_fields["target_chapters"] = target_chapters
        if premise is not None:
            patch_fields["premise"] = premise
        if target_words_per_chapter is not None:
            patch_fields["target_words_per_chapter"] = novel.target_words_per_chapter
        if generation_prefs is not None:
            patch_fields["generation_prefs_json"] = json.dumps(
                novel.generation_prefs.to_dict(), ensure_ascii=False
            )
        if patch_fields:
            self.novel_repository.patch(NovelId(novel_id), **patch_fields)

        return NovelDTO.from_domain(self._hydrate_chapters(novel))

    def update_novel_stage(self, novel_id: str, stage: str) -> NovelDTO:
        """更新小说阶段

        Args:
            novel_id: 小说 ID
            stage: 阶段

        Returns:
            更新后的 NovelDTO

        Raises:
            EntityNotFoundError: 如果小说不存在
        """
        novel = self.novel_repository.get_by_id(NovelId(novel_id))
        if novel is None:
            raise EntityNotFoundError("Novel", novel_id)

        novel.stage = NovelStage(stage)
        self.novel_repository.save(novel)

        return NovelDTO.from_domain(self._hydrate_chapters(novel))

    def update_auto_approve_mode(self, novel_id: str, auto_approve_mode: bool) -> NovelDTO:
        """更新全自动模式设置

        Args:
            novel_id: 小说 ID
            auto_approve_mode: 是否开启全自动模式

        Returns:
            更新后的 NovelDTO

        Raises:
            EntityNotFoundError: 如果小说不存在
        """
        novel = self.novel_repository.get_by_id(NovelId(novel_id))
        if novel is None:
            raise EntityNotFoundError("Novel", novel_id)

        novel.auto_approve_mode = auto_approve_mode
        self.novel_repository.save(novel)

        return NovelDTO.from_domain(self._hydrate_chapters(novel))

    def get_novel_statistics(self, novel_id: str) -> Dict[str, Any]:
        """获取小说统计信息（以 Chapter 仓储落盘为准，与列表/读写 API 一致）

        Args:
            novel_id: 小说 ID

        Returns:
            与前端顶栏 BookStats 对齐的字段；数据来源为 ``list_by_novel``，非 novel 聚合 JSON 内嵌章节。

        Raises:
            EntityNotFoundError: 如果小说不存在
        """
        novel = self.novel_repository.get_by_id(NovelId(novel_id))
        if novel is None:
            raise EntityNotFoundError("Novel", novel_id)

        chapters = self.chapter_repository.list_by_novel(NovelId(novel_id))
        total = len(chapters)
        total_words = sum(c.word_count.value for c in chapters)
        completed = sum(1 for c in chapters if c.word_count.value > 0)
        avg = total_words // total if total > 0 else 0
        completion = (completed / total) if total > 0 else 0.0

        return {
            "slug": novel_id,
            "title": novel.title,
            "total_chapters": total,
            "completed_chapters": completed,
            "total_words": total_words,
            "avg_chapter_words": avg,
            "completion_rate": completion,
            "stage": novel.stage.value,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    def duplicate_novel(self, old_novel_id: str, new_title: str) -> str:
        """深拷贝小说及其所有关联的 SQLite 记录"""
        import uuid
        import shutil
        import time
        import logging
        from pathlib import Path
        from infrastructure.persistence.database.connection import get_database

        logger = logging.getLogger(__name__)

        novel = self.novel_repository.get_by_id(NovelId(old_novel_id))
        if not novel:
            raise ValueError(f"Novel not found: {old_novel_id}")

        new_novel_id = f"novel-{int(time.time())}"
        new_slug = new_novel_id
        db = get_database()
        now = datetime.now().isoformat()

        from infrastructure.persistence.database.write_dispatch import startup_sqlite_writes_bypass_queue
        bypass = startup_sqlite_writes_bypass_queue()
        bypass.__enter__()
        try:
            with db.transaction() as conn:
                def safe_execute(sql, params=None):
                    import sqlite3
                    try:
                        if params is None:
                            return conn.execute(sql)
                        return conn.execute(sql, params)
                    except sqlite3.OperationalError as oe:
                        if "no such table" in str(oe):
                            logger.warning(f"Table not found, skipping replication: {oe}")
                            return None
                        raise

                def safe_fetchall(sql, params=None):
                    import sqlite3
                    try:
                        if params is None:
                            return conn.execute(sql).fetchall()
                        return conn.execute(sql, params).fetchall()
                    except sqlite3.OperationalError as oe:
                        if "no such table" in str(oe):
                            logger.warning(f"Table not found, skipping query: {oe}")
                            return []
                        raise

                def safe_fetchone(sql, params=None):
                    import sqlite3
                    try:
                        if params is None:
                            return conn.execute(sql).fetchone()
                        return conn.execute(sql, params).fetchone()
                    except sqlite3.OperationalError as oe:
                        if "no such table" in str(oe):
                            logger.warning(f"Table not found, skipping query: {oe}")
                            return None
                        raise
                # 1. 复制 novels 主表
                conn.execute(
                    """
                    INSERT INTO novels (
                        id, title, slug, author, target_chapters, premise,
                        autopilot_status, auto_approve_mode, current_stage, current_act, current_chapter_in_act,
                        max_auto_chapters, current_auto_chapters, last_chapter_tension,
                        consecutive_error_count, current_beat_index, beats_completed,
                        last_audit_chapter_number, last_audit_similarity, last_audit_drift_alert,
                        last_audit_narrative_ok, last_audit_at, last_audit_vector_stored,
                        last_audit_foreshadow_stored, last_audit_triples_extracted,
                        last_audit_quality_scores, last_audit_issues, target_words_per_chapter,
                        audit_progress, generation_prefs_json, created_at, updated_at
                    )
                    SELECT ?, ?, ?, author, target_chapters, premise,
                           'stopped', auto_approve_mode, current_stage, current_act, current_chapter_in_act,
                           max_auto_chapters, current_auto_chapters, last_chapter_tension,
                           0, current_beat_index, beats_completed,
                           last_audit_chapter_number, last_audit_similarity, last_audit_drift_alert,
                           last_audit_narrative_ok, last_audit_at, last_audit_vector_stored,
                           last_audit_foreshadow_stored, last_audit_triples_extracted,
                           last_audit_quality_scores, last_audit_issues, target_words_per_chapter,
                           audit_progress, generation_prefs_json, ?, ?
                    FROM novels WHERE id = ?
                    """,
                    (new_novel_id, new_title, new_slug, now, now, old_novel_id)
                )

                # 2. 复制 chapters 与 beat_sheets
                chapter_rows = conn.execute("SELECT * FROM chapters WHERE novel_id = ?", (old_novel_id,)).fetchall()
                chapter_id_map = {}
                for ch in chapter_rows:
                    old_ch_id = ch["id"]
                    new_ch_id = f"chapter-{uuid.uuid4().hex[:12]}"
                    chapter_id_map[old_ch_id] = new_ch_id
                    
                    conn.execute(
                        """
                        INSERT INTO chapters (
                            id, novel_id, number, title, content, outline, status, tension_score, word_count, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            new_ch_id, new_novel_id, ch["number"], ch["title"], ch["content"], ch["outline"],
                            ch["status"], ch["tension_score"], ch["word_count"] if "word_count" in ch.keys() else 0, now, now
                        )
                    )
                    
                    bs_row = safe_fetchone("SELECT * FROM beat_sheets WHERE chapter_id = ?", (old_ch_id,))
                    if bs_row:
                        new_bs_id = f"bs-{uuid.uuid4().hex[:12]}"
                        safe_execute(
                            "INSERT INTO beat_sheets (id, chapter_id, data, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                            (new_bs_id, new_ch_id, bs_row["data"], now, now)
                        )

                # 3. 复制大纲树节点 (story_nodes, chapter_elements, chapter_scenes)
                node_rows = conn.execute("SELECT * FROM story_nodes WHERE novel_id = ?", (old_novel_id,)).fetchall()
                node_id_map = {}
                for node in node_rows:
                    old_node_id = node["id"]
                    new_node_id = f"node-{uuid.uuid4().hex[:12]}"
                    node_id_map[old_node_id] = new_node_id

                for node in node_rows:
                    old_node_id = node["id"]
                    new_node_id = node_id_map[old_node_id]
                    old_parent_id = node["parent_id"]
                    new_parent_id = node_id_map.get(old_parent_id) if old_parent_id else None

                    # 映射 POV 角色 ID (如果 POV 角色有在新书中克隆出来)
                    # 后面在复制 bible_characters 时，我们也会填充 POV 映射
                    conn.execute(
                        """
                        INSERT INTO story_nodes (
                            id, novel_id, parent_id, node_type, number, title, description, order_index,
                            planning_status, planning_source, chapter_start, chapter_end, chapter_count,
                            suggested_chapter_count, content, outline, word_count, status, themes,
                            key_events, narrative_arc, conflicts, pov_character_id, timeline_start,
                            timeline_end, metadata, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            new_node_id, new_novel_id, new_parent_id, node["node_type"], node["number"], node["title"],
                            node["description"], node["order_index"], node["planning_status"], node["planning_source"],
                            node["chapter_start"], node["chapter_end"], node["chapter_count"], node["suggested_chapter_count"],
                            node["content"], node["outline"], node["word_count"], node["status"], node["themes"],
                            node["key_events"], node["narrative_arc"], node["conflicts"], node["pov_character_id"],
                            node["timeline_start"], node["timeline_end"], node["metadata"], now, now
                        )
                    )

                    # 复制 chapter_elements
                    elements = safe_fetchall("SELECT * FROM chapter_elements WHERE chapter_id = ?", (old_node_id,))
                    for el in elements:
                        new_el_id = f"el-{uuid.uuid4().hex[:12]}"
                        safe_execute(
                            """
                            INSERT INTO chapter_elements (
                                id, chapter_id, element_type, element_id, relation_type, importance, appearance_order, notes, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                new_el_id, new_node_id, el["element_type"], el["element_id"], el["relation_type"],
                                el["importance"], el["appearance_order"], el["notes"], now
                            )
                        )

                    # 复制 chapter_scenes
                    scenes = safe_fetchall("SELECT * FROM chapter_scenes WHERE chapter_id = ?", (old_node_id,))
                    for sc in scenes:
                        new_sc_id = f"scene-{uuid.uuid4().hex[:12]}"
                        safe_execute(
                            """
                            INSERT INTO chapter_scenes (
                                id, chapter_id, scene_number, location_id, timeline, summary, purpose, content, word_count, characters, order_index, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                new_sc_id, new_node_id, sc["scene_number"], sc["location_id"], sc["timeline"],
                                sc["summary"], sc["purpose"], sc["content"], sc["word_count"], sc["characters"],
                                sc["order_index"], now, now
                            )
                        )

                # 4. 复制 Bible 及其子表
                bible_row = safe_fetchone("SELECT * FROM bibles WHERE novel_id = ?", (old_novel_id,))
                char_id_map = {}
                loc_id_map = {}
                if bible_row:
                    new_bible_id = f"bible-{uuid.uuid4().hex[:12]}"
                    safe_execute(
                        "INSERT INTO bibles (id, novel_id, schema_version, extensions, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                        (new_bible_id, new_novel_id, bible_row["schema_version"], bible_row["extensions"], now, now)
                    )

                # 复制人物
                char_rows = safe_fetchall("SELECT * FROM bible_characters WHERE novel_id = ?", (old_novel_id,))
                for ch in char_rows:
                    old_char_id = ch["id"]
                    new_char_id = f"char-{uuid.uuid4().hex[:12]}"
                    char_id_map[old_char_id] = new_char_id

                    safe_execute(
                        """
                        INSERT INTO bible_characters (
                            id, novel_id, name, description, mental_state, mental_state_reason, verbal_tic, idle_behavior, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            new_char_id, new_novel_id, ch["name"], ch["description"], ch["mental_state"],
                            ch["mental_state_reason"], ch["verbal_tic"], ch["idle_behavior"], now, now
                        )
                    )

                    # 复制人物关系
                    rels = safe_fetchall("SELECT * FROM bible_character_relationships WHERE character_id = ?", (old_char_id,))
                    for rel in rels:
                        new_rel_id = f"rel-{uuid.uuid4().hex[:12]}"
                        safe_execute(
                            "INSERT INTO bible_character_relationships (id, character_id, target_name, relation, description) VALUES (?, ?, ?, ?, ?)",
                            (new_rel_id, new_char_id, rel["target_name"], rel["relation"], rel["description"])
                        )

                # 复制世界设定
                safe_execute(
                    """
                    INSERT INTO bible_world_settings (id, novel_id, name, description, setting_type, created_at, updated_at)
                    SELECT 'ws-' || lower(hex(randomblob(6))), ?, name, description, setting_type, ?, ?
                    FROM bible_world_settings WHERE novel_id = ?
                    """,
                    (new_novel_id, now, now, old_novel_id)
                )

                # 复制地理位置
                loc_rows = safe_fetchall("SELECT * FROM bible_locations WHERE novel_id = ?", (old_novel_id,))
                for loc in loc_rows:
                    old_loc_id = loc["id"]
                    new_loc_id = f"loc-{uuid.uuid4().hex[:12]}"
                    loc_id_map[old_loc_id] = new_loc_id

                for loc in loc_rows:
                    old_loc_id = loc["id"]
                    new_loc_id = loc_id_map[old_loc_id]
                    old_parent_loc_id = loc["parent_id"]
                    new_parent_loc_id = loc_id_map.get(old_parent_loc_id) if old_parent_loc_id else None

                    safe_execute(
                        """
                        INSERT INTO bible_locations (id, novel_id, name, description, location_type, parent_id, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            new_loc_id, new_novel_id, loc["name"], loc["description"], loc["location_type"],
                            new_parent_loc_id, now, now
                        )
                    )

                # 复制时间线备注
                safe_execute(
                    """
                    INSERT INTO bible_timeline_notes (id, novel_id, event, time_point, description, sort_order, created_at, updated_at)
                    SELECT 'tln-' || lower(hex(randomblob(6))), ?, event, time_point, description, sort_order, ?, ?
                    FROM bible_timeline_notes WHERE novel_id = ?
                    """,
                    (new_novel_id, now, now, old_novel_id)
                )

                # 复制写作风格备注
                safe_execute(
                    """
                    INSERT INTO bible_style_notes (id, novel_id, category, content, created_at, updated_at)
                    SELECT 'sn-' || lower(hex(randomblob(6))), ?, category, content, ?, ?
                    FROM bible_style_notes WHERE novel_id = ?
                    """,
                    (new_novel_id, now, now, old_novel_id)
                )

                # 5. 复制三元组及其多对多关联、属性、溯源
                triple_rows = safe_fetchall("SELECT * FROM triples WHERE novel_id = ?", (old_novel_id,))
                triple_id_map = {}
                for tr in triple_rows:
                    old_tr_id = tr["id"]
                    new_tr_id = f"triple-{uuid.uuid4().hex[:12]}"
                    triple_id_map[old_tr_id] = new_tr_id

                    # 映射 subject_entity_id / object_entity_id 引用
                    old_sub_id = tr["subject_entity_id"]
                    old_obj_id = tr["object_entity_id"]
                    new_sub_id = char_id_map.get(old_sub_id) or loc_id_map.get(old_sub_id) or old_sub_id
                    new_obj_id = char_id_map.get(old_obj_id) or loc_id_map.get(old_obj_id) or old_obj_id

                    safe_execute(
                        """
                        INSERT INTO triples (
                            id, novel_id, subject, predicate, object, chapter_number, note, entity_type,
                            importance, location_type, description, first_appearance, confidence, source_type,
                            subject_entity_id, object_entity_id, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            new_tr_id, new_novel_id, tr["subject"], tr["predicate"], tr["object"], tr["chapter_number"],
                            tr["note"], tr["entity_type"], tr["importance"], tr["location_type"], tr["description"],
                            tr["first_appearance"], tr["confidence"], tr["source_type"], new_sub_id, new_obj_id, now, now
                        )
                    )

                    # 标签
                    tags = safe_fetchall("SELECT * FROM triple_tags WHERE triple_id = ?", (old_tr_id,))
                    for tag in tags:
                        safe_execute("INSERT INTO triple_tags (triple_id, tag) VALUES (?, ?)", (new_tr_id, tag["tag"]))

                    # 扩展属性
                    attrs = safe_fetchall("SELECT * FROM triple_attr WHERE triple_id = ?", (old_tr_id,))
                    for attr in attrs:
                        safe_execute("INSERT INTO triple_attr (triple_id, attr_key, attr_value) VALUES (?, ?, ?)", (new_tr_id, attr["attr_key"], attr["attr_value"]))

                    # 溯源
                    provs = safe_fetchall("SELECT * FROM triple_provenance WHERE triple_id = ?", (old_tr_id,))
                    for prov in provs:
                        new_prov_id = f"prov-{uuid.uuid4().hex[:12]}"
                        old_snode_id = prov["story_node_id"]
                        new_snode_id = node_id_map.get(old_snode_id) if old_snode_id else None
                        safe_execute(
                            """
                            INSERT INTO triple_provenance (id, triple_id, novel_id, story_node_id, chapter_element_id, rule_id, role, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (new_prov_id, new_tr_id, new_novel_id, new_snode_id, prov["chapter_element_id"], prov["rule_id"], prov["role"], now)
                        )

                    # 关联更多章节
                    more_chaps = safe_fetchall("SELECT * FROM triple_more_chapters WHERE triple_id = ?", (old_tr_id,))
                    for mc in more_chaps:
                        safe_execute(
                            "INSERT INTO triple_more_chapters (triple_id, novel_id, chapter_number) VALUES (?, ?, ?)",
                            (new_tr_id, new_novel_id, mc["chapter_number"])
                        )

                # 6. 复制知识库与章节摘要
                k_row = safe_fetchone("SELECT * FROM knowledge WHERE novel_id = ?", (old_novel_id,))
                if k_row:
                    new_k_id = f"k-{uuid.uuid4().hex[:12]}"
                    safe_execute(
                        "INSERT INTO knowledge (id, novel_id, version, premise_lock, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                        (new_k_id, new_novel_id, k_row["version"], k_row["premise_lock"], now, now)
                    )

                    safe_execute(
                        """
                        INSERT INTO chapter_summaries (id, knowledge_id, chapter_number, summary, created_at, updated_at)
                        SELECT 'sum-' || lower(hex(randomblob(6))), ?, chapter_number, summary, ?, ?
                        FROM chapter_summaries WHERE knowledge_id = ?
                        """,
                        (new_k_id, now, now, k_row["id"])
                    )

                # 7. 复制章节审阅记录 (chapter_reviews)
                safe_execute(
                    """
                    INSERT INTO chapter_reviews (novel_id, chapter_number, status, memo, created_at, updated_at)
                    SELECT ?, chapter_number, status, memo, ?, ? FROM chapter_reviews WHERE novel_id = ?
                    """,
                    (new_novel_id, now, now, old_novel_id)
                )

                # 8. 复制文风漂移分数 (chapter_style_scores)
                safe_execute(
                    """
                    INSERT INTO chapter_style_scores (score_id, novel_id, chapter_number, adjective_density, avg_sentence_length, sentence_count, similarity_score, computed_at)
                    SELECT 'style-' || lower(hex(randomblob(6))), ?, chapter_number, adjective_density, avg_sentence_length, sentence_count, similarity_score, ?
                    FROM chapter_style_scores WHERE novel_id = ?
                    """,
                    (new_novel_id, now, old_novel_id)
                )

                # 9. 复制安全护栏快照 (chapter_guardrail_snapshots)
                safe_execute(
                    """
                    INSERT INTO chapter_guardrail_snapshots (novel_id, chapter_number, report_json, updated_at)
                    SELECT ?, chapter_number, report_json, ? FROM chapter_guardrail_snapshots WHERE novel_id = ?
                    """,
                    (new_novel_id, now, old_novel_id)
                )

                # 10. 复制故事线 (storylines) 与里程碑
                sl_rows = safe_fetchall("SELECT * FROM storylines WHERE novel_id = ?", (old_novel_id,))
                for sl in sl_rows:
                    old_sl_id = sl["id"]
                    new_sl_id = f"sl-{uuid.uuid4().hex[:12]}"
                    safe_execute(
                        """
                        INSERT INTO storylines (id, novel_id, storyline_type, status, estimated_chapter_start, estimated_chapter_end, current_milestone_index, extensions, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (new_sl_id, new_novel_id, sl["storyline_type"], sl["status"], sl["estimated_chapter_start"], sl["estimated_chapter_end"], sl["current_milestone_index"], sl["extensions"], now, now)
                    )

                    safe_execute(
                        """
                        INSERT INTO storyline_milestones (id, storyline_id, milestone_order, title, description, target_chapter_start, target_chapter_end, prerequisite_list, milestone_triggers)
                        SELECT 'ms-' || lower(hex(randomblob(6))), ?, milestone_order, title, description, target_chapter_start, target_chapter_end, prerequisite_list, milestone_triggers
                        FROM storyline_milestones WHERE storyline_id = ?
                        """,
                        (new_sl_id, old_sl_id)
                    )

                # 11. 复制情节弧线与剧情点
                pa_rows = safe_fetchall("SELECT * FROM plot_arcs WHERE novel_id = ?", (old_novel_id,))
                for pa in pa_rows:
                    old_pa_id = pa["id"]
                    new_pa_id = f"arc-{uuid.uuid4().hex[:12]}"
                    safe_execute(
                        "INSERT INTO plot_arcs (id, novel_id, slug, display_name, extensions, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (new_pa_id, new_novel_id, pa["slug"], pa["display_name"], pa["extensions"], now, now)
                    )

                    safe_execute(
                        """
                        INSERT INTO plot_points (id, plot_arc_id, sort_order, chapter_number, point_type, description, tension)
                        SELECT 'pt-' || lower(hex(randomblob(6))), ?, sort_order, chapter_number, point_type, description, tension
                        FROM plot_points WHERE plot_arc_id = ?
                        """,
                        (new_pa_id, old_pa_id)
                    )

                # 12. 复制物理实体基类、事件溯源、文风指纹和伏笔
                safe_execute(
                    """
                    INSERT INTO entity_base (id, novel_id, entity_type, name, core_attributes, created_at)
                    SELECT 'eb-' || lower(hex(randomblob(6))), ?, entity_type, name, core_attributes, ?
                    FROM entity_base WHERE novel_id = ?
                    """,
                    (new_novel_id, now, old_novel_id)
                )

                safe_execute(
                    """
                    INSERT INTO narrative_events (event_id, novel_id, chapter_number, event_summary, mutations, tags, timestamp_ts)
                    SELECT 'evt-' || lower(hex(randomblob(6))), ?, chapter_number, event_summary, mutations, tags, ?
                    FROM narrative_events WHERE novel_id = ?
                    """,
                    (new_novel_id, now, old_novel_id)
                )

                safe_execute(
                    """
                    INSERT INTO voice_vault (sample_id, novel_id, chapter_number, scene_type, ai_original, author_refined, diff_analysis, created_at)
                    SELECT 'vv-' || lower(hex(randomblob(6))), ?, chapter_number, scene_type, ai_original, author_refined, diff_analysis, ?
                    FROM voice_vault WHERE novel_id = ?
                    """,
                    (new_novel_id, now, old_novel_id)
                )

                safe_execute(
                    """
                    INSERT INTO voice_fingerprint (fingerprint_id, novel_id, pov_character_id, adjective_density, avg_sentence_length, sentence_count, sample_count, last_updated)
                    SELECT 'vfp-' || lower(hex(randomblob(6))), ?, pov_character_id, adjective_density, avg_sentence_length, sentence_count, sample_count, ?
                    FROM voice_fingerprint WHERE novel_id = ?
                    """,
                    (new_novel_id, now, old_novel_id)
                )

                safe_execute(
                    """
                    INSERT INTO novel_foreshadow_registry (novel_id, payload, updated_at)
                    SELECT ?, payload, ? FROM novel_foreshadow_registry WHERE novel_id = ?
                    """,
                    (new_novel_id, now, old_novel_id)
                )

                safe_execute(
                    """
                    INSERT INTO dag_versions (id, novel_id, version, dag_id, name, description, nodes_json, edges_json, fingerprint, created_at, updated_at)
                    SELECT 'dag-' || lower(hex(randomblob(6))), ?, version, dag_id, name, description, nodes_json, edges_json, fingerprint, ?, ?
                    FROM dag_versions WHERE novel_id = ?
                    """,
                    (new_novel_id, now, now, old_novel_id)
                )

                # 更新新书 POV 角色映射以保证引用的完整性 (若 node 绑定的 pov 角色属于旧书，映射到新克隆出来的角色ID)
                for old_char_id, new_char_id in char_id_map.items():
                    conn.execute(
                        "UPDATE story_nodes SET pov_character_id = ? WHERE novel_id = ? AND pov_character_id = ?",
                        (new_char_id, new_novel_id, old_char_id)
                    )

        except Exception as e:
            logger.error(f"Failed to duplicate SQLite records for {old_novel_id}: {e}")
            raise e
        finally:
            bypass.__exit__(None, None, None)

        # 13. 复制物理磁盘文件夹下的文件设定 (Bible, Foreshadows JSON 等)
        try:
            from application.paths import get_db_path
            db_path = get_db_path()
            db_dir = Path(db_path).parent
            old_novel_dir = db_dir / "novels" / old_novel_id
            new_novel_dir = db_dir / "novels" / new_novel_id
            if old_novel_dir.exists() and old_novel_dir.is_dir():
                shutil.copytree(old_novel_dir, new_novel_dir)
                logger.info(f"Duplicated physical novel files directory from {old_novel_dir} to {new_novel_dir}")
        except Exception as e:
            logger.warning(f"Failed to copy physical directories for novel duplication: {e}")

        logger.info(f"Successfully duplicated novel {old_novel_id} -> {new_novel_id}")
        return new_novel_id

    def clear_novel_drafts(self, novel_id: str) -> None:
        """选择 1：清空已生成正文（保留大纲）"""
        import logging
        from infrastructure.persistence.database.connection import get_database
        logger = logging.getLogger(__name__)
        db = get_database()

        with db.transaction() as conn:
            def safe_execute(sql, params=None):
                import sqlite3
                try:
                    if params is None:
                        return conn.execute(sql)
                    return conn.execute(sql, params)
                except sqlite3.OperationalError as oe:
                    if "no such table" in str(oe):
                        logger.warning(f"Table not found, skipping delete: {oe}")
                        return None
                    raise

            # 删正文、大纲、评定
            # 删正文、评定、快照
            conn.execute("DELETE FROM chapters WHERE novel_id = ?", (novel_id,))
            safe_execute("DELETE FROM chapter_guardrail_snapshots WHERE novel_id = ?", (novel_id,))
            safe_execute("DELETE FROM chapter_style_scores WHERE novel_id = ?", (novel_id,))
            
            # 清除衍生的僵尸数据
            safe_execute("DELETE FROM chapter_reviews WHERE novel_id = ?", (novel_id,))
            # chapter_summaries is linked by knowledge_id. Get knowledge_id first:
            safe_execute("DELETE FROM chapter_summaries WHERE knowledge_id IN (SELECT id FROM knowledge WHERE novel_id = ?)", (novel_id,))
            safe_execute("DELETE FROM beat_sheets WHERE chapter_id IN (SELECT id FROM chapters WHERE novel_id = ?)", (novel_id,))

            # 重置故事线进度
            safe_execute("UPDATE storylines SET current_milestone_index = 0 WHERE novel_id = ?", (novel_id,))
            
            # 将所有 chapter 大纲节点重置为 draft 和零词数（坚决保留 outline 细纲！）
            conn.execute(
                """
                UPDATE story_nodes
                SET status = 'draft', word_count = 0, content = NULL
                WHERE novel_id = ? AND node_type = 'chapter'
                """,
                (novel_id,)
            )

            # 更新 novels 统计
            conn.execute(
                """
                UPDATE novels
                SET current_chapter_in_act = 0, current_beat_index = 0, beats_completed = 0,
                    last_audit_chapter_number = NULL, last_audit_similarity = NULL,
                    last_audit_drift_alert = 0, last_audit_narrative_ok = 1
                WHERE id = ?
                """,
                (novel_id,)
            )
        logger.info(f"Cleared chapter drafts and reset metadata for novel {novel_id}")

        # 同样需要清理向量库中关于此书的所有记忆
        try:
            from infrastructure.ai.chromadb_vector_store import ChromaDBVectorStore
            import asyncio
            vector_store = ChromaDBVectorStore()
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(vector_store.delete(collection="novel_vectors", where={"novel_id": novel_id}))
            except RuntimeError:
                asyncio.run(vector_store.delete(collection="novel_vectors", where={"novel_id": novel_id}))
            logger.info(f"Triggered vector store cleanup for novel drafts {novel_id}")
        except Exception as e:
            logger.warning(f"Failed to clear vector store for {novel_id}: {e}")

        # 同步多进程缓存
        try:
            from application.engine.services.state_bootstrap import bootstrap_novel_state
            bootstrap_novel_state(novel_id, force=True)
            logger.info(f"Synchronized daemon shared state for novel drafts {novel_id}")
        except Exception as e:
            logger.warning(f"Failed to sync daemon shared state for {novel_id}: {e}")

    def clear_novel_outline(self, novel_id: str) -> None:
        """选择 2：彻底重设（清空正文与大纲树，恢复至规划中）"""
        import logging
        from infrastructure.persistence.database.connection import get_database
        logger = logging.getLogger(__name__)
        db = get_database()

        with db.transaction() as conn:
            def safe_execute(sql, params=None):
                import sqlite3
                try:
                    if params is None:
                        return conn.execute(sql)
                    return conn.execute(sql, params)
                except sqlite3.OperationalError as oe:
                    if "no such table" in str(oe):
                        logger.warning(f"Table not found, skipping delete: {oe}")
                        return None
                    raise

            # 1. 删正文和评定
            conn.execute("DELETE FROM chapters WHERE novel_id = ?", (novel_id,))
            safe_execute("DELETE FROM chapter_guardrail_snapshots WHERE novel_id = ?", (novel_id,))
            safe_execute("DELETE FROM chapter_style_scores WHERE novel_id = ?", (novel_id,))

            # 2. 删整个故事结构树 (外键级联删除 elements 和 scenes)
            conn.execute("DELETE FROM story_nodes WHERE novel_id = ?", (novel_id,))

            # 3. 删提取的三元组及关联数据
            safe_execute("DELETE FROM triples WHERE novel_id = ?", (novel_id,))
            safe_execute("DELETE FROM triple_provenance WHERE novel_id = ?", (novel_id,))
            safe_execute("DELETE FROM triple_more_chapters WHERE novel_id = ?", (novel_id,))
            
            # 4. 删大体量故事线、情节弧、事件、DAG版本
            safe_execute("DELETE FROM storylines WHERE novel_id = ?", (novel_id,))
            safe_execute("DELETE FROM plot_arcs WHERE novel_id = ?", (novel_id,))
            safe_execute("DELETE FROM plot_points WHERE plot_arc_id IN (SELECT id FROM plot_arcs WHERE novel_id = ?)", (novel_id,))
            safe_execute("DELETE FROM narrative_events WHERE novel_id = ?", (novel_id,))
            safe_execute("DELETE FROM dag_versions WHERE novel_id = ?", (novel_id,))
            
            # 4.5. 删伏笔账本与文风声线库
            safe_execute("DELETE FROM novel_foreshadow_registry WHERE novel_id = ?", (novel_id,))
            safe_execute("DELETE FROM voice_vault WHERE novel_id = ?", (novel_id,))
            safe_execute("DELETE FROM voice_fingerprint WHERE novel_id = ?", (novel_id,))

            # 5. 重设主表状态至规划中 (planning)
            conn.execute(
                """
                UPDATE novels
                SET current_stage = 'planning', autopilot_status = 'stopped',
                    current_act = 0, current_chapter_in_act = 0, current_beat_index = 0,
                    beats_completed = 0, last_audit_chapter_number = NULL, last_audit_similarity = NULL,
                    last_audit_drift_alert = 0, last_audit_narrative_ok = 1, current_auto_chapters = 0
                WHERE id = ?
                """,
                (novel_id,)
            )
        logger.info(f"Fully cleared and reset outline and drafts for novel {novel_id}")
        
        # 6. 删除向量库中的嵌入记忆，防止 RAG 幽灵上下文
        try:
            from infrastructure.ai.chromadb_vector_store import ChromaDBVectorStore
            import asyncio
            vector_store = ChromaDBVectorStore()
            # Since vector store methods are async, we use the event loop
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(vector_store.delete(collection="novel_vectors", where={"novel_id": novel_id}))
            except RuntimeError:
                asyncio.run(vector_store.delete(collection="novel_vectors", where={"novel_id": novel_id}))
            logger.info(f"Triggered vector store cleanup for novel {novel_id}")
        except Exception as e:
            logger.warning(f"Failed to clear vector store for {novel_id}: {e}")

        # 7. 删除本地磁盘上的物理缓存和导出文件
        try:
            import shutil
            from pathlib import Path
            from application.paths import get_db_path
            db_dir = Path(get_db_path()).parent
            chapters_dir = db_dir / "novels" / novel_id / "chapters"
            if chapters_dir.exists() and chapters_dir.is_dir():
                shutil.rmtree(chapters_dir)
                logger.info(f"Removed physical chapters directory for {novel_id}")
        except Exception as e:
            logger.warning(f"Failed to clear physical directories for {novel_id}: {e}")

        # 8. 同步清除/重载守护进程的多进程共享状态缓存
        try:
            from application.engine.services.state_bootstrap import bootstrap_novel_state
            # Force a re-bootstrap which will read the newly reset SQLite state and update shared memory
            bootstrap_novel_state(novel_id, force=True)
            logger.info(f"Synchronized daemon shared state for novel {novel_id}")
        except Exception as e:
            logger.warning(f"Failed to sync daemon shared state for {novel_id}: {e}")

