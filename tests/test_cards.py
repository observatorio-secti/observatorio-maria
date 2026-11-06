"""Testes de hidratação de cards estruturados de pesquisadores e produções."""

import json
import sqlite3
from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from observatorio_maria.models import CatalogDataSource
from observatorio_maria.query.cards import (
    MAX_CARDS,
    hydrate_productions,
    hydrate_researchers,
)
from observatorio_maria.query.execution import (
    QueryResult,
    ResultStore,
    result_from_block,
)
from observatorio_maria.query.tool import QueryRunner
from observatorio_maria.services.chat import ChatService
from observatorio_maria.settings import Settings


@pytest.fixture
def simcc_full_db(tmp_path):
    db_file = tmp_path / 'simcc_full.db'
    with sqlite3.connect(db_file) as conn:
        conn.executescript(
            """
            CREATE TABLE state (
                id TEXT PRIMARY KEY,
                name TEXT,
                abbreviation TEXT
            );
            INSERT INTO state VALUES ('st-ba', 'Bahia', 'BA');

            CREATE TABLE city (
                id TEXT PRIMARY KEY,
                name TEXT,
                state_id TEXT
            );
            INSERT INTO city VALUES ('ct-ssa', 'Salvador', 'st-ba');

            CREATE TABLE institution (
                id TEXT PRIMARY KEY,
                name TEXT,
                acronym TEXT,
                city_id TEXT
            );
            INSERT INTO institution VALUES
                ('inst-ufba', 'UFBA Salvador', 'UFBA', 'ct-ssa');

            CREATE TABLE researcher (
                id TEXT PRIMARY KEY,
                name TEXT,
                lattes_id TEXT,
                abstract TEXT,
                orcid TEXT,
                graduation TEXT,
                city_id TEXT
            );
            INSERT INTO researcher VALUES (
                'r-001',
                'Dra. Maria Bahia',
                '1111222233334444',
                'Pesquisadora titular com CPF 123.456.789-00 em saúde.',
                '0000-0001-2345-6789',
                'Doutorado',
                'ct-ssa'
            ), (
                'r-002',
                'Dr. João do Sertão',
                '5555666677778888',
                'Bolsista em automação.',
                NULL,
                'Mestrado',
                NULL
            );

            CREATE TABLE researcher_institution (
                researcher_id TEXT,
                institution_id TEXT,
                identity_territory TEXT
            );
            INSERT INTO researcher_institution VALUES
                ('r-001', 'inst-ufba', 'Metropolitano de Salvador'),
                ('r-002', 'inst-ufba', 'Portal do Sertão');

            CREATE TABLE researcher_production (
                researcher_id TEXT PRIMARY KEY,
                articles INTEGER,
                book_chapters INTEGER,
                book INTEGER,
                patent INTEGER,
                software INTEGER,
                brand INTEGER
            );
            INSERT INTO researcher_production VALUES
                ('r-001', 25, 4, 2, 1, 0, 0),
                ('r-002', 10, 1, 0, 2, 3, 0);

            CREATE TABLE openalex_researcher (
                researcher_id TEXT PRIMARY KEY,
                h_index INTEGER,
                i10_index INTEGER,
                cited_by_count INTEGER,
                openalex TEXT
            );
            INSERT INTO openalex_researcher VALUES
                ('r-001', 14, 20, 650, 'https://openalex.org/A123');

            CREATE TABLE bibliographic_production (
                id TEXT PRIMARY KEY,
                researcher_id TEXT,
                type TEXT,
                title TEXT,
                year_ INTEGER,
                doi TEXT,
                nature TEXT,
                authors TEXT
            );
            INSERT INTO bibliographic_production VALUES
                ('bp-1', 'r-001', 'ARTICLE', 'Estudo Dengue', 2024,
                 '10.1000/182', 'COMPLETO', 'BAHIA, M.; SOUZA, J.'),
                ('bp-2', 'r-001', 'BOOK', 'Manual de Saúde Pública',
                 2023, NULL, 'LIVRO', 'BAHIA, M.');

            CREATE TABLE bibliographic_production_article (
                bibliographic_production_id TEXT PRIMARY KEY,
                periodical_magazine_name TEXT,
                issn TEXT,
                qualis TEXT
            );
            INSERT INTO bibliographic_production_article VALUES
                ('bp-1', 'Revista de Saúde Coletiva', '1413-8123', 'A1');

            CREATE TABLE bibliographic_production_book (
                bibliographic_production_id TEXT PRIMARY KEY,
                isbn TEXT,
                publishing_company TEXT
            );
            INSERT INTO bibliographic_production_book VALUES
                ('bp-2', '978-85-12345-67-8', 'Editora UFBA');

            CREATE TABLE patent (
                id TEXT PRIMARY KEY,
                researcher_id TEXT,
                title TEXT,
                category TEXT,
                code TEXT,
                development_year TEXT,
                deposit_date TEXT,
                grant_date TEXT
            );
            INSERT INTO patent VALUES
                ('pat-1', 'r-002', 'Dispositivo Sensor', 'Invenção',
                 'BR102024001', '2024', '2024-01-15', '2024-06-20');

            CREATE TABLE software (
                id TEXT PRIMARY KEY,
                researcher_id TEXT,
                title TEXT,
                year INTEGER,
                platform TEXT,
                environment TEXT,
                availability TEXT
            );
            INSERT INTO software VALUES
                ('soft-1', 'r-002', 'Simulador Epidemiológico', 2023,
                 'Web', 'Linux', 'Aberto');

            CREATE TABLE participation_events (
                id TEXT PRIMARY KEY,
                researcher_id TEXT,
                title TEXT,
                event_name TEXT,
                year INTEGER,
                nature TEXT,
                form_participation TEXT,
                type_participation TEXT
            );
            INSERT INTO participation_events VALUES
                ('ev-1', 'r-001', 'Apresentação Oral Dengue',
                 'Congresso Brasileiro', 2024, 'Nacional', 'Oral',
                 'Participante');
            """
        )
    return str(db_file)


@pytest.mark.asyncio
async def test_hydrate_researchers_empty():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    cards = await hydrate_researchers(engine, 'main', [])
    assert cards == []
    await engine.dispose()


@pytest.mark.asyncio
async def test_hydrate_researchers_full(simcc_full_db):
    engine = create_async_engine(f'sqlite+aiosqlite:///{simcc_full_db}')
    # Busca r-001 por Lattes e r-002 por UUID
    cards = await hydrate_researchers(
        engine, 'main', ['1111222233334444', 'r-002']
    )
    assert len(cards) == 2  # noqa: PLR2004

    c1 = cards[0]
    assert c1.id == 'r-001'
    assert c1.name == 'Dra. Maria Bahia'
    assert c1.lattes_id == '1111222233334444'
    assert '[CPF MASCARADO]' in c1.abstract
    assert '123.456.789-00' not in c1.abstract
    assert c1.orcid == '0000-0001-2345-6789'
    assert c1.city == 'Salvador'
    assert c1.state == 'BA'
    assert c1.territory == 'Metropolitano de Salvador'
    assert len(c1.affiliations) == 1
    assert c1.affiliations[0].institution_acronym == 'UFBA'
    assert c1.metrics.articles == 25  # noqa: PLR2004
    assert c1.metrics.books == 2  # noqa: PLR2004
    assert c1.metrics.total_productions == 32  # noqa: PLR2004 (25+4+2+1)
    assert c1.metrics.h_index == 14  # noqa: PLR2004
    assert c1.metrics.citations == 650  # noqa: PLR2004
    assert c1.openalex_id == 'https://openalex.org/A123'

    c2 = cards[1]
    assert c2.id == 'r-002'
    assert c2.territory == 'Portal do Sertão'
    assert c2.metrics.software == 3  # noqa: PLR2004
    assert c2.metrics.patents == 2  # noqa: PLR2004

    await engine.dispose()


@pytest.mark.asyncio
async def test_hydrate_researchers_minimal_fallback(tmp_path):
    db_file = tmp_path / 'simcc_min.db'
    with sqlite3.connect(db_file) as conn:
        conn.execute(
            'CREATE TABLE researcher '
            '(id TEXT PRIMARY KEY, name TEXT, lattes_id TEXT)'
        )
        conn.execute(
            'INSERT INTO researcher VALUES '
            "('r-min', 'Pesquisador Mínimo', '9999')"
        )
    engine = create_async_engine(f'sqlite+aiosqlite:///{db_file}')
    cards = await hydrate_researchers(engine, 'main', ['r-min'])
    assert len(cards) == 1
    assert cards[0].id == 'r-min'
    assert cards[0].name == 'Pesquisador Mínimo'
    assert cards[0].metrics.articles == 0
    await engine.dispose()


@pytest.mark.asyncio
async def test_hydrate_researchers_max_cards_cap(tmp_path):
    db_file = tmp_path / 'simcc_cap.db'
    with sqlite3.connect(db_file) as conn:
        conn.execute(
            'CREATE TABLE researcher '
            '(id TEXT PRIMARY KEY, name TEXT, lattes_id TEXT)'
        )
        for i in range(30):
            conn.execute(
                f"INSERT INTO researcher VALUES ('r-{i}', 'P {i}', 'l-{i}')"
            )
    engine = create_async_engine(f'sqlite+aiosqlite:///{db_file}')
    requested = [f'r-{i}' for i in range(30)]
    cards = await hydrate_researchers(engine, 'main', requested)
    assert len(cards) == MAX_CARDS
    await engine.dispose()


@pytest.mark.asyncio
async def test_hydrate_productions_empty():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    cards = await hydrate_productions(engine, 'main', [])
    assert cards == []
    await engine.dispose()


@pytest.mark.asyncio
async def test_hydrate_productions_full(simcc_full_db):
    engine = create_async_engine(f'sqlite+aiosqlite:///{simcc_full_db}')
    cards = await hydrate_productions(
        engine, 'main', ['bp-1', 'bp-2', 'pat-1', 'soft-1', 'ev-1']
    )
    assert len(cards) == 5  # noqa: PLR2004

    # 1. Artigo
    art = cards[0]
    assert art.id == 'bp-1'
    assert art.type == 'article'
    assert art.type_label == 'Artigo em Periódico'
    assert art.year == 2024  # noqa: PLR2004
    assert art.details.qualis == 'A1'
    assert art.details.doi == '10.1000/182'
    assert art.details.magazine == 'Revista de Saúde Coletiva'
    assert len(art.authors) == 2  # noqa: PLR2004
    assert art.authors[0].name == 'BAHIA, M.'

    # 2. Livro
    bk = cards[1]
    assert bk.id == 'bp-2'
    assert bk.type == 'book'
    assert bk.type_label == 'Livro'
    assert bk.details.isbn == '978-85-12345-67-8'

    # 3. Patente
    pat = cards[2]
    assert pat.id == 'pat-1'
    assert pat.type == 'patent'
    assert pat.type_label == 'Patente'
    assert pat.year == 2024  # noqa: PLR2004
    assert pat.details.grant_date == '2024-06-20'

    # 4. Software
    sft = cards[3]
    assert sft.id == 'soft-1'
    assert sft.type == 'software'
    assert sft.type_label == 'Software'
    assert sft.year == 2023  # noqa: PLR2004

    # 5. Evento
    ev = cards[4]
    assert ev.id == 'ev-1'
    assert ev.type == 'event'
    assert ev.type_label == 'Participação em Evento'
    assert ev.details.event_name == 'Congresso Brasileiro'

    await engine.dispose()


@pytest.mark.asyncio
async def test_hydrate_productions_canonical_view_fallback(tmp_path):
    db_file = tmp_path / 'simcc_canon.db'
    with sqlite3.connect(db_file) as conn:
        conn.executescript(
            """
            CREATE TABLE mv_canonical_articles (
                canonical_id TEXT PRIMARY KEY,
                title TEXT,
                year INTEGER,
                doi TEXT,
                qualis TEXT,
                magazine_name TEXT,
                issn TEXT
            );
            INSERT INTO mv_canonical_articles VALUES (
                'can-1', 'Artigo Canônico', 2025, '10.123/art', 'A2',
                'Revista Canônica', '1234-5678'
            );
            """
        )
    engine = create_async_engine(f'sqlite+aiosqlite:///{db_file}')
    cards = await hydrate_productions(engine, 'main', ['can-1'])
    assert len(cards) == 1
    assert cards[0].id == 'can-1'
    assert cards[0].title == 'Artigo Canônico'
    assert cards[0].type == 'article'
    assert cards[0].details.qualis == 'A2'
    assert cards[0].details.magazine == 'Revista Canônica'
    await engine.dispose()


@pytest.mark.asyncio
async def test_query_runner_show_researchers_and_productions(
    simcc_full_db, session, monkeypatch
):
    monkeypatch.setenv('TEST_SIMCC_URL', f'sqlite+aiosqlite:///{simcc_full_db}')
    ds = CatalogDataSource(
        id='simcc',
        name='Simcc',
        connection_env='TEST_SIMCC_URL',
        schemas=['main'],
        enabled=True,
    )
    session.add(ds)
    await session.commit()

    store = ResultStore()
    res1 = store.add(
        'simcc',
        'SELECT id, name FROM researcher',
        ['id', 'name'],
        [['r-001', 'Dra. Maria Bahia']],
        truncated=False,
    )
    res2 = store.add(
        'simcc',
        'SELECT id, title FROM bibliographic_production',
        ['id', 'title'],
        [['bp-1', 'Estudo Dengue']],
        truncated=False,
    )

    test_engine = create_async_engine(f'sqlite+aiosqlite:///{simcc_full_db}')
    runner = QueryRunner(
        session,
        store,
        engine_factory=lambda _: test_engine,
    )

    # 1. show_researchers
    res_r = await runner.show_researchers(res1.result_id)
    assert res_r['status'] == 'ok'
    assert len(runner.pending_blocks) == 1
    block_r = runner.pending_blocks[0]
    assert block_r['type'] == 'researchers'
    assert len(block_r['researchers']) == 1
    assert block_r['researchers'][0]['name'] == 'Dra. Maria Bahia'

    # 2. show_productions
    res_p = await runner.show_productions(res2.result_id)
    assert res_p['status'] == 'ok'
    assert len(runner.pending_blocks) == 2  # noqa: PLR2004
    block_p = runner.pending_blocks[1]
    assert block_p['type'] == 'productions'
    assert len(block_p['productions']) == 1
    assert block_p['productions'][0]['id'] == 'bp-1'

    # 3. Erro quando coluna não existe
    err_col = await runner.show_researchers(
        res1.result_id, id_column='nao_existe'
    )
    assert 'error' in err_col

    # 4. Erro quando resultado não existe
    err_res = await runner.show_researchers('r999')
    assert 'error' in err_res

    await runner.close()
    await test_engine.dispose()


@pytest.mark.asyncio
async def test_chat_service_executes_card_tool_calls(
    simcc_full_db, session, monkeypatch
):
    monkeypatch.setenv('TEST_SIMCC_URL', f'sqlite+aiosqlite:///{simcc_full_db}')
    ds = CatalogDataSource(
        id='simcc',
        name='Simcc',
        connection_env='TEST_SIMCC_URL',
        schemas=['main'],
        enabled=True,
    )
    session.add(ds)
    await session.commit()

    store = ResultStore()
    res1 = store.add(
        'simcc',
        'SELECT id FROM researcher',
        ['id'],
        [['r-001']],
        truncated=False,
    )
    res2 = store.add(
        'simcc',
        'SELECT id FROM bibliographic_production',
        ['id'],
        [['bp-1']],
        truncated=False,
    )

    test_engine = create_async_engine(f'sqlite+aiosqlite:///{simcc_full_db}')
    runner = QueryRunner(
        session,
        store,
        engine_factory=lambda _: test_engine,
    )

    chat_service = ChatService(
        session=session,
        registry=MagicMock(),
        tracer=MagicMock(),
        callbacks=[],
        settings=Settings(),
    )

    msg_r, _ = await chat_service._execute_tool_call(
        {
            'name': 'show_researchers',
            'args': {'result_id': res1.result_id},
            'id': 'c1',
        },
        runner,
        MagicMock(),
        'sess-1',
    )
    assert json.loads(msg_r.content)['status'] == 'ok'

    msg_p, _ = await chat_service._execute_tool_call(
        {
            'name': 'show_productions',
            'args': {'result_id': res2.result_id},
            'id': 'c2',
        },
        runner,
        MagicMock(),
        'sess-2',
    )
    assert json.loads(msg_p.content)['status'] == 'ok'

    assert len(runner.pending_blocks) == 2  # noqa: PLR2004
    assert runner.pending_blocks[0]['type'] == 'researchers'
    assert runner.pending_blocks[1]['type'] == 'productions'

    await runner.close()
    await test_engine.dispose()


def test_result_from_block_for_cards():
    r_block = {
        'type': 'researchers',
        'researchers': [
            {'id': 'r-1', 'name': 'Pesquisador Um', 'lattes_id': '123'},
            {'id': 'r-2', 'name': 'Pesquisador Dois', 'lattes_id': '456'},
        ],
        'origin': {'sources': ['Simcc']},
    }
    q_r = result_from_block(r_block, 'h1')
    assert isinstance(q_r, QueryResult)
    assert q_r.result_id == 'h1'
    assert q_r.columns == ['id', 'name', 'lattes_id']
    assert len(q_r.rows) == 2  # noqa: PLR2004
    assert q_r.rows[0] == ['r-1', 'Pesquisador Um', '123']

    p_block = {
        'type': 'productions',
        'productions': [
            {
                'id': 'p-1',
                'title': 'Artigo Um',
                'type': 'article',
                'year': 2024,
            }
        ],
        'origin': {'sources': ['Simcc']},
    }
    q_p = result_from_block(p_block, 'h2')
    assert isinstance(q_p, QueryResult)
    assert q_p.result_id == 'h2'
    assert q_p.columns == ['id', 'title', 'type', 'year']
    assert q_p.rows[0] == ['p-1', 'Artigo Um', 'article', 2024]
