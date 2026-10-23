import sqlite3
from datetime import date
from decimal import Decimal

import pytest

from observatorio_maria.catalog.introspection import create_readonly_engine
from observatorio_maria.models import (
    CatalogColumn,
    CatalogDataSource,
    CatalogEntity,
)
from observatorio_maria.query.errors import QueryValidationError
from observatorio_maria.query.execution import (
    QueryTimeoutError,
    ResultStore,
    execute_readonly_query,
    sanitize_purpose,
    serialize_value,
)
from observatorio_maria.query.tool import QueryRunner
from observatorio_maria.query.validator import (
    build_query_schema,
    validate_query,
)


@pytest.fixture
def sqlite_source(tmp_path):
    db_file = tmp_path / 'source.db'
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
                (1, 'Projeto Dengue', 'Dengue e arboviroses.', 2024, 150.5),
                (2, 'Saúde', 'Arboviroses e Saúde.', 2025, 200.0),
                (3, 'Robótica', 'Automação no cacau.', 2024, 80.0);

            CREATE TABLE registros_muitos (
                id INTEGER PRIMARY KEY,
                valor TEXT
            );
        """
        )
        for i in range(1, 15):
            conn.execute(
                'INSERT INTO registros_muitos VALUES (?, ?)',
                (i, f'item_{i}'),
            )
    return str(db_file)


@pytest.fixture
def source_engine(sqlite_source):
    return create_readonly_engine(f'sqlite+aiosqlite:///{sqlite_source}')


@pytest.mark.asyncio
async def test_serialize_values():
    assert serialize_value(Decimal('10.5')) == 10.5  # noqa: PLR2004
    assert serialize_value(Decimal('10.0')) == 10  # noqa: PLR2004
    assert serialize_value(date(2024, 5, 1)) == '2024-05-01'
    assert serialize_value(b'teste') == 'teste'


@pytest.mark.asyncio
async def test_execute_readonly_query_with_truncation(source_engine):
    sql = 'SELECT id, valor FROM registros_muitos ORDER BY id'
    cols, rows, truncated, col_types = await execute_readonly_query(
        source_engine, sql, max_rows=10, timeout_seconds=5.0
    )
    assert cols == ['id', 'valor']
    assert len(rows) == 10  # noqa: PLR2004
    assert truncated is True
    assert col_types['id'] == 'number'
    assert col_types['valor'] == 'string'


@pytest.mark.asyncio
async def test_execute_readonly_query_within_limit(source_engine):
    sql = 'SELECT id, nome, orcamento FROM projetos ORDER BY id'
    cols, rows, truncated, _ = await execute_readonly_query(
        source_engine, sql, max_rows=10, timeout_seconds=5.0
    )
    assert cols == ['id', 'nome', 'orcamento']
    assert len(rows) == 3  # noqa: PLR2004
    assert truncated is False
    assert rows[0][1] == 'Projeto Dengue'


@pytest.mark.asyncio
async def test_execute_readonly_query_blocks_writes(source_engine):
    sql = "INSERT INTO projetos (id, nome) VALUES (99, 'Hack')"
    with pytest.raises(QueryValidationError):
        await execute_readonly_query(source_engine, sql)


@pytest.mark.asyncio
async def test_match_text_against_sqlite_accents(source_engine):
    ds = CatalogDataSource(
        id='teste_ds',
        name='Teste',
        connection_env='TESTE_URL',
        schemas=['main'],
    )
    ent = CatalogEntity(
        datasource_id=ds.id,
        schema_name='main',
        name='projetos',
        visible=True,
        queryable=True,
        present=True,
    )
    ent.columns = [
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
    ]
    query_schema = build_query_schema(ds, [ent], dialect='sqlite')

    # Busca 'dengue'
    sql1 = validate_query(
        "SELECT id, nome FROM projetos WHERE MATCH_TEXT(resumo, 'Dengue')",
        query_schema,
    )
    _, rows1, _, _ = await execute_readonly_query(source_engine, sql1)
    assert len(rows1) == 1
    assert rows1[0][0] == 1

    # Busca 'arboviroses' - deve achar ambos
    sql2 = validate_query(
        'SELECT id, nome FROM projetos '
        "WHERE MATCH_TEXT(resumo, 'arboviroses')",
        query_schema,
    )
    _, rows2, _, _ = await execute_readonly_query(source_engine, sql2)
    assert len(rows2) == 2  # noqa: PLR2004

    # Busca 'Saúde'
    sql3 = validate_query(
        "SELECT id, nome FROM projetos WHERE MATCH_TEXT(resumo, 'saude')",
        query_schema,
    )
    _, rows3, _, _ = await execute_readonly_query(source_engine, sql3)
    assert len(rows3) == 1
    assert rows3[0][0] == 2  # noqa: PLR2004


@pytest.mark.asyncio
async def test_result_store():
    store = ResultStore()
    r1 = store.add(
        'fomento',
        'SELECT 1',
        ['a'],
        [[1]],
        truncated=False,
        column_types={'a': 'number'},
    )
    assert r1.result_id == 'r1'
    r2 = store.add(
        'fomento',
        'SELECT 2',
        ['b'],
        [[2]],
        truncated=True,
        column_types={'b': 'number'},
    )
    assert r2.result_id == 'r2'
    assert store.get('r1') == r1
    assert len(store.all()) == 2  # noqa: PLR2004


@pytest.mark.asyncio
async def test_query_runner_max_per_call(session, sqlite_source, monkeypatch):
    monkeypatch.setenv('TEST_DB_URL', f'sqlite+aiosqlite:///{sqlite_source}')
    ds = CatalogDataSource(
        id='fonte1',
        name='Fonte 1',
        connection_env='TEST_DB_URL',
        schemas=['main'],
    )
    session.add(ds)
    ent = CatalogEntity(
        datasource_id=ds.id,
        schema_name='main',
        name='projetos',
        visible=True,
        queryable=True,
        present=True,
    )
    ent.columns = [
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
    ]
    session.add(ent)
    await session.commit()

    runner = QueryRunner(
        session,
        ResultStore(),
        max_rows=10,
        max_per_call=2,
        calls_left=2,
    )

    # Chamada 1: ok
    res1 = await runner.query_data('fonte1', 'SELECT id FROM projetos')
    assert 'result_id' in res1
    assert res1['result_id'] == 'r1'

    # Chamada 2: ok
    res2 = await runner.query_data('fonte1', 'SELECT nome FROM projetos')
    assert 'result_id' in res2
    assert res2['result_id'] == 'r2'

    # Chamada 3: excede max_per_call (2)
    res3 = await runner.query_data('fonte1', 'SELECT id, nome FROM projetos')
    assert 'error' in res3
    assert 'Limite de consultas por chamada excedido' in res3['error']

    # Reset budget para a próxima chamada
    runner.reset_call_budget(calls_left=1)
    res4 = await runner.query_data('fonte1', 'SELECT id FROM projetos')
    assert 'result_id' in res4

    await runner.close()


@pytest.mark.asyncio
async def test_sanitize_purpose():
    assert (
        sanitize_purpose('Buscando projetos sobre dengue', 'Fomento')
        == 'Buscando projetos sobre dengue'
    )
    assert sanitize_purpose('', 'Fomento') == 'Consultando Fomento'
    assert (
        sanitize_purpose('SELECT * FROM fomento', 'Fomento')
        == 'Consultando Fomento'
    )
    long_purpose = 'A' * 150
    sanitized = sanitize_purpose(long_purpose, 'Fomento')
    assert len(sanitized) == 120  # noqa: PLR2004
    assert sanitized.endswith('...')


@pytest.mark.asyncio
async def test_execute_query_timeout(source_engine):
    with pytest.raises(
        QueryTimeoutError, match='Tempo limite de execução esgotado'
    ):
        await execute_readonly_query(
            source_engine,
            'SELECT 1',
            timeout_seconds=0.00001,
        )


@pytest.mark.asyncio
async def test_unreachable_source_in_query_runner(session, monkeypatch):
    monkeypatch.setenv(
        'BAD_SOURCE_URL',
        'postgresql+psycopg://user:senha_secreta@127.0.0.1:1/nao_existe',
    )
    ds = CatalogDataSource(
        id='fonte_quebrada',
        name='Fonte Quebrada',
        connection_env='BAD_SOURCE_URL',
        schemas=['public'],
    )
    session.add(ds)
    await session.commit()

    runner = QueryRunner(session, ResultStore(), calls_left=1)
    res = await runner.query_data('fonte_quebrada', 'SELECT 1')
    assert 'error' in res
    assert 'senha_secreta' not in res['error']
    assert '127.0.0.1' not in res['error']
    await runner.close()
