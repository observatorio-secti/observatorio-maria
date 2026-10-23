import pytest

from observatorio_maria.catalog.context import render_context
from observatorio_maria.catalog.introspection import introspect
from observatorio_maria.catalog.sync import (
    load_entities,
    load_relationships,
    sync_datasource,
)
from observatorio_maria.models import ColumnAccess


@pytest.fixture
async def synced(session, datasource, source_db):
    """Fonte sincronizada com `bolsas` e `pesquisadores` visíveis."""
    await sync_datasource(
        session,
        datasource,
        await introspect(f'sqlite+aiosqlite:///{source_db}', ['main']),
    )
    entities = {e.name: e for e in await load_entities(session, 'origem')}
    for name in ('bolsas', 'pesquisadores'):
        entities[name].visible = entities[name].queryable = True
        for column in entities[name].columns:
            column.visible = True
    await session.commit()
    return entities


async def context(session, datasource):
    return render_context(
        datasource,
        await load_entities(session, datasource.id),
        await load_relationships(session, datasource.id),
    )


async def test_hidden_entities_and_columns_stay_out(
    session, datasource, synced
):
    synced['pesquisadores'].columns[2].visible = False  # lattes
    await session.commit()

    text = await context(session, datasource)

    assert '`main.bolsas` (tabela)' in text
    assert '`main.pesquisadores` (tabela)' in text
    assert 'instituicoes' not in text
    assert 'bolsas_por_status' not in text
    assert '`nome`' in text
    assert 'lattes' not in text


async def test_missing_items_stay_out(session, datasource, synced):
    synced['pesquisadores'].present = False
    synced['bolsas'].columns[1].present = False  # status
    await session.commit()

    text = await context(session, datasource)

    assert 'pesquisadores' not in text
    assert '`status`' not in text


async def test_editorial_details_are_rendered(session, datasource, synced):
    datasource.instructions = 'Conte bolsas pendentes de revisão.'
    bolsas = synced['bolsas']
    bolsas.label = 'Bolsas'
    bolsas.description = 'Bolsas concedidas.'
    bolsas.synonyms = ['fomento', 'auxílio']
    status = bolsas.columns[1]
    status.description = 'Situação da bolsa'
    status.values = [
        {'value': 'REGULAR', 'description': 'válida'},
        {'value': 'DESCARTADA'},
    ]
    nome = synced['pesquisadores'].columns[1]
    nome.access = ColumnAccess.AGGREGATE
    synced['pesquisadores'].queryable = False
    await session.commit()

    text = await context(session, datasource)

    assert '## Instruções\nConte bolsas pendentes de revisão.' in text
    assert '`main.bolsas` (tabela): Bolsas\nBolsas concedidas.' in text
    assert 'Sinônimos: fomento, auxílio.' in text
    assert (
        '- `status` (VARCHAR(20)): Situação da bolsa. '
        'Valores: `REGULAR` = válida; `DESCARTADA`'
    ) in text
    assert '- `id` (INTEGER, chave primária)' in text
    assert '`nome` (VARCHAR(255)). **Somente agregação**' in text
    section = text.split('`main.pesquisadores`')[1]
    assert '_Somente referência: não pode ser consultada._' in section


async def test_relationships_between_included_entities(
    session, datasource, synced
):
    text = await context(session, datasource)

    assert '- `main.bolsas.pesquisador_id` -> `main.pesquisadores.id`' in text
    # instituicoes está oculta, então o relacionamento com ela não aparece.
    assert 'instituicao_id` ->' not in text


async def test_disabled_relationship_stays_out(session, datasource, synced):
    (relationship,) = [
        r
        for r in await load_relationships(session, 'origem')
        if r.from_columns == ['pesquisador_id']
    ]
    relationship.enabled = False
    await session.commit()

    assert '## Relacionamentos' not in await context(session, datasource)


async def test_disabled_datasource_has_empty_context(
    session, datasource, synced
):
    datasource.enabled = False
    await session.commit()

    assert not await context(session, datasource)


async def test_searchable_column_rendered_in_context(
    session, datasource, synced
):
    bolsas = synced['bolsas']
    status = bolsas.columns[1]
    status.searchable = True

    # Coluna oculta mas pesquisável não deve aparecer
    pesquisadores = synced['pesquisadores']
    lattes = pesquisadores.columns[2]
    lattes.searchable = True
    lattes.visible = False
    await session.commit()

    text = await context(session, datasource)

    assert '- `status` (VARCHAR(20)). aceita busca textual' in text
    assert 'lattes' not in text
