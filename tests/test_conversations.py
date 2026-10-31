from http import HTTPStatus
from uuid import UUID, uuid4

from fastapi import HTTPException

from observatorio_maria.app import app
from observatorio_maria.llm.registry import get_model_registry
from observatorio_maria.models import Message, MessageRole


async def add_messages(session, conversation, count):
    session.add_all(
        Message(
            conversation_id=UUID(conversation['id']),
            role=MessageRole.USER,
            content=[{'type': 'text', 'text': f'Pergunta {index}'}],
        )
        for index in range(count)
    )
    await session.commit()


async def test_create_conversation_with_title(client):
    response = await client.post(
        '/conversations', json={'title': 'Pesquisa em Salvador'}
    )

    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data['title'] == 'Pesquisa em Salvador'
    assert {'id', 'created_at', 'updated_at', 'total_tokens'} <= data.keys()
    assert data['total_tokens'] == 0


async def test_create_conversation_without_title(client):
    response = await client.post('/conversations', json={})

    assert response.status_code == HTTPStatus.CREATED
    assert response.json()['title'] is None


async def test_create_conversation_rejects_empty_title(client):
    response = await client.post('/conversations', json={'title': ''})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


async def test_list_conversations_most_recent_first(client):
    first = (await client.post('/conversations', json={'title': 'A'})).json()
    second = (await client.post('/conversations', json={'title': 'B'})).json()

    response = await client.get('/conversations')

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['total'] == 2  # noqa: PLR2004
    assert [c['id'] for c in data['conversations']] == [
        second['id'],
        first['id'],
    ]


async def test_list_conversations_paginates(client):
    for title in ('A', 'B', 'C'):
        await client.post('/conversations', json={'title': title})

    response = await client.get('/conversations?offset=1&limit=1')

    data = response.json()
    assert len(data['conversations']) == 1
    assert data['conversations'][0]['title'] == 'B'
    assert data['total'] == 3  # noqa: PLR2004


async def test_list_conversations_rejects_limit_above_max(client):
    response = await client.get('/conversations?limit=101')

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


async def test_read_conversation(client, conversation):
    response = await client.get(f'/conversations/{conversation["id"]}')

    assert response.status_code == HTTPStatus.OK
    assert conversation.items() <= response.json().items()


async def test_read_missing_conversation_returns_404(client):
    response = await client.get(f'/conversations/{uuid4()}')

    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_rename_conversation(client, conversation):
    response = await client.patch(
        f'/conversations/{conversation["id"]}', json={'title': 'Novo título'}
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['title'] == 'Novo título'
    assert data['updated_at'] > conversation['updated_at']


async def test_rename_missing_conversation_returns_404(client):
    response = await client.patch(
        f'/conversations/{uuid4()}', json={'title': 'Novo título'}
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_delete_conversation_with_messages(client, conversation):
    url = f'/conversations/{conversation["id"]}'
    await client.post(f'{url}/messages', json={'content': 'Oi'})

    response = await client.delete(url)

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert (await client.get(url)).status_code == HTTPStatus.NOT_FOUND


async def test_delete_missing_conversation_returns_404(client):
    response = await client.delete(f'/conversations/{uuid4()}')

    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_read_conversation_counts_questions(
    client, session, conversation, monkeypatch
):
    monkeypatch.setenv('CONVERSATION_MAX_QUESTIONS', '10')
    await add_messages(session, conversation, 3)

    data = (await client.get(f'/conversations/{conversation["id"]}')).json()

    assert data['questions_asked'] == 3  # noqa: PLR2004
    assert data['questions_limit'] == 10  # noqa: PLR2004


async def test_read_new_conversation_has_no_questions(client, conversation):
    data = (await client.get(f'/conversations/{conversation["id"]}')).json()

    assert data['questions_asked'] == 0


async def test_read_conversation_with_limit_disabled(
    client, session, conversation, monkeypatch
):
    monkeypatch.setenv('CONVERSATION_MAX_QUESTIONS', '0')
    await add_messages(session, conversation, 5)

    data = (await client.get(f'/conversations/{conversation["id"]}')).json()

    assert data['questions_asked'] == 5  # noqa: PLR2004
    assert data['questions_limit'] is None


async def test_read_conversation_works_without_model(client, conversation):
    def no_model():
        raise HTTPException(HTTPStatus.SERVICE_UNAVAILABLE)

    app.dependency_overrides[get_model_registry] = no_model
    try:
        response = await client.get(f'/conversations/{conversation["id"]}')
    finally:
        del app.dependency_overrides[get_model_registry]

    assert response.status_code == HTTPStatus.OK
    assert response.json()['questions_asked'] == 0


async def test_only_read_returns_question_count(client, conversation):
    url = f'/conversations/{conversation["id"]}'
    listed = (await client.get('/conversations')).json()['conversations'][0]
    renamed = (await client.patch(url, json={'title': 'Outro'})).json()
    created = (await client.post('/conversations', json={})).json()

    for data in (listed, renamed, created):
        assert 'questions_asked' not in data
        assert 'questions_limit' not in data
