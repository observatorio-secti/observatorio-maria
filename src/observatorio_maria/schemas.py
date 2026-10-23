from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from observatorio_maria.models import MessageRole


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
