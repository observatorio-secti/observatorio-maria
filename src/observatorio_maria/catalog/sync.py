"""Fusão de um `SchemaSnapshot` com o catálogo de uma fonte.

Regras: a sincronização só toca campos técnicos e `present`; o que é novo
entra oculto e não consultável; o que sumiu fica ausente com a configuração
intacta. Relacionamentos manuais (declarados no YAML) nunca ficam ausentes.
"""

import argparse
import asyncio
import sys
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from observatorio_maria.catalog.introspection import (
    ConnectionNotConfiguredError,
    SchemaSnapshot,
    SourceUnavailableError,
    introspect,
    resolve_connection_url,
)
from observatorio_maria.database import SessionLocal
from observatorio_maria.models import (
    CatalogColumn,
    CatalogDataSource,
    CatalogEntity,
    CatalogRelationship,
    RelationshipOrigin,
    SchemaStatus,
    utcnow,
)
from observatorio_maria.settings import Settings


@dataclass
class SyncReport:
    synced_at: datetime
    added_entities: list[str] = field(default_factory=list)
    missing_entities: list[str] = field(default_factory=list)
    added_columns: list[str] = field(default_factory=list)
    missing_columns: list[str] = field(default_factory=list)
    new_enum_values: list[str] = field(default_factory=list)
    added_relationships: int = 0
    missing_relationships: int = 0


async def load_entities(
    session: AsyncSession, datasource_id: str
) -> list[CatalogEntity]:
    entities = await session.scalars(
        select(CatalogEntity)
        .where(CatalogEntity.datasource_id == datasource_id)
        .order_by(CatalogEntity.schema_name, CatalogEntity.name)
    )
    return list(entities.all())


async def load_relationships(
    session: AsyncSession, datasource_id: str
) -> list[CatalogRelationship]:
    relationships = await session.scalars(
        select(CatalogRelationship).where(
            CatalogRelationship.datasource_id == datasource_id
        )
    )
    return list(relationships.all())


def relationship_key(relationship: CatalogRelationship):
    return (
        relationship.from_entity_id,
        tuple(relationship.from_columns),
        relationship.to_entity_id,
        tuple(relationship.to_columns),
    )


def _merge_columns(entity, snapshot, report):
    columns = {column.name: column for column in entity.columns}
    for snap in snapshot.columns:
        column = columns.get(snap.name)
        if column is None:
            column = CatalogColumn(entity_id=entity.id, name=snap.name)
            entity.columns.append(column)
            report.added_columns.append(f'{entity.qualified_name}.{snap.name}')
        column.data_type = snap.data_type
        column.nullable = snap.nullable
        column.primary_key = snap.primary_key
        column.position = snap.position
        column.present = True
        if column.enum_values is not None and snap.enum_values:
            report.new_enum_values.extend(
                f'{entity.qualified_name}.{snap.name}={value}'
                for value in snap.enum_values
                if value not in column.enum_values
            )
        column.enum_values = (
            list(snap.enum_values) if snap.enum_values else None
        )

    seen = {snap.name for snap in snapshot.columns}
    for column in entity.columns:
        if column.name not in seen and column.present:
            column.present = False
            report.missing_columns.append(
                f'{entity.qualified_name}.{column.name}'
            )


async def sync_datasource(
    session: AsyncSession,
    datasource: CatalogDataSource,
    snapshot: SchemaSnapshot,
) -> SyncReport:
    report = SyncReport(synced_at=utcnow())
    entities = {
        (entity.schema_name, entity.name): entity
        for entity in await load_entities(session, datasource.id)
    }

    for snap in snapshot.entities:
        entity = entities.get((snap.schema_name, snap.name))
        if entity is None:
            entity = CatalogEntity(
                datasource_id=datasource.id,
                schema_name=snap.schema_name,
                name=snap.name,
            )
            session.add(entity)
            entities[snap.schema_name, snap.name] = entity
            report.added_entities.append(entity.qualified_name)
        entity.kind = snap.kind
        entity.present = True
        _merge_columns(entity, snap, report)

    seen = {(snap.schema_name, snap.name) for snap in snapshot.entities}
    for key, entity in entities.items():
        if key not in seen and entity.present:
            entity.present = False
            report.missing_entities.append(entity.qualified_name)

    relationships = {
        relationship_key(r): r
        for r in await load_relationships(session, datasource.id)
    }
    found = set()
    for snap in snapshot.entities:
        source = entities[snap.schema_name, snap.name]
        for fk in snap.foreign_keys:
            target = entities.get((fk.referred_schema, fk.referred_entity))
            if target is None:  # referência a um schema não sincronizado
                continue
            key = (source.id, fk.columns, target.id, fk.referred_columns)
            relationship = relationships.get(key)
            if relationship is None:
                relationship = CatalogRelationship(
                    datasource_id=datasource.id,
                    from_entity_id=source.id,
                    from_columns=list(fk.columns),
                    to_entity_id=target.id,
                    to_columns=list(fk.referred_columns),
                    origin=RelationshipOrigin.FOREIGN_KEY,
                )
                session.add(relationship)
                relationships[key] = relationship
                report.added_relationships += 1
            relationship.origin = RelationshipOrigin.FOREIGN_KEY
            relationship.present = True
            found.add(key)

    for key, relationship in relationships.items():
        if (
            key not in found
            and relationship.origin == RelationshipOrigin.FOREIGN_KEY
            and relationship.present
        ):
            relationship.present = False
            report.missing_relationships += 1

    datasource.last_synced_at = report.synced_at
    datasource.schema_fingerprint = snapshot.fingerprint()
    datasource.schema_status = SchemaStatus.UP_TO_DATE
    datasource.last_checked_at = report.synced_at
    datasource.drift = None
    datasource.check_error = None
    await session.commit()
    return report


async def sync_all(datasource_ids: list[str] | None = None) -> int:
    """Sincroniza as fontes informadas ou todas as fontes ativas."""
    # Import local evita ciclo com `observed`, que usa `load_entities`.
    from observatorio_maria.catalog.observed import (  # noqa: PLC0415
        refresh_observed_values,
    )

    Settings().export_environment()
    async with SessionLocal() as session:
        stmt = select(CatalogDataSource.id).order_by(CatalogDataSource.id)
        if datasource_ids:
            stmt = stmt.where(CatalogDataSource.id.in_(datasource_ids))
        else:
            stmt = stmt.where(CatalogDataSource.enabled)
        ids = list((await session.scalars(stmt)).all())

    if not ids:
        print('Nenhuma fonte ativa para sincronizar.')
        return 0

    for datasource_id in ids:
        try:
            async with SessionLocal() as session:
                datasource = await session.get(
                    CatalogDataSource, datasource_id
                )
                if datasource is None:
                    continue
                url = resolve_connection_url(datasource.connection_env)
                snapshot = await introspect(url, datasource.schemas)
                report = await sync_datasource(session, datasource, snapshot)
                await refresh_observed_values(session, datasource)
                print(
                    f'{datasource.id}: sincronizada '
                    f'(+{len(report.added_entities)} entidade(s), '
                    f'+{len(report.added_columns)} coluna(s))'
                )
        except (ConnectionNotConfiguredError, SourceUnavailableError) as exc:
            print(
                f'{datasource_id}: aviso: {exc}',
                file=sys.stderr,
            )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Sincroniza o catálogo com os bancos de origem.'
    )
    parser.add_argument(
        'datasources',
        nargs='*',
        help='IDs das fontes (padrão: todas as fontes ativas)',
    )
    args = parser.parse_args(argv)
    return asyncio.run(sync_all(args.datasources or None))


if __name__ == '__main__':
    sys.exit(main())
