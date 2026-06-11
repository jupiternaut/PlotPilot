from application.ai.llm_control_service import LLMProfile
from infrastructure.ai.provider_factory import LLMProviderFactory
from infrastructure.ai.providers.codex_app_server_provider import CodexAppServerProvider
from infrastructure.ai.providers.mock_provider import MockProvider


def test_provider_factory_creates_codex_provider_without_api_key_or_model():
    provider = LLMProviderFactory().create_from_profile(
        LLMProfile(
            id="codex",
            name="Codex",
            preset_key="codex-app-server-chatgpt",
            protocol="codex",
            api_key="",
            model="",
        )
    )

    assert isinstance(provider, CodexAppServerProvider)
    assert provider.settings.protocol == "codex"
    assert provider.settings.api_key == ""
    assert provider.settings.default_model == ""


def test_provider_factory_keeps_non_codex_missing_credentials_on_mock():
    provider = LLMProviderFactory().create_from_profile(
        LLMProfile(
            id="openai",
            name="OpenAI",
            protocol="openai",
            api_key="",
            model="gpt-test",
        )
    )

    assert isinstance(provider, MockProvider)
