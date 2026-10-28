from http import HTTPStatus
from itertools import repeat
from uuid import UUID, uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import ValidationError
from sqlalchemy import select

from observatorio_maria.app import app
from observatorio_maria.llm.prompts import (
    build_system_prompt,
)
from observatorio_maria.llm.registry import (
    ModelRegistry,
    ModelTier,
    RegisteredModel,
    get_model_registry,
)
from observatorio_maria.models import Conversation, Message, MessageRole
from observatorio_maria.services.chat import CHAT_MODEL_TIER
from observatorio_maria.settings import Settings
from tests.conftest import FailingChatModel, UsageReportingFakeChatModel


def messages_url(conversation):
    return f'/conversations/{conversation["id"]}/messages'


async def test_send_message_returns_exchange(client, conversation):
    response = await client.post(
        messages_url(conversation), json={'content': 'Oi'}
    )

    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data['user_message']['role'] == 'user'
    assert data['user_message']['content'] == [{'type': 'text', 'text': 'Oi'}]
    assistant = data['assistant_message']
    assert assistant['role'] == 'assistant'
    assert assistant['content'] == [
        {'type': 'text', 'text': 'Resposta do modelo medium'}
    ]
    assert 'model_tier' not in assistant
    assert 'model_name' not in assistant


async def test_send_message_uses_internal_tier(client, conversation, session):
    await client.post(messages_url(conversation), json={'content': 'Oi'})

    stored = await session.scalar(
        select(Message).where(Message.role == MessageRole.ASSISTANT)
    )
    assert stored.model_tier == CHAT_MODEL_TIER
    assert stored.model_name == f'fake:{CHAT_MODEL_TIER}'


@pytest.mark.parametrize('model', ['fast', 'ultra'])
async def test_send_message_rejects_model_choice(client, conversation, model):
    url = messages_url(conversation)

    response = await client.post(url, json={'content': 'Oi', 'model': model})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert (await client.get(url)).json()['messages'] == []


async def test_openapi_hides_model_details(client):
    schemas = (await client.get('/openapi.json')).json()['components'][
        'schemas'
    ]

    assert 'model' not in schemas['MessageCreate']['properties']
    assert 'model_tier' not in schemas['MessagePublic']['properties']
    assert 'model_name' not in schemas['MessagePublic']['properties']


async def test_send_message_rejects_empty_content(client, conversation):
    response = await client.post(
        messages_url(conversation), json={'content': ''}
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


async def test_send_message_to_missing_conversation_returns_404(client):
    response = await client.post(
        f'/conversations/{uuid4()}/messages', json={'content': 'Oi'}
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_model_receives_system_prompt_and_history(
    client, conversation, model_handler
):
    url = messages_url(conversation)
    await client.post(url, json={'content': 'Primeira pergunta'})
    await client.post(url, json={'content': 'Segunda pergunta'})

    assert model_handler.calls[-1] == [
        SystemMessage(build_system_prompt()),
        HumanMessage('Primeira pergunta'),
        AIMessage('Resposta do modelo medium'),
        HumanMessage('Segunda pergunta'),
    ]


async def test_model_failure_returns_502_and_keeps_history(
    client, conversation, model_registry
):
    url = messages_url(conversation)
    await client.post(url, json={'content': 'Oi'})
    failing = ModelRegistry([
        *(r for r in model_registry.all() if r.tier != ModelTier.MEDIUM),
        RegisteredModel(ModelTier.MEDIUM, 'fake:fail', FailingChatModel()),
    ])
    app.dependency_overrides[get_model_registry] = lambda: failing

    response = await client.post(url, json={'content': 'Vai falhar'})

    assert response.status_code == HTTPStatus.BAD_GATEWAY
    history = (await client.get(url)).json()['messages']
    assert [m['content'][0]['text'] for m in history] == [
        'Oi',
        'Resposta do modelo medium',
    ]


async def test_first_message_sets_title(client):
    conversation = (await client.post('/conversations', json={})).json()
    content = 'Quantas bolsas de pesquisa a FAPESB concedeu em 2024 no total?'

    await client.post(messages_url(conversation), json={'content': content})

    title = (await client.get(f'/conversations/{conversation["id"]}')).json()[
        'title'
    ]
    assert len(title) <= 60  # noqa: PLR2004
    assert content.startswith(title.removesuffix('…'))


async def test_existing_title_is_preserved(client, conversation):
    await client.post(messages_url(conversation), json={'content': 'Oi'})

    response = await client.get(f'/conversations/{conversation["id"]}')

    assert response.json()['title'] == 'Bolsas'


async def test_sending_message_bumps_conversation(client, conversation):
    other = (await client.post('/conversations', json={'title': 'X'})).json()

    await client.post(messages_url(conversation), json={'content': 'Oi'})

    listed = (await client.get('/conversations')).json()['conversations']
    assert [c['id'] for c in listed] == [conversation['id'], other['id']]


async def test_list_messages_in_chronological_order(client, conversation):
    await client.post(messages_url(conversation), json={'content': 'Oi'})

    response = await client.get(messages_url(conversation))

    assert response.status_code == HTTPStatus.OK
    roles = [m['role'] for m in response.json()['messages']]
    assert roles == ['user', 'assistant']


async def test_list_messages_of_missing_conversation_returns_404(client):
    response = await client.get(f'/conversations/{uuid4()}/messages')

    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_list_messages_does_not_require_models(client, conversation):
    def unavailable():
        raise AssertionError('o histórico não deve instanciar modelos')

    app.dependency_overrides[get_model_registry] = unavailable

    response = await client.get(messages_url(conversation))

    assert response.status_code == HTTPStatus.OK


async def test_send_message_accumulates_tokens(client, conversation):
    usage = {'input_tokens': 20, 'output_tokens': 10, 'total_tokens': 30}
    fake = UsageReportingFakeChatModel(
        messages=repeat(AIMessage('Resposta com tokens')), usage=usage
    )
    registry = ModelRegistry([
        RegisteredModel(tier, f'fake:{tier}', fake) for tier in ModelTier
    ])
    app.dependency_overrides[get_model_registry] = lambda: registry

    response = await client.post(
        messages_url(conversation), json={'content': 'Oi'}
    )
    assert response.status_code == HTTPStatus.CREATED

    conv_res = await client.get(f'/conversations/{conversation["id"]}')
    assert conv_res.json()['total_tokens'] == 30  # noqa: PLR2004


async def test_send_message_rejects_when_token_ceiling_reached(
    client, conversation, session, monkeypatch
):
    monkeypatch.setenv('CONVERSATION_TOKEN_CEILING', '100000')
    db_conv = await session.get(Conversation, UUID(conversation['id']))
    db_conv.total_tokens = 100_000
    await session.commit()

    response = await client.post(
        messages_url(conversation), json={'content': 'Mais uma mensagem'}
    )
    assert response.status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert 'Limite de tokens da conversa atingido' in response.json()['detail']

    history = (await client.get(messages_url(conversation))).json()['messages']
    assert len(history) == 0


def use_failing_model():
    """Qualquer chamada ao modelo falharia: prova que a recusa vem antes."""
    registry = ModelRegistry([
        RegisteredModel(tier, f'fake:{tier}', FailingChatModel())
        for tier in ModelTier
    ])
    app.dependency_overrides[get_model_registry] = lambda: registry


async def add_questions(session, conversation, count):
    """Grava `count` pares de pergunta e resposta na conversa."""
    conversation_id = UUID(conversation['id'])
    for index in range(count):
        session.add_all([
            Message(
                conversation_id=conversation_id,
                role=MessageRole.USER,
                content=[{'type': 'text', 'text': f'Pergunta {index}'}],
            ),
            Message(
                conversation_id=conversation_id,
                role=MessageRole.ASSISTANT,
                content=[{'type': 'text', 'text': 'Resposta'}],
            ),
        ])
    await session.commit()


async def count_questions(session, conversation):
    rows = await session.scalars(
        select(Message).where(
            Message.conversation_id == UUID(conversation['id']),
            Message.role == MessageRole.USER,
        )
    )
    return len(rows.all())


async def test_send_message_rejects_when_question_limit_reached(
    client, conversation, session, monkeypatch
):
    monkeypatch.delenv('CONVERSATION_MAX_QUESTIONS', raising=False)
    await add_questions(session, conversation, 10)
    use_failing_model()

    response = await client.post(
        messages_url(conversation), json={'content': 'Mais uma pergunta'}
    )

    assert response.status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert 'Limite de 10 perguntas' in response.json()['detail']
    assert 'nova conversa' in response.json()['detail']
    assert await count_questions(session, conversation) == 10  # noqa: PLR2004


async def test_send_message_allows_last_question_before_limit(
    client, conversation, session, monkeypatch
):
    monkeypatch.delenv('CONVERSATION_MAX_QUESTIONS', raising=False)
    await add_questions(session, conversation, 9)

    response = await client.post(
        messages_url(conversation), json={'content': 'Décima pergunta'}
    )

    assert response.status_code == HTTPStatus.CREATED
    assert await count_questions(session, conversation) == 10  # noqa: PLR2004


async def test_send_message_respects_configured_question_limit(
    client, conversation, session, monkeypatch
):
    monkeypatch.setenv('CONVERSATION_MAX_QUESTIONS', '3')
    await add_questions(session, conversation, 3)

    response = await client.post(
        messages_url(conversation), json={'content': 'Quarta pergunta'}
    )

    assert response.status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert 'Limite de 3 perguntas' in response.json()['detail']


async def test_send_message_question_limit_disabled(
    client, conversation, session, monkeypatch
):
    monkeypatch.setenv('CONVERSATION_MAX_QUESTIONS', '0')
    await add_questions(session, conversation, 50)

    response = await client.post(
        messages_url(conversation), json={'content': 'Pergunta 51'}
    )

    assert response.status_code == HTTPStatus.CREATED


async def test_token_ceiling_disabled_by_default(
    client, conversation, session, monkeypatch
):
    monkeypatch.delenv('CONVERSATION_TOKEN_CEILING', raising=False)
    monkeypatch.delenv('CONVERSATION_MAX_QUESTIONS', raising=False)
    await add_questions(session, conversation, 2)
    db_conv = await session.get(Conversation, UUID(conversation['id']))
    db_conv.total_tokens = 500_000
    await session.commit()

    response = await client.post(
        messages_url(conversation), json={'content': 'Terceira pergunta'}
    )

    assert response.status_code == HTTPStatus.CREATED


def test_negative_question_limit_is_rejected():
    with pytest.raises(ValidationError):
        Settings(CONVERSATION_MAX_QUESTIONS=-1)
