from collections.abc import AsyncIterable
from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.sse import EventSourceResponse, ServerSentEvent
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from observatorio_maria.database import get_session
from observatorio_maria.models import Conversation
from observatorio_maria.schemas import (
    ActivityPublic,
    ChatExchange,
    ContentDeltaPublic,
    ConversationCreate,
    ConversationList,
    ConversationPublic,
    ConversationUpdate,
    MessageCreate,
    MessageList,
    MessagePublic,
    Pagination,
    StreamError,
)
from observatorio_maria.services.chat import (
    Activity,
    AssistantMessageCompleted,
    ChatEvent,
    ChatService,
    ContentDelta,
    ConversationTokenLimitExceededError,
    ModelInvocationError,
    UserMessageCreated,
    get_chat_service,
    get_history,
)

router = APIRouter(prefix='/conversations', tags=['conversations'])

Session = Annotated[AsyncSession, Depends(get_session)]
Chat = Annotated[ChatService, Depends(get_chat_service)]


async def get_conversation(conversation_id: UUID, session: Session):
    conversation = await session.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail='Conversa não encontrada',
        )
    return conversation


CurrentConversation = Annotated[Conversation, Depends(get_conversation)]


def check_conversation_token_ceiling(
    conversation: CurrentConversation, chat: Chat
) -> Conversation:
    try:
        chat.check_token_ceiling(conversation)
    except ConversationTokenLimitExceededError as exc:
        raise HTTPException(
            status_code=HTTPStatus.TOO_MANY_REQUESTS,
            detail=str(exc),
        ) from exc
    return conversation


ActiveConversation = Annotated[
    Conversation, Depends(check_conversation_token_ceiling)
]


@router.post(
    '', status_code=HTTPStatus.CREATED, response_model=ConversationPublic
)
async def create_conversation(data: ConversationCreate, session: Session):
    conversation = Conversation(title=data.title)
    session.add(conversation)
    await session.commit()
    return conversation


@router.get('', response_model=ConversationList)
async def list_conversations(
    session: Session, pagination: Annotated[Pagination, Query()]
):
    conversations = await session.scalars(
        select(Conversation)
        .order_by(Conversation.updated_at.desc())
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    total = await session.scalar(select(func.count(Conversation.id)))
    return {'conversations': conversations.all(), 'total': total}


@router.get('/{conversation_id}', response_model=ConversationPublic)
async def read_conversation(conversation: CurrentConversation):
    return conversation


@router.patch('/{conversation_id}', response_model=ConversationPublic)
async def update_conversation(
    data: ConversationUpdate,
    conversation: CurrentConversation,
    session: Session,
):
    conversation.title = data.title
    await session.commit()
    await session.refresh(conversation)
    return conversation


@router.delete('/{conversation_id}', status_code=HTTPStatus.NO_CONTENT)
async def delete_conversation(
    conversation: CurrentConversation, session: Session
):
    await session.delete(conversation)
    await session.commit()


@router.get('/{conversation_id}/messages', response_model=MessageList)
async def list_messages(conversation: CurrentConversation, session: Session):
    return {'messages': await get_history(session, conversation)}


@router.post(
    '/{conversation_id}/messages',
    status_code=HTTPStatus.CREATED,
    response_model=ChatExchange,
)
async def send_message(
    data: MessageCreate, conversation: ActiveConversation, chat: Chat
):
    try:
        user_message, assistant_message = await chat.send_message(
            conversation, data.content
        )
    except ModelInvocationError as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_GATEWAY,
            detail=f'Falha ao gerar resposta do modelo: {exc}',
        ) from exc
    return {
        'user_message': user_message,
        'assistant_message': assistant_message,
    }


def to_server_sent_event(event: ChatEvent) -> ServerSentEvent:
    match event:
        case UserMessageCreated(message=message):
            return ServerSentEvent(
                event='message.user',
                data=MessagePublic.model_validate(message),
            )
        case Activity(kind=kind, source=source, description=description):
            return ServerSentEvent(
                event='activity',
                data=ActivityPublic(
                    kind=kind, source=source, description=description
                ),
            )
        case ContentDelta(
            index=index, text=text, type=delta_type, block=block
        ):
            return ServerSentEvent(
                event='content.delta',
                data=ContentDeltaPublic(
                    index=index,
                    type=delta_type or 'text',
                    text=text,
                    block=block,
                ),
            )
        case AssistantMessageCompleted(message=message):
            return ServerSentEvent(
                event='message.assistant',
                data=MessagePublic.model_validate(message),
            )


@router.post(
    '/{conversation_id}/messages/stream',
    response_class=EventSourceResponse,
    summary='Envia uma mensagem e recebe a resposta em streaming (SSE)',
    description=(
        'Eventos, nesta ordem: `message.user` (MessagePublic), '
        '`content.delta` (ContentDeltaPublic, zero ou mais) e '
        '`message.assistant` (MessagePublic persistida). Falhas do modelo '
        'após o início do stream chegam como `error` (StreamError).'
    ),
)
async def stream_message(
    data: MessageCreate, conversation: ActiveConversation, chat: Chat
) -> AsyncIterable[ServerSentEvent]:
    try:
        async for event in chat.stream_message(conversation, data.content):
            yield to_server_sent_event(event)
    except ModelInvocationError as exc:
        yield ServerSentEvent(
            event='error',
            data=StreamError(
                detail=f'Falha ao gerar resposta do modelo: {exc}'
            ),
        )
