import json
import sqlite3
from datetime import datetime
from http import HTTPStatus
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
from langchain_core.messages import AIMessage, SystemMessage
from pydantic import ValidationError

from observatorio_maria.app import app
from observatorio_maria.catalog.context import render_context
from observatorio_maria.catalog.sync import load_entities, load_relationships
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
    Message,
    MessageRole,
)
from observatorio_maria.schemas import TextBlock
from observatorio_maria.settings import Settings
from tests.conftest import ScriptedToolChatModel


@pytest.fixture
def fomento_source(tmp_path, monkeypatch):
    db_file = tmp_path / 'fomento.db'
    with sqlite3.connect(db_file) as conn:
        conn.executescript(
            """
            CREATE TABLE projetos (
                id INTEGER PRIMARY KEY,
                nome TEXT,
                resumo TEXT,
                ano INTEGER,
                orcamento REAL
            );
            INSERT INTO projetos VALUES
                (1, 'Dengue Bahia', 'Estudo Dengue e Aedes.', 2024, 150.0),
                (2, 'Robótica Agro', 'Automação no cultivo.', 2024, 80.0),
                (3, 'Prevenção Dengue', 'Saúde e dengue.', 2025, 200.0);
        """
        )
    monkeypatch.setenv('TEST_FOMENTO_URL', f'sqlite+aiosqlite:///{db_file}')
    return 'TEST_FOMENTO_URL'


async def setup_catalog(session, connection_env: str):
    ds = CatalogDataSource(
        id='fomento',
        name='Fomento à Pesquisa',
        connection_env=connection_env,
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
    cols = [
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
            searchable=True,
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
        CatalogColumn(
            entity_id=ent.id,
            name='ano',
            visible=True,
            present=True,
            data_type='INTEGER',
        ),
        CatalogColumn(
            entity_id=ent.id,
            name='orcamento',
            visible=True,
            present=True,
            data_type='REAL',
        ),
    ]
    session.add_all(cols)
    await session.commit()
    return ds


def set_test_model(model):
    registry = ModelRegistry([
        RegisteredModel(tier, f'fake:{tier}', model) for tier in ModelTier
    ])
    app.dependency_overrides[get_model_registry] = lambda: registry


def parse_sse(body: str) -> list[tuple[str, dict]]:
    events = []
    for raw in body.strip().split('\n\n'):
        fields = dict(
            line.split(': ', 1)
            for line in raw.splitlines()
            if line and not line.startswith(':')
        )
        if 'event' in fields:
            events.append((fields['event'], json.loads(fields['data'])))
    return events


@pytest.mark.asyncio
async def test_scripted_model_query_then_response(
    client, session, conversation, fomento_source
):
    await setup_catalog(session, fomento_source)

    turn1 = AIMessage(
        content='',
        tool_calls=[
            {
                'name': 'query_data',
                'args': {
                    'source': 'fomento',
                    'sql': (
                        'SELECT id, nome, ano FROM projetos '
                        "WHERE MATCH_TEXT(resumo, 'dengue') ORDER BY id"
                    ),
                    'purpose': 'Buscando projetos sobre dengue',
                },
                'id': 'call_1',
            }
        ],
    )
    turn2 = AIMessage(content='Encontrei 2 projetos de fomento sobre dengue.')

    model = ScriptedToolChatModel(responses=[turn1, turn2])
    set_test_model(model)

    res = await client.post(
        f'/conversations/{conversation["id"]}/messages',
        json={'content': 'Existe fomento de dengue?'},
    )
    assert res.status_code == HTTPStatus.CREATED
    data = res.json()
    first_block = data['assistant_message']['content'][0]
    assert 'Encontrei 2 projetos' in first_block['text']

    # Verifica que o modelo foi chamado duas vezes e recebeu o resultado
    assert len(model.recorded_calls) == 2  # noqa: PLR2004
    # Na segunda chamada, a última mensagem é ToolMessage com o resultado
    tool_msg = model.recorded_calls[1][-1]
    assert tool_msg.tool_call_id == 'call_1'
    tool_data = json.loads(tool_msg.content)
    assert tool_data['result_id'] == 'r1'
    assert len(tool_data['rows']) == 2  # noqa: PLR2004


@pytest.mark.asyncio
async def test_system_prompt_contains_date_and_consultable_sources(
    client, session, conversation, fomento_source
):
    ds = await setup_catalog(session, fomento_source)
    expected_ctx = render_context(
        ds,
        await load_entities(session, ds.id),
        await load_relationships(session, ds.id),
    )

    model = ScriptedToolChatModel(
        responses=[AIMessage(content='Resposta teste.')]
    )
    set_test_model(model)

    await client.post(
        f'/conversations/{conversation["id"]}/messages',
        json={'content': 'Quais projetos existem?'},
    )

    first_call_msgs = model.recorded_calls[0]
    sys_msg = first_call_msgs[0]
    assert isinstance(sys_msg, SystemMessage)

    # Verifica data no fuso America/Bahia
    hoje = datetime.now(ZoneInfo('America/Bahia')).strftime('%d/%m/%Y')
    assert hoje in sys_msg.content

    # Verifica contexto da fonte fomento
    assert expected_ctx.strip() in sys_msg.content


@pytest.mark.asyncio
async def test_history_summarizes_chart_and_table(
    client, session, conversation
):
    # Insere manualmente uma troca anterior com blocos chart e table grandes
    chart_data = [{'ano': 2020 + i, 'total': i * 10} for i in range(40)]
    table_rows = [{'nome': f'Projeto {i}', 'ano': 2024} for i in range(12)]

    conv_id = UUID(str(conversation['id']))
    user_msg = Message(
        conversation_id=conv_id,
        role=MessageRole.USER,
        content=[TextBlock(text='Mostre gráficos e tabelas').model_dump()],
    )
    asst_msg = Message(
        conversation_id=conv_id,
        role=MessageRole.ASSISTANT,
        content=[
            TextBlock(text='Aqui estão:').model_dump(),
            {
                'type': 'chart',
                'chart_type': 'bar',
                'title': 'Evolução de Bolsas',
                'x': {'key': 'ano', 'label': 'Ano'},
                'series': [{'key': 'total', 'label': 'Total'}],
                'data': chart_data,
            },
            {
                'type': 'table',
                'title': 'Projetos Recentes',
                'columns': [
                    {'key': 'nome', 'label': 'Nome do Projeto'},
                    {'key': 'ano', 'label': 'Ano'},
                ],
                'rows': table_rows,
            },
        ],
    )
    session.add_all([user_msg, asst_msg])
    await session.commit()

    model = ScriptedToolChatModel(
        responses=[AIMessage(content='Nova resposta.')]
    )
    set_test_model(model)

    await client.post(
        f'/conversations/{conversation["id"]}/messages',
        json={'content': 'E sobre 2025?'},
    )

    first_call_msgs = model.recorded_calls[0]
    # Mensagem 2 é a resposta anterior do assistente
    asst_history = first_call_msgs[2]
    assert isinstance(asst_history, AIMessage)
    # Verifica que contém os resumos e NÃO os dados brutos
    assert 'Evolução de Bolsas' in asst_history.content
    assert 'Total de registros: 40' in asst_history.content
    assert 'Projetos Recentes' in asst_history.content
    assert 'Total de linhas: 12' in asst_history.content
    assert 'Projeto 39' not in asst_history.content


@pytest.mark.asyncio
async def test_budget_exhausted_strips_query_tools_on_last_call(
    client, session, conversation, fomento_source
):
    await setup_catalog(session, fomento_source)

    # 3 chamadas: chamada 1 query, chamada 2 query, chamada 3 última
    turn1 = AIMessage(
        content='',
        tool_calls=[{
            'name': 'query_data',
            'args': {'source': 'fomento', 'sql': 'SELECT id FROM projetos'},
            'id': 'c1',
        }],
    )
    turn2 = AIMessage(
        content='',
        tool_calls=[{
            'name': 'query_data',
            'args': {'source': 'fomento', 'sql': 'SELECT id FROM projetos'},
            'id': 'c2',
        }],
    )
    turn3 = AIMessage(content='Concluo com as informações que obtive.')

    model = ScriptedToolChatModel(responses=[turn1, turn2, turn3])
    set_test_model(model)

    res = await client.post(
        f'/conversations/{conversation["id"]}/messages',
        json={'content': 'Pergunta longa'},
    )
    assert res.status_code == HTTPStatus.CREATED
    assert len(model.recorded_calls) == 3  # noqa: PLR2004

    # Na chamada 3, a última chamada avisou sobre o fim do orçamento
    last_call_messages = model.recorded_calls[2]
    system_warnings = [
        m.content
        for m in last_call_messages
        if isinstance(m, SystemMessage) and 'última chamada' in m.content
    ]
    assert len(system_warnings) == 1


@pytest.mark.asyncio
async def test_server_populates_chart_and_table_blocks(
    client, session, conversation, fomento_source
):
    await setup_catalog(session, fomento_source)

    turn1 = AIMessage(
        content='',
        tool_calls=[{
            'name': 'query_data',
            'args': {
                'source': 'fomento',
                'sql': (
                    'SELECT ano, orcamento, nome FROM projetos ORDER BY ano'
                ),
            },
            'id': 'c1',
        }],
    )
    turn2 = AIMessage(
        content='Veja o resumo a seguir:',
        tool_calls=[
            {
                'name': 'show_chart',
                'args': {
                    'result_id': 'r1',
                    'chart_type': 'bar',
                    'title': 'Orçamento por Ano',
                    'x': 'ano',
                    'series': ['orcamento'],
                },
                'id': 'c2',
            },
            {
                'name': 'show_table',
                'args': {
                    'result_id': 'r1',
                    'columns': ['nome', 'ano'],
                    'title': 'Projetos',
                },
                'id': 'c3',
            },
        ],
    )

    model = ScriptedToolChatModel(responses=[turn1, turn2])
    set_test_model(model)

    res = await client.post(
        f'/conversations/{conversation["id"]}/messages',
        json={'content': 'Resumo financeiro'},
    )
    assert res.status_code == HTTPStatus.CREATED
    blocks = res.json()['assistant_message']['content']

    # Ordem: texto, depois gráfico, depois tabela
    assert blocks[0]['type'] == 'text'
    assert blocks[0]['text'] == 'Veja o resumo a seguir:'

    assert blocks[1]['type'] == 'chart'
    assert blocks[1]['title'] == 'Orçamento por Ano'
    assert len(blocks[1]['data']) == 3  # noqa: PLR2004
    assert blocks[1]['data'][0]['ano'] == 2024  # noqa: PLR2004
    assert blocks[1]['data'][0]['orcamento'] == 150.0  # noqa: PLR2004

    assert blocks[2]['type'] == 'table'
    assert blocks[2]['title'] == 'Projetos'
    assert len(blocks[2]['rows']) == 3  # noqa: PLR2004
    assert 'nome' in blocks[2]['rows'][0]
    assert 'orcamento' not in blocks[2]['rows'][0]


@pytest.mark.asyncio
async def test_streaming_emits_activity_and_block_deltas(
    client, session, conversation, fomento_source
):
    await setup_catalog(session, fomento_source)

    turn1 = AIMessage(
        content='',
        tool_calls=[{
            'name': 'query_data',
            'args': {
                'source': 'fomento',
                'sql': 'SELECT id, nome FROM projetos',
                'purpose': 'Consultando projetos para listar',
            },
            'id': 'c1',
        }],
    )
    turn2 = AIMessage(
        content='Aqui está a tabela:',
        tool_calls=[{
            'name': 'show_table',
            'args': {
                'result_id': 'r1',
                'columns': ['nome'],
                'title': 'Tabela de Projetos',
            },
            'id': 'c2',
        }],
    )

    model = ScriptedToolChatModel(responses=[turn1, turn2])
    set_test_model(model)

    res = await client.post(
        f'/conversations/{conversation["id"]}/messages/stream',
        json={'content': 'Liste os projetos'},
    )
    assert res.status_code == HTTPStatus.OK
    events = parse_sse(res.text)

    names = [name for name, _ in events]
    # Ordem: message.user -> activity -> content.delta -> message.assistant
    assert names[0] == 'message.user'
    assert 'activity' in names
    activity_idx = names.index('activity')
    assert events[activity_idx][1]['kind'] == 'query'
    assert events[activity_idx][1]['source'] == 'Fomento à Pesquisa'
    assert (
        events[activity_idx][1]['description']
        == 'Consultando projetos para listar'
    )

    # Deltas
    deltas = [(name, data) for name, data in events if name == 'content.delta']
    assert deltas[0][1]['index'] == 0
    assert deltas[0][1]['type'] == 'text'
    # Delta do bloco completo da tabela
    assert deltas[-1][1]['index'] == 1
    assert deltas[-1][1]['type'] == 'table'
    assert deltas[-1][1]['block']['title'] == 'Tabela de Projetos'

    assert names[-1] == 'message.assistant'


@pytest.mark.asyncio
async def test_partial_response_scenario_dengue_and_articles(
    client, session, conversation, fomento_source
):
    await setup_catalog(session, fomento_source)

    # O usuário pergunta sobre fomento E sobre artigos produzidos.
    # O fomento existe, mas artigos não existem em nenhuma fonte do catálogo.
    turn1 = AIMessage(
        content='',
        tool_calls=[{
            'name': 'query_data',
            'args': {
                'source': 'fomento',
                'sql': (
                    'SELECT nome, orcamento FROM projetos '
                    "WHERE MATCH_TEXT(resumo, 'dengue')"
                ),
                'purpose': 'Consultando projetos de dengue',
            },
            'id': 'c1',
        }],
    )
    turn2 = AIMessage(
        content=(
            'Identifiquei projetos sobre dengue. No entanto, os artigos '
            'resultantes ainda não estão disponíveis para consulta.'
        )
    )

    model = ScriptedToolChatModel(responses=[turn1, turn2])
    set_test_model(model)

    res = await client.post(
        f'/conversations/{conversation["id"]}/messages',
        json={
            'content': (
                'Existe fomento de dengue entre 2024 e 2026? '
                'Quais projetos e quais artigos foram produzidos?'
            )
        },
    )
    assert res.status_code == HTTPStatus.CREATED
    text = res.json()['assistant_message']['content'][0]['text']
    assert 'artigos resultantes ainda não estão disponíveis' in text


def test_zero_max_model_calls_rejected():
    with pytest.raises(ValidationError):
        Settings(MARIA_AGENT_MAX_MODEL_CALLS=0)
