from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_MODEL = 'openai:gpt-6-luna'
DEFAULT_MODEL_KWARGS = {'reasoning_effort': 'low'}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )

    DATABASE_URL: str = 'sqlite+aiosqlite:///./observatorio.db'
    ENVIRONMENT: str = 'development'
    DEMO_ENABLED: bool = True
    # Intervalo da verificação de defasagem do catálogo; 0 desliga.
    CATALOG_CHECK_INTERVAL_SECONDS: float = 3600

    # Modelos por nível no formato "provedor:modelo" (init_chat_model).
    # Os *_KWARGS são repassados ao construtor do modelo (JSON no .env).
    LLM_FAST_MODEL: str = DEFAULT_MODEL
    LLM_FAST_MODEL_KWARGS: dict[str, Any] = DEFAULT_MODEL_KWARGS
    LLM_MEDIUM_MODEL: str = DEFAULT_MODEL
    LLM_MEDIUM_MODEL_KWARGS: dict[str, Any] = DEFAULT_MODEL_KWARGS
    LLM_ADVANCED_MODEL: str = DEFAULT_MODEL
    LLM_ADVANCED_MODEL_KWARGS: dict[str, Any] = DEFAULT_MODEL_KWARGS
