import os
from pathlib import Path
from typing import Any, List

from pydantic import field_validator, model_validator
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
    FRONTEND_URL: str = ""

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
    AUTH_OTP_MAX_ATTEMPTS: int = 3
    AUTH_OTP_LOCK_MINUTES: int = 15
    AUTH_OTP_RESEND_COOLDOWN_SECONDS: int = 60
    AUTH_OTP_MAX_RESEND_ATTEMPTS: int = 3
    AUTH_ALLOW_PASSWORD_ONLY_FALLBACK: bool = False
    AUTH_EXPOSE_DEBUG_OTP: bool = False

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
    SMTP_TIMEOUT_SECONDS: int = 10
    SENDGRID_API_KEY: str = ""

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = ""
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
    KIE_API_KEY: str = ""
    TOGETHER_API_KEY: str = ""

    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_SITE: str = ""
    OPENROUTER_APP: str = ""
    OPENROUTER_IMAGE_MODEL: str = "sourceful/riverflow-v2-fast-preview"
    KIE_BASE_URL: str = "https://api.kie.ai"
    KIE_IMAGE_POLL_INTERVAL_SECONDS: float = 5.0
    KIE_IMAGE_TIMEOUT_SECONDS: int = 300
    ANTHROPIC_MODEL: str = ""
    GROQ_MODEL: str = ""

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_NUM_PREDICT: int = 512
    OLLAMA_NUM_CTX: int = 2048

    AI_PROVIDER: str = ""
    AI_IMAGE_PROVIDER: str = ""
    IMAGE_PROMPT_ENHANCER_PROVIDER: str = ""
    AI_MODEL: str = ""
    AI_TEMPERATURE: float = 0.3
    AI_TOP_P: float = 0.95
    AI_MAX_TOKENS: int = 8192
    AI_FAST_MAX_TOKENS: int = 640
    AI_REQUEST_TIMEOUT_SECONDS: int = 180
    AI_STREAM_HEARTBEAT_SECONDS: int = 15
    AI_STREAM_RETRY_ATTEMPTS: int = 3
    AI_STREAM_RETRY_BACKOFF_SECONDS: float = 1.0
    AI_STREAM_REPAIR_MAX_TOKENS: int = 4096
    AI_STREAM_REPAIR_ATTEMPTS: int = 3
    AI_IMAGE_REQUEST_TIMEOUT_SECONDS: int = 180
    AI_AUTO_MAX_PROVIDER_ATTEMPTS: int = 6
    AI_DEBUG_LOGGING: bool = False
    AI_LOG_PREVIEW_CHARS: int = 400
    CHAT_AUTO_WEB_SEARCH_IN_CHAT: bool = False
    CHAT_AUTO_WEB_FALLBACK_IN_CHAT: bool = False

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
    FILE_MAX_SIZE_MB: int = 25
    FILE_PREVIEW_CHAR_LIMIT: int = 1800
    FILE_CHUNK_SIZE: int = 1200
    FILE_CHUNK_OVERLAP: int = 180
    FILE_RETRIEVAL_LIMIT: int = 6
    FILE_SESSION_TTL_SECONDS: int = 86400
    FILE_QUEUE_NAME: str = "nova:file-processing"
    FILE_EMBED_CACHE_TTL_SECONDS: int = 604800
    FILE_CONTEXT_CHAR_LIMIT: int = 18000
    FILE_ALLOWED_EXTENSIONS: str = (
        ".pdf,.docx,.txt,.md,.csv,.xlsx,.xlsm,.xls,.pptx,.png,.jpg,.jpeg,.webp,.gif,.bmp,"
        ".py,.js,.jsx,.ts,.tsx,.json,.html,.htm,.css,.xml,.yml,.yaml,.java,.c,.cpp,.cs,.go,.rs,.php,.sql"
    )
    TESSERACT_CMD: str = ""
    MALWARE_SCAN_COMMAND: str = ""
    MALWARE_SCAN_TIMEOUT_SECONDS: int = 20
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

    @model_validator(mode="after")
    def _apply_legacy_model_aliases(self) -> "Settings":
        legacy_openai_model = str(self.OPENAI_MODEL or "").strip()
        explicitly_set = set(self.model_fields_set)

        if legacy_openai_model:
            if "OPENAI_CHAT_MODEL" not in explicitly_set:
                self.OPENAI_CHAT_MODEL = legacy_openai_model
            if "OPENAI_CODE_MODEL" not in explicitly_set:
                self.OPENAI_CODE_MODEL = legacy_openai_model
            if "OPENAI_EXPLAIN_MODEL" not in explicitly_set:
                self.OPENAI_EXPLAIN_MODEL = legacy_openai_model

        return self

    @staticmethod
    def _normalize_public_url(value: Any) -> str | None:
        candidate = str(value or "").strip().rstrip("/")
        if candidate.startswith("http://") or candidate.startswith("https://"):
            return candidate
        return None

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def cors_origin_regex_value(self) -> str | None:
        value = str(getattr(self, "CORS_ORIGIN_REGEX", "") or "").strip()
        return value or None

    @property
    def file_allowed_extensions_list(self) -> List[str]:
        values = []
        for raw_value in str(self.FILE_ALLOWED_EXTENSIONS or "").split(","):
            candidate = raw_value.strip().lower()
            if not candidate:
                continue
            if not candidate.startswith("."):
                candidate = f".{candidate}"
            values.append(candidate)
        return values

    @property
    def public_frontend_url(self) -> str | None:
        for candidate in (self.OPENROUTER_SITE, self.FRONTEND_URL):
            normalized = self._normalize_public_url(candidate)
            if normalized:
                return normalized

        local_candidate = None
        for candidate in self.cors_origins_list:
            normalized = self._normalize_public_url(candidate)
            if not normalized:
                continue
            if "localhost" in normalized or "127.0.0.1" in normalized:
                local_candidate = local_candidate or normalized
                continue
            return normalized

        return local_candidate

    @property
    def openrouter_referer(self) -> str:
        return self.public_frontend_url or "http://localhost:3000"

    @property
    def openrouter_app_name(self) -> str:
        return str(self.OPENROUTER_APP or "").strip() or self.APP_NAME

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
