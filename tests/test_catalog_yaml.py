import re
import sqlite3
from pathlib import Path

import pytest
import yaml

from observatorio_maria.catalog import seed as seed_cli
from observatorio_maria.catalog.context import check_examples, render_context
from observatorio_maria.catalog.introspection import introspect
from observatorio_maria.catalog.sync import (
    load_entities,
    load_relationships,
    sync_datasource,
)
from observatorio_maria.catalog.yaml_io import (
    CatalogFile,
    CatalogFileError,
    dump_catalog_file,
    export_catalog,
    load_catalog_file,
    seed_catalog,
)
from observatorio_maria.models import (
    CatalogDataSource,
    ColumnAccess,
    RelationshipOrigin,
)

CATALOG_YAML = """
datasource:
  id: origem
  name: Origem de teste
  connection_env: SOURCE_DATABASE_URL
  schemas: [main]
  instructions: Contagens incluem bolsas pendentes.
  examples:
    - question: Quantas bolsas ativas?
      sql: SELECT count(*) FROM bolsas;
entities:
  - name: bolsas
    label: Bolsas
    description: Bolsas concedidas
    synonyms: [fomento]
    columns:
      - name: status
        searchable: true
        values:
          - {value: REGULAR, description: Bolsa válida}
  - name: pesquisadores
    queryable: false
    columns:
      - name: nome
        access: aggregate
      - name: lattes
        visible: false
  - name: bolsas_por_status
relationships:
  - from: bolsas.pesquisador_id
    to: pesquisadores.id
    description: Pesquisador bolsista
  - from: bolsas_por_status.status
    to: bolsas.status
"""


@pytest.fixture
def catalog_path(tmp_path):
    path = tmp_path / 'origem.yaml'
    path.write_text(CATALOG_YAML, encoding='utf-8')
    return path


@pytest.fixture
def document(catalog_path):
    return load_catalog_file(catalog_path)


def by_name(entities):
    return {entity.name: entity for entity in entities}


async def test_seed_creates_datasource_entities_columns(session, document):
    report = await seed_catalog(session, document)

    assert report.datasource_created
    assert (report.entities, report.columns, report.relationships) == (3, 3, 2)
    datasource = await session.get(CatalogDataSource, 'origem')
    assert datasource.instructions == 'Contagens incluem bolsas pendentes.'
    assert datasource.examples == [
        {
            'question': 'Quantas bolsas ativas?',
            'sql': 'SELECT count(*) FROM bolsas;',
        }
    ]

    entities = by_name(await load_entities(session, 'origem'))
    bolsas = entities['bolsas']
    assert bolsas.visible
    assert bolsas.queryable
    assert not bolsas.present  # só existe na origem após sincronizar
    assert bolsas.synonyms == ['fomento']
    assert bolsas.columns[0].searchable is True
    assert bolsas.columns[0].values == [
        {'value': 'REGULAR', 'description': 'Bolsa válida'}
    ]
    pesquisadores = entities['pesquisadores']
    assert pesquisadores.visible
    assert not pesquisadores.queryable
    columns = {c.name: c for c in pesquisadores.columns}
    assert columns['nome'].access == ColumnAccess.AGGREGATE
    assert columns['nome'].searchable is False
    assert not columns['lattes'].visible

    relationships = await load_relationships(session, 'origem')
    assert {r.origin for r in relationships} == {RelationshipOrigin.MANUAL}


async def test_seed_does_not_overwrite_edits(session, document):
    await seed_catalog(session, document)
    bolsas = by_name(await load_entities(session, 'origem'))['bolsas']
    bolsas.description = 'Editada pela API'
    await session.commit()

    report = await seed_catalog(session, document)

    assert not report.datasource_created
    assert (report.entities, report.columns, report.relationships) == (0, 0, 0)
    bolsas = by_name(await load_entities(session, 'origem'))['bolsas']
    assert bolsas.description == 'Editada pela API'


async def test_seed_adds_only_missing_items(session, document):
    await seed_catalog(session, document)
    document.entities.append(
        document.entities[0].model_copy(update={'name': 'instituicoes'})
    )

    report = await seed_catalog(session, document)

    assert report.entities == 1
    assert 'instituicoes' in by_name(await load_entities(session, 'origem'))


async def test_seed_reset_recreates_from_file(session, document):
    await seed_catalog(session, document)
    bolsas = by_name(await load_entities(session, 'origem'))['bolsas']
    bolsas.description = 'Editada pela API'
    await session.commit()

    report = await seed_catalog(session, document, reset=True)

    assert report.datasource_created
    entities = by_name(await load_entities(session, 'origem'))
    assert entities['bolsas'].description == 'Bolsas concedidas'
    assert len(await load_relationships(session, 'origem')) == 2  # noqa: PLR2004


@pytest.mark.parametrize(
    ('content', 'message'),
    [
        ('datasource: [', 'origem.yaml'),
        (
            CATALOG_YAML.replace('access: aggregate', 'access: secreto'),
            'access',
        ),
        (
            CATALOG_YAML.replace(
                'queryable: false', 'visible: false\n    queryable: true'
            ),
            'consultável precisa ser visível',
        ),
        (
            CATALOG_YAML.replace(
                'question: Quantas bolsas ativas?', 'question: ""'
            ),
            'question',
        ),
        (CATALOG_YAML.replace('id: origem', 'id: Origem!'), 'id'),
    ],
)
def test_invalid_file_is_rejected(tmp_path, content, message):
    path = tmp_path / 'origem.yaml'
    path.write_text(content, encoding='utf-8')

    with pytest.raises(CatalogFileError, match=message):
        load_catalog_file(path)


async def test_unknown_relationship_entity_leaves_catalog_unchanged(
    session, document
):
    document.relationships[0].to = 'inexistente.id'

    with pytest.raises(CatalogFileError, match='entidade desconhecida'):
        await seed_catalog(session, document)

    assert await session.get(CatalogDataSource, 'origem') is None


async def test_export_round_trip(session, document, source_db):
    await seed_catalog(session, document)
    datasource = await session.get(CatalogDataSource, 'origem')
    await sync_datasource(
        session,
        datasource,
        await introspect(f'sqlite+aiosqlite:///{source_db}', ['main']),
    )
    exported = await export_catalog(session, datasource)
    text = dump_catalog_file(exported)

    await seed_catalog(
        session,
        CatalogFile.model_validate(yaml.safe_load(text)),
        reset=True,
    )

    again = await export_catalog(
        session, await session.get(CatalogDataSource, 'origem')
    )
    assert dump_catalog_file(again) == text
    # A sincronização reconheceu o relacionamento como chave estrangeira e
    # manteve o manual (a view não tem chave estrangeira).
    assert 'Pesquisador bolsista' in text
    assert 'bolsas_por_status.status' in text
    assert 'searchable: true' in text
    assert 'Quantas bolsas ativas?' in text


def test_seed_cli_reports_invalid_file(tmp_path, capsys):
    path = tmp_path / 'ruim.yaml'
    path.write_text('datasource: {}', encoding='utf-8')

    assert seed_cli.main([str(path)]) == 1
    assert 'Erro' in capsys.readouterr().err


async def test_fomento_seed_examples_pass_catalog_rules(session):
    """Os exemplos do seed do fomento só citam o que o próprio seed deixa
    visível; um exemplo quebrado ficaria fora do contexto do modelo."""
    document = load_catalog_file(Path('catalog/fomento.yaml'))
    await seed_catalog(session, document)
    datasource = await session.get(CatalogDataSource, document.datasource.id)
    entities = await load_entities(session, datasource.id)
    # Simula a origem com tudo o que o seed declara.
    for entity in entities:
        entity.present = True
        for column in entity.columns:
            column.present = True
    await session.commit()

    accepted, rejected = check_examples(datasource, entities)

    assert rejected == []
    assert len(accepted) == len(document.datasource.examples)


def test_fomento_seed_has_no_guessed_modalidade_values():
    document = load_catalog_file(Path('catalog/fomento.yaml'))
    bolsas = next(e for e in document.entities if e.name == 'bolsas')
    modalidade = next(c for c in bolsas.columns if c.name == 'modalidade')

    assert not modalidade.values


SIMCC_SEARCHABLE = {
    ('researcher', 'name'),
    ('researcher', 'abstract'),
    ('bibliographic_production', 'title'),
    ('patent', 'title'),
    ('software', 'title'),
    ('participation_events', 'title'),
    ('participation_events', 'event_name'),
    ('research_project', 'project_name'),
    ('research_project', 'description'),
    ('mv_canonical_articles', 'title'),
    ('mv_canonical_articles', 'abstract'),
    ('mv_canonical_articles', 'keywords'),
    ('mv_canonical_books', 'title'),
    ('mv_canonical_book_chapters', 'title'),
    ('mv_canonical_patents', 'title'),
    ('mv_canonical_software', 'title'),
    ('mv_canonical_events', 'title'),
    ('mv_canonical_events', 'event_name'),
    ('mv_canonical_research_projects', 'title'),
    ('mv_canonical_research_projects', 'description'),
}

# Arrays, JSON, tsvector, URLs e campos internos do ETL do Simcc.
SIMCC_TECHNICAL_COLUMNS = {
    'search_vector',
    'production_ids',
    'researcher_ids',
    'institution_ids',
    'graduate_program_ids',
    'platform_authors',
    'foment',
    'components',
    'productions',
    'great_area_',
    'sequence_code',
    'is_new',
    'stars',
    'has_image',
    'relevance',
    'abstract_en',
    'abstract_ai',
    'extra_field',
    'homepage',
    'landing_page_url',
    'pdf_url',
}


def simcc_columns():
    document = load_catalog_file(Path('catalog/simcc.yaml'))
    return [
        (entity.name, column)
        for entity in document.entities
        for column in entity.columns
    ]


def test_simcc_seed_loads_source():
    document = load_catalog_file(Path('catalog/simcc.yaml'))

    assert document.datasource.id == 'simcc'
    assert document.datasource.connection_env == 'SIMCC_DATABASE_URL'
    assert document.datasource.schemas == ['public']


def test_simcc_seed_has_no_guessed_values():
    assert [
        f'{entity}.{column.name}'
        for entity, column in simcc_columns()
        if column.values
    ] == []


def test_simcc_seed_searchable_columns():
    searchable = {
        (entity, column.name)
        for entity, column in simcc_columns()
        if column.searchable
    }

    assert searchable == SIMCC_SEARCHABLE


def test_simcc_seed_researcher_personal_data_is_full():
    access = {
        column.name: column.access
        for entity, column in simcc_columns()
        if entity == 'researcher'
    }

    assert access['name'] == ColumnAccess.FULL
    assert access['orcid'] == ColumnAccess.FULL
    assert access['abstract'] == ColumnAccess.FULL


def test_simcc_seed_lists_no_technical_columns():
    listed = {column.name for _, column in simcc_columns()}
    # `year` é texto em bibliographic_production; o ano numérico é `year_`.
    text_year = [
        column.name
        for entity, column in simcc_columns()
        if entity == 'bibliographic_production' and column.name == 'year'
    ]

    assert listed & SIMCC_TECHNICAL_COLUMNS == set()
    assert text_year == []


async def test_simcc_seed_examples_pass_catalog_rules(session):
    """Os exemplos do seed do Simcc só citam o que o próprio seed deixa
    visível; um exemplo quebrado ficaria fora do contexto do modelo."""
    document = load_catalog_file(Path('catalog/simcc.yaml'))
    await seed_catalog(session, document)
    datasource = await session.get(CatalogDataSource, 'simcc')
    entities = await load_entities(session, datasource.id)
    # Simula a origem com tudo o que o seed declara.
    for entity in entities:
        entity.present = True
        for column in entity.columns:
            column.present = True
    await session.commit()

    accepted, rejected = check_examples(datasource, entities)

    assert rejected == []
    assert len(accepted) == len(document.datasource.examples)


async def test_simcc_technical_columns_hidden_after_sync(session, tmp_path):
    """Colunas que o seed não lista entram ocultas e ficam fora da prévia."""
    path = tmp_path / 'simcc.db'
    with sqlite3.connect(path) as conn:
        conn.execute(
            'CREATE TABLE mv_canonical_articles ('
            'canonical_id TEXT PRIMARY KEY, title TEXT, year INTEGER, '
            'search_vector TEXT, researcher_ids TEXT, production_ids TEXT, '
            'platform_authors TEXT)'
        )
    document = load_catalog_file(Path('catalog/simcc.yaml'))
    document.datasource.schemas = ['main']
    await seed_catalog(session, document)
    datasource = await session.get(CatalogDataSource, 'simcc')
    await sync_datasource(
        session,
        datasource,
        await introspect(f'sqlite+aiosqlite:///{path}', ['main']),
    )

    entities = await load_entities(session, 'simcc')
    articles = next(e for e in entities if e.name == 'mv_canonical_articles')
    visible = {c.name for c in articles.columns if c.visible and c.present}
    text = render_context(
        datasource, entities, await load_relationships(session, 'simcc')
    )

    assert visible == {'canonical_id', 'title', 'year'}
    for name in (
        'search_vector',
        'researcher_ids',
        'production_ids',
        'platform_authors',
    ):
        assert name not in text


def match_text_terms(sql):
    terms = set()
    for args in re.findall(r'MATCH_TEXT\(\s*[^,]+,([^)]*)\)', sql):
        terms |= {t.strip().strip("'").lower() for t in args.split(',')}
    return terms


def test_seed_examples_do_not_repeat_across_sources():
    """Um exemplo repetido entre fontes ensina o modelo a escolher uma delas
    para a pergunta ambígua (issue #2)."""
    fomento, simcc = (
        load_catalog_file(Path(f'catalog/{name}.yaml')).datasource.examples
        for name in ('fomento', 'simcc')
    )

    questions = {e.question.lower() for e in fomento}
    assert questions & {e.question.lower() for e in simcc} == set()
    fomento_terms = set().union(*(match_text_terms(e.sql) for e in fomento))
    simcc_terms = set().union(*(match_text_terms(e.sql) for e in simcc))
    assert fomento_terms
    assert simcc_terms
    assert fomento_terms & simcc_terms == set()


def test_simcc_seed_links_researchers_by_researcher_institution():
    document = load_catalog_file(Path('catalog/simcc.yaml'))
    entities = {e.name: e for e in document.entities}

    researcher_columns = {c.name for c in entities['researcher'].columns}
    assert 'institution_id' not in researcher_columns
    link = {c.name for c in entities['researcher_institution'].columns}
    assert {'researcher_id', 'institution_id'} <= link
    assert 'researcher_institution' in document.datasource.instructions
    assert 'COUNT(DISTINCT' in document.datasource.instructions
