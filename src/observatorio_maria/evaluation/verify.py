"""Conferência das respostas esperadas contra os bancos de origem.

Executa as consultas `verify` de cada pergunta, sem modelo, pelo mesmo
validador e conexão somente leitura do agente, e aponta as perguntas cuja
resposta esperada não bate mais com os dados. Nunca altera o arquivo.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal

from observatorio_maria.evaluation.checks import (
    extract_numbers,
    normalize_text,
    parse_number,
)
from observatorio_maria.evaluation.reference import (
    ListCheck,
    NumbersCheck,
    ReferenceQuestion,
)
from observatorio_maria.evaluation.runner import SessionFactory
from observatorio_maria.query.execution import QueryResult, ResultStore
from observatorio_maria.query.tool import QueryRunner
from observatorio_maria.settings import Settings

ExpectedStatus = Literal['ok', 'divergent', 'error', 'skipped']

# Fonte de uma etapa de conferência que é consulta entre fontes.
FEDERATED_SOURCE = 'federated'

# Quantos valores atuais mostrar quando a resposta esperada diverge.
MAX_SHOWN_VALUES = 20


@dataclass
class ExpectedCheck:
    question_id: str
    status: ExpectedStatus
    details: list[str] = field(default_factory=list)


def sql_literals(values: list[Any]) -> str:
    """Valores como lista de literais SQL; vazia vira NULL (casa nada)."""
    if not values:
        return 'NULL'
    literals = []
    for value in values:
        if value is None:
            literals.append('NULL')
        elif isinstance(value, int | float | Decimal) and not isinstance(
            value, bool
        ):
            literals.append(str(value))
        else:
            literals.append("'" + str(value).replace("'", "''") + "'")
    return ', '.join(literals)


def _numbers_in(cells: list[Any]) -> set[Decimal]:
    numbers = set()
    for cell in cells:
        if isinstance(cell, int | float | Decimal) and not isinstance(
            cell, bool
        ):
            numbers.add(Decimal(str(cell)))
        elif isinstance(cell, str) and (number := parse_number(cell)):
            numbers.add(number)
        elif cell is not None:
            numbers |= extract_numbers([str(cell)])
    return numbers


def _show(values: list[str]) -> str:
    shown = ', '.join(values[:MAX_SHOWN_VALUES])
    if len(values) > MAX_SHOWN_VALUES:
        shown += f' … (+{len(values) - MAX_SHOWN_VALUES})'
    return shown or 'nenhum'


def compare_result(
    question: ReferenceQuestion,
    result: QueryResult,
    column: str | None,
    coverage: dict[str, Any] | None = None,
) -> ExpectedCheck:
    """Compara a última etapa com os critérios `numbers` e `list`."""
    if column and column not in result.columns:
        return ExpectedCheck(
            question.id,
            'error',
            [f'Coluna "{column}" ausente na última etapa.'],
        )
    index = result.columns.index(column) if column else 0
    details = []
    divergent = False
    for check in question.checks:
        match check:
            case NumbersCheck():
                cells = (
                    [row[index] for row in result.rows]
                    if column
                    else [cell for row in result.rows for cell in row]
                )
                # A cobertura também é resposta esperada ("2 de 20").
                if coverage and coverage.get('available'):
                    cells = [*cells, coverage['keys'], coverage['found']]
                actual = _numbers_in(cells)
                missing = [v for v in check.values if v not in actual]
                if missing:
                    divergent = True
                    details.append(
                        'numbers: esperado(s) '
                        + _show([format(v.normalize(), 'f') for v in missing])
                        + '; atual: '
                        + _show(
                            sorted(format(v.normalize(), 'f') for v in actual)
                        )
                    )
            case ListCheck():
                actual = {
                    normalize_text(str(row[index]))
                    for row in result.rows
                    if row[index] is not None
                }
                expected = {normalize_text(i) for i in check.items}
                missing = sorted(expected - actual)
                extra = sorted(actual - expected)
                if missing or extra:
                    divergent = True
                    details.append(
                        f'list: {len(missing)} ausente(s) nos dados '
                        f'({_show(missing)}); {len(extra)} novo(s) '
                        f'({_show(extra)})'
                    )
    if result.truncated:
        details.append(
            f'A última etapa foi truncada em {len(result.rows)} linhas.'
        )
    return ExpectedCheck(
        question.id, 'divergent' if divergent else 'ok', details
    )


async def verify_question(
    runner: QueryRunner, store: ResultStore, question: ReferenceQuestion
) -> ExpectedCheck:
    if not question.verify:
        return ExpectedCheck(
            question.id, 'skipped', ['Sem consultas de conferência.']
        )
    previous: list[Any] = []
    result: QueryResult | None = None
    coverage: dict[str, Any] | None = None
    for number, step in enumerate(question.verify, start=1):
        sql = step.sql.replace('{previous}', sql_literals(previous)).replace(
            '{previous_count}', str(len(previous))
        )
        if step.source == FEDERATED_SOURCE:
            response = await runner.query_across_sources(sql)
        else:
            response = await runner.query_data(step.source, sql)
        if 'error' in response:
            return ExpectedCheck(
                question.id, 'error', [f'Etapa {number}: {response["error"]}']
            )
        result = store.get(response['result_id'])
        coverage = response.get('coverage')
        previous = [row[0] for row in result.rows]
    return compare_result(
        question, result, question.verify[-1].column, coverage
    )


async def check_expected(
    questions: list[ReferenceQuestion],
    *,
    session_factory: SessionFactory,
    settings: Settings,
) -> list[ExpectedCheck]:
    results = []
    async with session_factory() as session:
        store = ResultStore()
        runner = QueryRunner(
            session,
            store,
            max_rows=settings.QUERY_MAX_ROWS,
            timeout_seconds=settings.QUERY_TIMEOUT_SECONDS,
            max_cost=settings.QUERY_MAX_ESTIMATED_COST,
            # A conferência não tem orçamento de chamadas do agente.
            max_per_call=10**9,
        )
        try:
            for question in questions:
                results.append(await verify_question(runner, store, question))
        finally:
            await runner.close()
    return results


def format_expected(results: list[ExpectedCheck]) -> str:
    labels = {
        'ok': 'ok',
        'divergent': 'divergente',
        'error': 'erro',
        'skipped': 'sem conferência',
    }
    width = max((len(r.question_id) for r in results), default=10)
    lines = []
    for r in results:
        lines.append(f'{r.question_id:<{width}}  {labels[r.status]}')
        lines.extend(f'    {detail}' for detail in r.details)
    counts = {s: sum(r.status == s for r in results) for s in labels}
    lines.append('')
    lines.append(
        f'Conferidas: {counts["ok"]} ok, {counts["divergent"]} divergente(s), '
        f'{counts["error"]} erro(s), {counts["skipped"]} sem conferência'
    )
    return '\n'.join(lines)
