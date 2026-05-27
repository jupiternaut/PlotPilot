ALTER TABLE llm_profiles RENAME TO llm_profiles_old;

CREATE TABLE llm_profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    preset_key TEXT NOT NULL DEFAULT 'custom-openai-compatible',
    protocol TEXT NOT NULL DEFAULT 'openai' CHECK(protocol IN ('openai', 'anthropic', 'gemini', 'vertex-ai', 'codex')),
    base_url TEXT NOT NULL DEFAULT '',
    api_key TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    temperature REAL NOT NULL DEFAULT 0.7,
    max_tokens INTEGER NOT NULL DEFAULT 4096,
    timeout_seconds INTEGER NOT NULL DEFAULT 300,
    extra_headers TEXT NOT NULL DEFAULT '{}',
    extra_query TEXT NOT NULL DEFAULT '{}',
    extra_body TEXT NOT NULL DEFAULT '{}',
    notes TEXT NOT NULL DEFAULT '',
    use_legacy_chat_completions INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO llm_profiles SELECT * FROM llm_profiles_old;
DROP TABLE llm_profiles_old;
