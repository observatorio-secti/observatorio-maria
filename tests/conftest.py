import os
from itertools import repeat

import pytest
from httpx import ASGITransport, AsyncClient
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import (
    GenericFakeChatModel,
)
from langchain_core.messages import AIMessage
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

# A suíte padrão roda sem telemetria; os testes de observabilidade religam o
# SDK com exportadores em memória (ver test_observability.py).
os.environ['OTEL_SDK_DISABLED'] = 'true'

from observatorio_maria.app import app  # noqa: E402
from observatorio_maria.database import (
    SessionLocal,
    enable_sqlite_foreign_keys,
    get_session,
)
from observatorio_maria.llm.registry import (
    ModelRegistry,
    ModelTier,
    RegisteredModel,
    get_model_registry,
)
from observatorio_maria.models import table_registry


class RecordingHandler(BaseCallbackHandler):
    """Guarda as mensagens que cada chamada enviou ao modelo."""

    def __init__(self):
        self.calls = []

    def on_chat_model_start(self, serialized, messages, **kwargs):
        self.calls.extend(messages)


class FailingChatModel(BaseChatModel):
    """Simula um provedor indisponível."""

    @property
    def _llm_type(self):
        return 'failing-fake'

    def _generate(  # noqa: PLR6301
        self, messages, stop=None, run_manager=None, **kwargs
    ):
        raise RuntimeError('provedor indisponível')


def fake_model(tier: ModelTier, handler: RecordingHandler):
    return GenericFakeChatModel(
        messages=repeat(AIMessage(f'Resposta do modelo {tier}')),
        callbacks=[handler],
    )


@pytest.fixture
async def engine():
    engine = create_async_engine(
        'sqlite+aiosqlite:///:memory:', poolclass=StaticPool
    )
    enable_sqlite_foreign_keys(engine)
    async with engine.begin() as conn:
        await conn.run_sync(table_registry.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(engine):
    async with SessionLocal(bind=engine) as session:
        yield session


@pytest.fixture
def model_handler():
    return RecordingHandler()


@pytest.fixture
def model_registry(model_handler):
    return ModelRegistry([
        RegisteredModel(
            tier=tier,
            name=f'fake:{tier}',
            model=fake_model(tier, model_handler),
        )
        for tier in ModelTier
    ])


@pytest.fixture
async def client(session, model_registry):
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_model_registry] = lambda: model_registry
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def conversation(client):
    response = await client.post('/conversations', json={'title': 'Bolsas'})
    return response.json()
