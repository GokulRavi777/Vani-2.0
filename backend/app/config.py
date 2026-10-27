from typing import List, Optional, Union
import json
from pydantic import field_validator
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
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173"
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                return json.loads(v)
            return [x.strip() for x in v.split(",") if x.strip()]
        return v
    
    # Optional LLM integration
    OPENAI_API_KEY: Optional[str] = None
    LLM_MODEL: str = "gpt-4o-mini"
    
    # STT Provider configuration
    DEFAULT_STT_MODE: str = "sarvam"
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None
    SARVAM_API_KEY: Optional[str] = None

    # Gnani AI Configuration
    GNANI_API_KEY: Optional[str] = None
    GNANI_TTS_ENDPOINT: str = "https://api.vachana.ai/api/v1/tts/inference"
    GNANI_TTS_MODEL: str = "timbre-v2.5"
    GNANI_VOICE_CLONE_MODEL: str = "vachana-vc-v1"
    GNANI_VOICE_CLONE_EMBEDDINGS_ENDPOINT: str = "https://api.vachana.ai/api/v1/tts/voice-clone/embeddings"
    GNANI_DEFAULT_VOICE: str = "Pranav"
    GNANI_DEFAULT_LANGUAGE: str = "en-IN"

    # Gnani Realtime STT & Voice Activity Detection (VAD) Tuning Parameters
    GNANI_STT_WS_ENDPOINT: str = "wss://api.vachana.ai/stt/v3/stream"
    GNANI_VAD_THRESHOLD: float = 0.55   # 0.0 - 1.0 (Optimal: 0.55 for web mic)
    GNANI_MIN_SILENCE_MS: int = 700     # 100 - 2000 ms (Optimal: 700ms for technical interview turns)
    GNANI_MIN_SPEECH_MS: int = 120      # 50 - 2000 ms (Optimal: 120ms noise gate against breath/clicks)
    GNANI_MIN_SEGMENT_MS: int = 120     # 100 - 1000 ms (Optimal: 120ms segment floor)
    GNANI_MAX_SPEECH_S: float = 20.0    # 5.0 - 120.0 s (Optimal: 20s monologue cap)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
