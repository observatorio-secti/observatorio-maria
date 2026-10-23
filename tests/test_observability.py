# A API de logs do OpenTelemetry para Python é experimental (`_logs`).
# ruff: noqa: PLC2701
import logging
from itertools import repeat

from fastapi import FastAPI
from langchain_core.messages import AIMessage
from openinference.semconv.trace import SpanAttributes
from opentelemetry.sdk._logs import (
    LoggerProvider,
    LoggingHandler,
)
from opentelemetry.sdk._logs.export import (
    InMemoryLogRecordExporter,
    SimpleLogRecordProcessor,
)
from opentelemetry.trace import StatusCode

from observatorio_maria.app import app
from observatorio_maria.database import engine
from observatorio_maria.llm.registry import (
    ModelRegistry,
    ModelTier,
    RegisteredModel,
    get_model_registry,
)
from observatorio_maria.observability.telemetry import setup_telemetry
from tests.conftest import (
    FailingChatModel,
    UsageReportingFakeChatModel,
    chat_and_llm_spans,
    finished,
    metric_points,
)

USAGE = {'input_tokens': 12, 'output_tokens': 5, 'total_tokens': 17}


def registry_with(model):
    return ModelRegistry([
        RegisteredModel(tier, f'fake:{tier}', model) for tier in ModelTier
    ])


def answering_model():
    return UsageReportingFakeChatModel(
        messages=repeat(AIMessage('Resposta')), usage=USAGE
    )


async def send(client, conversation, content='Oi'):
    return await client.post(
        f'/conversations/{conversation["id"]}/messages',
        json={'content': content},
    )


async def test_chat_span_groups_llm_call_by_session(
    client, conversation, spans
):
    app.dependency_overrides[get_model_registry] = lambda: registry_with(
        answering_model()
    )

    await send(client, conversation)

    chat, llm = chat_and_llm_spans(spans)
    attrs = chat.attributes
    assert attrs[SpanAttributes.OPENINFERENCE_SPAN_KIND] == 'CHAIN'
    assert attrs[SpanAttributes.SESSION_ID] == conversation['id']
    assert attrs[SpanAttributes.INPUT_VALUE] == 'Oi'
    assert attrs[SpanAttributes.OUTPUT_VALUE] == 'Resposta'
    assert len(llm) == 1
    assert llm[0].parent.span_id == chat.context.span_id
    assert llm[0].attributes[SpanAttributes.SESSION_ID] == conversation['id']
    assert llm[0].attributes[SpanAttributes.LLM_TOKEN_COUNT_PROMPT] == 12  # noqa: PLR2004


async def test_model_failure_marks_span_and_logs_trace_id(
    client, conversation, spans
):
    log_exporter = InMemoryLogRecordExporter()
    logger_provider = LoggerProvider()
    logger_provider.add_log_record_processor(
        SimpleLogRecordProcessor(log_exporter)
    )
    handler = LoggingHandler(logger_provider=logger_provider)
    logger = logging.getLogger('observatorio_maria.services.chat')
    logger.addHandler(handler)
    app.dependency_overrides[get_model_registry] = lambda: registry_with(
        FailingChatModel()
    )

    try:
        await send(client, conversation)
    finally:
        logger.removeHandler(handler)

    (chat,) = finished(spans, 'maria.chat')
    assert chat.status.status_code == StatusCode.ERROR
    assert any(event.name == 'exception' for event in chat.events)
    (record,) = log_exporter.get_finished_logs()
    log = getattr(record, 'log_record', record)
    assert log.trace_id == chat.context.trace_id


async def test_hidden_content_keeps_structure(
    hidden_content, client, conversation, spans
):
    app.dependency_overrides[get_model_registry] = lambda: registry_with(
        answering_model()
    )

    await send(client, conversation, 'dado pessoal sensível')

    chat, llm = chat_and_llm_spans(spans)
    exported = [chat.attributes, llm[0].attributes]
    assert not any(
        'dado pessoal sensível' in str(value)
        for attrs in exported
        for value in attrs.values()
    )
    assert llm[0].attributes[SpanAttributes.LLM_TOKEN_COUNT_PROMPT] == 12  # noqa: PLR2004


async def test_genai_metrics_record_tokens_and_duration(
    client, conversation, metric_reader
):
    app.dependency_overrides[get_model_registry] = lambda: registry_with(
        answering_model()
    )

    await send(client, conversation)

    tokens = {
        p.attributes['gen_ai.token.type']: p.sum
        for p in metric_points(metric_reader, 'gen_ai.client.token.usage')
    }
    assert tokens == {'input': 12, 'output': 5}
    (duration,) = metric_points(
        metric_reader, 'gen_ai.client.operation.duration'
    )
    assert duration.count == 1
    assert duration.attributes['gen_ai.operation.name'] == 'chat'


async def test_genai_metrics_record_error_type(
    client, conversation, metric_reader
):
    app.dependency_overrides[get_model_registry] = lambda: registry_with(
        FailingChatModel()
    )

    await send(client, conversation)

    (duration,) = metric_points(
        metric_reader, 'gen_ai.client.operation.duration'
    )
    assert duration.attributes['error.type'] == 'RuntimeError'
    assert not metric_points(metric_reader, 'gen_ai.client.token.usage')


def test_setup_telemetry_is_noop_when_disabled(monkeypatch):
    monkeypatch.setenv('OTEL_SDK_DISABLED', 'true')
    fresh_app = FastAPI()

    setup_telemetry(fresh_app, engine)

    assert fresh_app.user_middleware == []
