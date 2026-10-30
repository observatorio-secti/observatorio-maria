import json
import os
import sqlite3
from itertools import repeat

import pytest
from httpx import ASGITransport, AsyncClient
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import (
    GenericFakeChatModel,
)
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    ToolCallChunk,
)
from langchain_core.outputs import (
    ChatGeneration,
    ChatGenerationChunk,
    ChatResult,
)
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
    configure_sqlite,
    get_session,
)
from observatorio_maria.llm.registry import (
    ModelRegistry,
    ModelTier,
    RegisteredModel,
    get_model_registry,
)
from observatorio_maria.models import CatalogDataSource, table_registry
from observatorio_maria.observability.genai import (
    AgentMetrics,
    GenAIMetricsHandler,
    get_agent_metrics,
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


class ScriptedToolChatModel(BaseChatModel):
    """Fake que aceita bind_tools e devolve tool_calls roteirizados."""

    responses: list[AIMessage]
    bound_tools: list = []
    bind_count: int = 0
    recorded_calls: list[list[BaseMessage]] = []

    @property
    def _llm_type(self) -> str:
        return 'scripted-fake'

    def bind_tools(self, tools, **kwargs):
        self.bound_tools = list(tools)
        self.bind_count += 1
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.recorded_calls.append(list(messages))
        msg = self.responses.pop(0) if self.responses else AIMessage('Fim')
        return ChatResult(generations=[ChatGeneration(message=msg)])

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        self.recorded_calls.append(list(messages))
        msg = self.responses.pop(0) if self.responses else AIMessage('Fim')
        if msg.tool_calls:
            tc_chunks = [
                ToolCallChunk(
                    name=tc['name'],
                    args=(
                        json.dumps(tc['args'])
                        if isinstance(tc['args'], dict)
                        else tc['args']
                    ),
                    id=tc.get('id', f'call_{i}'),
                    index=i,
                )
                for i, tc in enumerate(msg.tool_calls)
            ]
            yield ChatGenerationChunk(
                message=AIMessageChunk(
                    content=msg.content or '',
                    tool_call_chunks=tc_chunks,
                )
            )
        else:
            for char in msg.content or ['']:
                yield ChatGenerationChunk(message=AIMessageChunk(content=char))


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
    configure_sqlite(engine)
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
    meter = MeterProvider(metric_readers=[reader]).get_meter('test')
    handler = GenAIMetricsHandler(meter)
    agent_metrics = AgentMetrics(meter)
    app.dependency_overrides[get_llm_callbacks] = lambda: [handler]
    app.dependency_overrides[get_agent_metrics] = lambda: agent_metrics
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


# --- Catálogo: banco de origem SQLite em arquivo -----------------------------

SOURCE_DDL = """
CREATE TABLE instituicoes (
    id INTEGER PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,
    sigla VARCHAR(32)
);
CREATE TABLE pesquisadores (
    id INTEGER PRIMARY KEY,
    nome VARCHAR(255),
    lattes VARCHAR(255)
);
CREATE TABLE bolsas (
    id INTEGER PRIMARY KEY,
    status VARCHAR(20) NOT NULL,
    pesquisador_id INTEGER NOT NULL REFERENCES pesquisadores (id),
    instituicao_id INTEGER NOT NULL REFERENCES instituicoes (id)
);
CREATE VIEW bolsas_por_status AS
    SELECT status, COUNT(*) AS quantidade FROM bolsas GROUP BY status;
"""


@pytest.fixture
def source_db(tmp_path, monkeypatch):
    """Banco de origem em arquivo e a URL dele em SOURCE_DATABASE_URL."""
    path = tmp_path / 'origem.db'
    with sqlite3.connect(path) as conn:
        conn.executescript(SOURCE_DDL)
    monkeypatch.setenv('SOURCE_DATABASE_URL', f'sqlite+aiosqlite:///{path}')
    return path


@pytest.fixture
async def datasource(session):
    datasource = CatalogDataSource(
        id='origem',
        name='Origem de teste',
        connection_env='SOURCE_DATABASE_URL',
        schemas=['main'],
    )
    session.add(datasource)
    await session.commit()
    return datasource
