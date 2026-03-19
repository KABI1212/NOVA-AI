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

    DATABASE_URL: str = "sqlite:///./data/nova_ai.db"

    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    OPENAI_API_KEY: str = ""
    OPENAI_CHAT_MODEL: str = "gpt-4-turbo-preview"
    OPENAI_CODE_MODEL: str = "gpt-4-turbo-preview"
    OPENAI_EXPLAIN_MODEL: str = "gpt-4-turbo-preview"
    OPENAI_IMAGE_MODEL: str = "dall-e-3"
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

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_NUM_PREDICT: int = 512
    OLLAMA_NUM_CTX: int = 2048

    AI_PROVIDER: str = "openai"
    AI_MODEL: str = "gpt-4"
    AI_TEMPERATURE: float = 0.3
    AI_MAX_TOKENS: int = 2048
    AI_REQUEST_TIMEOUT_SECONDS: int = 60
    AI_DEBUG_LOGGING: bool = True
    AI_LOG_PREVIEW_CHARS: int = 400

    CORS_ORIGINS: str = (
        "http://localhost:3000,"
        "http://127.0.0.1:3000,"
        "http://localhost:5173,"
        "http://127.0.0.1:5173"
    )
    MAX_FILE_SIZE_MB: int = 10
    UPLOAD_DIR: str = "./uploads"
    REDIS_URL: str = "redis://localhost:6379"

    VECTOR_DB_TYPE: str = "faiss"
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

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        case_sensitive=True,
    )


settings = Settings()
