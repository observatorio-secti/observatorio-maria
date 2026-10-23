# A API de logs do OpenTelemetry para Python é experimental (`_logs`).
# ruff: noqa: PLC2701, PLR0913, PLR0917
import logging
import sqlite3
from itertools import repeat

from fastapi import FastAPI
from langchain_core.messages import AIMessage
from openinference.semconv.trace import SpanAttributes
from opentelemetry.sdk._logs import (
    LoggerProvider,
    LoggingHandler,
)
from opentelemetry.sdk._logs.export import (
    InMemoryLogRecordExporter,
    SimpleLogRecordProcessor,
)
from opentelemetry.trace import StatusCode

from observatorio_maria.app import app
from observatorio_maria.database import engine
from observatorio_maria.llm.registry import (
    ModelRegistry,
    ModelTier,
    RegisteredModel,
    get_model_registry,
)
from observatorio_maria.models import (
    CatalogColumn,
    CatalogDataSource,
    CatalogEntity,
)
from observatorio_maria.observability.telemetry import setup_telemetry
from tests.conftest import (
    FailingChatModel,
    ScriptedToolChatModel,
    UsageReportingFakeChatModel,
    chat_and_llm_spans,
    finished,
    metric_points,
)

USAGE = {'input_tokens': 12, 'output_tokens': 5, 'total_tokens': 17}


def registry_with(model):
    return ModelRegistry([
        RegisteredModel(tier, f'fake:{tier}', model) for tier in ModelTier
    ])


def answering_model():
    return UsageReportingFakeChatModel(
        messages=repeat(AIMessage('Resposta')), usage=USAGE
    )


async def send(client, conversation, content='Oi'):
    return await client.post(
        f'/conversations/{conversation["id"]}/messages',
        json={'content': content},
    )


async def test_chat_span_groups_llm_call_by_session(
    client, conversation, spans
):
    app.dependency_overrides[get_model_registry] = lambda: registry_with(
        answering_model()
    )

    await send(client, conversation)

    chat, llm = chat_and_llm_spans(spans)
    attrs = chat.attributes
    assert attrs[SpanAttributes.OPENINFERENCE_SPAN_KIND] == 'CHAIN'
    assert attrs[SpanAttributes.SESSION_ID] == conversation['id']
    assert attrs[SpanAttributes.INPUT_VALUE] == 'Oi'
    assert attrs[SpanAttributes.OUTPUT_VALUE] == 'Resposta'
    assert len(llm) == 1
    assert llm[0].parent.span_id == chat.context.span_id
    assert llm[0].attributes[SpanAttributes.SESSION_ID] == conversation['id']
    assert llm[0].attributes[SpanAttributes.LLM_TOKEN_COUNT_PROMPT] == 12  # noqa: PLR2004


async def test_model_failure_marks_span_and_logs_trace_id(
    client, conversation, spans
):
    log_exporter = InMemoryLogRecordExporter()
    logger_provider = LoggerProvider()
    logger_provider.add_log_record_processor(
        SimpleLogRecordProcessor(log_exporter)
    )
    handler = LoggingHandler(logger_provider=logger_provider)
    logger = logging.getLogger('observatorio_maria.services.chat')
    logger.addHandler(handler)
    app.dependency_overrides[get_model_registry] = lambda: registry_with(
        FailingChatModel()
    )

    try:
        await send(client, conversation)
    finally:
        logger.removeHandler(handler)

    (chat,) = finished(spans, 'maria.chat')
    assert chat.status.status_code == StatusCode.ERROR
    assert any(event.name == 'exception' for event in chat.events)
    (record,) = log_exporter.get_finished_logs()
    log = getattr(record, 'log_record', record)
    assert log.trace_id == chat.context.trace_id


async def test_hidden_content_keeps_structure(
    hidden_content, client, conversation, spans
):
    app.dependency_overrides[get_model_registry] = lambda: registry_with(
        answering_model()
    )

    await send(client, conversation, 'dado pessoal sensível')

    chat, llm = chat_and_llm_spans(spans)
    exported = [chat.attributes, llm[0].attributes]
    assert not any(
        'dado pessoal sensível' in str(value)
        for attrs in exported
        for value in attrs.values()
    )
    assert llm[0].attributes[SpanAttributes.LLM_TOKEN_COUNT_PROMPT] == 12  # noqa: PLR2004


async def test_genai_metrics_record_tokens_and_duration(
    client, conversation, metric_reader
):
    app.dependency_overrides[get_model_registry] = lambda: registry_with(
        answering_model()
    )

    await send(client, conversation)

    tokens = {
        p.attributes['gen_ai.token.type']: p.sum
        for p in metric_points(metric_reader, 'gen_ai.client.token.usage')
    }
    assert tokens == {'input': 12, 'output': 5}
    (duration,) = metric_points(
        metric_reader, 'gen_ai.client.operation.duration'
    )
    assert duration.count == 1
    assert duration.attributes['gen_ai.operation.name'] == 'chat'


async def test_genai_metrics_record_error_type(
    client, conversation, metric_reader
):
    app.dependency_overrides[get_model_registry] = lambda: registry_with(
        FailingChatModel()
    )

    await send(client, conversation)

    (duration,) = metric_points(
        metric_reader, 'gen_ai.client.operation.duration'
    )
    assert duration.attributes['error.type'] == 'RuntimeError'
    assert not metric_points(metric_reader, 'gen_ai.client.token.usage')


def test_setup_telemetry_is_noop_when_disabled(monkeypatch):
    monkeypatch.setenv('OTEL_SDK_DISABLED', 'true')
    fresh_app = FastAPI()

    setup_telemetry(fresh_app, engine)

    assert fresh_app.user_middleware == []


async def _setup_fomento(session, tmp_path, monkeypatch):
    db_file = tmp_path / 'fomento_obs.db'
    with sqlite3.connect(db_file) as conn:
        conn.executescript(
            """
            CREATE TABLE projetos (
                id INTEGER PRIMARY KEY,
                nome TEXT,
                resumo TEXT
            );
            INSERT INTO projetos VALUES
                (1, 'Projeto Dengue', 'Estudo sobre Dengue.'),
                (2, 'Projeto Arboviroses', 'Pesquisa arboviroses.');
        """
        )
    monkeypatch.setenv('TEST_OBS_URL', f'sqlite+aiosqlite:///{db_file}')
    ds = CatalogDataSource(
        id='fomento',
        name='Fomento à Pesquisa',
        connection_env='TEST_OBS_URL',
        schemas=['main'],
        enabled=True,
    )
    session.add(ds)
    await session.flush()
    ent = CatalogEntity(
        datasource_id=ds.id,
        schema_name='main',
        name='projetos',
        visible=True,
        queryable=True,
        present=True,
    )
    session.add(ent)
    await session.flush()
    session.add_all([
        CatalogColumn(
            entity_id=ent.id,
            name='id',
            visible=True,
            present=True,
            data_type='INTEGER',
        ),
        CatalogColumn(
            entity_id=ent.id,
            name='nome',
            visible=True,
            present=True,
            data_type='TEXT',
        ),
        CatalogColumn(
            entity_id=ent.id,
            name='resumo',
            visible=True,
            present=True,
            searchable=True,
            data_type='TEXT',
        ),
    ])
    await session.commit()
    return ds


async def test_query_tool_span_generated_under_chat(
    client, session, conversation, spans, tmp_path, monkeypatch
):
    await _setup_fomento(session, tmp_path, monkeypatch)
    turn1 = AIMessage(
        content='',
        tool_calls=[{
            'name': 'query_data',
            'args': {
                'source': 'fomento',
                'sql': (
                    'SELECT id, nome FROM projetos '
                    "WHERE MATCH_TEXT(resumo, 'dengue')"
                ),
                'purpose': 'Consultando dengue',
            },
            'id': 'c1',
        }],
    )
    turn2 = AIMessage(content='Encontrado 1 projeto.')
    app.dependency_overrides[get_model_registry] = lambda: registry_with(
        ScriptedToolChatModel(responses=[turn1, turn2])
    )

    await send(client, conversation, 'Dengue?')

    (chat,) = finished(spans, 'maria.chat')
    tool_spans = finished(spans, 'query_data')
    assert len(tool_spans) == 1
    tspan = tool_spans[0]
    assert tspan.parent.span_id == chat.context.span_id
    attrs = tspan.attributes
    assert attrs[SpanAttributes.OPENINFERENCE_SPAN_KIND] == 'TOOL'
    assert attrs[SpanAttributes.TOOL_NAME] == 'query_data'
    assert attrs['datasource.id'] == 'fomento'
    assert attrs['query.row_count'] == 1
    assert attrs['query.truncated'] is False
    assert 'MATCH_TEXT' in attrs[SpanAttributes.INPUT_VALUE]
    assert 'Projeto Dengue' in attrs[SpanAttributes.OUTPUT_VALUE]


async def test_query_tool_span_respects_hidden_content(
    hidden_content, client, session, conversation, spans, tmp_path, monkeypatch
):
    await _setup_fomento(session, tmp_path, monkeypatch)
    turn1 = AIMessage(
        content='',
        tool_calls=[{
            'name': 'query_data',
            'args': {
                'source': 'fomento',
                'sql': (
                    'SELECT id, nome FROM projetos '
                    "WHERE MATCH_TEXT(resumo, 'dengue')"
                ),
                'purpose': 'Consultando dengue',
            },
            'id': 'c1',
        }],
    )
    turn2 = AIMessage(content='Encontrado 1 projeto.')
    app.dependency_overrides[get_model_registry] = lambda: registry_with(
        ScriptedToolChatModel(responses=[turn1, turn2])
    )

    await send(client, conversation, 'Dengue?')

    (tspan,) = finished(spans, 'query_data')
    attrs = tspan.attributes
    assert attrs['datasource.id'] == 'fomento'
    assert not any('Projeto Dengue' in str(v) for v in attrs.values())
    assert not any('MATCH_TEXT' in str(v) for v in attrs.values())


async def test_rejected_query_tool_span_records_error_and_status(
    client, session, conversation, spans, tmp_path, monkeypatch
):
    await _setup_fomento(session, tmp_path, monkeypatch)
    turn1 = AIMessage(
        content='',
        tool_calls=[{
            'name': 'query_data',
            'args': {
                'source': 'fomento',
                'sql': 'SELECT * FROM projetos',
                'purpose': 'Consulta proibida com asterisco',
            },
            'id': 'c1',
        }],
    )
    turn2 = AIMessage(content='Consulta recusada.')
    app.dependency_overrides[get_model_registry] = lambda: registry_with(
        ScriptedToolChatModel(responses=[turn1, turn2])
    )

    await send(client, conversation, 'Asterisco?')

    (tspan,) = finished(spans, 'query_data')
    assert tspan.status.status_code == StatusCode.ERROR
    assert '*' in tspan.attributes['query.error']


async def test_agent_metrics_model_calls_and_query_count(
    client, session, conversation, metric_reader, tmp_path, monkeypatch
):
    await _setup_fomento(session, tmp_path, monkeypatch)
    turn1 = AIMessage(
        content='',
        tool_calls=[{
            'name': 'query_data',
            'args': {
                'source': 'fomento',
                'sql': 'SELECT * FROM projetos',
            },
            'id': 'c1',
        }],
    )
    turn2 = AIMessage(
        content='',
        tool_calls=[{
            'name': 'query_data',
            'args': {
                'source': 'fomento',
                'sql': 'SELECT id, nome FROM projetos',
            },
            'id': 'c2',
        }],
    )
    turn3 = AIMessage(content='Terminei.')

    app.dependency_overrides[get_model_registry] = lambda: registry_with(
        ScriptedToolChatModel(responses=[turn1, turn2, turn3])
    )

    await send(client, conversation, 'Multi-passo?')

    calls = metric_points(metric_reader, 'maria.agent.model_calls')
    assert len(calls) == 1
    assert calls[0].count == 1
    assert calls[0].sum == 3  # noqa: PLR2004

    queries = metric_points(metric_reader, 'maria.query.count')
    outcomes = {
        (p.attributes['outcome'], p.attributes['source']): p.value
        for p in queries
    }
    assert outcomes == {
        ('rejected', 'fomento'): 1,
        ('executed', 'fomento'): 1,
    }
