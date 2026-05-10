from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Any, List
from pydantic import field_validator

_BASE_DIR = Path(__file__).resolve().parents[1]
_ENV_FILE = _BASE_DIR / ".env"
_ROOT_BACKEND_ENV_FILE = _BASE_DIR.parents[1] / "backend" / ".env"


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "NOVA AI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Email OTP
    AUTH_OTP_EXPIRE_MINUTES: int = 5
    AUTH_OTP_LENGTH: int = 6
    EMAIL_PROVIDER: str = ""
    EMAIL_FROM: str = ""
    EMAIL_FROM_ADDRESS: str = ""
    EMAIL_FROM_NAME: str = "NOVA AI"
    EMAIL_REPLY_TO: str = ""
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASS: str = ""
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    SMTP_USE_SSL: bool = False
    SMTP_TIMEOUT_SECONDS: int = 20

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_CHAT_MODEL: str = "gpt-4-turbo-preview"
    OPENAI_CODE_MODEL: str = "gpt-4-turbo-preview"
    OPENAI_EXPLAIN_MODEL: str = "gpt-4-turbo-preview"
    OPENAI_IMAGE_MODEL: str = "dall-e-3"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-ada-002"
    OPENAI_EMBEDDING_DIM: int = 1536

    # Other AI Providers
    ANTHROPIC_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""
    PERPLEXITY_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    GROQ_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_NUM_PREDICT: int = 512
    OLLAMA_NUM_CTX: int = 2048
    AI_PROVIDER: str = "openai"
    AI_MODEL: str = "gpt-4"

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000"

    # File Upload
    MAX_FILE_SIZE_MB: int = 10
    UPLOAD_DIR: str = "./uploads"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # Vector Database
    VECTOR_DB_TYPE: str = "faiss"
    PINECONE_API_KEY: str = ""
    PINECONE_ENVIRONMENT: str = ""

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @field_validator("DEBUG", mode="before")
    @classmethod
    def _parse_debug(cls, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return True
        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "yes", "y", "on", "debug", "development"}:
            return True
        if normalized in {"0", "false", "no", "n", "off", "release", "prod", "production", "warn", "warning"}:
            return False
        return bool(value)

    class Config:
        env_file = (str(_ROOT_BACKEND_ENV_FILE), str(_ENV_FILE))
        case_sensitive = True
        extra = "ignore"


settings = Settings()
