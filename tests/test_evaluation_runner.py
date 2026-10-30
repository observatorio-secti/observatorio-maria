import asyncio
import json
import sqlite3

import pytest
from langchain_core.messages import AIMessage
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from observatorio_maria.evaluation import __main__ as cli
from observatorio_maria.evaluation.reference import (
    ReferenceQuestion,
    load_reference_file,
)
from observatorio_maria.evaluation.report import (
    build_report,
    format_summary,
    summarize,
    write_report,
)
from observatorio_maria.evaluation.runner import (
    EvaluationError,
    maria_database_copy,
    run_evaluation,
)
from observatorio_maria.evaluation.verify import (
    check_expected,
    compare_result,
    sql_literals,
    verify_question,
)
from observatorio_maria.llm.registry import (
    ModelRegistry,
    ModelTier,
    RegisteredModel,
)
from observatorio_maria.models import Conversation, table_registry
from observatorio_maria.query.execution import QueryResult
from observatorio_maria.settings import Settings
from tests.conftest import FailingChatModel, ScriptedToolChatModel
from tests.test_agent_chat import setup_catalog

SOURCE_URL_ENV = 'TEST_FOMENTO_URL'


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
    url = f'sqlite+aiosqlite:///{db_file}'
    monkeypatch.setenv(SOURCE_URL_ENV, url)
    return url


@pytest.fixture
async def maria_db(tmp_path, fomento_source):
    """Banco da Maria em arquivo, com o catálogo da fonte `fomento`."""
    path = tmp_path / 'maria.db'
    url = f'sqlite+aiosqlite:///{path}'
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(table_registry.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        await setup_catalog(session, SOURCE_URL_ENV)
    await engine.dispose()
    return url


async def count_conversations(url):
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        total = await conn.scalar(
            select(func.count()).select_from(Conversation)
        )
    await engine.dispose()
    return total


def registry_with(model):
    return ModelRegistry([
        RegisteredModel(tier, f'fake:{tier}', model) for tier in ModelTier
    ])


def query_turn(sql):
    return AIMessage(
        content='',
        tool_calls=[
            {
                'name': 'query_data',
                'args': {'source': 'fomento', 'sql': sql, 'purpose': 'Busca'},
                'id': 'c1',
            }
        ],
    )


def question(**overrides):
    data = {
        'id': 'projetos-dengue',
        'question': 'Quantos projetos sobre dengue existem?',
        'tags': ['busca-textual'],
        'checks': [
            {'type': 'sources', 'required': ['fomento']},
            {'type': 'numbers', 'values': [2]},
        ],
    }
    return ReferenceQuestion.model_validate({**data, **overrides})


DENGUE_SQL = (
    "SELECT COUNT(*) AS total FROM projetos WHERE MATCH_TEXT(resumo, 'dengue')"
)


@pytest.mark.asyncio
async def test_right_answer_passes_and_records_metrics(maria_db):
    model = ScriptedToolChatModel(
        responses=[query_turn(DENGUE_SQL), AIMessage('Existem 2 projetos.')]
    )

    (run,) = await run_evaluation(
        [question()],
        registry=registry_with(model),
        database_url=maria_db,
        settings=Settings(),
    )

    assert run.status == 'passed'
    assert [c.status for c in run.checks] == ['passed', 'passed']
    assert run.model_calls == 2  # noqa: PLR2004
    assert run.queries[0].source == 'fomento'
    assert run.answer[0]['text'] == 'Existem 2 projetos.'


@pytest.mark.asyncio
async def test_wrong_answer_fails(maria_db):
    model = ScriptedToolChatModel(responses=[AIMessage('Existem 5 projetos.')])

    (run,) = await run_evaluation(
        [question()],
        registry=registry_with(model),
        database_url=maria_db,
        settings=Settings(),
    )

    assert run.status == 'failed'
    sources, numbers = run.checks
    assert 'não consultou fomento' in sources.detail
    assert numbers.status == 'failed'


@pytest.mark.asyncio
async def test_model_failure_is_error_and_next_question_runs(maria_db):
    runs = await run_evaluation(
        [question(), question(id='outra')],
        registry=registry_with(FailingChatModel()),
        database_url=maria_db,
        settings=Settings(),
        repeat=2,
    )

    assert len(runs) == 4  # noqa: PLR2004
    assert {r.status for r in runs} == {'error'}
    assert all(r.error for r in runs)


@pytest.mark.asyncio
async def test_original_database_keeps_no_conversations(maria_db):
    model = ScriptedToolChatModel(responses=[AIMessage('2')])

    await run_evaluation(
        [question()],
        registry=registry_with(model),
        database_url=maria_db,
        settings=Settings(),
    )

    assert await count_conversations(maria_db) == 0


@pytest.mark.asyncio
async def test_non_sqlite_database_is_rejected():
    with pytest.raises(EvaluationError, match='SQLite'):
        async with maria_database_copy(
            'postgresql+psycopg://u:p@localhost/maria'
        ):
            pass


@pytest.mark.asyncio
async def test_report_has_fields_and_no_connection_urls(
    maria_db, fomento_source, tmp_path
):
    model = ScriptedToolChatModel(
        responses=[query_turn(DENGUE_SQL), AIMessage('São 2.')]
    )
    registry = registry_with(model)
    questions = [question()]
    runs = await run_evaluation(
        questions,
        registry=registry,
        database_url=maria_db,
        settings=Settings(),
    )
    from datetime import UTC, datetime  # noqa: PLC0415

    report = build_report(questions, runs, registry, datetime.now(UTC))
    path = write_report(report, tmp_path / 'results')

    data = json.loads(path.read_text(encoding='utf-8'))
    assert data['passed'] == 1
    assert data['models']['medium'] == 'fake:medium'
    (entry,) = data['questions']
    assert entry['question_id'] == 'projetos-dengue'
    assert entry['results'][0]['queries'][0]['sql']
    raw = path.read_text(encoding='utf-8')
    assert fomento_source not in raw
    assert maria_db not in raw
    assert '1/1' in format_summary(summarize(questions, runs))


def test_sql_literals():
    assert sql_literals([]) == 'NULL'
    assert sql_literals([1, "O'Neil", None]) == "1, 'O''Neil', NULL"


async def run_check(maria_db, questions):
    async with maria_database_copy(maria_db) as session_factory:
        return await check_expected(
            questions, session_factory=session_factory, settings=Settings()
        )


@pytest.mark.asyncio
async def test_check_expected_equal_value_is_ok(maria_db):
    q = question(
        verify=[{'source': 'fomento', 'sql': DENGUE_SQL}],
    )

    (result,) = await run_check(maria_db, [q])

    assert result.status == 'ok'


@pytest.mark.asyncio
async def test_check_expected_reports_divergence(maria_db):
    q = question(
        checks=[{'type': 'numbers', 'values': [29]}],
        verify=[{'source': 'fomento', 'sql': DENGUE_SQL}],
    )

    (result,) = await run_check(maria_db, [q])

    assert result.status == 'divergent'
    assert '29' in result.details[0]
    assert 'atual: 2' in result.details[0]


@pytest.mark.asyncio
async def test_check_expected_in_two_steps(maria_db):
    q = question(
        checks=[
            {'type': 'numbers', 'values': [350, 2]},
            {'type': 'list', 'items': ['Dengue Bahia', 'Prevenção Dengue']},
        ],
        verify=[
            {
                'source': 'fomento',
                'sql': (
                    'SELECT id FROM projetos '
                    "WHERE MATCH_TEXT(resumo, 'dengue')"
                ),
            },
            {
                'source': 'fomento',
                'sql': (
                    'SELECT nome, SUM(orcamento) OVER () AS total, '
                    '{previous_count} AS encontrados '
                    'FROM projetos WHERE id IN ({previous})'
                ),
            },
        ],
    )

    (result,) = await run_check(maria_db, [q])

    assert result.status == 'ok', result.details


@pytest.mark.asyncio
async def test_check_expected_skips_question_without_verify(maria_db):
    (result,) = await run_check(maria_db, [question()])

    assert result.status == 'skipped'


def fake_result(rows):
    return QueryResult(
        result_id='r1',
        source='a+b',
        sql='SELECT 1',
        columns=['n'],
        rows=rows,
        truncated=False,
    )


def test_coverage_counts_as_expected_number():
    q = question(checks=[{'type': 'numbers', 'values': [119, 26, 3653]}])
    coverage = {'available': True, 'keys': 3653, 'found': 26}

    result = compare_result(q, fake_result([[119]]), None, coverage)

    assert result.status == 'ok'


def test_federated_step_uses_consulta_entre_fontes():
    class Runner:
        def __init__(self):
            self.calls = []

        async def query_across_sources(self, sql):
            self.calls.append(sql)
            return {'result_id': 'r1', 'coverage': None}

    class Store:
        @staticmethod
        def get(result_id):
            return fake_result([[2]])

    q = question(
        checks=[{'type': 'numbers', 'values': [2]}],
        verify=[{'source': 'federated', 'sql': 'SELECT 2 AS n'}],
    )
    runner = Runner()

    result = asyncio.run(verify_question(runner, Store(), q))

    assert result.status == 'ok'
    assert runner.calls == ['SELECT 2 AS n']


def write_reference(tmp_path):
    path = tmp_path / 'reference.yaml'
    path.write_text(
        """
questions:
  - id: projetos-dengue
    question: Quantos projetos sobre dengue existem?
    tags: [busca-textual]
    checks:
      - type: numbers
        values: [2]
    verify:
      - source: fomento
        sql: SELECT COUNT(*) FROM projetos WHERE MATCH_TEXT(resumo, 'dengue')
  - id: outra
    question: Outra?
    tags: [outra]
    checks:
      - type: numbers
        values: [1]
""",
        encoding='utf-8',
    )
    return path


def test_cli_rejects_invalid_arguments(tmp_path):
    with pytest.raises(SystemExit) as exc:
        cli.main(['--repeat', '0'])
    assert exc.value.code != 0

    missing = tmp_path / 'nao-existe.yaml'
    assert cli.main(['--file', str(missing), '--check-expected']) == 1
    reference = write_reference(tmp_path)
    assert cli.main(['--file', str(reference), '--question', 'xyz']) == 1


def test_cli_filters_by_id_and_tag(tmp_path, maria_db, monkeypatch, capsys):
    monkeypatch.setenv('DATABASE_URL', maria_db)
    reference = write_reference(tmp_path)

    code = cli.main([
        '--file',
        str(reference),
        '--tag',
        'busca-textual',
        '--check-expected',
    ])

    output = capsys.readouterr().out
    assert code == 0
    assert 'projetos-dengue  ok' in output
    assert 'outra' not in output

    code = cli.main([
        '--file',
        str(reference),
        '--question',
        'outra',
        '--check-expected',
    ])

    output = capsys.readouterr().out
    assert code == 0
    assert 'sem conferência' in output
    assert 'projetos-dengue' not in output


def test_reference_file_of_the_repository_is_valid():
    questions = load_reference_file(cli.DEFAULT_FILE)

    assert len(questions) >= 4  # noqa: PLR2004
