from pathlib import Path
from uuid import uuid4

import pytest

from observatorio_maria.catalog.context import (
    check_examples,
    render_concepts,
    render_context,
)
from observatorio_maria.catalog.introspection import introspect
from observatorio_maria.catalog.sync import (
    load_entities,
    load_relationships,
    sync_datasource,
)
from observatorio_maria.catalog.yaml_io import load_catalog_file, seed_catalog
from observatorio_maria.models import (
    CatalogColumn,
    CatalogConcept,
    CatalogDataSource,
    CatalogEntity,
    CatalogRelationship,
    ColumnAccess,
)


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

    line = next(
        lin
        for lin in text.splitlines()
        if lin.startswith('- `pesquisador_id`')
    )
    assert line.endswith('→ main.pesquisadores.id')
    # instituicoes está oculta, então o relacionamento com ela não aparece.
    assert '→ main.instituicoes' not in text
    assert '## Relacionamentos' not in text


async def test_disabled_relationship_stays_out(session, datasource, synced):
    (relationship,) = [
        r
        for r in await load_relationships(session, 'origem')
        if r.from_columns == ['pesquisador_id']
    ]
    relationship.enabled = False
    await session.commit()

    assert '→ main.pesquisadores.id' not in await context(session, datasource)


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


async def test_few_shot_examples_rendered_in_context(
    session, datasource, synced
):
    datasource.examples = [
        {
            'question': 'Quantas bolsas ativas?',
            'sql': "SELECT COUNT(*) FROM bolsas\nWHERE status = 'REGULAR';",
        }
    ]
    await session.commit()

    text = await context(session, datasource)

    assert '## Exemplos de consultas (few-shot)' in text
    assert '- Pergunta: "Quantas bolsas ativas?"' in text
    assert (
        '  ```sql\n  SELECT COUNT(*) FROM bolsas\n'
        "  WHERE status = 'REGULAR';\n  ```"
    ) in text


async def test_datasource_without_examples_omits_section(
    session, datasource, synced
):
    datasource.examples = []
    await session.commit()

    text = await context(session, datasource)
    assert '## Exemplos de consultas (few-shot)' not in text


async def test_observed_values_replace_editorial_ones(
    session, datasource, synced
):
    status = synced['bolsas'].columns[1]
    status.values = [
        {'value': 'Doutorado - Cotas', 'description': 'cotas de doutorado'},
        {'value': 'Doutorado'},
    ]
    status.observed_values = ['Doutorado - Cotas', 'Mestrado - Cotas']
    await session.commit()

    text = await context(session, datasource)

    assert (
        'Valores: `Doutorado - Cotas` = cotas de doutorado; `Mestrado - Cotas`'
    ) in text
    assert '`Doutorado`' not in text


async def test_without_source_values_editorial_values_stay(
    session, datasource, synced
):
    status = synced['bolsas'].columns[1]
    status.values = [{'value': 'REGULAR', 'description': 'válida'}]
    await session.commit()

    text = await context(session, datasource)

    assert 'Valores: `REGULAR` = válida' in text
    assert 'existentes na origem' not in text


INVALID_EXAMPLE = {
    'question': 'Total por ano',
    'sql': 'SELECT ano, COUNT(*) FROM main.bolsas GROUP BY ano',
}
VALID_EXAMPLE = {
    'question': 'Bolsas por status',
    'sql': 'SELECT status, COUNT(*) FROM main.bolsas GROUP BY status',
}


async def test_example_with_unknown_column_is_rejected(
    session, datasource, synced
):
    datasource.examples = [INVALID_EXAMPLE, VALID_EXAMPLE]
    await session.commit()

    text = await context(session, datasource)
    _, rejected = check_examples(
        datasource, await load_entities(session, datasource.id)
    )

    assert '- Pergunta: "Bolsas por status"' in text
    assert 'Total por ano' not in text
    assert len(rejected) == 1
    assert rejected[0]['question'] == 'Total por ano'
    assert 'ano' in rejected[0]['reason']


async def test_valid_examples_are_all_kept(session, datasource, synced):
    datasource.examples = [VALID_EXAMPLE]
    await session.commit()

    accepted, rejected = check_examples(
        datasource, await load_entities(session, datasource.id)
    )

    assert accepted == [VALID_EXAMPLE]
    assert rejected == []


async def test_preview_lists_rejected_examples(
    client, session, datasource, synced
):
    datasource.examples = [INVALID_EXAMPLE, VALID_EXAMPLE]
    await session.commit()

    data = (await client.get('/catalog/datasources/origem/context')).json()

    assert [r['question'] for r in data['rejected_examples']] == [
        'Total por ano'
    ]
    assert data['rejected_examples'][0]['reason']
    assert 'Bolsas por status' in data['content']


async def seeded_context(session, path):
    """Prévia gerada a partir de um seed, com tudo o que ele declara
    presente."""
    document = load_catalog_file(Path(path))
    await seed_catalog(session, document)
    datasource = await session.get(CatalogDataSource, document.datasource.id)
    entities = await load_entities(session, datasource.id)
    for entity in entities:
        entity.present = True
        for column in entity.columns:
            column.present = True
    await session.commit()
    return render_context(
        datasource, entities, await load_relationships(session, datasource.id)
    )


async def test_simcc_instructions_in_context(session):
    text = await seeded_context(session, 'catalog/simcc.yaml')

    # Tabelas base x views canônicas, e o ano numérico.
    assert 'mv_canonical_*' in text
    assert 'para totais de produções' in text.lower()
    assert '`year_`' in text
    # Ligação com o fomento, sem limite de Lattes por consulta.
    assert '`researcher.lattes_id`' in text
    assert '`pesquisadores.lattes`' in text
    assert 'consulta entre fontes' in text
    assert '100' not in text.split('## Instruções')[1].split('## Entidades')[0]


async def test_fomento_instructions_point_to_simcc(session):
    text = await seeded_context(session, 'catalog/fomento.yaml')

    assert 'estão na fonte `simcc`' in text
    assert '`pesquisadores.lattes` = `researcher.lattes_id`' in text


# --- Conceitos em várias fontes ----------------------------------------------


def concept_entity(datasource_id, name, concept_id='projetos', **overrides):
    data = {
        'datasource_id': datasource_id,
        'schema_name': 'public',
        'name': name,
        'concept_id': concept_id,
        'visible': True,
        'queryable': True,
        'present': True,
    }
    return CatalogEntity(**{**data, **overrides})


def two_sources():
    return [
        CatalogDataSource(id='fomento', name='Fomento', connection_env='A'),
        CatalogDataSource(id='simcc', name='Simcc', connection_env='B'),
    ]


PROJETOS = CatalogConcept(
    id='projetos',
    label='Projetos',
    description='Projetos de pesquisa.',
    instructions='- Pergunta genérica: use o fomento e mencione o Simcc.',
)


def test_concept_in_two_sources_is_listed():
    entities = [
        concept_entity('fomento', 'projetos', label='Projetos com bolsa'),
        concept_entity('simcc', 'research_project'),
        concept_entity('simcc', 'mv_canonical_research_projects'),
    ]

    text = render_concepts([PROJETOS], entities, two_sources())

    assert text.startswith('# Conceitos em várias fontes')
    assert '## Projetos (`projetos`)' in text
    assert '- Fomento (`fomento`): `public.projetos` (Projetos com bolsa)' in (
        text
    )
    assert (
        '- Simcc (`simcc`): `public.mv_canonical_research_projects`, '
        '`public.research_project`'
    ) in text
    assert 'use o fomento e mencione o Simcc' in text


def test_concept_in_one_source_is_left_out():
    entities = [
        concept_entity('fomento', 'projetos'),
        concept_entity('simcc', 'research_project'),
    ]
    only_fomento = two_sources()[:1]

    assert not render_concepts([PROJETOS], entities, only_fomento)


def test_hidden_entity_does_not_count_as_source():
    entities = [
        concept_entity('fomento', 'projetos'),
        concept_entity('simcc', 'research_project', visible=False),
    ]

    assert not render_concepts([PROJETOS], entities, two_sources())


async def test_entity_section_shows_concept(session, datasource, synced):
    synced['bolsas'].concept_id = 'projetos'
    session.add(CatalogConcept(id='projetos', label='Projetos'))
    await session.commit()

    text = render_context(
        datasource,
        await load_entities(session, datasource.id),
        await load_relationships(session, datasource.id),
        {'projetos': 'Projetos'},
    )

    bolsas = text.split('### `main.bolsas`')[1].split('###')[0]
    assert 'Conceito: Projetos' in bolsas
    pesquisadores = text.split('### `main.pesquisadores`')[1]
    assert 'Conceito:' not in pesquisadores


# --- Listagem de valores e relacionamentos na coluna -------------------------


def column(name, **fields):
    data = {
        'name': name,
        'visible': True,
        'present': True,
        'data_type': 'TEXT',
    }
    return CatalogColumn(entity_id=uuid4(), **{**data, **fields})


def entity_with(name, *columns, datasource_id='origem'):
    entity = CatalogEntity(
        datasource_id=datasource_id,
        schema_name='main',
        name=name,
        visible=True,
        queryable=True,
        present=True,
    )
    entity.columns = list(columns)
    return entity


SOURCE = CatalogDataSource(id='origem', name='Origem', connection_env='A')


def render(*entities, relationships=(), max_values=20):
    return render_context(
        SOURCE, list(entities), list(relationships), max_values=max_values
    )


def line_of(text, name):
    return next(
        lin for lin in text.splitlines() if lin.startswith(f'- `{name}`')
    )


def values_line(col, max_values=20):
    return line_of(
        render(entity_with('t', col), max_values=max_values), col.name
    )


QUALIS = [f'Q{i}' for i in range(10)]


def test_short_category_is_listed():
    line = values_line(column('qualis', observed_values=QUALIS))

    assert 'Valores: `Q0`; `Q1`' in line


def test_too_many_values_are_not_listed():
    many = [f'v{i}' for i in range(38)]

    assert 'Valores' not in values_line(column('jcr', observed_values=many))


def test_long_values_are_not_listed():
    titles = [
        'Um título de patente bem longo número ' + str(i) for i in range(4)
    ]

    assert 'Valores' not in values_line(
        column('title', observed_values=titles)
    )


def test_searchable_column_is_not_listed():
    col = column('tipo', observed_values=QUALIS, searchable=True)

    assert 'Valores' not in values_line(col)


def test_enum_is_listed_above_limit():
    col = column('status', enum_values=[f'S{i}' for i in range(30)])

    assert 'Valores: `S0`' in values_line(col)


def test_described_values_are_listed_above_limit():
    many = [f'v{i}' for i in range(30)]
    col = column(
        'tipo',
        observed_values=many,
        values=[{'value': 'v1', 'description': 'um'}],
    )

    assert '`v1` = um' in values_line(col)


def test_always_lists_and_never_hides():
    many = [f'v{i}' for i in range(38)]

    always = values_line(
        column('a', observed_values=many, list_values='always')
    )
    never = values_line(
        column('b', enum_values=['X', 'Y'], list_values='never')
    )

    assert 'Valores: `v0`' in always
    assert 'Valores' not in never


def test_context_values_max_is_respected():
    col = column('qualis', observed_values=QUALIS)

    assert 'Valores' not in values_line(col, max_values=5)
    assert col.observed_values == QUALIS


def test_long_values_label_is_gone():
    text = render(entity_with('t', column('qualis', observed_values=QUALIS)))

    assert 'existentes na origem' not in text


def relationship(source, target, from_columns, to_columns, **fields):
    data = {'enabled': True, 'present': True, 'origin': 'foreign_key'}
    return CatalogRelationship(
        datasource_id='origem',
        from_entity_id=source.id,
        from_columns=from_columns,
        to_entity_id=target.id,
        to_columns=to_columns,
        **{**data, **fields},
    )


def test_manual_relationship_shows_description():
    target = entity_with('pessoas', column('id'))
    source = entity_with('bolsas', column('pessoa_id'))
    rel = relationship(
        source, target, ['pessoa_id'], ['id'], description='Bolsista'
    )

    text = render(source, target, relationships=[rel])

    assert line_of(text, 'pessoa_id').endswith('→ main.pessoas.id (Bolsista)')


def test_composite_relationship_on_first_column():
    target = entity_with('vinculos', column('a'), column('b'))
    source = entity_with('uso', column('x'), column('y'))
    rel = relationship(source, target, ['x', 'y'], ['a', 'b'])

    text = render(source, target, relationships=[rel])

    assert line_of(text, 'x').endswith('→ main.vinculos.a, b (com x, y)')
    assert '→' not in line_of(text, 'y')


def test_hidden_source_column_hides_relationship():
    target = entity_with('pessoas', column('id'))
    source = entity_with(
        'bolsas', column('id'), column('pessoa_id', visible=False)
    )
    rel = relationship(source, target, ['pessoa_id'], ['id'])

    assert '→' not in render(source, target, relationships=[rel])


def test_relationship_description_equal_to_column_is_not_repeated():
    target = entity_with('projetos', column('id'))
    source = entity_with(
        'bolsas', column('projeto_id', description='Projeto da bolsa.')
    )
    rel = relationship(
        source, target, ['projeto_id'], ['id'], description='Projeto da bolsa'
    )

    line = line_of(render(source, target, relationships=[rel]), 'projeto_id')

    assert line.endswith('Projeto da bolsa. → main.projetos.id')
