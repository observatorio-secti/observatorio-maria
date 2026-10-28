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
    # Máximo de valores distintos para uma coluna de texto ser categórica.
    CATALOG_OBSERVED_VALUES_MAX: int = Field(50, ge=1)

    # Consultas a fontes do catálogo e orçamento do agente.
    QUERY_MAX_ROWS: int = Field(100, ge=1)
    QUERY_TIMEOUT_SECONDS: float = Field(15.0, gt=0)
    QUERY_MAX_PER_CALL: int = Field(4, ge=1)
    QUERY_MAX_ESTIMATED_COST: float = Field(50_000.0, ge=0.0)
    MARIA_AGENT_MAX_MODEL_CALLS: int = Field(6, ge=1)

    # Perguntas por conversa; 0 desliga o limite.
    CONVERSATION_MAX_QUESTIONS: int = Field(10, ge=0)
    # Teto de tokens por conversa, opcional; 0 (padrão) desliga.
    CONVERSATION_TOKEN_CEILING: int = Field(0, ge=0)

    # Modelos por nível no formato "provedor:modelo" (init_chat_model).
    # Os *_KWARGS são repassados ao construtor do modelo (JSON no .env).
    LLM_FAST_MODEL: str = DEFAULT_MODEL
    LLM_FAST_MODEL_KWARGS: dict[str, Any] = DEFAULT_MODEL_KWARGS
    LLM_MEDIUM_MODEL: str = DEFAULT_MODEL
    LLM_MEDIUM_MODEL_KWARGS: dict[str, Any] = DEFAULT_MODEL_KWARGS
    LLM_ADVANCED_MODEL: str = DEFAULT_MODEL
    LLM_ADVANCED_MODEL_KWARGS: dict[str, Any] = DEFAULT_MODEL_KWARGS
