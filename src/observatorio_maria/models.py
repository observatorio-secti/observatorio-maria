from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
    false,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, registry, relationship

table_registry = registry()


def utcnow() -> datetime:
    # Timestamps gerados na aplicação têm precisão de microssegundos,
    # o que garante ordenação estável mesmo no SQLite.
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator):
    """DateTime sempre com fuso UTC, inclusive no SQLite (que o descarta)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_result_value(self, value, dialect):  # noqa: PLR6301
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


class MessageRole(StrEnum):
    USER = 'user'
    ASSISTANT = 'assistant'


@table_registry.mapped_as_dataclass
class Conversation:
    __tablename__ = 'conversations'

    id: Mapped[UUID] = mapped_column(
        init=False, primary_key=True, default_factory=uuid4
    )
    title: Mapped[str | None] = mapped_column(String(200), default=None)
    total_tokens: Mapped[int] = mapped_column(
        Integer, server_default=text('0'), default=0
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, init=False, default_factory=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        init=False,
        default_factory=utcnow,
        onupdate=utcnow,
    )


@table_registry.mapped_as_dataclass
class Message:
    __tablename__ = 'messages'

    id: Mapped[UUID] = mapped_column(
        init=False, primary_key=True, default_factory=uuid4
    )
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey('conversations.id', ondelete='CASCADE'), index=True
    )
    role: Mapped[MessageRole] = mapped_column(String(20))
    # Lista de blocos tipados (ver schemas.ContentBlock), gravada como JSON
    # para que novos tipos de bloco não exijam migração.
    content: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    model_tier: Mapped[str | None] = mapped_column(String(20), default=None)
    model_name: Mapped[str | None] = mapped_column(String(200), default=None)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, init=False, default_factory=utcnow
    )


# --- Catálogo de fontes de dados ---------------------------------------------
# Descreve bancos externos para a IA. Campos técnicos (tipo, presença, chaves)
# vêm da sincronização com a origem; os editoriais (rótulos, descrições,
# interruptores) vêm de pessoas e nunca são sobrescritos automaticamente.


class EntityKind(StrEnum):
    TABLE = 'table'
    VIEW = 'view'
    MATERIALIZED_VIEW = 'materialized_view'


class ColumnAccess(StrEnum):
    FULL = 'full'
    AGGREGATE = 'aggregate'


class ValueListing(StrEnum):
    """Se os valores conhecidos de uma coluna entram no contexto do modelo."""

    AUTO = 'auto'
    ALWAYS = 'always'
    NEVER = 'never'


class RelationshipOrigin(StrEnum):
    FOREIGN_KEY = 'foreign_key'
    MANUAL = 'manual'


class SchemaStatus(StrEnum):
    UNKNOWN = 'unknown'
    UP_TO_DATE = 'up_to_date'
    OUTDATED = 'outdated'
    ERROR = 'error'


@table_registry.mapped_as_dataclass(kw_only=True)
class CatalogDataSource:
    __tablename__ = 'catalog_datasources'

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    # Nome da variável de ambiente com a URL de conexão, nunca a URL em si.
    connection_env: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    instructions: Mapped[str | None] = mapped_column(Text, default=None)
    examples: Mapped[list[dict[str, str]]] = mapped_column(
        JSON, default_factory=list, server_default=text("'[]'")
    )
    schemas: Mapped[list[str]] = mapped_column(
        JSON, default_factory=lambda: ['public']
    )
    enabled: Mapped[bool] = mapped_column(default=True)
    # Liga a sincronização automática quando a verificação detecta defasagem.
    auto_sync: Mapped[bool] = mapped_column(
        default=False, server_default=false()
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime, default=None
    )
    # Estado da defasagem: a impressão digital vem da última sincronização;
    # a verificação compara e registra o diff (`drift`) ou o erro.
    schema_fingerprint: Mapped[str | None] = mapped_column(
        String(64), default=None
    )
    schema_status: Mapped[SchemaStatus] = mapped_column(
        String(20),
        default=SchemaStatus.UNKNOWN,
        server_default=SchemaStatus.UNKNOWN.value,
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime, default=None
    )
    drift: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    check_error: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, init=False, default_factory=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, init=False, default_factory=utcnow, onupdate=utcnow
    )


@table_registry.mapped_as_dataclass(kw_only=True)
class CatalogConcept:
    """Assunto que aparece em mais de uma fonte (dado editorial)."""

    __tablename__ = 'catalog_concepts'

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    synonyms: Mapped[list[str]] = mapped_column(JSON, default_factory=list)
    # Política de resposta: o que o conceito é em cada fonte e qual usar.
    instructions: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, init=False, default_factory=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, init=False, default_factory=utcnow, onupdate=utcnow
    )


@table_registry.mapped_as_dataclass(kw_only=True)
class CatalogEntity:
    __tablename__ = 'catalog_entities'
    __table_args__ = (
        UniqueConstraint('datasource_id', 'schema_name', 'name'),
    )

    id: Mapped[UUID] = mapped_column(
        init=False, primary_key=True, default_factory=uuid4
    )
    datasource_id: Mapped[str] = mapped_column(
        ForeignKey('catalog_datasources.id', ondelete='CASCADE'), index=True
    )
    schema_name: Mapped[str] = mapped_column(String(128))
    name: Mapped[str] = mapped_column(String(128))
    # Preenchido pela sincronização; None enquanto só existe no seed.
    kind: Mapped[str | None] = mapped_column(String(30), default=None)
    label: Mapped[str | None] = mapped_column(String(200), default=None)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    synonyms: Mapped[list[str]] = mapped_column(JSON, default_factory=list)
    # Conceito editorial ao qual a entidade pertence; a sincronização não o
    # altera.
    concept_id: Mapped[str | None] = mapped_column(
        ForeignKey('catalog_concepts.id', ondelete='SET NULL'),
        default=None,
        index=True,
    )
    visible: Mapped[bool] = mapped_column(default=False)
    queryable: Mapped[bool] = mapped_column(default=False)
    present: Mapped[bool] = mapped_column(default=False)
    columns: Mapped[list['CatalogColumn']] = relationship(
        init=False,
        cascade='all, delete-orphan',
        passive_deletes=True,
        lazy='selectin',
        order_by='CatalogColumn.position',
    )

    @property
    def qualified_name(self) -> str:
        return f'{self.schema_name}.{self.name}'


@table_registry.mapped_as_dataclass(kw_only=True)
class CatalogColumn:
    __tablename__ = 'catalog_columns'
    __table_args__ = (UniqueConstraint('entity_id', 'name'),)

    id: Mapped[UUID] = mapped_column(
        init=False, primary_key=True, default_factory=uuid4
    )
    entity_id: Mapped[UUID] = mapped_column(
        ForeignKey('catalog_entities.id', ondelete='CASCADE'), index=True
    )
    name: Mapped[str] = mapped_column(String(128))
    data_type: Mapped[str | None] = mapped_column(String(100), default=None)
    nullable: Mapped[bool | None] = mapped_column(default=None)
    primary_key: Mapped[bool] = mapped_column(default=False)
    position: Mapped[int | None] = mapped_column(default=None)
    # Valores do tipo enum na origem (técnico); None se a coluna não é enum.
    enum_values: Mapped[list[str] | None] = mapped_column(JSON, default=None)
    # Valores distintos lidos dos dados da origem (técnico); None se a coluna
    # não é categórica ou não foi lida.
    observed_values: Mapped[list[str] | None] = mapped_column(
        JSON, default=None
    )
    label: Mapped[str | None] = mapped_column(String(200), default=None)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    synonyms: Mapped[list[str]] = mapped_column(JSON, default_factory=list)
    # Valores conhecidos: [{"value": ..., "description": ...}].
    values: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default_factory=list
    )
    visible: Mapped[bool] = mapped_column(default=False)
    access: Mapped[ColumnAccess] = mapped_column(
        String(20), default=ColumnAccess.FULL
    )
    searchable: Mapped[bool] = mapped_column(
        default=False, server_default=false()
    )
    # Editorial: `auto` segue a regra de categorias de catalog/context.py.
    list_values: Mapped[ValueListing] = mapped_column(
        String(10),
        default=ValueListing.AUTO,
        server_default=ValueListing.AUTO.value,
    )
    present: Mapped[bool] = mapped_column(default=False)

    def _described(self) -> set[str]:
        return {
            str(item['value'])
            for item in self.values
            if item.get('description')
        }

    @property
    def source_values(self) -> list[str] | None:
        """Valores atuais da origem: os do enum ou, sem enum, os observados
        nos dados. None quando a origem não informa valores."""
        if self.enum_values is not None:
            return self.enum_values
        return self.observed_values

    @property
    def undescribed_values(self) -> list[str]:
        """Valores da origem ainda sem descrição editorial."""
        described = self._described()
        return [v for v in self.source_values or [] if v not in described]

    @property
    def obsolete_values(self) -> list[str]:
        """Valores editoriais que não existem (mais) na origem."""
        if self.source_values is None:
            return []
        current = set(self.source_values)
        return [
            str(item['value'])
            for item in self.values
            if str(item['value']) not in current
        ]


@table_registry.mapped_as_dataclass(kw_only=True)
class CatalogRelationship:
    __tablename__ = 'catalog_relationships'

    id: Mapped[UUID] = mapped_column(
        init=False, primary_key=True, default_factory=uuid4
    )
    datasource_id: Mapped[str] = mapped_column(
        ForeignKey('catalog_datasources.id', ondelete='CASCADE'), index=True
    )
    from_entity_id: Mapped[UUID] = mapped_column(
        ForeignKey('catalog_entities.id', ondelete='CASCADE')
    )
    from_columns: Mapped[list[str]] = mapped_column(JSON)
    to_entity_id: Mapped[UUID] = mapped_column(
        ForeignKey('catalog_entities.id', ondelete='CASCADE')
    )
    to_columns: Mapped[list[str]] = mapped_column(JSON)
    origin: Mapped[RelationshipOrigin] = mapped_column(String(20))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    enabled: Mapped[bool] = mapped_column(default=True)
    present: Mapped[bool] = mapped_column(default=True)
