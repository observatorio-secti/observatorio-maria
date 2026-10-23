"""Detecção de defasagem entre o catálogo e o schema real da origem.

A sincronização grava a impressão digital do schema; a verificação lê o
schema de novo (somente leitura), compara e registra o estado da fonte e o
diff do que a próxima sincronização aplicaria. Nada editorial é alterado.
"""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from observatorio_maria.catalog.introspection import (
    ConnectionNotConfiguredError,
    Introspector,
    SchemaSnapshot,
    SourceUnavailableError,
    resolve_connection_url,
)
from observatorio_maria.catalog.sync import (
    SyncReport,
    load_entities,
    load_relationships,
    relationship_key,
    sync_datasource,
)
from observatorio_maria.models import (
    CatalogDataSource,
    CatalogEntity,
    CatalogRelationship,
    RelationshipOrigin,
    SchemaStatus,
    utcnow,
)

logger = logging.getLogger(__name__)


@dataclass
class SchemaDiff:
    added_entities: list[str] = field(default_factory=list)
    missing_entities: list[str] = field(default_factory=list)
    added_columns: list[str] = field(default_factory=list)
    missing_columns: list[str] = field(default_factory=list)
    changed_columns: list[str] = field(default_factory=list)
    new_enum_values: list[str] = field(default_factory=list)
    removed_enum_values: list[str] = field(default_factory=list)
    added_relationships: int = 0
    missing_relationships: int = 0


@dataclass
class CheckResult:
    status: SchemaStatus
    checked_at: datetime
    drift: SchemaDiff | None = None
    error: str | None = None
    sync: SyncReport | None = None


def _diff_columns(entity: CatalogEntity, snap, diff: SchemaDiff):
    prefix = entity.qualified_name
    columns = {column.name: column for column in entity.columns}
    for col in snap.columns:
        column = columns.get(col.name)
        if column is None:
            diff.added_columns.append(f'{prefix}.{col.name}')
            continue
        if column.data_type is not None:
            before = (column.data_type, column.nullable, column.primary_key)
            after = (col.data_type, col.nullable, col.primary_key)
            if before != after:
                diff.changed_columns.append(
                    f'{prefix}.{col.name}: {_describe(before)} -> '
                    f'{_describe(after)}'
                )
        if column.enum_values is not None:
            current = col.enum_values or ()
            diff.new_enum_values += [
                f'{prefix}.{col.name}={v}'
                for v in current
                if v not in column.enum_values
            ]
            diff.removed_enum_values += [
                f'{prefix}.{col.name}={v}'
                for v in column.enum_values
                if v not in current
            ]
    seen = {col.name for col in snap.columns}
    diff.missing_columns += [
        f'{prefix}.{column.name}'
        for column in entity.columns
        if column.present and column.name not in seen
    ]


def _describe(technical) -> str:
    data_type, nullable, primary_key = technical
    flags = ['nulo' if nullable else 'não nulo']
    if primary_key:
        flags.append('chave primária')
    return f'{data_type} ({", ".join(flags)})'


def diff_schema(
    entities: list[CatalogEntity],
    relationships: list[CatalogRelationship],
    snapshot: SchemaSnapshot,
) -> SchemaDiff:
    """O que `sync_datasource` aplicaria, sem alterar nada."""
    diff = SchemaDiff()
    catalog = {(e.schema_name, e.name): e for e in entities}
    snapshot_keys = {(s.schema_name, s.name) for s in snapshot.entities}

    for snap in snapshot.entities:
        entity = catalog.get((snap.schema_name, snap.name))
        if entity is None:
            diff.added_entities.append(f'{snap.schema_name}.{snap.name}')
            diff.added_columns += [
                f'{snap.schema_name}.{snap.name}.{col.name}'
                for col in snap.columns
            ]
        else:
            _diff_columns(entity, snap, diff)
    diff.missing_entities = [
        entity.qualified_name
        for key, entity in catalog.items()
        if entity.present and key not in snapshot_keys
    ]

    existing = {relationship_key(r) for r in relationships}
    found = set()
    for snap in snapshot.entities:
        source = catalog.get((snap.schema_name, snap.name))
        for fk in snap.foreign_keys:
            target_key = (fk.referred_schema, fk.referred_entity)
            target = catalog.get(target_key)
            if source is None or target is None:
                # Uma das pontas é nova: a sincronização criará a ligação,
                # desde que a ponta exista na origem.
                if target is not None or target_key in snapshot_keys:
                    diff.added_relationships += 1
                continue
            key = (source.id, fk.columns, target.id, fk.referred_columns)
            found.add(key)
            if key not in existing:
                diff.added_relationships += 1
    diff.missing_relationships = sum(
        1
        for r in relationships
        if r.origin == RelationshipOrigin.FOREIGN_KEY
        and r.present
        and relationship_key(r) not in found
    )
    return diff


async def check_datasource(
    session: AsyncSession,
    datasource: CatalogDataSource,
    introspect: Introspector,
) -> CheckResult:
    """Verifica a defasagem e registra o estado na fonte."""
    checked_at = utcnow()
    try:
        url = resolve_connection_url(datasource.connection_env)
        snapshot = await introspect(url, datasource.schemas)
    except (ConnectionNotConfiguredError, SourceUnavailableError) as exc:
        datasource.schema_status = SchemaStatus.ERROR
        datasource.check_error = str(exc)
        datasource.last_checked_at = checked_at
        await session.commit()
        return CheckResult(SchemaStatus.ERROR, checked_at, error=str(exc))

    if snapshot.fingerprint() == datasource.schema_fingerprint:
        datasource.schema_status = SchemaStatus.UP_TO_DATE
        datasource.drift = None
        datasource.check_error = None
        datasource.last_checked_at = checked_at
        await session.commit()
        return CheckResult(SchemaStatus.UP_TO_DATE, checked_at)

    if datasource.auto_sync:
        report = await sync_datasource(session, datasource, snapshot)
        logger.info(
            'Fonte %s sincronizada automaticamente: %s',
            datasource.id,
            asdict(report),
        )
        return CheckResult(SchemaStatus.UP_TO_DATE, checked_at, sync=report)

    diff = diff_schema(
        await load_entities(session, datasource.id),
        await load_relationships(session, datasource.id),
        snapshot,
    )
    datasource.schema_status = SchemaStatus.OUTDATED
    datasource.drift = asdict(diff)
    datasource.check_error = None
    datasource.last_checked_at = checked_at
    await session.commit()
    logger.warning('Fonte %s com schema defasado: %s', datasource.id, diff)
    return CheckResult(SchemaStatus.OUTDATED, checked_at, drift=diff)


SessionFactory = Callable[[], AsyncSession]


async def check_all(
    session_factory: SessionFactory, introspect: Introspector
) -> dict[str, SchemaStatus]:
    """Verifica as fontes ativas, cada uma isolada das falhas das outras."""
    async with session_factory() as session:
        ids = (
            await session.scalars(
                select(CatalogDataSource.id).where(CatalogDataSource.enabled)
            )
        ).all()

    results = {}
    for datasource_id in ids:
        try:
            async with session_factory() as session:
                datasource = await session.get(
                    CatalogDataSource, datasource_id
                )
                result = await check_datasource(
                    session, datasource, introspect
                )
                results[datasource_id] = result.status
        except Exception:
            logger.exception('Falha ao verificar a fonte %s', datasource_id)
    return results


async def run_periodic_checks(
    interval: float, session_factory: SessionFactory, introspect: Introspector
):
    while True:
        await check_all(session_factory, introspect)
        await asyncio.sleep(interval)


def start_periodic_checks(
    interval: float, session_factory: SessionFactory, introspect: Introspector
) -> asyncio.Task | None:
    """Inicia o laço (a primeira verificação é imediata); `0` desliga."""
    if interval <= 0:
        return None
    return asyncio.create_task(
        run_periodic_checks(interval, session_factory, introspect),
        name='catalog-schema-checks',
    )
