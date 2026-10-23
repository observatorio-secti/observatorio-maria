from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from observatorio_maria.settings import Settings


class ModelConfigurationError(Exception):
    """Não foi possível instanciar os modelos configurados."""


class ModelTier(StrEnum):
    FAST = 'fast'
    MEDIUM = 'medium'
    ADVANCED = 'advanced'


@dataclass(frozen=True)
class RegisteredModel:
    tier: ModelTier
    name: str
    model: BaseChatModel


class ModelRegistry:
    """Catálogo dos modelos disponíveis, um por nível.

    O restante da aplicação depende apenas desta classe e da interface
    BaseChatModel do LangChain, nunca de um provedor específico.
    """

    def __init__(self, models: list[RegisteredModel]):
        self._models = {registered.tier: registered for registered in models}
        missing = set(ModelTier) - self._models.keys()
        if missing:
            raise ValueError(f'Níveis sem modelo configurado: {missing}')

    def get(self, tier: ModelTier) -> RegisteredModel:
        return self._models[tier]

    def all(self) -> list[RegisteredModel]:
        return [self._models[tier] for tier in ModelTier]


def build_model_registry(settings: Settings) -> ModelRegistry:
    configs = {
        ModelTier.FAST: (
            settings.LLM_FAST_MODEL,
            settings.LLM_FAST_MODEL_KWARGS,
        ),
        ModelTier.MEDIUM: (
            settings.LLM_MEDIUM_MODEL,
            settings.LLM_MEDIUM_MODEL_KWARGS,
        ),
        ModelTier.ADVANCED: (
            settings.LLM_ADVANCED_MODEL,
            settings.LLM_ADVANCED_MODEL_KWARGS,
        ),
    }
    return ModelRegistry([
        RegisteredModel(
            tier=tier,
            name=name,
            model=init_chat_model(name, **kwargs),
        )
        for tier, (name, kwargs) in configs.items()
    ])


@lru_cache
def get_model_registry() -> ModelRegistry:
    # Construído sob demanda e uma única vez; nos testes é substituído via
    # app.dependency_overrides, sem instanciar provedores reais.
    try:
        return build_model_registry(Settings())
    except Exception as exc:
        # Ex.: credencial ausente ou provedor não instalado. Exceções não
        # entram no lru_cache, então a próxima requisição tenta de novo.
        raise ModelConfigurationError(str(exc)) from exc
