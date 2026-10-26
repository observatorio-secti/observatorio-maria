import pytest
import yaml

from observatorio_maria.catalog import seed as seed_cli
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
