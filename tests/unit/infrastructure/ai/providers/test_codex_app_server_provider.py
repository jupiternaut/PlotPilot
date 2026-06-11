import pytest

from domain.ai.services.llm_service import GenerationConfig
from domain.ai.value_objects.prompt import Prompt
from infrastructure.ai.config.settings import Settings
from infrastructure.ai.providers.codex_app_server_provider import CodexAppServerProvider


class FakeCodexClient:
    def __init__(self):
        self.calls = []
        self.closed = False

    async def generate_text(self, **kwargs):
        self.calls.append(kwargs)
        return "连接成功"

    async def stream_text(self, **kwargs):
        self.calls.append(kwargs)
        yield "连"
        yield "接成功"

    async def aclose(self):
        self.closed = True


@pytest.mark.asyncio
async def test_codex_provider_treats_codex_default_as_app_server_default_model():
    client = FakeCodexClient()
    provider = CodexAppServerProvider(
        Settings(default_model="codex-default", protocol="codex"),
        client=client,
    )

    result = await provider.generate(
        Prompt(system="system", user="user"),
        GenerationConfig(model="codex-default"),
    )

    assert result.content == "连接成功"
    assert client.calls[0]["model"] == ""
    assert client.closed is False


@pytest.mark.asyncio
async def test_codex_provider_extracts_json_schema_for_app_server():
    client = FakeCodexClient()
    provider = CodexAppServerProvider(
        Settings(default_model="", protocol="codex"),
        client=client,
    )
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}

    await provider.generate(
        Prompt(system="system", user="user"),
        GenerationConfig(
            response_format={
                "type": "json_schema",
                "json_schema": {"schema": schema},
            },
        ),
    )

    assert client.calls[0]["output_schema"] == schema
