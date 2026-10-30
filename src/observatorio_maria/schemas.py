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
    ValueListing,
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
    total_tokens: int = 0
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


class BlockCoverage(BaseModel):
    keys: int = Field(description='Chaves na fonte de origem da ligação.')
    found: int = Field(description='Chaves encontradas na outra fonte.')


class BlockOrigin(BaseModel):
    sources: list[str] = Field(description='Nomes das fontes consultadas.')
    description: str = Field(description='O que foi consultado.')
    queried_at: datetime = Field(description='Momento da consulta.')
    coverage: BlockCoverage | None = None


class ChartBlock(BaseModel):
    type: Literal['chart'] = 'chart'
    chart_type: Literal['bar', 'line', 'area', 'pie', 'scatter']
    title: str
    x: ChartAxis
    series: list[ChartSeries]
    data: list[dict[str, Any]] = Field(
        description='Registros; cada um contém `x.key` e as `series[].key`.'
    )
    truncated: bool = Field(
        default=False,
        description='O resultado foi cortado pelo limite de linhas.',
    )
    origin: BlockOrigin | None = None


class TableColumn(BaseModel):
    key: str
    label: str
    type: Literal['string', 'number', 'date'] = 'string'


class TableBlock(BaseModel):
    type: Literal['table'] = 'table'
    title: str | None = None
    columns: list[TableColumn]
    rows: list[dict[str, Any]]
    truncated: bool = Field(
        default=False,
        description='O resultado foi cortado pelo limite de linhas.',
    )
    origin: BlockOrigin | None = None


class SuggestionsBlock(BaseModel):
    type: Literal['suggestions'] = 'suggestions'
    questions: list[str] = Field(
        description='Perguntas de continuação, para o usuário enviar.'
    )


ContentBlock = Annotated[
    TextBlock | ChartBlock | TableBlock | SuggestionsBlock,
    Field(discriminator='type'),
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


class ActivityPublic(BaseModel):
    """Evento `activity`: ação em andamento (ex: consulta a dados)."""

    kind: Literal['query'] = 'query'
    source: str = Field(description='Nome da fonte de dados consultada.')
    description: str = Field(description='Descrição curta da consulta.')


class ContentDeltaPublic(BaseModel):
    """Evento `content.delta`: fragmento do bloco `index` da resposta."""

    index: int
    type: Literal['text', 'chart', 'table', 'suggestions'] = 'text'
    text: str | None = None
    block: dict[str, Any] | None = None


class StreamError(BaseModel):
    """Evento `error`: falha depois de iniciado o stream."""

    detail: str


# --- Catálogo de fontes de dados ---------------------------------------------
# Nos PATCH, campos omitidos não mudam. Os textos opcionais aceitam null para
# limpar; os demais (sem `| None`) rejeitam null.

Label = Annotated[str, Field(min_length=1, max_length=200)]
Synonyms = list[Annotated[str, Field(min_length=1, max_length=100)]]


class QueryExample(BaseModel):
    model_config = ConfigDict(extra='forbid')

    question: Annotated[str, Field(min_length=1, max_length=500)]
    sql: Annotated[str, Field(min_length=1)]


class DataSourceCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: Slug
    name: Label
    connection_env: EnvName
    description: str | None = None
    instructions: str | None = None
    examples: list[QueryExample] = Field(default_factory=list)
    schemas: list[str] = Field(['public'], min_length=1)
    enabled: bool = True
    auto_sync: bool = False


class DataSourceUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    name: Label = None
    connection_env: EnvName = None
    description: str | None = None
    instructions: str | None = None
    examples: list[QueryExample] | None = None
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
    examples: list[QueryExample] = Field(default_factory=list)
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
    observed_values: list[str] | None = Field(
        description=(
            'Valores distintos lidos dos dados da origem; nulo se a coluna '
            'não é categórica, não é lida ou ainda não foi lida.'
        )
    )
    undescribed_values: list[str]
    obsolete_values: list[str]
    visible: bool
    access: ColumnAccess
    searchable: bool
    list_values: ValueListing
    present: bool


class ColumnUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    label: Label | None = None
    description: str | None = None
    synonyms: Synonyms = None
    values: list[ColumnValue] = None
    visible: bool = None
    access: ColumnAccess = None
    searchable: bool = None
    list_values: ValueListing = None


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
    concept_id: str | None = None
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
    concept_id: Slug | None = None
    visible: bool = None
    queryable: bool = None


class ConceptCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: Slug
    label: Label
    description: str | None = None
    synonyms: Synonyms = Field(default_factory=list)
    instructions: str | None = None


class ConceptUpdate(BaseModel):
    """O identificador do conceito é imutável."""

    model_config = ConfigDict(extra='forbid')

    label: Label = None
    description: str | None = None
    synonyms: Synonyms = None
    instructions: str | None = None


class ConceptEntity(BaseModel):
    id: UUID
    datasource_id: str
    schema_name: str
    name: str
    label: str | None


class ConceptPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    label: str
    description: str | None
    synonyms: list[str]
    instructions: str | None
    entities: list[ConceptEntity] = Field(default_factory=list)


class ConceptList(BaseModel):
    concepts: list[ConceptPublic]


class ConceptContextPreview(BaseModel):
    content: str = Field(
        description=(
            'Seção "Conceitos em várias fontes" do prompt, em Markdown; '
            'vazia quando nenhum conceito tem entidades em duas fontes.'
        )
    )


class SourceLinkEnd(BaseModel):
    """Uma ponta da ligação: fonte, entidade e coluna."""

    model_config = ConfigDict(extra='forbid')

    datasource_id: str
    schema_name: str = 'public'
    entity: str
    column: str


class SourceLinkCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    source: SourceLinkEnd = Field(alias='from')
    target: SourceLinkEnd = Field(alias='to')
    description: str | None = None
    enabled: bool = True


class SourceLinkUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    description: str | None = None
    enabled: bool = None


class SourceLinkPublic(BaseModel):
    id: UUID
    from_datasource_id: str
    from_entity: str
    from_column: str
    to_datasource_id: str
    to_entity: str
    to_column: str
    description: str | None
    enabled: bool
    active: bool = Field(
        description=(
            'Ligada e com as duas colunas visíveis e presentes: só assim '
            'vale para consultas.'
        )
    )


class SourceLinkList(BaseModel):
    links: list[SourceLinkPublic]


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


class RejectedExample(BaseModel):
    question: str
    reason: str


class ContextPreview(BaseModel):
    datasource_id: str
    enabled: bool
    content: str = Field(description='Texto em Markdown enviado ao modelo.')
    rejected_examples: list[RejectedExample] = Field(
        default_factory=list,
        description=(
            'Exemplos few-shot fora do contexto por não passarem nas regras '
            'de consulta do catálogo.'
        ),
    )
