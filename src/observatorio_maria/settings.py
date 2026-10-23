from typing import Any

from pydantic import Field
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

    # Consultas a fontes do catálogo e orçamento do agente.
    QUERY_MAX_ROWS: int = Field(100, ge=1)
    QUERY_TIMEOUT_SECONDS: float = Field(15.0, gt=0)
    QUERY_MAX_PER_CALL: int = Field(4, ge=1)
    MARIA_AGENT_MAX_MODEL_CALLS: int = Field(3, ge=1)

    # Modelos por nível no formato "provedor:modelo" (init_chat_model).
    # Os *_KWARGS são repassados ao construtor do modelo (JSON no .env).
    LLM_FAST_MODEL: str = DEFAULT_MODEL
    LLM_FAST_MODEL_KWARGS: dict[str, Any] = DEFAULT_MODEL_KWARGS
    LLM_MEDIUM_MODEL: str = DEFAULT_MODEL
    LLM_MEDIUM_MODEL_KWARGS: dict[str, Any] = DEFAULT_MODEL_KWARGS
    LLM_ADVANCED_MODEL: str = DEFAULT_MODEL
    LLM_ADVANCED_MODEL_KWARGS: dict[str, Any] = DEFAULT_MODEL_KWARGS
