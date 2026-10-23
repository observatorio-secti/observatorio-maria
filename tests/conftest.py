import os
from itertools import repeat

import pytest
from httpx import ASGITransport, AsyncClient
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import (
    GenericFakeChatModel,
)
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGenerationChunk
from openinference.instrumentation import OITracer, TraceConfig
from openinference.instrumentation.langchain import LangChainInstrumentor
from openinference.semconv.trace import SpanAttributes
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
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
from observatorio_maria.observability.genai import (
    GenAIMetricsHandler,
    get_llm_callbacks,
    get_tracer,
)


class RecordingHandler(BaseCallbackHandler):
    """Guarda as mensagens que cada chamada enviou ao modelo."""

    def __init__(self):
        self.calls = []

    def on_chat_model_start(self, serialized, messages, **kwargs):
        self.calls.extend(messages)


class UsageReportingFakeChatModel(GenericFakeChatModel):
    """Fake que, como a OpenAI com `stream_usage`, informa o uso de tokens
    num último chunk vazio do stream."""

    usage: dict

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        yield from super()._stream(messages, stop, run_manager, **kwargs)
        yield ChatGenerationChunk(
            message=AIMessageChunk(content='', usage_metadata=self.usage)
        )


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


# --- Observabilidade em memória --------------------------------------------


@pytest.fixture
def hidden_content(monkeypatch):
    # Definido antes de `spans`: a configuração é lida ao instrumentar.
    monkeypatch.setenv('OPENINFERENCE_HIDE_INPUTS', 'true')
    monkeypatch.setenv('OPENINFERENCE_HIDE_OUTPUTS', 'true')


@pytest.fixture
def spans(monkeypatch):
    """Instrumenta o LangChain e o ChatService com exportador em memória."""
    monkeypatch.setenv('OTEL_SDK_DISABLED', 'false')
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    instrumentor = LangChainInstrumentor()
    instrumentor.instrument(tracer_provider=provider)
    app.dependency_overrides[get_tracer] = lambda: OITracer(
        provider.get_tracer('test'), config=TraceConfig()
    )
    yield exporter
    instrumentor.uninstrument()


@pytest.fixture
def metric_reader(monkeypatch):
    monkeypatch.setenv('OTEL_SDK_DISABLED', 'false')
    reader = InMemoryMetricReader()
    handler = GenAIMetricsHandler(
        MeterProvider(metric_readers=[reader]).get_meter('test')
    )
    app.dependency_overrides[get_llm_callbacks] = lambda: [handler]
    return reader


def finished(exporter, name):
    return [s for s in exporter.get_finished_spans() if s.name == name]


def chat_and_llm_spans(exporter):
    (chat,) = finished(exporter, 'maria.chat')
    llm = [
        s
        for s in exporter.get_finished_spans()
        if s.attributes.get(SpanAttributes.OPENINFERENCE_SPAN_KIND) == 'LLM'
    ]
    return chat, llm


def metric_points(reader, name):
    data = reader.get_metrics_data()
    return [
        point
        for resource in data.resource_metrics
        for scope in resource.scope_metrics
        for metric in scope.metrics
        if metric.name == name
        for point in metric.data.data_points
    ]
