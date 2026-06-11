from __future__ import annotations

from typing import Any, AsyncIterator, Optional

from domain.ai.services.llm_service import GenerationConfig, GenerationResult
from domain.ai.value_objects.prompt import Prompt
from domain.ai.value_objects.token_usage import TokenUsage
from infrastructure.ai.codex_app_server_client import CodexAppServerClient
from infrastructure.ai.config.settings import Settings

from .base import BaseProvider


class CodexAppServerProvider(BaseProvider):
    """LLMService adapter backed by the official Codex app-server."""

    def __init__(
        self,
        settings: Settings,
        client: Optional[CodexAppServerClient] = None,
    ) -> None:
        super().__init__(settings)
        self.client = client or CodexAppServerClient()
        self._owns_client = client is None

    async def generate(self, prompt: Prompt, config: GenerationConfig) -> GenerationResult:
        content = await self.client.generate_text(
            system=prompt.system,
            user=self._build_user_prompt(prompt.user, config),
            model=self._resolve_model(config),
            timeout=float(self.settings.timeout_seconds),
            output_schema=self._extract_output_schema(config.response_format),
        )
        return GenerationResult(
            content=content,
            token_usage=TokenUsage(input_tokens=0, output_tokens=0),
        )

    async def stream_generate(self, prompt: Prompt, config: GenerationConfig) -> AsyncIterator[str]:
        async for chunk in self.client.stream_text(
            system=prompt.system,
            user=self._build_user_prompt(prompt.user, config),
            model=self._resolve_model(config),
            timeout=float(self.settings.timeout_seconds),
            output_schema=self._extract_output_schema(config.response_format),
        ):
            yield chunk

    async def aclose(self) -> None:
        await self._close_owned_client()

    async def _close_owned_client(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    def _resolve_model(self, config: GenerationConfig) -> str:
        model = (config.model or self.settings.default_model or "").strip()
        if model == "codex-default":
            return ""
        return model

    @staticmethod
    def _build_user_prompt(user_prompt: str, config: GenerationConfig) -> str:
        return (
            f"{user_prompt}\n\n"
            "[PlotPilot Codex adapter constraints]\n"
            f"- temperature target: {config.temperature}\n"
            f"- max output tokens target: {config.max_tokens}\n"
            "- Return only the final requested text.\n"
        )

    @staticmethod
    def _extract_output_schema(response_format: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        if not response_format:
            return None
        if response_format.get("type") != "json_schema":
            return None
        json_schema = response_format.get("json_schema")
        if isinstance(json_schema, dict):
            schema = json_schema.get("schema")
            if isinstance(schema, dict):
                return schema
        return None
