from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from observatorio_maria.catalog.yaml_io import ColumnValue, EnvName, Slug
from observatorio_maria.models import (
    ColumnAccess,
    EntityKind,
    MessageRole,
    RelationshipOrigin,
    SchemaStatus,
)


class Message(BaseModel):
    message: str


class HealthCheck(BaseModel):
    status: str
    database: str


# --- Conversas ---------------------------------------------------------------

Title = Annotated[str, Field(min_length=1, max_length=200)]


class ConversationCreate(BaseModel):
    title: Title | None = None


class ConversationUpdate(BaseModel):
    title: Title


class ConversationPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str | None
    created_at: datetime
    updated_at: datetime


class ConversationList(BaseModel):
    conversations: list[ConversationPublic]
    total: int


class Pagination(BaseModel):
    offset: int = Field(0, ge=0)
    limit: int = Field(20, ge=1, le=100)


# --- Blocos de conteúdo ------------------------------------------------------
# O conteúdo de uma mensagem é uma lista de blocos discriminados por "type".
# O frontend renderiza cada bloco conforme o tipo e ignora tipos que não
# conhece, então novos blocos podem ser adicionados sem quebrar clientes.


class TextBlock(BaseModel):
    type: Literal['text'] = 'text'
    text: str = Field(description='Texto em Markdown.')


class ChartAxis(BaseModel):
    key: str = Field(description='Chave do eixo em cada item de `data`.')
    label: str
    type: Literal['category', 'number', 'date'] = 'category'


class ChartSeries(BaseModel):
    key: str = Field(description='Chave do valor em cada item de `data`.')
    label: str
    unit: str | None = None


class ChartBlock(BaseModel):
    type: Literal['chart'] = 'chart'
    chart_type: Literal['bar', 'line', 'area', 'pie', 'scatter']
    title: str
    x: ChartAxis
    series: list[ChartSeries]
    data: list[dict[str, Any]] = Field(
        description='Registros; cada um contém `x.key` e as `series[].key`.'
    )


class TableColumn(BaseModel):
    key: str
    label: str
    type: Literal['string', 'number', 'date'] = 'string'


class TableBlock(BaseModel):
    type: Literal['table'] = 'table'
    title: str | None = None
    columns: list[TableColumn]
    rows: list[dict[str, Any]]


ContentBlock = Annotated[
    TextBlock | ChartBlock | TableBlock, Field(discriminator='type')
]


# --- Mensagens ---------------------------------------------------------------


class MessageCreate(BaseModel):
    # Só o texto: o modelo usado é decisão interna e não pode ser escolhido
    # pelo cliente, por isso campos extras são rejeitados.
    model_config = ConfigDict(extra='forbid')

    content: str = Field(min_length=1, max_length=10_000)


class MessagePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    role: MessageRole
    content: list[ContentBlock]
    created_at: datetime


class MessageList(BaseModel):
    messages: list[MessagePublic]


class ChatExchange(BaseModel):
    user_message: MessagePublic
    assistant_message: MessagePublic


# --- Streaming (Server-Sent Events) ------------------------------------------


class ContentDeltaPublic(BaseModel):
    """Evento `content.delta`: fragmento do bloco `index` da resposta."""

    index: int
    type: Literal['text'] = 'text'
    text: str


class StreamError(BaseModel):
    """Evento `error`: falha depois de iniciado o stream."""

    detail: str


# --- Catálogo de fontes de dados ---------------------------------------------
# Nos PATCH, campos omitidos não mudam. Os textos opcionais aceitam null para
# limpar; os demais (sem `| None`) rejeitam null.

Label = Annotated[str, Field(min_length=1, max_length=200)]
Synonyms = list[Annotated[str, Field(min_length=1, max_length=100)]]


class DataSourceCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: Slug
    name: Label
    connection_env: EnvName
    description: str | None = None
    instructions: str | None = None
    schemas: list[str] = Field(['public'], min_length=1)
    enabled: bool = True
    auto_sync: bool = False


class DataSourceUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    name: Label = None
    connection_env: EnvName = None
    description: str | None = None
    instructions: str | None = None
    schemas: list[str] = Field(None, min_length=1)
    enabled: bool = None
    auto_sync: bool = None


class SchemaDiffPublic(BaseModel):
    """O que a próxima sincronização aplicaria."""

    added_entities: list[str]
    missing_entities: list[str]
    added_columns: list[str]
    missing_columns: list[str]
    changed_columns: list[str]
    new_enum_values: list[str]
    removed_enum_values: list[str]
    added_relationships: int
    missing_relationships: int


class DataSourcePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    connection_env: str
    description: str | None
    instructions: str | None
    schemas: list[str]
    enabled: bool
    auto_sync: bool
    last_synced_at: datetime | None
    schema_status: SchemaStatus
    last_checked_at: datetime | None
    drift: SchemaDiffPublic | None
    check_error: str | None
    created_at: datetime
    updated_at: datetime
    entities_total: int = 0
    entities_visible: int = 0
    entities_queryable: int = 0


class DataSourceList(BaseModel):
    datasources: list[DataSourcePublic]


class SyncReportPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    synced_at: datetime
    added_entities: list[str]
    missing_entities: list[str]
    added_columns: list[str]
    missing_columns: list[str]
    new_enum_values: list[str]
    added_relationships: int
    missing_relationships: int


class CheckResultPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: SchemaStatus
    checked_at: datetime
    drift: SchemaDiffPublic | None
    error: str | None
    sync: SyncReportPublic | None = Field(
        description='Resumo da sincronização automática, quando houve.'
    )


class ColumnPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    entity_id: UUID
    name: str
    data_type: str | None
    nullable: bool | None
    primary_key: bool
    position: int | None
    label: str | None
    description: str | None
    synonyms: list[str]
    values: list[ColumnValue]
    enum_values: list[str] | None = Field(
        description='Valores do enum na origem; nulo se a coluna não é enum.'
    )
    undescribed_values: list[str]
    obsolete_values: list[str]
    visible: bool
    access: ColumnAccess
    present: bool


class ColumnUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    label: Label | None = None
    description: str | None = None
    synonyms: Synonyms = None
    values: list[ColumnValue] = None
    visible: bool = None
    access: ColumnAccess = None


class EntitySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    datasource_id: str
    schema_name: str
    name: str
    kind: EntityKind | None
    label: str | None
    description: str | None
    synonyms: list[str]
    visible: bool
    queryable: bool
    present: bool
    columns_total: int
    columns_visible: int


class EntityDetail(EntitySummary):
    columns: list[ColumnPublic]


class EntityList(BaseModel):
    entities: list[EntitySummary]


class EntityUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    label: Label | None = None
    description: str | None = None
    synonyms: Synonyms = None
    visible: bool = None
    queryable: bool = None


class RelationshipPublic(BaseModel):
    id: UUID
    from_entity_id: UUID
    from_entity: str
    from_columns: list[str]
    to_entity_id: UUID
    to_entity: str
    to_columns: list[str]
    origin: RelationshipOrigin
    description: str | None
    enabled: bool
    present: bool


class RelationshipList(BaseModel):
    relationships: list[RelationshipPublic]


class RelationshipUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    description: str | None = None
    enabled: bool = None


class ContextPreview(BaseModel):
    datasource_id: str
    enabled: bool
    content: str = Field(description='Texto em Markdown enviado ao modelo.')
