from pydantic_settings import BaseSettings
from pathlib import Path
from typing import List

_BASE_DIR = Path(__file__).resolve().parents[1]
_ENV_FILE = _BASE_DIR / ".env"

<<<<<<< HEAD
=======

>>>>>>> 3520f8c8a820e9822841d33c9bb59a09576e92cf
class Settings(BaseSettings):
    # Application
    APP_NAME: str = "NOVA AI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
<<<<<<< HEAD
    
    # Database
    DATABASE_URL: str
    
=======

    # Database
    DATABASE_URL: str

>>>>>>> 3520f8c8a820e9822841d33c9bb59a09576e92cf
    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
<<<<<<< HEAD
    
=======

>>>>>>> 3520f8c8a820e9822841d33c9bb59a09576e92cf
    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_CHAT_MODEL: str = "gpt-4-turbo-preview"
    OPENAI_CODE_MODEL: str = "gpt-4-turbo-preview"
    OPENAI_EXPLAIN_MODEL: str = "gpt-4-turbo-preview"
    OPENAI_IMAGE_MODEL: str = "dall-e-3"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-ada-002"
    OPENAI_EMBEDDING_DIM: int = 1536
<<<<<<< HEAD
    
=======

>>>>>>> 3520f8c8a820e9822841d33c9bb59a09576e92cf
    # Other AI Providers
    ANTHROPIC_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""
    PERPLEXITY_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    GROQ_API_KEY: str = ""
<<<<<<< HEAD
    OPENROUTER_API_KEY: str = ""  # NEW: OpenRouter Support
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"  # NEW
    
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
    
=======
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

>>>>>>> 3520f8c8a820e9822841d33c9bb59a09576e92cf
    # Vector Database
    VECTOR_DB_TYPE: str = "faiss"
    PINECONE_API_KEY: str = ""
    PINECONE_ENVIRONMENT: str = ""
<<<<<<< HEAD
    
    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
=======

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

>>>>>>> 3520f8c8a820e9822841d33c9bb59a09576e92cf
    class Config:
        env_file = str(_ENV_FILE)
        case_sensitive = True

<<<<<<< HEAD
settings = Settings()
=======

settings = Settings()


>>>>>>> 3520f8c8a820e9822841d33c9bb59a09576e92cf
