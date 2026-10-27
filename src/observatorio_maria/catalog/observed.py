"""Valores observados nos dados da origem para colunas categóricas de texto.

Diferente da introspecção, aqui se leem dados, então a leitura é guiada pelo
catálogo: só colunas de texto sem enum, visíveis, presentes e com acesso
`full`, em entidades visíveis, presentes e consultáveis. Colunas ocultas ou
somente para agregação nunca são lidas. Os valores são técnicos e não entram
na impressão digital do schema.
"""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession

from observatorio_maria.catalog.introspection import (
    ConnectionNotConfiguredError,
    create_readonly_engine,
    resolve_connection_url,
)
from observatorio_maria.catalog.sync import load_entities
from observatorio_maria.models import (
    CatalogColumn,
    CatalogDataSource,
    CatalogEntity,
    ColumnAccess,
)
from observatorio_maria.settings import Settings

logger = logging.getLogger(__name__)

TEXT_TYPE_PREFIXES = (
    'VARCHAR',
    'NVARCHAR',
    'CHARACTER',
    'CHAR',
    'TEXT',
    'CITEXT',
    'NAME',
    'STRING',
)


@dataclass
class ObservedReport:
    read_columns: list[str] = field(default_factory=list)
    failed_columns: list[str] = field(default_factory=list)
    error: str | None = None


def is_text_type(data_type: str | None) -> bool:
    return bool(data_type) and data_type.upper().startswith(TEXT_TYPE_PREFIXES)


def is_eligible(entity: CatalogEntity, column: CatalogColumn) -> bool:
    return (
        entity.visible
        and entity.present
        and entity.queryable
        and column.visible
        and column.present
        and column.access == ColumnAccess.FULL
        and column.enum_values is None
        and is_text_type(column.data_type)
    )


async def _read_distinct(
    connection: AsyncConnection,
    entity: CatalogEntity,
    column: CatalogColumn,
    max_values: int,
    timeout_seconds: float,
) -> list[str] | None:
    quote = connection.dialect.identifier_preparer.quote
    name = quote(column.name)
    sql = (
        f'SELECT DISTINCT {name} FROM {quote(entity.schema_name)}.'
        f'{quote(entity.name)} WHERE {name} IS NOT NULL '
        f'LIMIT {max_values + 1}'
    )
    postgres = connection.dialect.name == 'postgresql'
    async with asyncio.timeout(timeout_seconds), connection.begin():
        if postgres:
            timeout_ms = int(timeout_seconds * 1000)
            await connection.execute(
                text(f'SET LOCAL statement_timeout = {timeout_ms}')
            )
        rows = (await connection.execute(text(sql))).all()
    if len(rows) > max_values:
        return None
    return sorted(str(row[0]) for row in rows)


async def _read_columns(
    engine: AsyncEngine,
    eligible: list[tuple[CatalogEntity, CatalogColumn]],
    report: ObservedReport,
    max_values: int,
    timeout_seconds: float,
) -> None:
    """Lê cada coluna isolada das falhas das outras."""
    async with engine.connect() as connection:
        for entity, column in eligible:
            label = f'{entity.qualified_name}.{column.name}'
            try:
                column.observed_values = await _read_distinct(
                    connection, entity, column, max_values, timeout_seconds
                )
                report.read_columns.append(label)
            except (SQLAlchemyError, TimeoutError):
                report.failed_columns.append(label)


async def refresh_observed_values(
    session: AsyncSession,
    datasource: CatalogDataSource,
    *,
    max_values: int | None = None,
    timeout_seconds: float | None = None,
    engine_factory: Callable[[str], AsyncEngine] = create_readonly_engine,
) -> ObservedReport:
    """Relê os valores observados das colunas elegíveis da fonte.

    Colunas não elegíveis ficam sem valores observados. Falha numa coluna
    mantém os valores anteriores dela; falha de conexão mantém todos.
    """
    settings = Settings()
    max_values = max_values or settings.CATALOG_OBSERVED_VALUES_MAX
    timeout_seconds = timeout_seconds or settings.QUERY_TIMEOUT_SECONDS

    report = ObservedReport()
    eligible = []
    for entity in await load_entities(session, datasource.id):
        for column in entity.columns:
            if is_eligible(entity, column):
                eligible.append((entity, column))
            else:
                column.observed_values = None

    if eligible:
        try:
            engine = engine_factory(
                resolve_connection_url(datasource.connection_env)
            )
            try:
                await _read_columns(
                    engine, eligible, report, max_values, timeout_seconds
                )
            finally:
                await engine.dispose()
        except ConnectionNotConfiguredError as exc:
            report.error = str(exc)
        except (SQLAlchemyError, OSError) as exc:
            # A mensagem original pode repetir a URL: só o tipo é guardado.
            report.error = (
                f'Não foi possível ler valores da origem: {type(exc).__name__}'
            )

    if report.error or report.failed_columns:
        logger.warning(
            'Valores observados da fonte %s incompletos: %s',
            datasource.id,
            report,
        )
    await session.commit()
    return report
