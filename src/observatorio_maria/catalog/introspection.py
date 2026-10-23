"""Leitura do schema de uma fonte externa, sempre em modo somente leitura.

Só a estrutura é lida (tabelas, views, colunas e chaves); nenhum dado e
nenhuma escrita. O resultado é um `SchemaSnapshot` imutável, que a
sincronização funde com o catálogo.
"""

import hashlib
import json
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy import event, inspect
from sqlalchemy.engine import Connection, Inspector, make_url
from sqlalchemy.exc import ArgumentError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from observatorio_maria.models import EntityKind

CONNECT_TIMEOUT_SECONDS = 5


class ConnectionNotConfiguredError(Exception):
    """A variável de ambiente com a URL da fonte não está definida."""

    def __init__(self, env: str):
        super().__init__(f'Variável de ambiente {env} não definida')
        self.env = env


class SourceUnavailableError(Exception):
    """Não foi possível conectar ou ler o schema da origem."""


@dataclass(frozen=True)
class ColumnSnapshot:
    name: str
    data_type: str
    nullable: bool
    primary_key: bool
    position: int
    # Valores do tipo enum nativo, na ordem da origem; None se não é enum.
    enum_values: tuple[str, ...] | None = None


@dataclass(frozen=True)
class ForeignKeySnapshot:
    columns: tuple[str, ...]
    referred_schema: str
    referred_entity: str
    referred_columns: tuple[str, ...]


@dataclass(frozen=True)
class EntitySnapshot:
    schema_name: str
    name: str
    kind: EntityKind
    columns: tuple[ColumnSnapshot, ...]
    foreign_keys: tuple[ForeignKeySnapshot, ...]


@dataclass(frozen=True)
class SchemaSnapshot:
    entities: tuple[EntitySnapshot, ...]

    def fingerprint(self) -> str:
        """Hash da estrutura, independente da ordem de leitura e da posição
        das colunas (reordenar colunas não é defasagem)."""
        canonical = sorted(
            [
                entity.schema_name,
                entity.name,
                str(entity.kind),
                sorted(
                    [
                        c.name,
                        c.data_type,
                        c.nullable,
                        c.primary_key,
                        list(c.enum_values) if c.enum_values else None,
                    ]
                    for c in entity.columns
                ),
                sorted(
                    [
                        list(fk.columns),
                        fk.referred_schema,
                        fk.referred_entity,
                        list(fk.referred_columns),
                    ]
                    for fk in entity.foreign_keys
                ),
            ]
            for entity in self.entities
        )
        payload = json.dumps(canonical, ensure_ascii=False)
        return hashlib.sha256(payload.encode()).hexdigest()


Introspector = Callable[[str, list[str]], Awaitable[SchemaSnapshot]]


def resolve_connection_url(env: str) -> str:
    url = os.environ.get(env)
    if not url:
        raise ConnectionNotConfiguredError(env)
    return url


def create_readonly_engine(url: str) -> AsyncEngine:
    """Engine efêmero cujas sessões não conseguem escrever na origem."""
    backend = make_url(url).get_backend_name()
    connect_args = {}
    if backend == 'postgresql':
        connect_args = {
            'options': '-c default_transaction_read_only=on',
            'connect_timeout': CONNECT_TIMEOUT_SECONDS,
        }
    engine = create_async_engine(
        url, poolclass=NullPool, connect_args=connect_args
    )
    if backend == 'sqlite':

        @event.listens_for(engine.sync_engine, 'connect')
        def _query_only(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute('PRAGMA query_only=ON')
            cursor.close()

    return engine


def _type_name(column: dict, connection: Connection) -> str:
    try:
        return column['type'].compile(dialect=connection.dialect)
    except Exception:  # noqa: BLE001 - tipos sem compilação no dialeto
        return type(column['type']).__name__


def _enum_values(column: dict) -> tuple[str, ...] | None:
    # O ENUM do PostgreSQL refletido traz os rótulos em `enums`.
    values = getattr(column['type'], 'enums', None)
    return tuple(values) if values else None


def _names_by_kind(
    inspector: Inspector, schema: str
) -> list[tuple[str, EntityKind]]:
    names = [(n, EntityKind.TABLE) for n in inspector.get_table_names(schema)]
    names += [(n, EntityKind.VIEW) for n in inspector.get_view_names(schema)]
    try:
        names += [
            (n, EntityKind.MATERIALIZED_VIEW)
            for n in inspector.get_materialized_view_names(schema)
        ]
    except NotImplementedError:  # dialetos sem views materializadas
        pass
    return sorted(names)


def _read_schema(connection: Connection, schemas: list[str]) -> SchemaSnapshot:
    inspector = inspect(connection)
    entities = []
    for schema in schemas:
        for name, kind in _names_by_kind(inspector, schema):
            primary_key = set(
                inspector.get_pk_constraint(name, schema)[
                    'constrained_columns'
                ]
                or []
            )
            columns = tuple(
                ColumnSnapshot(
                    name=column['name'],
                    data_type=_type_name(column, connection),
                    nullable=bool(column['nullable']),
                    primary_key=column['name'] in primary_key,
                    position=position,
                    enum_values=_enum_values(column),
                )
                for position, column in enumerate(
                    inspector.get_columns(name, schema), start=1
                )
            )
            foreign_keys = tuple(
                ForeignKeySnapshot(
                    columns=tuple(fk['constrained_columns']),
                    referred_schema=fk['referred_schema'] or schema,
                    referred_entity=fk['referred_table'],
                    referred_columns=tuple(fk['referred_columns']),
                )
                for fk in inspector.get_foreign_keys(name, schema)
            )
            entities.append(
                EntitySnapshot(schema, name, kind, columns, foreign_keys)
            )
    return SchemaSnapshot(entities=tuple(entities))


async def introspect(url: str, schemas: list[str]) -> SchemaSnapshot:
    try:
        engine = create_readonly_engine(url)
    except ArgumentError as exc:
        # A mensagem original repete a URL, com a senha: não é repassada.
        raise SourceUnavailableError(
            'URL de conexão inválida ou driver não suportado'
        ) from exc
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(_read_schema, schemas)
    except (SQLAlchemyError, OSError) as exc:
        cause = getattr(exc, 'orig', None) or exc
        detail = str(cause).strip().splitlines()[0] if str(cause) else ''
        raise SourceUnavailableError(
            f'Não foi possível ler a origem: {detail or type(cause).__name__}'
        ) from exc
    finally:
        await engine.dispose()


def get_introspector() -> Introspector:
    return introspect
