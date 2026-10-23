import json
from typing import Annotated

from fastapi import Depends
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from observatorio_maria.database import get_session
from observatorio_maria.llm.prompts import MARIA_SYSTEM_PROMPT
from observatorio_maria.llm.registry import (
    ModelRegistry,
    ModelTier,
    get_model_registry,
)
from observatorio_maria.models import (
    Conversation,
    Message,
    MessageRole,
)
from observatorio_maria.schemas import TextBlock

AUTO_TITLE_MAX_LENGTH = 60


class ModelInvocationError(Exception):
    """O modelo de linguagem falhou ao gerar a resposta."""


def blocks_to_text(blocks: list[dict]) -> str:
    """Converte blocos persistidos no texto enviado ao modelo."""
    parts = [
        block['text'] if block.get('type') == 'text' else json.dumps(block)
        for block in blocks
    ]
    return '\n\n'.join(parts)


def to_langchain_message(message: Message) -> BaseMessage:
    text = blocks_to_text(message.content)
    if message.role == MessageRole.USER:
        return HumanMessage(text)
    return AIMessage(text)


def auto_title(content: str) -> str:
    title = ' '.join(content.split())
    if len(title) <= AUTO_TITLE_MAX_LENGTH:
        return title
    return title[: AUTO_TITLE_MAX_LENGTH - 1].rstrip() + '…'


async def get_history(
    session: AsyncSession, conversation: Conversation
) -> list[Message]:
    """Mensagens da conversa em ordem cronológica (não usa o modelo)."""
    result = await session.scalars(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at)
    )
    return list(result.all())


class ChatService:
    def __init__(self, session: AsyncSession, registry: ModelRegistry):
        self.session = session
        self.registry = registry

    async def send_message(
        self, conversation: Conversation, content: str, tier: ModelTier
    ) -> tuple[Message, Message]:
        registered = self.registry.get(tier)
        history = await get_history(self.session, conversation)

        user_message = Message(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content=[TextBlock(text=content).model_dump()],
        )
        prompt = [
            SystemMessage(MARIA_SYSTEM_PROMPT),
            *(to_langchain_message(message) for message in history),
            HumanMessage(content),
        ]

        try:
            response = await registered.model.ainvoke(prompt)
        except Exception as exc:
            raise ModelInvocationError(str(exc)) from exc

        assistant_message = Message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=[TextBlock(text=response.text).model_dump()],
            model_tier=tier,
            model_name=registered.name,
        )
        # Só persiste depois que o modelo respondeu: em caso de falha a
        # conversa permanece exatamente como estava.
        if conversation.title is None:
            conversation.title = auto_title(content)
        conversation.updated_at = assistant_message.created_at

        self.session.add_all([user_message, assistant_message])
        await self.session.commit()
        return user_message, assistant_message


def get_chat_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    registry: Annotated[ModelRegistry, Depends(get_model_registry)],
) -> ChatService:
    return ChatService(session, registry)
