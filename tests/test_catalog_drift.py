import asyncio
import sqlite3

import pytest

from observatorio_maria.catalog.drift import (
    check_all,
    check_datasource,
    diff_schema,
    start_periodic_checks,
)
from observatorio_maria.catalog.introspection import (
    ColumnSnapshot,
    EntitySnapshot,
    SchemaSnapshot,
    introspect,
)
from observatorio_maria.catalog.sync import (
    load_entities,
    load_relationships,
    sync_datasource,
)
from observatorio_maria.database import SessionLocal
from observatorio_maria.models import (
    CatalogDataSource,
    EntityKind,
    SchemaStatus,
)

SYNC_FIELDS = (
    'added_entities',
    'missing_entities',
    'added_columns',
    'missing_columns',
    'new_enum_values',
    'added_relationships',
    'missing_relationships',
)


@pytest.fixture
def url(source_db):
    return f'sqlite+aiosqlite:///{source_db}'


async def sync(session, datasource, url):
    return await sync_datasource(
        session, datasource, await introspect(url, datasource.schemas)
    )


def alter_source(source_db, script):
    with sqlite3.connect(source_db) as conn:
        conn.executescript(script)


async def entity_names(session):
    return {e.name for e in await load_entities(session, 'origem')}


async def test_sync_records_fingerprint_and_state(session, datasource, url):
    report = await sync(session, datasource, url)

    assert len(datasource.schema_fingerprint) == 64  # noqa: PLR2004
    assert datasource.schema_status == SchemaStatus.UP_TO_DATE
    assert datasource.last_checked_at == report.synced_at
    assert datasource.drift is None


async def test_check_unchanged_schema_is_up_to_date(session, datasource, url):
    await sync(session, datasource, url)

    result = await check_datasource(session, datasource, introspect)

    assert result.status == SchemaStatus.UP_TO_DATE
    assert result.drift is None
    assert datasource.last_checked_at == result.checked_at


async def test_check_detects_new_column_without_touching_catalog(
    session, datasource, url, source_db
):
    await sync(session, datasource, url)
    alter_source(source_db, 'ALTER TABLE bolsas ADD COLUMN modalidade TEXT')

    result = await check_datasource(session, datasource, introspect)

    assert result.status == SchemaStatus.OUTDATED
    assert result.drift.added_columns == ['main.bolsas.modalidade']
    assert datasource.schema_status == SchemaStatus.OUTDATED
    assert datasource.drift['added_columns'] == ['main.bolsas.modalidade']
    bolsas = next(
        e for e in await load_entities(session, 'origem') if e.name == 'bolsas'
    )
    assert 'modalidade' not in {c.name for c in bolsas.columns}


async def test_never_synced_source_is_outdated(session, datasource, source_db):
    result = await check_datasource(session, datasource, introspect)

    assert result.status == SchemaStatus.OUTDATED
    assert 'main.bolsas' in result.drift.added_entities
    assert await entity_names(session) == set()


async def test_check_error_is_recorded(session, datasource, url, monkeypatch):
    await sync(session, datasource, url)
    monkeypatch.delenv('SOURCE_DATABASE_URL')

    result = await check_datasource(session, datasource, introspect)

    assert result.status == SchemaStatus.ERROR
    assert 'SOURCE_DATABASE_URL' in datasource.check_error
    assert len(await entity_names(session)) == 4  # noqa: PLR2004


async def test_auto_sync_applies_drift(session, datasource, url, source_db):
    await sync(session, datasource, url)
    datasource.auto_sync = True
    await session.commit()
    alter_source(source_db, 'CREATE TABLE projetos (id INTEGER PRIMARY KEY)')

    result = await check_datasource(session, datasource, introspect)

    assert result.status == SchemaStatus.UP_TO_DATE
    assert result.sync.added_entities == ['main.projetos']
    projetos = next(
        e
        for e in await load_entities(session, 'origem')
        if e.name == 'projetos'
    )
    assert projetos.present
    assert not projetos.visible
    assert datasource.drift is None


async def test_without_auto_sync_new_table_stays_out(
    session, datasource, url, source_db
):
    await sync(session, datasource, url)
    alter_source(source_db, 'CREATE TABLE projetos (id INTEGER PRIMARY KEY)')

    result = await check_datasource(session, datasource, introspect)

    assert result.status == SchemaStatus.OUTDATED
    assert 'projetos' not in await entity_names(session)


async def test_diff_matches_next_sync_report(
    session, datasource, url, source_db
):
    await sync(session, datasource, url)
    alter_source(
        source_db,
        """
        DROP VIEW bolsas_por_status;
        ALTER TABLE pesquisadores DROP COLUMN lattes;
        ALTER TABLE instituicoes ADD COLUMN cep TEXT;
        CREATE TABLE projetos (
            id INTEGER PRIMARY KEY,
            instituicao_id INTEGER REFERENCES instituicoes (id)
        );
        """,
    )
    snapshot = await introspect(url, datasource.schemas)

    diff = diff_schema(
        await load_entities(session, 'origem'),
        await load_relationships(session, 'origem'),
        snapshot,
    )
    report = await sync_datasource(session, datasource, snapshot)

    def normalized(value):
        return sorted(value) if isinstance(value, list) else value

    assert {name: normalized(getattr(diff, name)) for name in SYNC_FIELDS} == {
        name: normalized(getattr(report, name)) for name in SYNC_FIELDS
    }
    assert diff.added_entities == ['main.projetos']
    assert diff.missing_entities == ['main.bolsas_por_status']
    assert diff.missing_columns == ['main.pesquisadores.lattes']
    assert diff.added_relationships == 1


def entity(columns, name='bolsas'):
    return EntitySnapshot('main', name, EntityKind.TABLE, columns, ())


async def test_diff_reports_changed_columns_and_enum_values(
    session, datasource
):
    await sync_datasource(
        session,
        datasource,
        SchemaSnapshot((
            entity((
                ColumnSnapshot('id', 'INTEGER', False, True, 1),
                ColumnSnapshot(
                    'status', 'bolsa_status', False, False, 2, ('A', 'B')
                ),
            )),
        )),
    )

    diff = diff_schema(
        await load_entities(session, 'origem'),
        await load_relationships(session, 'origem'),
        SchemaSnapshot((
            entity((
                ColumnSnapshot('id', 'BIGINT', False, True, 1),
                ColumnSnapshot(
                    'status', 'bolsa_status', True, False, 2, ('A', 'C')
                ),
            )),
        )),
    )

    assert diff.changed_columns == [
        'main.bolsas.id: INTEGER (não nulo, chave primária) -> '
        'BIGINT (não nulo, chave primária)',
        'main.bolsas.status: bolsa_status (não nulo) -> bolsa_status (nulo)',
    ]
    assert diff.new_enum_values == ['main.bolsas.status=C']
    assert diff.removed_enum_values == ['main.bolsas.status=B']


# --- Verificação periódica ---------------------------------------------------


@pytest.fixture
def session_factory(engine):
    return lambda: SessionLocal(bind=engine)


async def test_check_all_isolates_failures_and_skips_disabled(
    session, datasource, url, session_factory
):
    await sync(session, datasource, url)
    session.add_all([
        CatalogDataSource(
            id='quebrada', name='Quebrada', connection_env='NAO_DEFINIDA_URL'
        ),
        CatalogDataSource(
            id='desligada',
            name='Desligada',
            connection_env='SOURCE_DATABASE_URL',
            enabled=False,
        ),
    ])
    await session.commit()

    results = await check_all(session_factory, introspect)

    assert results == {
        'quebrada': SchemaStatus.ERROR,
        'origem': SchemaStatus.UP_TO_DATE,
    }
    async with session_factory() as other:
        desligada = await other.get(CatalogDataSource, 'desligada')
        assert desligada.last_checked_at is None


async def test_periodic_checks_disabled_with_zero(session_factory):
    assert start_periodic_checks(0, session_factory, introspect) is None


async def test_periodic_checks_run_until_cancelled(
    session, datasource, source_db, session_factory
):
    calls = []

    async def fake_introspect(url, schemas):
        calls.append(url)
        raise RuntimeError('falha inesperada')  # não derruba o laço

    task = start_periodic_checks(0.01, session_factory, fake_introspect)
    await asyncio.sleep(0.1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert len(calls) >= 2  # noqa: PLR2004
