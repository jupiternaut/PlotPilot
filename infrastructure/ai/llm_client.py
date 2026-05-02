"""LLM 客户端包装器，支持动态服务切换"""
import os
import logging
from typing import AsyncIterator, Optional, Any, Dict, Union

from domain.ai.services.llm_service import GenerationConfig, LLMService
from domain.ai.value_objects.prompt import Prompt
from infrastructure.ai.provider_factory import DynamicLLMService

logger = logging.getLogger(__name__)

class LLMClient:
    """LLM 客户端包装器，自动选择当前激活的提供者。
    
    采用上游 DynamicLLMService 架构，支持运行时动态切换模型配置。
    """

    def __init__(self, provider: Optional[LLMService] = None):
        """初始化 LLM 客户端
        
        Args:
            provider: 可选的 LLM 提供者实例。如果未提供，将使用 DynamicLLMService。
        """
        self.provider = provider or DynamicLLMService()

    def _build_config(self, **kwargs) -> GenerationConfig:
        """根据传入参数和 Provider 默认设置构建生成配置"""
        settings = getattr(self.provider, "settings", None)
        return GenerationConfig(
            model=kwargs.get("model", getattr(settings, "default_model", None)),
            max_tokens=kwargs.get("max_tokens", getattr(settings, "default_max_tokens", 4096)),
            temperature=kwargs.get("temperature", getattr(settings, "default_temperature", 0.7)),
        )

    async def generate(self, prompt: str, **kwargs) -> str:
        """生成文本内容"""
        prompt_obj = Prompt(
            system=kwargs.get("system_prompt", "你是一个专业的小说创作助手。"),
            user=prompt
        )
        config = self._build_config(**kwargs)
        result = await self.provider.generate(prompt_obj, config)
        return result.content

    async def stream_generate(
        self,
        prompt: Union[Prompt, str],
        config: Optional[GenerationConfig] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """流式生成内容"""
        if isinstance(prompt, str):
            prompt_obj = Prompt(
                system=kwargs.get("system_prompt", "你是一个专业的小说创作助手。"),
                user=prompt
            )
        else:
            prompt_obj = prompt

        if config is None:
            config = self._build_config(**kwargs)

        async for chunk in self.provider.stream_generate(prompt_obj, config):
            yield chunk
