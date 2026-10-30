import json
import sqlite3
from http import HTTPStatus

import duckdb
import pytest
from langchain_core.messages import AIMessage
from sqlalchemy import select

from observatorio_maria.app import app
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
    CatalogSourceLink,
    Conversation,
)
from observatorio_maria.observability.genai import get_tracer
from observatorio_maria.services.chat import ChatService
from observatorio_maria.settings import Settings
from tests.conftest import ScriptedToolChatModel


def extension_installed():
    connection = duckdb.connect(':memory:')
    try:
        connection.execute('LOAD sqlite')
    except duckdb.Error:
        return False
    finally:
        connection.close()
    return True


integration = pytest.mark.skipif(
    not extension_installed(),
    reason='Extensão sqlite do DuckDB ausente: rode task duckdb-extensions',
)

SQL = (
    'SELECT p.modalidade, SUM(r.artigos) AS artigos '
    'FROM fomento.main.pesquisadores p '
    'JOIN simcc.main.researcher r ON r.lattes_id = p.lattes '
    'GROUP BY p.modalidade'
)


async def add_source(session, source, table, columns):
    session.add(
        CatalogDataSource(
            id=source,
            name=source.capitalize(),
            connection_env=f'TEST_{source.upper()}_URL',
            schemas=['main'],
        )
    )
    await session.flush()
    entity = CatalogEntity(
        datasource_id=source,
        schema_name='main',
        name=table,
        visible=True,
        queryable=True,
        present=True,
    )
    session.add(entity)
    await session.flush()
    session.add_all([
        CatalogColumn(
            entity_id=entity.id,
            name=name,
            visible=True,
            present=True,
            data_type=kind,
        )
        for name, kind in columns
    ])
    await session.commit()
    return entity


@pytest.fixture
async def two_sources(session, tmp_path, monkeypatch):
    fomento = tmp_path / 'fomento.db'
    simcc = tmp_path / 'simcc.db'
    with sqlite3.connect(fomento) as conn:
        conn.executescript(
            """
            CREATE TABLE pesquisadores (lattes TEXT, modalidade TEXT);
            INSERT INTO pesquisadores VALUES
                ('L1', 'Doutorado'), ('L2', 'Doutorado');
            """
        )
    with sqlite3.connect(simcc) as conn:
        conn.executescript(
            """
            CREATE TABLE researcher (lattes_id TEXT, artigos INTEGER);
            INSERT INTO researcher VALUES ('L1', 5);
            """
        )
    monkeypatch.setenv('TEST_FOMENTO_URL', f'sqlite+aiosqlite:///{fomento}')
    monkeypatch.setenv('TEST_SIMCC_URL', f'sqlite+aiosqlite:///{simcc}')
    source = await add_source(
        session,
        'fomento',
        'pesquisadores',
        [('lattes', 'TEXT'), ('modalidade', 'TEXT')],
    )
    target = await add_source(
        session,
        'simcc',
        'researcher',
        [('lattes_id', 'TEXT'), ('artigos', 'INTEGER')],
    )
    session.add(
        CatalogSourceLink(
            from_entity_id=source.id,
            from_column='lattes',
            to_entity_id=target.id,
            to_column='lattes_id',
        )
    )
    await session.commit()


def registry_with(model):
    return ModelRegistry([
        RegisteredModel(tier, f'fake:{tier}', model) for tier in ModelTier
    ])


def across_turn(sql=SQL, call_id='c1'):
    return {
        'name': 'query_across_sources',
        'args': {'sql': sql, 'purpose': 'Artigos por modalidade'},
        'id': call_id,
    }


async def ask(session, model, **service_args):
    conversation = Conversation()
    session.add(conversation)
    await session.commit()
    service = ChatService(
        session, registry_with(model), get_tracer(), [], **service_args
    )
    return await service.send_message(conversation, 'Artigos por modalidade?')


def tool_names(model):
    return {tool.name for tool in model.bound_tools}


async def test_tool_is_offered_with_active_link(session, two_sources):
    model = ScriptedToolChatModel(responses=[AIMessage('Oi')])

    await ask(session, model)

    assert 'query_across_sources' in tool_names(model)
    prompt = model.recorded_calls[0][0].content
    assert '# Consultas entre fontes' in prompt
    assert 'coverage' in prompt


async def test_tool_is_not_offered_without_active_link(session, two_sources):
    link = await session.scalar(select(CatalogSourceLink))
    link.enabled = False
    await session.commit()
    model = ScriptedToolChatModel(responses=[AIMessage('Oi')])

    await ask(session, model)

    assert 'query_across_sources' not in tool_names(model)
    assert 'Consultas entre fontes' not in model.recorded_calls[0][0].content


async def test_tool_is_not_offered_with_one_source(session, two_sources):
    simcc = await session.get(CatalogDataSource, 'simcc')
    simcc.enabled = False
    await session.commit()
    model = ScriptedToolChatModel(responses=[AIMessage('Oi')])

    await ask(session, model)

    assert 'query_across_sources' not in tool_names(model)


@integration
async def test_result_has_coverage_and_feeds_table(session, two_sources):
    model = ScriptedToolChatModel(
        responses=[
            AIMessage(content='', tool_calls=[across_turn()]),
            AIMessage(
                content='Pronto.',
                tool_calls=[
                    {
                        'name': 'show_table',
                        'args': {
                            'result_id': 'r1',
                            'columns': ['modalidade', 'artigos'],
                            'title': 'Artigos',
                        },
                        'id': 'c2',
                    }
                ],
            ),
        ]
    )
    observations = []

    _, assistant = await ask(
        session, model, query_observer=observations.append
    )

    tool_data = json.loads(model.recorded_calls[1][-1].content)
    assert tool_data['rows'] == [['Doutorado', 5]]
    assert tool_data['coverage']['keys'] == 2  # noqa: PLR2004
    assert tool_data['coverage']['found'] == 1
    assert '<untrusted_database_data' in tool_data['untrusted_data']
    (observation,) = observations
    assert observation.sources == ('fomento', 'simcc')
    assert assistant.content[1]['rows'] == [
        {'modalidade': 'Doutorado', 'artigos': 5}
    ]
    origin = assistant.content[1]['origin']
    assert len(origin['sources']) == 2  # noqa: PLR2004
    assert origin['coverage'] == {'keys': 2, 'found': 1}


async def test_refused_query_goes_back_to_model(session, two_sources):
    sql = 'SELECT lattes FROM fomento.main.pesquisadores'
    model = ScriptedToolChatModel(
        responses=[
            AIMessage(content='', tool_calls=[across_turn(sql)]),
            AIMessage('Vou usar outra ferramenta.'),
        ]
    )

    await ask(session, model)

    tool_data = json.loads(model.recorded_calls[1][-1].content)
    assert 'query_data' in tool_data['error']


async def test_counts_for_queries_per_call(session, two_sources):
    calls = [across_turn(call_id=f'c{i}') for i in range(2)]
    model = ScriptedToolChatModel(
        responses=[AIMessage(content='', tool_calls=calls), AIMessage('Fim')]
    )
    settings = Settings(_env_file=None, QUERY_MAX_PER_CALL=1)

    await ask(session, model, settings=settings)

    last = json.loads(model.recorded_calls[1][-1].content)
    assert 'Limite de consultas' in last['error']


@integration
async def test_stream_activity_has_both_sources_without_sql(
    client, session, conversation, two_sources
):
    model = ScriptedToolChatModel(
        responses=[
            AIMessage(content='', tool_calls=[across_turn()]),
            AIMessage('Pronto.'),
        ]
    )
    registry = registry_with(model)
    app.dependency_overrides[get_model_registry] = lambda: registry

    response = await client.post(
        f'/conversations/{conversation["id"]}/messages/stream',
        json={'content': 'Artigos por modalidade?'},
    )

    assert response.status_code == HTTPStatus.OK
    activity = next(
        json.loads(line.removeprefix('data: '))
        for block in response.text.split('\n\n')
        if block.startswith('event: activity')
        for line in block.splitlines()
        if line.startswith('data: ')
    )
    assert activity['source'] == 'Fomento e Simcc'
    assert 'SELECT' not in json.dumps(activity)
