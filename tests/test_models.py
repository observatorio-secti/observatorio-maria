from http import HTTPStatus

import pytest

from observatorio_maria.app import app
from observatorio_maria.llm import registry as registry_module
from observatorio_maria.llm.registry import (
    ModelRegistry,
    ModelTier,
    build_model_registry,
    get_model_registry,
)
from observatorio_maria.settings import Settings


async def test_list_models(client):
    response = await client.get('/models')

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        'models': [
            {'tier': 'fast', 'model_name': 'fake:fast'},
            {'tier': 'medium', 'model_name': 'fake:medium'},
            {'tier': 'advanced', 'model_name': 'fake:advanced'},
        ]
    }


def test_build_model_registry_uses_settings(monkeypatch):
    calls = []

    def fake_init_chat_model(model, **kwargs):
        calls.append((model, kwargs))
        return object()

    monkeypatch.setattr(
        registry_module, 'init_chat_model', fake_init_chat_model
    )
    settings = Settings(
        _env_file=None,
        LLM_ADVANCED_MODEL='anthropic:outro-modelo',
        LLM_ADVANCED_MODEL_KWARGS={'temperature': 0},
    )

    registry = build_model_registry(settings)

    assert registry.get(ModelTier.FAST).name == 'openai:gpt-6-luna'
    assert registry.get(ModelTier.ADVANCED).name == 'anthropic:outro-modelo'
    assert calls == [
        ('openai:gpt-6-luna', {'reasoning_effort': 'low'}),
        ('openai:gpt-6-luna', {'reasoning_effort': 'low'}),
        ('anthropic:outro-modelo', {'temperature': 0}),
    ]


def test_registry_requires_all_tiers():
    with pytest.raises(ValueError, match='Níveis sem modelo'):
        ModelRegistry([])


async def test_misconfigured_models_return_503(client, monkeypatch):
    def broken_build(settings):
        raise RuntimeError('OPENAI_API_KEY ausente')

    monkeypatch.setattr(registry_module, 'build_model_registry', broken_build)
    registry_module.get_model_registry.cache_clear()
    app.dependency_overrides.pop(get_model_registry)

    response = await client.get('/models')

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert 'OPENAI_API_KEY ausente' in response.json()['detail']
