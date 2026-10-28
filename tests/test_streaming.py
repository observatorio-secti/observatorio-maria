import json
from http import HTTPStatus
from itertools import repeat
from uuid import UUID, uuid4

from langchain_core.messages import AIMessage
from opentelemetry.trace import StatusCode
from sqlalchemy import select

from observatorio_maria.app import app
from observatorio_maria.llm.registry import (
    ModelRegistry,
    ModelTier,
    RegisteredModel,
    get_model_registry,
)
from observatorio_maria.models import Conversation, Message, MessageRole
from observatorio_maria.observability.genai import get_tracer
from observatorio_maria.services.chat import ChatService, ContentDelta
from tests.conftest import (
    FailingChatModel,
    UsageReportingFakeChatModel,
    chat_and_llm_spans,
    metric_points,
)

ANSWER = 'Olá, sou a **Maria**.'


def stream_url(conversation):
    return f'/conversations/{conversation["id"]}/messages/stream'


def use_model(model):
    registry = ModelRegistry([
        RegisteredModel(tier, f'fake:{tier}', model) for tier in ModelTier
    ])
    app.dependency_overrides[get_model_registry] = lambda: registry


def answering_model():
    return UsageReportingFakeChatModel(
        messages=repeat(AIMessage(ANSWER)),
        usage={'input_tokens': 12, 'output_tokens': 5, 'total_tokens': 17},
    )


def parse_sse(body: str) -> list[tuple[str, dict]]:
    events = []
    for raw in body.strip().split('\n\n'):
        fields = dict(
            line.split(': ', 1)
            for line in raw.splitlines()
            if line and not line.startswith(':')
        )
        if 'event' in fields:
            events.append((fields['event'], json.loads(fields['data'])))
    return events


async def stream(client, conversation, content='Oi'):
    response = await client.post(
        stream_url(conversation), json={'content': content}
    )
    return response, parse_sse(response.text)


async def test_stream_emits_user_deltas_and_assistant(client, conversation):
    use_model(answering_model())

    response, events = await stream(client, conversation)

    assert response.status_code == HTTPStatus.OK
    assert response.headers['content-type'].startswith('text/event-stream')
    names = [name for name, _ in events]
    assert names[0] == 'message.user'
    assert names[-1] == 'message.assistant'
    assert set(names[1:-1]) == {'content.delta'}
    deltas = [data for name, data in events if name == 'content.delta']
    assert all(d['index'] == 0 and d['type'] == 'text' for d in deltas)
    assert ''.join(d['text'] for d in deltas) == ANSWER
    assert events[-1][1]['content'] == [{'type': 'text', 'text': ANSWER}]


async def test_stream_persists_messages_with_streamed_ids(
    client, conversation
):
    use_model(answering_model())

    _, events = await stream(client, conversation)

    history = (
        await client.get(f'/conversations/{conversation["id"]}/messages')
    ).json()['messages']
    assert [m['id'] for m in history] == [
        events[0][1]['id'],
        events[-1][1]['id'],
    ]


async def test_stream_validates_before_streaming(client, conversation):
    missing = await client.post(
        f'/conversations/{uuid4()}/messages/stream', json={'content': 'Oi'}
    )
    extra = await client.post(
        stream_url(conversation), json={'content': 'Oi', 'model': 'fast'}
    )

    assert missing.status_code == HTTPStatus.NOT_FOUND
    assert extra.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


async def test_stream_failure_sends_error_and_persists_nothing(
    client, conversation
):
    use_model(FailingChatModel())

    response, events = await stream(client, conversation)

    assert response.status_code == HTTPStatus.OK
    assert [name for name, _ in events] == ['message.user', 'error']
    assert 'provedor indisponível' in events[-1][1]['detail']
    history = (
        await client.get(f'/conversations/{conversation["id"]}/messages')
    ).json()['messages']
    assert history == []


async def test_client_interruption_persists_nothing(
    session, conversation, model_registry, spans
):
    db_conversation = await session.get(Conversation, UUID(conversation['id']))
    tracer = app.dependency_overrides[get_tracer]()
    chat = ChatService(session, model_registry, tracer, callbacks=[])
    events = chat.stream_message(db_conversation, 'Oi')

    async for event in events:
        if isinstance(event, ContentDelta):
            break
    await events.aclose()

    assert (await session.scalars(select(Message))).all() == []
    chat_span, _ = chat_and_llm_spans(spans)
    assert chat_span.status.status_code == StatusCode.ERROR


async def test_stream_is_traced_and_measured(
    client, conversation, spans, metric_reader
):
    use_model(answering_model())

    await stream(client, conversation)

    chat_span, llm = chat_and_llm_spans(spans)
    assert chat_span.attributes['output.value'] == ANSWER
    assert llm[0].parent.span_id == chat_span.context.span_id
    tokens = {
        p.attributes['gen_ai.token.type']: p.sum
        for p in metric_points(metric_reader, 'gen_ai.client.token.usage')
    }
    assert tokens == {'input': 12, 'output': 5}


async def test_stream_rejects_when_token_ceiling_reached(
    client, conversation, session, monkeypatch
):
    monkeypatch.setenv('CONVERSATION_TOKEN_CEILING', '100000')
    db_conv = await session.get(Conversation, UUID(conversation['id']))
    db_conv.total_tokens = 100_000
    await session.commit()

    response = await client.post(
        stream_url(conversation), json={'content': 'Tentativa de stream'}
    )
    assert response.status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert 'Limite de tokens da conversa atingido' in response.json()['detail']


async def test_stream_accumulates_tokens(client, conversation):
    use_model(answering_model())

    await stream(client, conversation)

    conv_res = await client.get(f'/conversations/{conversation["id"]}')
    assert conv_res.json()['total_tokens'] == 17  # noqa: PLR2004


async def test_stream_rejects_when_question_limit_reached(
    client, conversation, session, monkeypatch
):
    monkeypatch.setenv('CONVERSATION_MAX_QUESTIONS', '1')
    session.add_all([
        Message(
            conversation_id=UUID(conversation['id']),
            role=MessageRole.USER,
            content=[{'type': 'text', 'text': 'Primeira pergunta'}],
        ),
        Message(
            conversation_id=UUID(conversation['id']),
            role=MessageRole.ASSISTANT,
            content=[{'type': 'text', 'text': 'Resposta'}],
        ),
    ])
    await session.commit()
    use_model(FailingChatModel())

    response = await client.post(
        stream_url(conversation), json={'content': 'Segunda pergunta'}
    )

    assert response.status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert 'Limite de 1 pergunta da conversa' in response.json()['detail']
    assert 'text/event-stream' not in response.headers['content-type']
