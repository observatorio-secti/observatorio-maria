import sqlite3

import pytest

from observatorio_maria.catalog.drift import check_datasource
from observatorio_maria.catalog.introspection import introspect
from observatorio_maria.catalog.observed import (
    is_text_type,
    refresh_observed_values,
)
from observatorio_maria.catalog.sync import load_entities, sync_datasource
from observatorio_maria.models import (
    CatalogColumn,
    ColumnAccess,
    SchemaStatus,
)

DATA = """
INSERT INTO instituicoes VALUES (1, 'Universidade A', 'UA'),
                                (2, 'Universidade B', NULL);
INSERT INTO pesquisadores VALUES (1, 'Ana', NULL), (2, 'Bia', NULL),
                                 (3, 'Caio', NULL), (4, 'Duda', NULL);
INSERT INTO bolsas VALUES (1, 'REGULAR', 1, 1), (2, 'REGULAR', 2, 1),
                          (3, 'DESCARTADA', 3, 2), (4, 'RESOLVIDA', 4, 2);
"""


def run_on_source(source_db, script):
    with sqlite3.connect(source_db) as conn:
        conn.executescript(script)


@pytest.fixture
async def catalog(session, datasource, source_db):
    """Fonte sincronizada com tudo visível e consultável."""
    run_on_source(source_db, DATA)
    url = f'sqlite+aiosqlite:///{source_db}'
    await sync_datasource(
        session, datasource, await introspect(url, datasource.schemas)
    )
    for entity in await load_entities(session, datasource.id):
        entity.visible = entity.queryable = True
        for column in entity.columns:
            column.visible = True
    await session.commit()
    return datasource


async def column(session, entity_name, column_name) -> CatalogColumn:
    entities = await load_entities(session, 'origem')
    entity = next(e for e in entities if e.name == entity_name)
    return next(c for c in entity.columns if c.name == column_name)


def test_text_types():
    assert is_text_type('VARCHAR(20)')
    assert is_text_type('text')
    assert is_text_type('CHARACTER VARYING')
    assert not is_text_type('INTEGER')
    assert not is_text_type('TIMESTAMP')
    assert not is_text_type(None)


async def test_categorical_column_is_read(session, catalog):
    report = await refresh_observed_values(session, catalog)

    status = await column(session, 'bolsas', 'status')
    assert status.observed_values == ['DESCARTADA', 'REGULAR', 'RESOLVIDA']
    assert 'main.bolsas.status' in report.read_columns
    # Números nunca são lidos.
    assert (await column(session, 'bolsas', 'id')).observed_values is None


async def test_nulls_are_excluded(session, catalog):
    await refresh_observed_values(session, catalog)

    sigla = await column(session, 'instituicoes', 'sigla')
    assert sigla.observed_values == ['UA']


async def test_hidden_column_is_not_read(session, catalog):
    status = await column(session, 'bolsas', 'status')
    status.observed_values = ['ANTIGO']
    status.visible = False
    await session.commit()

    report = await refresh_observed_values(session, catalog)

    assert status.observed_values is None
    assert 'main.bolsas.status' not in report.read_columns


async def test_non_queryable_entity_is_not_read(session, catalog):
    for entity in await load_entities(session, 'origem'):
        if entity.name == 'bolsas':
            entity.queryable = False
    await session.commit()

    report = await refresh_observed_values(session, catalog)

    assert (await column(session, 'bolsas', 'status')).observed_values is None
    assert 'main.bolsas.status' not in report.read_columns


async def test_aggregate_column_is_not_read(session, catalog):
    nome = await column(session, 'pesquisadores', 'nome')
    nome.access = ColumnAccess.AGGREGATE
    await session.commit()

    report = await refresh_observed_values(session, catalog)

    assert nome.observed_values is None
    assert 'main.pesquisadores.nome' not in report.read_columns


async def test_column_above_limit_is_free_text(session, catalog):
    await refresh_observed_values(session, catalog, max_values=3)

    nome = await column(session, 'pesquisadores', 'nome')
    status = await column(session, 'bolsas', 'status')
    assert nome.observed_values is None  # 4 nomes distintos
    assert status.observed_values == ['DESCARTADA', 'REGULAR', 'RESOLVIDA']


async def test_limit_comes_from_settings(session, catalog, monkeypatch):
    monkeypatch.setenv('CATALOG_OBSERVED_VALUES_MAX', '2')

    await refresh_observed_values(session, catalog)

    assert (await column(session, 'bolsas', 'status')).observed_values is None
    sigla = await column(session, 'instituicoes', 'sigla')
    assert sigla.observed_values == ['UA']


async def test_failed_column_keeps_previous_values(
    session, catalog, source_db
):
    await refresh_observed_values(session, catalog)
    # A tabela some da origem: a leitura dela falha, as outras seguem.
    run_on_source(
        source_db,
        'DROP VIEW bolsas_por_status; ALTER TABLE bolsas RENAME TO b2;',
    )
    run_on_source(source_db, "UPDATE instituicoes SET sigla = 'UB' WHERE id=2")

    report = await refresh_observed_values(session, catalog)

    status = await column(session, 'bolsas', 'status')
    assert status.observed_values == ['DESCARTADA', 'REGULAR', 'RESOLVIDA']
    assert 'main.bolsas.status' in report.failed_columns
    sigla = await column(session, 'instituicoes', 'sigla')
    assert sigla.observed_values == ['UA', 'UB']


async def test_missing_connection_keeps_values(session, catalog, monkeypatch):
    await refresh_observed_values(session, catalog)
    monkeypatch.delenv('SOURCE_DATABASE_URL')

    report = await refresh_observed_values(session, catalog)

    assert 'SOURCE_DATABASE_URL' in report.error
    status = await column(session, 'bolsas', 'status')
    assert status.observed_values == ['DESCARTADA', 'REGULAR', 'RESOLVIDA']


async def test_check_updates_values_without_drift(session, catalog, source_db):
    run_on_source(source_db, "INSERT INTO bolsas VALUES (5, 'SUSPENSA', 1, 1)")

    result = await check_datasource(session, catalog, introspect)

    assert result.status == SchemaStatus.UP_TO_DATE
    status = await column(session, 'bolsas', 'status')
    assert 'SUSPENSA' in status.observed_values


async def test_observed_values_are_undescribed_and_obsolete(session, catalog):
    status = await column(session, 'bolsas', 'status')
    status.values = [
        {'value': 'REGULAR', 'description': 'Bolsa válida'},
        {'value': 'Doutorado'},
    ]
    await session.commit()

    await refresh_observed_values(session, catalog)

    assert status.source_values == ['DESCARTADA', 'REGULAR', 'RESOLVIDA']
    assert status.undescribed_values == ['DESCARTADA', 'RESOLVIDA']
    assert status.obsolete_values == ['Doutorado']


async def test_enum_takes_precedence_over_observed():
    column = CatalogColumn(
        entity_id=None,
        name='status',
        enum_values=['A', 'B'],
        observed_values=['A'],
    )

    assert column.source_values == ['A', 'B']


async def test_api_exposes_and_sync_reads_values(client, session, catalog):
    status = await column(session, 'bolsas', 'status')

    response = await client.post('/catalog/datasources/origem/sync')
    assert response.status_code == 200  # noqa: PLR2004

    body = (await client.get(f'/catalog/entities/{status.entity_id}')).json()
    payload = next(c for c in body['columns'] if c['name'] == 'status')
    assert payload['observed_values'] == [
        'DESCARTADA',
        'REGULAR',
        'RESOLVIDA',
    ]
    assert payload['undescribed_values'] == payload['observed_values']


async def test_patch_to_aggregate_clears_values(client, session, catalog):
    await refresh_observed_values(session, catalog)
    status = await column(session, 'bolsas', 'status')

    response = await client.patch(
        f'/catalog/columns/{status.id}', json={'access': 'aggregate'}
    )

    assert response.json()['observed_values'] is None
