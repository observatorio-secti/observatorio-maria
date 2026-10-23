from http import HTTPStatus
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from observatorio_maria.app import app
from observatorio_maria.llm.prompts import MARIA_SYSTEM_PROMPT
from observatorio_maria.llm.registry import (
    ModelRegistry,
    ModelTier,
    RegisteredModel,
    get_model_registry,
)
from tests.conftest import FailingChatModel


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
    assert assistant['model_tier'] == 'medium'
    assert assistant['model_name'] == 'fake:medium'


async def test_send_message_uses_requested_tiers(client, conversation):
    url = messages_url(conversation)

    fast = await client.post(url, json={'content': 'Oi', 'model': 'fast'})
    advanced = await client.post(
        url, json={'content': 'E agora?', 'model': 'advanced'}
    )

    assert fast.json()['assistant_message']['model_tier'] == 'fast'
    assert advanced.json()['assistant_message']['content'] == [
        {'type': 'text', 'text': 'Resposta do modelo advanced'}
    ]


async def test_send_message_rejects_unknown_tier(client, conversation):
    response = await client.post(
        messages_url(conversation), json={'content': 'Oi', 'model': 'ultra'}
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


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
        SystemMessage(MARIA_SYSTEM_PROMPT),
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
