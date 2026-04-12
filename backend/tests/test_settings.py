from config.settings import Settings


def test_openai_model_alias_populates_default_openai_variants() -> None:
    settings = Settings(OPENAI_MODEL="gpt-4.1")

    assert settings.OPENAI_CHAT_MODEL == "gpt-4.1"
    assert settings.OPENAI_CODE_MODEL == "gpt-4.1"
    assert settings.OPENAI_EXPLAIN_MODEL == "gpt-4.1"
    assert settings.OPENAI_FAST_MODEL == "gpt-4o-mini"


def test_openai_model_alias_preserves_explicit_specific_model() -> None:
    settings = Settings(
        OPENAI_MODEL="gpt-4.1",
        OPENAI_CODE_MODEL="gpt-4.1-coder",
    )

    assert settings.OPENAI_CHAT_MODEL == "gpt-4.1"
    assert settings.OPENAI_CODE_MODEL == "gpt-4.1-coder"
    assert settings.OPENAI_EXPLAIN_MODEL == "gpt-4.1"


def test_openrouter_referer_prefers_frontend_url_and_normalizes_slash() -> None:
    settings = Settings(FRONTEND_URL="https://app.nova.example/")

    assert settings.openrouter_referer == "https://app.nova.example"
    assert settings.openrouter_app_name == "NOVA AI"


def test_openrouter_referer_falls_back_to_first_non_local_cors_origin() -> None:
    settings = Settings(
        CORS_ORIGINS="http://localhost:3000,https://nova-ai.vercel.app,https://app.nova.example"
    )

    assert settings.openrouter_referer == "https://nova-ai.vercel.app"
