from http import HTTPStatus

from sqlalchemy import select, text

from observatorio_maria.database import get_session
from observatorio_maria.models import Conversation, Message, MessageRole


async def test_database_connection(session):
    result = await session.scalar(text('SELECT 1'))
    assert result == 1


async def test_get_session():
    session_generator = get_session()
    session = await anext(session_generator)
    assert session is not None
    await session_generator.aclose()


async def test_health_check_endpoint(client):
    response = await client.get('/health')

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {'status': 'ok', 'database': 'connected'}


async def test_delete_conversation_cascades_to_messages(session):
    conversation = Conversation(title='Teste')
    session.add(conversation)
    await session.flush()
    session.add(
        Message(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content=[{'type': 'text', 'text': 'Oi'}],
        )
    )
    await session.commit()

    await session.delete(conversation)
    await session.commit()

    assert (await session.scalars(select(Message))).all() == []
