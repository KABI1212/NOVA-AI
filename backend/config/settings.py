from pydantic_settings import BaseSettings
from pathlib import Path
from typing import List

_BASE_DIR = Path(__file__).resolve().parents[1]
_ENV_FILE = _BASE_DIR / ".env"


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

    class Config:
        env_file = str(_ENV_FILE)
        case_sensitive = True


settings = Settings()


