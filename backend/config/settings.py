import os
from pathlib import Path
from typing import Any, List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BASE_DIR = Path(__file__).resolve().parents[1]
_ENV_FILE = _BASE_DIR / ".env"


class Settings(BaseSettings):
    APP_NAME: str = "NOVA AI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = int(os.getenv("PORT", "8000"))
    UVICORN_ACCESS_LOG: bool = False

    DATABASE_URL: str = "mongodb://localhost:27017/nova_ai"
    MONGODB_DB_NAME: str = ""
    MONGODB_SERVER_SELECTION_TIMEOUT_MS: int = 5000
    MONGODB_CONNECT_TIMEOUT_MS: int = 5000
    MONGODB_SOCKET_TIMEOUT_MS: int = 10000
    MONGODB_RETRY_ATTEMPTS: int = 3
    MONGODB_RETRY_DELAY_SECONDS: float = 2.0
    MONGODB_RETRY_BACKOFF_MULTIPLIER: float = 2.0
    MONGODB_RETRY_MAX_DELAY_SECONDS: float = 15.0
    MONGODB_REQUIRED: bool = False

    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    AUTH_OTP_EXPIRE_MINUTES: int = 5
    AUTH_OTP_LENGTH: int = 6

    EMAIL_PROVIDER: str = ""
    EMAIL_FROM_ADDRESS: str = ""
    EMAIL_FROM_NAME: str = "NOVA AI"
    EMAIL_REPLY_TO: str = ""
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    SMTP_USE_SSL: bool = False
    SMTP_TIMEOUT_SECONDS: int = 20
    SENDGRID_API_KEY: str = ""

    OPENAI_API_KEY: str = ""
    OPENAI_CHAT_MODEL: str = "gpt-4o"
    OPENAI_FAST_MODEL: str = "gpt-4o-mini"
    OPENAI_CODE_MODEL: str = "gpt-4o"
    OPENAI_EXPLAIN_MODEL: str = "gpt-4o"
    GEMINI_CHAT_MODEL: str = "gemini-2.5-flash"
    OPENAI_IMAGE_MODEL: str = "dall-e-3"
    OPENAI_IMAGE_QUALITY: str = "hd"
    GEMINI_IMAGE_MODEL: str = "gemini-2.5-flash-image"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-ada-002"
    OPENAI_EMBEDDING_DIM: int = 1536

    ANTHROPIC_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""
    PERPLEXITY_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    TOGETHER_API_KEY: str = ""

    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_IMAGE_MODEL: str = "sourceful/riverflow-v2-fast-preview"

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_NUM_PREDICT: int = 512
    OLLAMA_NUM_CTX: int = 2048

    AI_PROVIDER: str = ""
    AI_IMAGE_PROVIDER: str = ""
    IMAGE_PROMPT_ENHANCER_PROVIDER: str = ""
    AI_MODEL: str = ""
    AI_TEMPERATURE: float = 0.3
    AI_MAX_TOKENS: int = 2048
    AI_FAST_MAX_TOKENS: int = 320
    AI_REQUEST_TIMEOUT_SECONDS: int = 60
    AI_IMAGE_REQUEST_TIMEOUT_SECONDS: int = 180
    AI_DEBUG_LOGGING: bool = False
    AI_LOG_PREVIEW_CHARS: int = 400

    CORS_ORIGINS: str = (
        "http://localhost,"
        "http://127.0.0.1,"
        "http://localhost:3000,"
        "http://127.0.0.1:3000,"
        "http://localhost:5173,"
        "http://127.0.0.1:5173"
    )
    CORS_ORIGIN_REGEX: str = r"^https://([A-Za-z0-9-]+\.)*(vercel\.app|onrender\.com)$"
    MAX_FILE_SIZE_MB: int = 10
    UPLOAD_DIR: str = "./uploads"
    REDIS_URL: str = "redis://localhost:6379"
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_WARN_ON_MEMORY_FALLBACK: bool = False
    CHAT_RATE_LIMIT_REQUESTS: int = 20
    CHAT_RATE_LIMIT_WINDOW_SECONDS: int = 60
    IMAGE_RATE_LIMIT_REQUESTS: int = 10
    IMAGE_RATE_LIMIT_WINDOW_SECONDS: int = 3600
    CONVERSATION_SUMMARY_MIN_MESSAGES: int = 8
    CONVERSATION_SUMMARY_REFRESH_INTERVAL: int = 4
    CONVERSATION_SUMMARY_RECENT_MESSAGES: int = 18
    SUPPRESS_32BIT_CRYPTO_WARNING: bool = True

    VECTOR_DB_TYPE: str = "lexical"
    PINECONE_API_KEY: str = ""
    PINECONE_ENVIRONMENT: str = ""

    @field_validator("DEBUG", mode="before")
    @classmethod
    def _parse_debug(cls, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return True
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "y", "on", "debug", "development"}:
                return True
            if normalized in {"0", "false", "no", "n", "off", "release", "prod", "production"}:
                return False
        return bool(value)

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def cors_origin_regex_value(self) -> str | None:
        value = str(getattr(self, "CORS_ORIGIN_REGEX", "") or "").strip()
        return value or None

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        case_sensitive=True,
    )


settings = Settings()
