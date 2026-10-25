from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ENVIRONMENT: str = "development"
    
    # Supported skills for Vani 2.0 POC
    SUPPORTED_SKILLS: List[str] = [
        "Python",
        "SQL",
        "Java",
        "Machine Learning"
    ]
    
    DEFAULT_LANGUAGE: str = "en-IN"
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173"
    ]
    
    # Optional LLM integration
    OPENAI_API_KEY: Optional[str] = None
    LLM_MODEL: str = "gpt-4o-mini"
    
    # STT Provider neutral configuration (for Stages 2-4)
    DEFAULT_STT_MODE: str = "google"
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None
    SARVAM_API_KEY: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
