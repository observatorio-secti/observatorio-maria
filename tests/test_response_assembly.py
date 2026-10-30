import pytest

from observatorio_maria.services.assembly import (
    ResponseAssembler,
    plain_text,
)

CHART_A = {'type': 'chart', 'title': 'A'}
CHART_B = {'type': 'chart', 'title': 'B'}


def assemble(chunks, pending):
    assembler = ResponseAssembler()
    deltas = []
    for chunk in chunks:
        deltas += assembler.add_text(chunk, pending)
    deltas += assembler.finish(pending)
    return assembler.blocks, deltas


def shape(blocks):
    return [b.get('text') or b['title'] for b in blocks]


def test_blocks_are_placed_between_texts():
    blocks, _ = assemble(
        ['Um. [[bloco:2]] Dois. [[bloco:1]]'], [CHART_A, CHART_B]
    )

    assert shape(blocks) == ['Um.', 'B', 'Dois.', 'A']


def test_uncited_block_comes_after_the_text():
    blocks, _ = assemble(['Um. [[bloco:2]] Dois.'], [CHART_A, CHART_B])

    assert shape(blocks) == ['Um.', 'B', 'Dois.', 'A']


def test_text_without_markers_comes_first():
    blocks, _ = assemble(['Texto.'], [CHART_A, CHART_B])

    assert shape(blocks) == ['Texto.', 'A', 'B']


@pytest.mark.parametrize('marker', ['[[bloco:9]]', '[[bloco:0]]'])
def test_unknown_block_marker_is_removed(marker):
    blocks, deltas = assemble([f'Um. {marker} Dois.'], [CHART_A])

    assert shape(blocks) == ['Um.  Dois.', 'A']
    assert all('bloco' not in (d.text or '') for d in deltas)


def test_repeated_marker_keeps_one_block():
    blocks, _ = assemble(['[[bloco:1]] Meio. [[bloco:1]] Fim.'], [CHART_A])

    assert shape(blocks) == ['A', 'Meio.  Fim.']


def test_empty_texts_are_dropped():
    blocks, _ = assemble(['  [[bloco:1]]\n\n'], [CHART_A])

    assert shape(blocks) == ['A']


TEXT = 'Antes [[bloco:1]] depois'


@pytest.mark.parametrize('cut', range(1, len(TEXT)))
def test_marker_split_at_any_point_never_leaks(cut):
    blocks, deltas = assemble([TEXT[:cut], TEXT[cut:]], [CHART_A])

    assert shape(blocks) == ['Antes', 'A', 'depois']
    assert all(
        not set(d.text or '') & set('[]') and 'bloco' not in (d.text or '')
        for d in deltas
    )


def test_character_by_character_stream_keeps_indexes_in_order():
    _, deltas = assemble(list(TEXT), [CHART_A])

    assert [d.index for d in deltas] == sorted(d.index for d in deltas)


@pytest.mark.parametrize(
    'text',
    ['Referência [1', 'Lista [a] e [[outra]]', 'Fim [[', 'Quase [[bloco:12'],
)
def test_common_brackets_are_kept(text):
    blocks, deltas = assemble([text], [])

    assert shape(blocks) == [text]
    assert ''.join(d.text or '' for d in deltas) == text


def test_plain_text_removes_markers():
    assert plain_text('Um.\n[[bloco:1]]\nDois.') == 'Um.\n\nDois.'
