"""Novel API 路由"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Response
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field
import logging

from application.core.services.novel_service import NovelService
from application.world.services.auto_bible_generator import AutoBibleGenerator
from application.world.services.auto_knowledge_generator import AutoKnowledgeGenerator
from application.core.dtos.novel_dto import NovelDTO
from application.core.chapter_target_limits import CHAPTER_TARGET_WORDS_MAX, CHAPTER_TARGET_WORDS_MIN
from application.ai_invocation.variable_hub import VariableWrite
from application.writing_spec import load_writing_spec_by_id
from infrastructure.persistence.database.connection import get_database
from infrastructure.persistence.database.sqlite_ai_invocation_repository import SqliteVariableHubRepository
from interfaces.api.dependencies import (
    get_novel_service,
    get_auto_bible_generator,
    get_auto_knowledge_generator
)
from interfaces.api.urls import bible_generation_status_url
from domain.shared.exceptions import EntityNotFoundError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/novels", tags=["novels"])


# Request Models
class CreateNovelRequest(BaseModel):
    """创建小说请求"""
    novel_id: str = Field(..., description="小说 ID")
    title: str = Field(..., description="小说标题")
    author: str = Field(..., description="作者")
    target_chapters: int = Field(
        100,
        ge=0,
        description="目标章节数；选 V1 体量档时可传 0 由服务端推导",
    )
    premise: str = Field(default="", max_length=2000, description="故事梗概/创意（建议 2000 字内）")
    genre: str = Field(default="", description="赛道/类型（下拉预设）")
    world_preset: str = Field(default="", description="世界观基调（下拉预设）")
    story_structure: str = Field(default="", description="剧情结构（题材预设，可由用户修改）")
    pacing_control: str = Field(default="", description="节奏把控（题材预设，可由用户修改）")
    writing_style: str = Field(default="", description="写作风格（题材预设，可由用户修改）")
    special_requirements: str = Field(default="", description="特殊要求（题材预设，可由用户修改）")
    length_tier: Optional[Literal["short", "standard", "epic"]] = Field(
        None,
        description="V1 目标篇幅档：short≈30万字 / standard≈100万字 / epic≈300万字（推导章数与每章字数）",
    )
    target_words_per_chapter: Optional[int] = Field(
        None,
        ge=CHAPTER_TARGET_WORDS_MIN,
        le=CHAPTER_TARGET_WORDS_MAX,
        description="每章目标字数；可选，与体量档或自定义章数搭配",
    )


class UpdateStageRequest(BaseModel):
    """更新阶段请求"""
    stage: str = Field(..., description="小说阶段")


class UpdateNovelRequest(BaseModel):
    """更新小说基本信息请求"""
    title: str = Field(None, description="小说标题")
    author: str = Field(None, description="作者")
    target_chapters: int = Field(None, gt=0, description="目标章节数")
    premise: str = Field(None, description="故事梗概/创意")
    target_words_per_chapter: Optional[int] = Field(
        None,
        ge=CHAPTER_TARGET_WORDS_MIN,
        le=CHAPTER_TARGET_WORDS_MAX,
        description="每章目标字数（全托管节拍与章长参考）",
    )
    generation_prefs: Optional[Dict[str, Any]] = Field(
        None,
        description="生成偏好（与库内合并）；键示例：phase_display_mode, inline_prose_aggregation_enabled, conductor_converge_threshold, conductor_land_threshold",
    )


class UpdateAutoApproveRequest(BaseModel):
    """更新全自动模式请求"""
    auto_approve_mode: bool = Field(..., description="是否开启全自动模式（跳过所有人工审阅）")


class WritingSpecBindingRequest(BaseModel):
    """项目 WritingSpec 绑定请求"""
    writing_spec_id: str = Field(
        "",
        max_length=120,
        description="WritingSpec ID；传空字符串表示清空绑定",
    )


class WritingSpecBindingResponse(BaseModel):
    """项目 WritingSpec 绑定响应"""
    novel_id: str
    writing_spec_id: str = ""
    spec_title: str = ""
    spec_version: str = ""
    context_key: str


class HumanizerSettingsRequest(BaseModel):
    """项目 Humanizer 设置请求"""
    enabled: bool = Field(False, description="是否在章节正文生成后、保存前执行 Humanizer")
    revision_note: str = Field("", max_length=4000, description="本项目 Humanizer 专项润色要求")
    failure_policy: Literal["fallback_original", "fail"] = Field(
        "fallback_original",
        description="Humanizer 或复审失败时，fallback_original=回退到润色前正文，fail=阻断本次生成",
    )
    temperature: float = Field(0.65, ge=0, le=2, description="Humanizer 温度")
    max_tokens: Optional[int] = Field(None, gt=0, description="Humanizer 最大输出 token；空表示自动估算")


class HumanizerSettingsResponse(HumanizerSettingsRequest):
    """项目 Humanizer 设置响应"""
    novel_id: str
    context_key: str


async def _generate_bible_background(
    novel_id: str,
    title: str,
    target_chapters: int,
    bible_generator: AutoBibleGenerator,
    knowledge_generator: AutoKnowledgeGenerator
):
    """后台任务：生成 Bible 和 Knowledge"""
    bible_summary = ""
    try:
        bible_data = await bible_generator.generate_and_save(
            novel_id,
            title,
            target_chapters
        )
        # 构建 Bible 摘要供 Knowledge 生成使用
        chars = bible_data.get("characters", [])
        locs = bible_data.get("locations", [])
        char_desc = "、".join(f"{c['name']}（{c.get('role', '')}）" for c in chars[:5])
        loc_desc = "、".join(c['name'] for c in locs[:3])
        bible_summary = f"主要角色：{char_desc}。重要地点：{loc_desc}。文风：{bible_data.get('style', '')}。"

        # 生成初始 Knowledge
        await knowledge_generator.generate_and_save(
            novel_id,
            title,
            bible_summary
        )
        logger.info(f"Bible and Knowledge generated successfully for {novel_id}")
    except Exception as e:
        logger.error(f"Failed to generate Bible/Knowledge for {novel_id}: {e}")


def _writing_spec_context_key(novel_id: str) -> str:
    return f"novel_id:{novel_id}"


def _novel_variable_context_key(novel_id: str) -> str:
    return f"novel_id:{novel_id}"


def _writing_spec_binding_response(novel_id: str, writing_spec_id: str) -> WritingSpecBindingResponse:
    spec_title = ""
    spec_version = ""
    if writing_spec_id:
        spec = load_writing_spec_by_id(writing_spec_id)
        spec_title = spec.title
        spec_version = spec.version
    return WritingSpecBindingResponse(
        novel_id=novel_id,
        writing_spec_id=writing_spec_id,
        spec_title=spec_title,
        spec_version=spec_version,
        context_key=_writing_spec_context_key(novel_id),
    )


def _humanizer_settings_response(novel_id: str, repo: SqliteVariableHubRepository) -> HumanizerSettingsResponse:
    context_key = _novel_variable_context_key(novel_id)

    def get_value(key: str, default: Any) -> Any:
        value = repo.get_value(key, context_key)
        return value.value if value is not None else default

    def as_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        return str(value or "").strip().lower() in {"1", "true", "yes", "on", "enabled", "开启", "是"}

    failure_policy = str(get_value("novel.humanizer.failure_policy", "fallback_original"))
    if failure_policy not in {"fallback_original", "fail"}:
        failure_policy = "fallback_original"
    max_tokens_raw = get_value("novel.humanizer.max_tokens", None)
    try:
        max_tokens = int(max_tokens_raw) if max_tokens_raw not in (None, "") else None
    except (TypeError, ValueError):
        max_tokens = None
    try:
        temperature = float(get_value("novel.humanizer.temperature", 0.65))
    except (TypeError, ValueError):
        temperature = 0.65
    return HumanizerSettingsResponse(
        novel_id=novel_id,
        context_key=context_key,
        enabled=as_bool(get_value("novel.humanizer.enabled", False)),
        revision_note=str(get_value("novel.humanizer.revision_note", "") or ""),
        failure_policy=failure_policy,  # type: ignore[arg-type]
        temperature=max(0.0, min(2.0, temperature)),
        max_tokens=max_tokens if max_tokens and max_tokens > 0 else None,
    )


# Routes
@router.post("/", response_model=NovelDTO, status_code=201)
async def create_novel(
    request: CreateNovelRequest,
    service: NovelService = Depends(get_novel_service)
):
    """创建新小说（不自动生成 Bible）

    创建小说后，前端应该：
    1. 调用 POST /bible/novels/{novel_id}/generate 触发 Bible 生成
    2. 轮询 GET /bible/novels/{novel_id}/bible/status 检查生成状态
    3. 引导用户确认 Bible
    4. 用户手动触发规划（通过 POST /novels/{novel_id}/structure/plan 接口）

    Args:
        request: 创建小说请求
        service: Novel 服务

    Returns:
        创建的小说 DTO
    """
    # 只创建小说实体，不生成 Bible
    novel_dto = service.create_novel(
        novel_id=request.novel_id,
        title=request.title,
        author=request.author,
        target_chapters=request.target_chapters,
        premise=request.premise,
        genre=request.genre,
        world_preset=request.world_preset,
        story_structure=request.story_structure,
        pacing_control=request.pacing_control,
        writing_style=request.writing_style,
        special_requirements=request.special_requirements,
        length_tier=request.length_tier,
        target_words_per_chapter=request.target_words_per_chapter,
    )

    return novel_dto


@router.get("/{novel_id}", response_model=NovelDTO)
async def get_novel(
    novel_id: str,
    service: NovelService = Depends(get_novel_service)
):
    """获取小说详情

    Args:
        novel_id: 小说 ID
        service: Novel 服务

    Returns:
        小说 DTO

    Raises:
        HTTPException: 如果小说不存在
    """
    novel = service.get_novel(novel_id)
    if novel is None:
        raise HTTPException(status_code=404, detail=f"Novel not found: {novel_id}")
    return novel


@router.get("/{novel_id}/writing-spec", response_model=WritingSpecBindingResponse)
async def get_novel_writing_spec(
    novel_id: str,
    service: NovelService = Depends(get_novel_service),
):
    """读取项目默认 WritingSpec 绑定。"""
    if service.get_novel(novel_id) is None:
        raise HTTPException(status_code=404, detail=f"Novel not found: {novel_id}")
    repo = SqliteVariableHubRepository(get_database())
    value = repo.get_value("novel.writing_spec_id", _writing_spec_context_key(novel_id))
    spec_id = str(value.value or "").strip() if value is not None else ""
    try:
        return _writing_spec_binding_response(novel_id, spec_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{novel_id}/writing-spec", response_model=WritingSpecBindingResponse)
async def set_novel_writing_spec(
    novel_id: str,
    request: WritingSpecBindingRequest,
    service: NovelService = Depends(get_novel_service),
):
    """绑定项目默认 WritingSpec；生成管线会自动读取并执行。"""
    if service.get_novel(novel_id) is None:
        raise HTTPException(status_code=404, detail=f"Novel not found: {novel_id}")
    spec_id = request.writing_spec_id.strip()
    if spec_id:
        try:
            load_writing_spec_by_id(spec_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))

    repo = SqliteVariableHubRepository(get_database())
    repo.set_value(
        VariableWrite(
            key="novel.writing_spec_id",
            value=spec_id,
            context_key=_writing_spec_context_key(novel_id),
            source_trace_id="writing_spec_binding",
            source_node_key="writing_spec_binding",
            value_type="string",
            display_name="项目 WritingSpec",
            scope="novel",
            stage="writing",
        )
    )
    return _writing_spec_binding_response(novel_id, spec_id)


@router.get("/{novel_id}/humanizer", response_model=HumanizerSettingsResponse)
async def get_novel_humanizer_settings(
    novel_id: str,
    service: NovelService = Depends(get_novel_service),
):
    """读取项目 Humanizer 设置。"""
    if service.get_novel(novel_id) is None:
        raise HTTPException(status_code=404, detail=f"Novel not found: {novel_id}")
    return _humanizer_settings_response(
        novel_id,
        SqliteVariableHubRepository(get_database()),
    )


@router.put("/{novel_id}/humanizer", response_model=HumanizerSettingsResponse)
async def set_novel_humanizer_settings(
    novel_id: str,
    request: HumanizerSettingsRequest,
    service: NovelService = Depends(get_novel_service),
):
    """设置项目 Humanizer；生成管线只在 enabled=true 时执行。"""
    if service.get_novel(novel_id) is None:
        raise HTTPException(status_code=404, detail=f"Novel not found: {novel_id}")
    repo = SqliteVariableHubRepository(get_database())
    context_key = _novel_variable_context_key(novel_id)
    values = {
        "novel.humanizer.enabled": (request.enabled, "boolean", "Humanizer 开关"),
        "novel.humanizer.revision_note": (request.revision_note.strip(), "string", "Humanizer 专项润色要求"),
        "novel.humanizer.failure_policy": (request.failure_policy, "string", "Humanizer 失败策略"),
        "novel.humanizer.temperature": (request.temperature, "float", "Humanizer 温度"),
        "novel.humanizer.max_tokens": (request.max_tokens, "integer", "Humanizer 最大输出 token"),
    }
    for key, (value, value_type, display_name) in values.items():
        repo.set_value(
            VariableWrite(
                key=key,
                value=value,
                context_key=context_key,
                source_trace_id="humanizer_settings",
                source_node_key="humanizer_settings",
                value_type=value_type,
                display_name=display_name,
                scope="novel",
                stage="writing",
            )
        )
    return _humanizer_settings_response(novel_id, repo)


@router.get("/", response_model=List[NovelDTO])
async def list_novels(
    response: Response,
    service: NovelService = Depends(get_novel_service),
):
    """列出所有小说

    Args:
        service: Novel 服务

    Returns:
        小说 DTO 列表
    """
    novels = service.list_novels()
    repo = service.novel_repository
    consume = getattr(repo, "consume_sqlite_corruption_warning", None)
    if callable(consume) and consume():
        response.headers["X-SQLite-State"] = "corrupted"
    return novels


@router.put("/{novel_id}", response_model=NovelDTO)
async def update_novel(
    novel_id: str,
    request: UpdateNovelRequest,
    service: NovelService = Depends(get_novel_service)
):
    """更新小说基本信息

    Args:
        novel_id: 小说 ID
        request: 更新小说请求
        service: Novel 服务

    Returns:
        更新后的小说 DTO

    Raises:
        HTTPException: 如果小说不存在
    """
    try:
        return service.update_novel(
            novel_id,
            request.title,
            request.author,
            request.target_chapters,
            request.premise,
            target_words_per_chapter=request.target_words_per_chapter,
            generation_prefs=request.generation_prefs,
        )
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{novel_id}/stage", response_model=NovelDTO)
async def update_novel_stage(
    novel_id: str,
    request: UpdateStageRequest,
    service: NovelService = Depends(get_novel_service)
):
    """更新小说阶段

    Args:
        novel_id: 小说 ID
        request: 更新阶段请求
        service: Novel 服务

    Returns:
        更新后的小说 DTO

    Raises:
        HTTPException: 如果小说不存在
    """
    try:
        return service.update_novel_stage(novel_id, request.stage)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{novel_id}", status_code=204)
async def delete_novel(
    novel_id: str,
    service: NovelService = Depends(get_novel_service)
):
    """删除小说

    Args:
        novel_id: 小说 ID
        service: Novel 服务
    """
    service.delete_novel(novel_id)


@router.post("/{novel_id}/bible/generate", status_code=202)
async def generate_bible_alias(
    novel_id: str,
    background_tasks: BackgroundTasks,
    stage: str = "all",
    bible_generator: AutoBibleGenerator = Depends(get_auto_bible_generator),
    knowledge_generator: AutoKnowledgeGenerator = Depends(get_auto_knowledge_generator),
    novel_service: NovelService = Depends(get_novel_service),
):
    """手动触发 Bible 生成（别名路由，与 POST /bible/novels/{novel_id}/generate 等价）

    Args:
        novel_id: 小说 ID
        background_tasks: FastAPI 后台任务
        stage: 生成阶段 (all / worldbuilding / characters / locations)

    Returns:
        202 Accepted
    """
    try:
        import traceback

        novel = novel_service.get_novel(novel_id)
        if not novel:
            raise HTTPException(status_code=404, detail=f"Novel not found: {novel_id}")

        async def _generate_task():
            try:
                premise = novel.premise if novel.premise else novel.title
                bible_data = await bible_generator.generate_and_save(
                    novel_id=novel_id,
                    premise=premise,
                    target_chapters=novel.target_chapters,
                    stage=stage
                )
                if knowledge_generator and stage in ("all", "worldbuilding"):
                    chars = bible_data.get("characters", [])
                    locs = bible_data.get("locations", [])
                    char_desc = "、".join(f"{c.get('name', '')}（{c.get('role', '')}）" for c in chars[:5])
                    loc_desc = "、".join(c.get("name", "") for c in locs[:3])
                    bible_summary = f"主要角色：{char_desc}。重要地点：{loc_desc}。文风：{bible_data.get('style', '')}。"
                    await knowledge_generator.generate_and_save(
                        novel_id=novel_id,
                        title=novel.title,
                        bible_summary=bible_summary,
                    )
            except Exception as e:
                logger.error(f"Failed to generate Bible/Knowledge for {novel_id}: {e}")
                logger.error(traceback.format_exc())

        background_tasks.add_task(_generate_task)

        return {
            "message": "Bible generation started",
            "novel_id": novel_id,
            "status_url": bible_generation_status_url(novel_id),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动Bible生成失败: {str(e)}")


@router.patch("/{novel_id}/auto-approve-mode", response_model=NovelDTO)
async def update_auto_approve_mode(
    novel_id: str,
    request: UpdateAutoApproveRequest,
    service: NovelService = Depends(get_novel_service)
):
    """更新全自动模式设置
    
    Args:
        novel_id: 小说 ID
        request: 更新全自动模式请求
        service: Novel 服务
        
    Returns:
        更新后的小说 DTO
        
    Raises:
        HTTPException: 如果小说不存在
    """
    try:
        return service.update_auto_approve_mode(novel_id, request.auto_approve_mode)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{novel_id}/statistics")
async def get_novel_statistics(
    novel_id: str,
    service: NovelService = Depends(get_novel_service)
):
    """获取小说统计信息

    Args:
        novel_id: 小说 ID
        service: Novel 服务

    Returns:
        统计信息字典

    Raises:
        HTTPException: 如果小说不存在
    """
    try:
        return service.get_novel_statistics(novel_id)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
