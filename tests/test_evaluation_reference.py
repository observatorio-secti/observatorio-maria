from decimal import Decimal

import pytest

from observatorio_maria.evaluation.reference import (
    NumbersCheck,
    ReferenceFileError,
    load_reference_file,
    select_questions,
)

VALID = """
questions:
  - id: artigos-por-ano
    question: Quantos artigos por ano?
    tags: [simcc-totais, exemplo]
    checks:
      - type: sources
        required: [simcc]
        forbidden: [fomento]
      - type: numbers
        values: [16, 19]
    verify:
      - source: simcc
        sql: SELECT 16
  - id: limite
    question: Quantos artigos de todos os bolsistas?
    tags: [entre-fontes]
    checks:
      - type: judge
        criterion: declara o limite
      - type: list
        items: [A, B]
        min_ratio: 0.5
"""


def write(tmp_path, content):
    path = tmp_path / 'reference.yaml'
    path.write_text(content, encoding='utf-8')
    return path


def test_valid_file_is_loaded(tmp_path):
    questions = load_reference_file(write(tmp_path, VALID))

    assert [q.id for q in questions] == ['artigos-por-ano', 'limite']
    first = questions[0]
    assert first.tags == ['simcc-totais', 'exemplo']
    assert isinstance(first.checks[1], NumbersCheck)
    assert first.checks[1].values == [Decimal(16), Decimal(19)]
    assert first.verify[0].source == 'simcc'
    assert questions[1].checks[1].min_ratio == 0.5  # noqa: PLR2004


def test_repeated_id_is_rejected(tmp_path):
    content = VALID.replace('id: limite', 'id: artigos-por-ano')

    with pytest.raises(
        ReferenceFileError, match='"artigos-por-ano".*repetido'
    ):
        load_reference_file(write(tmp_path, content))


def test_unknown_check_type_is_rejected(tmp_path):
    content = VALID.replace('type: judge', 'type: regex')

    with pytest.raises(ReferenceFileError, match='"limite"'):
        load_reference_file(write(tmp_path, content))


def test_question_without_checks_is_rejected(tmp_path):
    content = """
questions:
  - id: sem-criterio
    question: Pergunta?
    checks: []
"""
    with pytest.raises(ReferenceFileError, match='"sem-criterio".*checks'):
        load_reference_file(write(tmp_path, content))


def test_missing_file_is_rejected(tmp_path):
    with pytest.raises(ReferenceFileError, match='Não foi possível ler'):
        load_reference_file(tmp_path / 'nao-existe.yaml')


def test_select_by_id_and_tag(tmp_path):
    questions = load_reference_file(write(tmp_path, VALID))

    assert len(select_questions(questions)) == 2  # noqa: PLR2004
    assert [q.id for q in select_questions(questions, ids=['limite'])] == [
        'limite'
    ]
    assert [q.id for q in select_questions(questions, tags=['exemplo'])] == [
        'artigos-por-ano'
    ]
    with pytest.raises(ReferenceFileError, match='inexistente.*outra'):
        select_questions(questions, ids=['outra'])
