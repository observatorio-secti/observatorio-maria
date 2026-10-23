from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, String, TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column, registry

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
