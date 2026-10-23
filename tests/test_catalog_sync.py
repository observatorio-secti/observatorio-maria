import sqlite3

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from observatorio_maria.catalog.introspection import (
    SourceUnavailableError,
    create_readonly_engine,
    introspect,
)
from observatorio_maria.catalog.sync import (
    load_entities,
    load_relationships,
    sync_datasource,
)
from observatorio_maria.models import EntityKind, RelationshipOrigin


async def sync(session, datasource, url):
    return await sync_datasource(
        session, datasource, await introspect(url, datasource.schemas)
    )


def by_name(entities):
    return {entity.name: entity for entity in entities}


@pytest.fixture
def url(source_db):
    return f'sqlite+aiosqlite:///{source_db}'


async def test_introspect_reads_tables_views_columns_and_keys(url):
    snapshot = await introspect(url, ['main'])

    entities = {entity.name: entity for entity in snapshot.entities}
    assert entities.keys() == {
        'bolsas',
        'bolsas_por_status',
        'instituicoes',
        'pesquisadores',
    }
    assert entities['bolsas_por_status'].kind == EntityKind.VIEW
    bolsas = entities['bolsas']
    assert bolsas.kind == EntityKind.TABLE
    assert [c.name for c in bolsas.columns] == [
        'id',
        'status',
        'pesquisador_id',
        'instituicao_id',
    ]
    assert bolsas.columns[0].primary_key
    assert not bolsas.columns[1].nullable
    assert {fk.referred_entity for fk in bolsas.foreign_keys} == {
        'pesquisadores',
        'instituicoes',
    }


async def test_readonly_engine_cannot_write(url):
    engine = create_readonly_engine(url)
    async with engine.connect() as conn:
        with pytest.raises(OperationalError):
            await conn.execute(
                text("INSERT INTO instituicoes VALUES (1, 'X', 'X')")
            )
    await engine.dispose()


async def test_introspect_unreachable_source_raises():
    with pytest.raises(SourceUnavailableError):
        await introspect(
            'sqlite+aiosqlite:///file:/nao/existe.db?mode=ro&uri=true',
            ['main'],
        )


@pytest.mark.parametrize(
    'url',
    [
        'postgresql+psycopg://maria:segredo@127.0.0.1:1/fomento',
        'postgresql+driverinexistente://maria:segredo@host/fomento',
        'não é uma url com segredo',
    ],
)
async def test_introspect_errors_do_not_leak_credentials(url):
    with pytest.raises(SourceUnavailableError) as error:
        await introspect(url, ['public'])

    assert 'segredo' not in str(error.value)


async def test_first_sync_adds_everything_hidden(session, datasource, url):
    report = await sync(session, datasource, url)

    assert sorted(report.added_entities) == [
        'main.bolsas',
        'main.bolsas_por_status',
        'main.instituicoes',
        'main.pesquisadores',
    ]
    assert 'main.bolsas.status' in report.added_columns
    assert report.added_relationships == 2  # noqa: PLR2004
    assert datasource.last_synced_at == report.synced_at

    for entity in await load_entities(session, datasource.id):
        assert entity.present
        assert not entity.visible
        assert not entity.queryable
        assert all(
            c.present and not c.visible and not c.searchable
            for c in entity.columns
        )

    relationships = await load_relationships(session, datasource.id)
    assert all(
        r.origin == RelationshipOrigin.FOREIGN_KEY and r.enabled and r.present
        for r in relationships
    )


async def test_resync_preserves_editorial_config(session, datasource, url):
    await sync(session, datasource, url)
    bolsas = by_name(await load_entities(session, datasource.id))['bolsas']
    bolsas.description = 'Bolsas concedidas'
    bolsas.visible = bolsas.queryable = True
    bolsas.columns[1].description = 'Situação da bolsa'
    bolsas.columns[1].visible = True
    bolsas.columns[1].searchable = True
    await session.commit()

    report = await sync(session, datasource, url)

    assert report.added_entities == []
    assert report.added_columns == []
    bolsas = by_name(await load_entities(session, datasource.id))['bolsas']
    assert bolsas.description == 'Bolsas concedidas'
    assert bolsas.visible
    assert bolsas.queryable
    assert bolsas.columns[1].description == 'Situação da bolsa'
    assert bolsas.columns[1].visible
    assert bolsas.columns[1].searchable


async def test_removed_table_becomes_missing_and_returns(
    session, datasource, url, source_db
):
    await sync(session, datasource, url)
    instituicoes = by_name(await load_entities(session, datasource.id))[
        'instituicoes'
    ]
    instituicoes.description = 'Instituições de ensino'
    await session.commit()

    with sqlite3.connect(source_db) as conn:
        conn.executescript(
            'DROP VIEW bolsas_por_status; DROP TABLE bolsas;'
            'ALTER TABLE instituicoes RENAME TO instituicoes_old;'
        )
    report = await sync(session, datasource, url)

    assert 'main.instituicoes' in report.missing_entities
    assert report.missing_relationships == 2  # noqa: PLR2004
    entities = by_name(await load_entities(session, datasource.id))
    assert not entities['instituicoes'].present
    assert entities['instituicoes'].description == 'Instituições de ensino'

    with sqlite3.connect(source_db) as conn:
        conn.execute('ALTER TABLE instituicoes_old RENAME TO instituicoes')
    report = await sync(session, datasource, url)

    assert report.added_entities == []
    entities = by_name(await load_entities(session, datasource.id))
    assert entities['instituicoes'].present
    assert entities['instituicoes'].description == 'Instituições de ensino'


async def test_removed_column_becomes_missing(
    session, datasource, url, source_db
):
    await sync(session, datasource, url)
    with sqlite3.connect(source_db) as conn:
        conn.execute('ALTER TABLE pesquisadores DROP COLUMN lattes')

    report = await sync(session, datasource, url)

    assert report.missing_columns == ['main.pesquisadores.lattes']
    pesquisadores = by_name(await load_entities(session, datasource.id))[
        'pesquisadores'
    ]
    lattes = next(c for c in pesquisadores.columns if c.name == 'lattes')
    assert not lattes.present
