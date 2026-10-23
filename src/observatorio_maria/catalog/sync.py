"""Fusão de um `SchemaSnapshot` com o catálogo de uma fonte.

Regras: a sincronização só toca campos técnicos e `present`; o que é novo
entra oculto e não consultável; o que sumiu fica ausente com a configuração
intacta. Relacionamentos manuais (declarados no YAML) nunca ficam ausentes.
"""

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from observatorio_maria.catalog.introspection import SchemaSnapshot
from observatorio_maria.models import (
    CatalogColumn,
    CatalogDataSource,
    CatalogEntity,
    CatalogRelationship,
    RelationshipOrigin,
    SchemaStatus,
    utcnow,
)


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
