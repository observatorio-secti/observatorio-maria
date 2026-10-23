import json
import logging
from collections.abc import AsyncIterator
from contextlib import suppress
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from openinference.instrumentation import OITracer, using_session
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
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
from observatorio_maria.observability.genai import (
    get_llm_callbacks,
    get_tracer,
)
from observatorio_maria.schemas import TextBlock

logger = logging.getLogger(__name__)

AUTO_TITLE_MAX_LENGTH = 60

# Nível usado nas respostas do chat. Decisão interna: não é exposta nem
# configurável por clientes da API.
CHAT_MODEL_TIER = ModelTier.MEDIUM


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


@dataclass(frozen=True)
class UserMessageCreated:
    message: Message


@dataclass(frozen=True)
class ContentDelta:
    """Fragmento do bloco `index` do conteúdo da resposta."""

    index: int
    text: str


@dataclass(frozen=True)
class AssistantMessageCompleted:
    message: Message


ChatEvent = UserMessageCreated | ContentDelta | AssistantMessageCompleted


class _ModelStep:
    """Avança o stream do modelo com o span `maria.chat` ativo.

    O contexto é ativado apenas durante cada passo, e não entre os `yield`s
    do gerador, para não vazar para o código que consome os eventos.
    """

    def __init__(self, span, session_id: str, stream):
        self.span = span
        self.session_id = session_id
        self.stream = stream

    async def next_chunk(self) -> AIMessageChunk | None:
        with (
            trace.use_span(self.span, end_on_exit=False),
            using_session(self.session_id),
        ):
            try:
                return await anext(self.stream)
            except StopAsyncIteration:
                return None
            except Exception as exc:
                logger.exception(
                    'Falha ao gerar resposta do modelo',
                    extra={'conversation.id': self.session_id},
                )
                raise ModelInvocationError(str(exc)) from exc

    async def close(self):
        with suppress(Exception):
            await self.stream.aclose()


class ChatService:
    def __init__(
        self,
        session: AsyncSession,
        registry: ModelRegistry,
        tracer: OITracer,
        callbacks: list[BaseCallbackHandler],
    ):
        self.session = session
        self.registry = registry
        self.tracer = tracer
        self.callbacks = callbacks

    async def stream_message(
        self, conversation: Conversation, content: str
    ) -> AsyncIterator[ChatEvent]:
        """Gera a resposta em partes; é o único fluxo de geração da Maria.

        Pergunta e resposta só são gravadas ao final. Falha do modelo
        (ModelInvocationError) ou interrupção pelo consumidor não deixam
        registros parciais.
        """
        registered = self.registry.get(CHAT_MODEL_TIER)
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
        yield UserMessageCreated(user_message)

        # Span de cadeia que agrupa o caminho da IA nesta resposta; a sessão
        # (id da conversa) permite ver a conversa inteira no Phoenix.
        session_id = str(conversation.id)
        with using_session(session_id):
            span = self.tracer.start_span(
                'maria.chat', openinference_span_kind='chain'
            )
        span.set_input(content)
        step = _ModelStep(
            span,
            session_id,
            registered.model.astream(
                prompt,
                config={
                    'callbacks': self.callbacks,
                    'metadata': {'model_tier': str(registered.tier)},
                },
            ),
        )

        response: AIMessageChunk | None = None
        try:
            while (chunk := await step.next_chunk()) is not None:
                response = chunk if response is None else response + chunk
                if chunk.text:
                    yield ContentDelta(index=0, text=chunk.text)
        except ModelInvocationError:
            span.end()
            raise
        except BaseException:
            # Cancelamento ou fechamento do stream pelo cliente.
            span.set_status(
                Status(StatusCode.ERROR, 'Resposta interrompida pelo cliente')
            )
            span.end()
            await step.close()
            raise

        text = response.text if response is not None else ''
        span.set_output(text)
        with trace.use_span(span, end_on_exit=True):
            logger.info(
                'Resposta gerada',
                extra={
                    'conversation.id': str(conversation.id),
                    'model.tier': str(registered.tier),
                },
            )

        assistant_message = Message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=[TextBlock(text=text).model_dump()],
            model_tier=registered.tier,
            model_name=registered.name,
        )
        if conversation.title is None:
            conversation.title = auto_title(content)
        conversation.updated_at = assistant_message.created_at

        self.session.add_all([user_message, assistant_message])
        await self.session.commit()
        yield AssistantMessageCompleted(assistant_message)

    async def send_message(
        self, conversation: Conversation, content: str
    ) -> tuple[Message, Message]:
        """Resposta completa, consumindo o mesmo fluxo do streaming."""
        user_message = assistant_message = None
        async for event in self.stream_message(conversation, content):
            match event:
                case UserMessageCreated(message=message):
                    user_message = message
                case AssistantMessageCompleted(message=message):
                    assistant_message = message
        return user_message, assistant_message


def get_chat_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    registry: Annotated[ModelRegistry, Depends(get_model_registry)],
    tracer: Annotated[OITracer, Depends(get_tracer)],
    callbacks: Annotated[
        list[BaseCallbackHandler], Depends(get_llm_callbacks)
    ],
) -> ChatService:
    return ChatService(session, registry, tracer, callbacks)
