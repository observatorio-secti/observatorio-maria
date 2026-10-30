import asyncio
import sqlite3
import time

import duckdb
import pytest

from observatorio_maria.catalog.introspection import SourceUnavailableError
from observatorio_maria.query import federation
from observatorio_maria.query.errors import QueryValidationError
from observatorio_maria.query.execution import QueryTimeoutError
from observatorio_maria.query.federated_validator import (
    CoverageQuery,
    FederatedQuery,
)
from observatorio_maria.query.federation import (
    FederationLimits,
    execute_federated_query,
)


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


@pytest.fixture
def urls(tmp_path):
    fomento = tmp_path / 'fomento.db'
    simcc = tmp_path / 'simcc.db'
    with sqlite3.connect(fomento) as conn:
        conn.executescript(
            """
            CREATE TABLE pesquisadores (
                id INTEGER, lattes TEXT, modalidade TEXT
            );
            INSERT INTO pesquisadores VALUES
                (1, 'L1', 'Doutorado'), (2, 'L2', 'Doutorado'),
                (3, 'L3', 'Mestrado'), (4, NULL, 'Mestrado');
            """
        )
    with sqlite3.connect(simcc) as conn:
        conn.executescript(
            """
            CREATE TABLE researcher (lattes_id TEXT, artigos INTEGER);
            INSERT INTO researcher VALUES ('L1', 5), ('L3', 2), ('L9', 7);
            """
        )
    return {
        'fomento': f'sqlite+aiosqlite:///{fomento}',
        'simcc': f'sqlite+aiosqlite:///{simcc}',
    }


JOIN = (
    'SELECT p.modalidade, SUM(r.artigos) AS artigos '
    'FROM fomento.main.pesquisadores p '
    'JOIN simcc.main.researcher r ON r.lattes_id = p.lattes '
    'GROUP BY p.modalidade ORDER BY p.modalidade'
)
COVERAGE = (
    'SELECT COUNT(DISTINCT p.lattes) AS total, '
    'COUNT(DISTINCT CASE WHEN p.lattes IN '
    '(SELECT lattes_id FROM simcc.main.researcher) THEN p.lattes END) '
    'AS found '
    'FROM fomento.main.pesquisadores p'
)


def query(sql=JOIN, coverage=COVERAGE):
    return FederatedQuery(
        sql=sql,
        sources=('fomento', 'simcc'),
        coverage=CoverageQuery(coverage, 'fomento', 'simcc'),
    )


@integration
async def test_join_and_aggregate_between_sources(urls):
    result = await execute_federated_query(query(), urls, FederationLimits())

    assert result.columns == ['modalidade', 'artigos']
    assert result.rows == [['Doutorado', 5], ['Mestrado', 2]]
    assert result.truncated is False
    assert result.coverage == {
        'available': True,
        'source': 'fomento',
        'target': 'simcc',
        'keys': 3,
        'found': 2,
    }


@integration
async def test_rows_are_truncated(urls):
    sql = 'SELECT id FROM fomento.main.pesquisadores ORDER BY id'

    result = await execute_federated_query(
        query(sql), urls, FederationLimits(max_rows=2)
    )

    assert result.rows == [[1], [2]]
    assert result.truncated is True


@integration
@pytest.mark.parametrize(
    'sql',
    [
        "SET memory_limit='4GB'",
        "SELECT * FROM read_csv('/etc/passwd')",
        "INSERT INTO fomento.main.pesquisadores VALUES (9, 'x', 'y')",
        'CREATE TABLE simcc.main.nova (a INTEGER)',
    ],
)
async def test_session_is_locked_and_sources_read_only(urls, sql):
    # O validador já recusa estas instruções; aqui o executor é a última
    # barreira. As origens são arquivos temporários.
    execution = federation._Execution(query(), urls, FederationLimits())
    connection = execution._connect()
    try:
        with pytest.raises(duckdb.Error):
            connection.execute(sql)
    finally:
        connection.close()


@integration
async def test_timeout_interrupts_query(urls):
    sql = 'SELECT COUNT(*) AS n FROM range(10000000000000) a, range(100000) b'

    started = time.monotonic()
    with pytest.raises(QueryTimeoutError):
        await execute_federated_query(
            query(sql), urls, FederationLimits(timeout_seconds=0.3)
        )

    assert time.monotonic() - started < 4  # noqa: PLR2004


@integration
async def test_memory_limit_gives_guidance(urls):
    sql = (
        'SELECT COUNT(*) AS n FROM (SELECT DISTINCT i, '
        'repeat(CAST(i AS TEXT), 50) FROM range(20000000) t(i))'
    )

    with pytest.raises(QueryValidationError, match='limite de memória'):
        await execute_federated_query(
            query(sql),
            urls,
            FederationLimits(memory_limit='32MB', timeout_seconds=30),
        )


@integration
async def test_third_query_waits_for_a_slot(urls, monkeypatch):
    running = 0
    peak = 0
    original = federation._Execution._execute

    def tracked(self):
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        time.sleep(0.1)
        try:
            return original(self)
        finally:
            running -= 1

    monkeypatch.setattr(federation._Execution, '_execute', tracked)
    limits = FederationLimits(max_concurrent=2)

    await asyncio.gather(
        *(execute_federated_query(query(), urls, limits) for _ in range(3))
    )

    assert peak == 2  # noqa: PLR2004


@integration
async def test_unavailable_source_does_not_leak_url():
    secret = 'postgresql+psycopg://usuario:segredo@127.0.0.1:1/banco'

    with pytest.raises(SourceUnavailableError) as exc:
        await execute_federated_query(
            query(), {'fomento': secret}, FederationLimits()
        )

    assert 'segredo' not in str(exc.value)


@integration
async def test_coverage_failure_keeps_result(urls):
    result = await execute_federated_query(
        query(coverage='SELECT nao_existe FROM fomento.main.pesquisadores'),
        urls,
        FederationLimits(),
    )

    assert result.rows
    assert result.coverage['available'] is False


@integration
async def test_coverage_reason_when_not_flat(urls):
    plain = FederatedQuery(
        sql=JOIN, sources=('fomento', 'simcc'), coverage_reason='CTE'
    )

    result = await execute_federated_query(plain, urls, FederationLimits())

    assert result.coverage == {'available': False, 'reason': 'CTE'}


def test_attach_limits_postgres_connection():
    sql = federation._attach_statement(
        'simcc',
        "postgresql+psycopg://u:p'w@read_db:5432/simcc",
        15000,
    )

    assert 'statement_timeout=15000' in sql
    assert 'default_transaction_read_only=on' in sql
    assert "password=''p\\''w''" in sql
    assert '(TYPE postgres, READ_ONLY)' in sql
