"""
BIS SmartAI — Application Configuration
Reads all configuration from environment variables via Pydantic Settings.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    # Application
    app_name: str = "BIS SmartAI"
    app_env: str = "development"
    debug: bool = True

    # Database — REQUIRED
    database_url: str

    # Groq AI — Primary High-Speed Provider
    groq_api_key: str = ""

    # Gemini AI — Key Rotation Pool (Fallback)
    gemini_api_key: str = ""     # Primary key
    gemini_api_key_2: str = ""   # Secondary key
    gemini_api_key_3: str = ""   # Tertiary key

    @property
    def gemini_api_keys(self) -> list[str]:
        """Returns all configured, non-empty Gemini API keys."""
        return [k for k in [
            self.gemini_api_key,
            self.gemini_api_key_2,
            self.gemini_api_key_3,
        ] if k and len(k) > 10]

    # JWT
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24 hours

    # RAG Settings
    rag_enabled: bool = True
    rag_top_k: int = 5
    embedding_model: str = "models/gemini-embedding-001"

    # CORS
    frontend_url: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def is_groq_configured(self) -> bool:
        """True if Groq API key is configured."""
        return bool(self.groq_api_key and len(self.groq_api_key) > 10)

    @property
    def is_gemini_configured(self) -> bool:
        """True if at least one Gemini API key is configured."""
        return len(self.gemini_api_keys) > 0

    @property
    def is_ai_configured(self) -> bool:
        """True if either Groq or Gemini is configured."""
        return self.is_groq_configured or self.is_gemini_configured

    @property
    def is_db_configured(self) -> bool:
        return bool(self.database_url)


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
