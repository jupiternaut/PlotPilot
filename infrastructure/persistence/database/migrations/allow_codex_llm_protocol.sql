-- Allow ChatGPT/Codex app-server profiles in the LLM control panel.
--
-- SQLite cannot alter a CHECK constraint in place, so rebuild llm_profiles
-- while preserving existing OpenAI/Anthropic/Gemini profiles.

PRAGMA foreign_keys=OFF;

CREATE TABLE IF NOT EXISTS llm_profiles_new (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    preset_key TEXT NOT NULL DEFAULT 'custom-openai-compatible',
    protocol TEXT NOT NULL DEFAULT 'openai' CHECK(protocol IN ('openai', 'anthropic', 'gemini', 'codex')),
    base_url TEXT NOT NULL DEFAULT '',
    api_key TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    temperature REAL NOT NULL DEFAULT 0.7,
    max_tokens INTEGER NOT NULL DEFAULT 120000,
    timeout_seconds INTEGER NOT NULL DEFAULT 300,
    extra_headers TEXT NOT NULL DEFAULT '{}',
    extra_query TEXT NOT NULL DEFAULT '{}',
    extra_body TEXT NOT NULL DEFAULT '{}',
    notes TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    use_legacy_chat_completions INTEGER NOT NULL DEFAULT 0
);

INSERT OR REPLACE INTO llm_profiles_new (
    id, name, preset_key, protocol, base_url, api_key, model, temperature,
    max_tokens, timeout_seconds, extra_headers, extra_query, extra_body,
    notes, sort_order, created_at, updated_at, use_legacy_chat_completions
)
SELECT
    id, name, preset_key, protocol, base_url, api_key, model, temperature,
    max_tokens, timeout_seconds, extra_headers, extra_query, extra_body,
    notes, sort_order, created_at, updated_at,
    COALESCE(use_legacy_chat_completions, 0)
FROM llm_profiles;

DROP TABLE llm_profiles;
ALTER TABLE llm_profiles_new RENAME TO llm_profiles;

CREATE INDEX IF NOT EXISTS idx_llm_profiles_sort ON llm_profiles(sort_order);

PRAGMA foreign_keys=ON;
