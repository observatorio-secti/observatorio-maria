from decimal import Decimal

import pytest
from langchain_core.runnables import RunnableLambda

from observatorio_maria.evaluation.checks import (
    answer_texts,
    check_list,
    check_numbers,
    check_sources,
    extract_numbers,
)
from observatorio_maria.evaluation.judge import JudgeVerdict, judge_answer
from observatorio_maria.evaluation.reference import (
    JudgeCheck,
    ListCheck,
    NumbersCheck,
    SourcesCheck,
)
from observatorio_maria.query.tool import QueryObservation


def numbers(*values):
    return NumbersCheck(type='numbers', values=list(values))


def test_answer_texts_reads_text_table_and_chart():
    blocks = [
        {'type': 'text', 'text': 'Foram 3.653 bolsistas.'},
        {'type': 'table', 'rows': [{'titulo': 'Artigo A', 'ano': 2024}]},
        {'type': 'chart', 'data': [{'ano': 2025, 'artigos': 29}]},
    ]

    texts = answer_texts(blocks)

    assert extract_numbers(texts) >= {
        Decimal(3653),
        Decimal(2024),
        Decimal(2025),
        Decimal(29),
    }
    assert 'Artigo A' in texts


def test_number_with_thousand_separator_passes():
    result = check_numbers(numbers(3653), ['Foram 3.653 bolsistas'])

    assert result.status == 'passed'


def test_number_with_decimal_comma_passes():
    result = check_numbers(numbers(Decimal('1234.5')), ['Total: 1.234,5'])

    assert result.status == 'passed'


def test_plain_and_machine_numbers_pass():
    texts = ['2020: 16, 2021: 19', '150.0']

    assert check_numbers(numbers(16, 19, 150), texts).status == 'passed'


def test_missing_number_fails_with_expected_value():
    result = check_numbers(numbers(20), ['Encontrei 19 artigos.'])

    assert result.status == 'failed'
    assert '20' in result.detail


def test_number_inside_bigger_number_does_not_count():
    result = check_numbers(numbers(20), ['Lattes 1234567890123456; 2020'])

    assert result.status == 'failed'


def titles(count):
    return [f'Título número {i}' for i in range(count)]


def test_complete_list_passes():
    check = ListCheck(type='list', items=titles(20))

    result = check_list(check, ['\n'.join(titles(20))])

    assert result.status == 'passed'
    assert '20/20' in result.detail


def test_incomplete_list_fails_with_count():
    check = ListCheck(type='list', items=titles(20), min_ratio=0.9)

    result = check_list(check, ['\n'.join(titles(15))])

    assert result.status == 'failed'
    assert '15/20' in result.detail


def test_list_ignores_case_accents_and_spaces():
    check = ListCheck(type='list', items=['Análise  da Dengue na Bahia'])

    result = check_list(check, ['ANALISE DA DENGUE\nNA BAHIA'])

    assert result.status == 'passed'


def test_list_ignores_typographic_dashes():
    check = ListCheck(type='list', items=['Covid-19 Outcomes - A Study'])

    result = check_list(check, ['COVID‑19 Outcomes – A Study'])

    assert result.status == 'passed'


def observation(source, error=None):
    return QueryObservation(
        source=source, sql='SELECT 1', row_count=1, error=error
    )


def test_required_source_consulted_passes():
    check = SourcesCheck(type='sources', required=['simcc'])

    result = check_sources(check, [observation('simcc')])

    assert result.status == 'passed'


def test_forbidden_source_consulted_fails_listing_sources():
    check = SourcesCheck(
        type='sources', required=['fomento'], forbidden=['simcc']
    )

    result = check_sources(
        check, [observation('fomento'), observation('simcc')]
    )

    assert result.status == 'failed'
    assert 'fomento, simcc' in result.detail


def test_failed_query_does_not_count_as_consulted():
    check = SourcesCheck(type='sources', required=['simcc'])

    result = check_sources(check, [observation('simcc', error='inválida')])

    assert result.status == 'failed'
    assert 'não consultou simcc' in result.detail


def test_across_sources_query_counts_for_both_sources():
    check = SourcesCheck(type='sources', required=['fomento', 'simcc'])
    query = QueryObservation(
        source='fomento+simcc',
        sql='SELECT 1',
        row_count=1,
        sources=('fomento', 'simcc'),
    )

    assert check_sources(check, [query]).status == 'passed'


class FakeJudgeModel:
    """Modelo-juiz falso com saída estruturada."""

    def __init__(self, verdict=None, error=None):
        self.verdict = verdict
        self.error = error
        self.prompts = []

    def with_structured_output(self, schema):
        assert schema is JudgeVerdict

        def answer(messages):
            self.prompts.append(messages)
            if self.error:
                raise self.error
            return self.verdict

        return RunnableLambda(answer)


LIMIT = JudgeCheck(type='judge', criterion='declara o limite')


@pytest.mark.asyncio
async def test_judge_approves():
    model = FakeJudgeModel(JudgeVerdict(passed=True, reason='Explica.'))

    result = await judge_answer(model, 'Pergunta?', 'Não é possível.', LIMIT)

    assert result.status == 'passed'
    assert result.detail == 'Explica.'
    prompt = model.prompts[0][-1].content
    assert 'declara o limite' in prompt
    assert 'Não é possível.' in prompt


@pytest.mark.asyncio
async def test_judge_rejects():
    model = FakeJudgeModel(JudgeVerdict(passed=False, reason='Inventou.'))

    result = await judge_answer(model, 'Pergunta?', '42.', LIMIT)

    assert result.status == 'failed'
    assert result.detail == 'Inventou.'


@pytest.mark.asyncio
async def test_judge_failure_is_error():
    model = FakeJudgeModel(error=RuntimeError('provedor indisponível'))

    result = await judge_answer(model, 'Pergunta?', 'Resposta.', LIMIT)

    assert result.status == 'error'
    assert 'provedor indisponível' in result.detail
