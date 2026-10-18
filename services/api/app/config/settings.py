import os
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # App Config
    APP_NAME: str = "ZeroDay PS2"
    DEBUG: bool = True

    # Privacy & Local Constraints
    BIND_ADDRESS: str = "127.0.0.1"
    BIND_PORT: int = 8000

    # Ollama Config
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "gemma3:1b")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    LLM_TEMPERATURE: float = 0.0
    LLM_SEED: int = 42
    LLM_CONTEXT_WINDOW: int = 2048

    
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 100
    RETRIEVAL_K: int = 5

    model_config = {
        "extra": "ignore",
        "env_file": ".env"
    }


settings = Settings()
