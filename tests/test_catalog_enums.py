from sqlalchemy import String
from sqlalchemy.dialects.postgresql import ENUM

from observatorio_maria.catalog.context import render_context
from observatorio_maria.catalog.introspection import (
    ColumnSnapshot,
    EntitySnapshot,
    SchemaSnapshot,
    _enum_values,  # noqa: PLC2701
)
from observatorio_maria.catalog.sync import (
    load_entities,
    load_relationships,
    sync_datasource,
)
from observatorio_maria.models import EntityKind


def snapshot(status_values):
    return SchemaSnapshot(
        entities=(
            EntitySnapshot(
                schema_name='main',
                name='bolsas',
                kind=EntityKind.TABLE,
                columns=(
                    ColumnSnapshot('id', 'INTEGER', False, True, 1),
                    ColumnSnapshot(
                        'status',
                        'bolsa_status',
                        False,
                        False,
                        2,
                        enum_values=status_values,
                    ),
                ),
                foreign_keys=(),
            ),
        )
    )


async def status_column(session):
    (bolsas,) = await load_entities(session, 'origem')
    return next(c for c in bolsas.columns if c.name == 'status')


def test_enum_values_read_from_postgres_enum_type():
    column = {'type': ENUM('REGULAR', 'DESCARTADA', name='bolsa_status')}

    assert _enum_values(column) == ('REGULAR', 'DESCARTADA')
    assert _enum_values({'type': String(20)}) is None


async def test_first_sync_stores_enum_without_reporting_new(
    session, datasource
):
    report = await sync_datasource(
        session, datasource, snapshot(('REGULAR', 'DESCARTADA'))
    )

    assert report.new_enum_values == []
    column = await status_column(session)
    assert column.enum_values == ['REGULAR', 'DESCARTADA']
    assert (await load_entities(session, 'origem'))[0].columns[
        0
    ].enum_values is None


async def test_new_enum_value_is_reported_and_undescribed(session, datasource):
    await sync_datasource(session, datasource, snapshot(('REGULAR',)))
    column = await status_column(session)
    column.values = [{'value': 'REGULAR', 'description': 'válida'}]
    await session.commit()

    report = await sync_datasource(
        session, datasource, snapshot(('REGULAR', 'SUSPENSA'))
    )

    assert report.new_enum_values == ['main.bolsas.status=SUSPENSA']
    column = await status_column(session)
    assert column.undescribed_values == ['SUSPENSA']
    assert column.obsolete_values == []


async def test_removed_enum_value_becomes_obsolete(session, datasource):
    await sync_datasource(
        session, datasource, snapshot(('REGULAR', 'DESCARTADA'))
    )
    column = await status_column(session)
    column.values = [
        {'value': 'REGULAR', 'description': 'válida'},
        {'value': 'DESCARTADA', 'description': 'descartada'},
    ]
    await session.commit()

    await sync_datasource(session, datasource, snapshot(('REGULAR',)))

    column = await status_column(session)
    assert column.obsolete_values == ['DESCARTADA']
    assert column.undescribed_values == []


async def test_context_lists_enum_values_without_obsolete(session, datasource):
    await sync_datasource(
        session, datasource, snapshot(('REGULAR', 'SUSPENSA'))
    )
    (bolsas,) = await load_entities(session, 'origem')
    bolsas.visible = True
    column = await status_column(session)
    column.visible = True
    column.values = [
        {'value': 'DESCARTADA', 'description': 'não existe mais'},
        {'value': 'REGULAR', 'description': 'válida'},
    ]
    await session.commit()

    text = render_context(
        datasource,
        await load_entities(session, 'origem'),
        await load_relationships(session, 'origem'),
    )

    assert 'Valores: `REGULAR` = válida; `SUSPENSA`' in text
    assert 'DESCARTADA' not in text


def test_fingerprint_ignores_order_and_position():
    first = snapshot(('A', 'B'))
    entity = first.entities[0]
    reordered = SchemaSnapshot(
        entities=(
            EntitySnapshot(
                entity.schema_name,
                entity.name,
                entity.kind,
                tuple(
                    ColumnSnapshot(
                        c.name,
                        c.data_type,
                        c.nullable,
                        c.primary_key,
                        10 - c.position,
                        c.enum_values,
                    )
                    for c in reversed(entity.columns)
                ),
                entity.foreign_keys,
            ),
        )
    )

    assert first.fingerprint() == reordered.fingerprint()
    assert first.fingerprint() != snapshot(('A', 'B', 'C')).fingerprint()
