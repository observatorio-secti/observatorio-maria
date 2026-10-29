import json
import logging
from collections.abc import AsyncIterator
from contextlib import suppress
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.outputs import LLMResult
from openinference.instrumentation import OITracer, using_session
from openinference.semconv.trace import SpanAttributes
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from observatorio_maria.catalog.context import (
    load_concept_labels,
    load_concepts_context,
    render_context,
)
from observatorio_maria.catalog.sync import (
    load_entities,
    load_relationships,
)
from observatorio_maria.database import get_session
from observatorio_maria.llm.prompts import build_system_prompt
from observatorio_maria.llm.registry import (
    ModelRegistry,
    ModelTier,
    get_model_registry,
)
from observatorio_maria.models import (
    CatalogDataSource,
    Conversation,
    Message,
    MessageRole,
)
from observatorio_maria.observability.genai import (
    AgentMetrics,
    get_agent_metrics,
    get_llm_callbacks,
    get_tracer,
)
from observatorio_maria.query.execution import (
    ResultStore,
    sanitize_purpose,
)
from observatorio_maria.query.tool import QueryObserver, QueryRunner
from observatorio_maria.schemas import TextBlock
from observatorio_maria.settings import Settings

logger = logging.getLogger(__name__)

AUTO_TITLE_MAX_LENGTH = 60

# Nível usado nas respostas do chat. Decisão interna: não é exposta nem
# configurável por clientes da API.
CHAT_MODEL_TIER = ModelTier.MEDIUM


class ModelInvocationError(Exception):
    """O modelo de linguagem falhou ao gerar a resposta."""


class ConversationTokenLimitExceededError(Exception):
    """O teto de tokens da conversa foi atingido."""


class ConversationQuestionLimitExceededError(Exception):
    """O limite de perguntas da conversa foi atingido."""


class _TokenUsageTracker(BaseCallbackHandler):
    run_inline = True

    def __init__(self):
        self.total_tokens = 0

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        try:
            for gens in response.generations:
                for gen in gens:
                    msg = getattr(gen, 'message', None)
                    usage = getattr(msg, 'usage_metadata', None)
                    if usage:
                        tokens = usage.get('total_tokens') or (
                            usage.get('input_tokens', 0)
                            + usage.get('output_tokens', 0)
                        )
                        self.total_tokens += tokens
        except Exception:
            pass


def summarize_chart(block: dict[str, Any]) -> str:
    """Resume bloco de gráfico para o histórico do modelo."""
    title = block.get('title') or 'Sem título'
    series = block.get('series') or []
    if isinstance(series, list):
        labels = [
            s.get('label', s.get('key', '')) if isinstance(s, dict) else str(s)
            for s in series
        ]
        series_str = ', '.join(filter(None, labels))
    else:
        series_str = str(series)
    data = block.get('data') or []
    return (
        f'[Gráfico: {title} | Séries: {series_str} | '
        f'Total de registros: {len(data)}]'
    )


def summarize_table(block: dict[str, Any]) -> str:
    """Resume bloco de tabela para o histórico do modelo."""
    title = block.get('title') or 'Tabela'
    columns = block.get('columns') or []
    labels = [
        c.get('label', c.get('key', '')) if isinstance(c, dict) else str(c)
        for c in columns
    ]
    col_str = ', '.join(filter(None, labels))
    rows = block.get('rows') or []
    return (
        f'[Tabela: {title} | Colunas: {col_str} | '
        f'Total de linhas: {len(rows)}]'
    )


def blocks_to_text(blocks: list[dict[str, Any]]) -> str:
    """Converte blocos persistidos no texto enviado ao modelo."""
    parts = []
    for block in blocks:
        btype = block.get('type')
        if btype == 'text':
            parts.append(block.get('text', ''))
        elif btype == 'chart':
            parts.append(summarize_chart(block))
        elif btype == 'table':
            parts.append(summarize_table(block))
        else:
            parts.append(json.dumps(block))
    return '\n\n'.join(p for p in parts if p)


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


async def get_consultable_sources_and_contexts(
    session: AsyncSession,
) -> tuple[list[CatalogDataSource], list[str]]:
    """Carrega fontes com entidades visíveis, consultáveis e presentes."""
    datasources = list(
        await session.scalars(
            select(CatalogDataSource)
            .where(CatalogDataSource.enabled.is_(True))
            .order_by(CatalogDataSource.id)
        )
    )
    consultable_ds = []
    contexts = []
    concept_labels = await load_concept_labels(session)
    for ds in datasources:
        entities = await load_entities(session, ds.id)
        has_queryable = any(
            e.visible and e.queryable and e.present for e in entities
        )
        if has_queryable:
            consultable_ds.append(ds)
            relationships = await load_relationships(session, ds.id)
            contexts.append(
                render_context(ds, entities, relationships, concept_labels)
            )
    return consultable_ds, contexts


@dataclass(frozen=True)
class UserMessageCreated:
    message: Message


@dataclass(frozen=True)
class Activity:
    kind: str
    source: str
    description: str


@dataclass(frozen=True)
class ContentDelta:
    """Fragmento de texto ou bloco completo da resposta."""

    index: int
    text: str | None = None
    type: str = 'text'
    block: dict[str, Any] | None = None


@dataclass(frozen=True)
class AssistantMessageCompleted:
    message: Message


ChatEvent = (
    UserMessageCreated | Activity | ContentDelta | AssistantMessageCompleted
)


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
    def __init__(  # noqa: PLR0913, PLR0917
        self,
        session: AsyncSession,
        registry: ModelRegistry,
        tracer: OITracer,
        callbacks: list[BaseCallbackHandler],
        settings: Settings | None = None,
        agent_metrics: AgentMetrics | None = None,
        query_observer: QueryObserver | None = None,
    ):
        self.session = session
        self.registry = registry
        self.tracer = tracer
        self.callbacks = callbacks
        self.settings = settings or Settings()
        self.agent_metrics = agent_metrics or get_agent_metrics()
        # Usado pela avaliação com perguntas de referência; a API não o usa.
        self.query_observer = query_observer

    async def check_conversation_limits(
        self, conversation: Conversation
    ) -> None:
        """Recusa a pergunta se a conversa atingiu o limite de perguntas ou
        o teto de tokens (quando ligado)."""
        max_questions = self.settings.CONVERSATION_MAX_QUESTIONS
        if max_questions > 0:
            questions = await self.session.scalar(
                select(func.count())
                .select_from(Message)
                .where(
                    Message.conversation_id == conversation.id,
                    Message.role == MessageRole.USER,
                )
            )
            if questions >= max_questions:
                noun = 'pergunta' if max_questions == 1 else 'perguntas'
                raise ConversationQuestionLimitExceededError(
                    f'Limite de {max_questions} {noun} da conversa '
                    'atingido. Inicie uma nova conversa para continuar.'
                )
        if (
            self.settings.CONVERSATION_TOKEN_CEILING > 0
            and (conversation.total_tokens or 0)
            >= self.settings.CONVERSATION_TOKEN_CEILING
        ):
            raise ConversationTokenLimitExceededError(
                'Limite de tokens da conversa atingido. '
                'Inicie uma nova conversa para continuar.'
            )

    async def stream_message(  # noqa: C901, PLR0912, PLR0914, PLR0915, PLR1702
        self, conversation: Conversation, content: str
    ) -> AsyncIterator[ChatEvent]:
        """Gera a resposta em partes; é o único fluxo de geração da Maria.

        Pergunta e resposta só são gravadas ao final. Falha do modelo
        (ModelInvocationError) ou interrupção pelo consumidor não deixam
        registros parciais.
        """
        await self.check_conversation_limits(conversation)
        registered = self.registry.get(CHAT_MODEL_TIER)
        (
            consultable_sources,
            contexts,
        ) = await get_consultable_sources_and_contexts(self.session)
        has_sources = len(consultable_sources) > 0
        max_calls = (
            self.settings.MARIA_AGENT_MAX_MODEL_CALLS if has_sources else 1
        )

        concepts_context = (
            await load_concepts_context(self.session, consultable_sources)
            if has_sources
            else None
        )
        system_prompt = build_system_prompt(
            source_contexts=contexts if has_sources else None,
            concepts_context=concepts_context,
        )
        history = await get_history(self.session, conversation)

        user_message = Message(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content=[TextBlock(text=content).model_dump()],
        )
        yield UserMessageCreated(user_message)

        result_store = ResultStore()
        query_runner = QueryRunner(
            self.session,
            result_store,
            max_rows=self.settings.QUERY_MAX_ROWS,
            timeout_seconds=self.settings.QUERY_TIMEOUT_SECONDS,
            max_cost=self.settings.QUERY_MAX_ESTIMATED_COST,
            max_per_call=self.settings.QUERY_MAX_PER_CALL,
            query_observer=self.query_observer,
        )
        query_tools = query_runner.build_query_tools() if has_sources else []
        presentation_tools = (
            query_runner.build_presentation_tools() if has_sources else []
        )

        messages: list[BaseMessage] = [
            SystemMessage(system_prompt),
            *(to_langchain_message(m) for m in history),
            HumanMessage(content),
        ]

        session_id = str(conversation.id)
        with using_session(session_id):
            span = self.tracer.start_span(
                'maria.chat', openinference_span_kind='chain'
            )
        span.set_input(content)

        accumulated_text = ''
        call_count = 0
        token_tracker = _TokenUsageTracker()

        try:
            while call_count < max_calls:
                call_count += 1
                is_last_call = call_count == max_calls
                calls_left = max_calls - call_count
                query_runner.reset_call_budget(calls_left=calls_left)

                turn_messages = list(messages)
                if is_last_call and has_sources and call_count > 1:
                    turn_messages.append(
                        SystemMessage(
                            'Esta é a última chamada do orçamento. Apresente '
                            'a resposta final com base nos dados obtidos.'
                        )
                    )

                if not has_sources:
                    active_model = registered.model
                elif is_last_call:
                    active_model = (
                        registered.model.bind_tools(presentation_tools)
                        if hasattr(registered.model, 'bind_tools')
                        else registered.model
                    )
                else:
                    active_model = (
                        registered.model.bind_tools(query_tools)
                        if hasattr(registered.model, 'bind_tools')
                        else registered.model
                    )

                step = _ModelStep(
                    span,
                    session_id,
                    active_model.astream(
                        turn_messages,
                        config={
                            'callbacks': [*self.callbacks, token_tracker],
                            'metadata': {'model_tier': str(registered.tier)},
                        },
                    ),
                )

                turn_chunk: AIMessageChunk | None = None
                try:
                    while (chunk := await step.next_chunk()) is not None:
                        turn_chunk = (
                            chunk if turn_chunk is None else turn_chunk + chunk
                        )
                        if chunk.text:
                            accumulated_text += chunk.text
                            yield ContentDelta(
                                index=0, text=chunk.text, type='text'
                            )
                except ModelInvocationError:
                    span.end()
                    raise
                except BaseException:
                    span.set_status(
                        Status(
                            StatusCode.ERROR,
                            'Resposta interrompida pelo cliente',
                        )
                    )
                    span.end()
                    await step.close()
                    raise

                ai_message = turn_chunk or AIMessage('')
                messages.append(ai_message)

                tool_calls = getattr(ai_message, 'tool_calls', None) or []
                if not tool_calls:
                    break

                has_query = any(
                    tc.get('name') == 'query_data' for tc in tool_calls
                )
                for tc in tool_calls:
                    tool_msg, activity = await self._execute_tool_call(
                        tc, query_runner, span, session_id
                    )
                    if activity:
                        yield activity
                    messages.append(tool_msg)

                if not has_query:
                    break
        finally:
            await query_runner.close()

        # Emite blocos de apresentação que foram acumulados
        for i, block in enumerate(query_runner.pending_blocks, start=1):
            yield ContentDelta(index=i, type=block['type'], block=block)

        content_blocks: list[dict[str, Any]] = []
        if accumulated_text:
            content_blocks.append(
                TextBlock(text=accumulated_text).model_dump()
            )
        content_blocks.extend(query_runner.pending_blocks)
        if not content_blocks:
            content_blocks = [TextBlock(text='').model_dump()]

        self.agent_metrics.record_model_calls(call_count)

        span.set_output(accumulated_text or json.dumps(content_blocks))
        with trace.use_span(span, end_on_exit=True):
            logger.info(
                'Resposta gerada',
                extra={
                    'conversation.id': str(conversation.id),
                    'model.tier': str(registered.tier),
                    'agent.model_calls': call_count,
                },
            )

        assistant_message = Message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=content_blocks,
            model_tier=registered.tier,
            model_name=registered.name,
        )
        tokens_used = token_tracker.total_tokens
        if (
            tokens_used == 0
            and turn_chunk
            and getattr(turn_chunk, 'usage_metadata', None)
        ):
            um = turn_chunk.usage_metadata
            tokens_used = um.get('total_tokens') or (
                um.get('input_tokens', 0) + um.get('output_tokens', 0)
            )

        conversation.total_tokens = (
            conversation.total_tokens or 0
        ) + tokens_used

        if conversation.title is None:
            conversation.title = auto_title(content)
        conversation.updated_at = assistant_message.created_at

        self.session.add_all([user_message, assistant_message, conversation])
        await self.session.commit()
        yield AssistantMessageCompleted(assistant_message)

    async def _execute_tool_call(  # noqa: PLR0912
        self,
        tc: dict[str, Any],
        query_runner: QueryRunner,
        span: Any,
        session_id: str,
    ) -> tuple[ToolMessage, Activity | None]:
        tc_name = tc.get('name')
        tc_args = tc.get('args') or {}
        tc_id = tc.get('id', 'call_id')

        if tc_name == 'show_chart':
            res = query_runner.show_chart(
                result_id=tc_args.get('result_id', ''),
                chart_type=tc_args.get('chart_type', ''),
                title=tc_args.get('title', ''),
                x=tc_args.get('x', ''),
                series=tc_args.get('series', []),
            )
            return (
                ToolMessage(content=json.dumps(res), tool_call_id=tc_id),
                None,
            )

        if tc_name == 'show_table':
            res = query_runner.show_table(
                result_id=tc_args.get('result_id', ''),
                columns=tc_args.get('columns', []),
                title=tc_args.get('title'),
            )
            return (
                ToolMessage(content=json.dumps(res), tool_call_id=tc_id),
                None,
            )

        source_id = tc_args.get('source', '')
        ds = await query_runner._get_datasource(source_id)
        source_name = ds.name if ds else source_id
        purpose = sanitize_purpose(tc_args.get('purpose'), source_name)
        activity = Activity(
            kind='query', source=source_name, description=purpose
        )

        with (
            trace.use_span(span, end_on_exit=False),
            using_session(session_id),
        ):
            tool_span = self.tracer.start_span(
                'query_data', openinference_span_kind='tool'
            )
        tool_span.set_attribute(SpanAttributes.TOOL_NAME, 'query_data')
        tool_span.set_input(tc_args.get('sql', ''))
        tool_span.set_attribute('datasource.id', source_id)

        outcome = 'executed'
        try:
            res = await query_runner.query_data(
                source_id,
                tc_args.get('sql', ''),
                purpose=tc_args.get('purpose', ''),
            )
            if 'error' in res:
                err = res['error']
                if 'Tempo limite' in err:
                    outcome = 'timeout'
                elif 'indisponível' in err or 'conexão' in err:
                    outcome = 'failed'
                else:
                    outcome = 'rejected'
                tool_span.set_status(Status(StatusCode.ERROR, err))
                tool_span.set_attribute('query.error', err)
            else:
                tool_span.set_attribute(
                    'query.row_count', len(res.get('rows', []))
                )
                tool_span.set_attribute(
                    'query.truncated', res.get('truncated', False)
                )
            tool_span.set_output(json.dumps(res))
            tool_msg = ToolMessage(content=json.dumps(res), tool_call_id=tc_id)
        except Exception as exc:  # noqa: BLE001
            outcome = 'failed'
            tool_span.set_status(Status(StatusCode.ERROR, str(exc)))
            tool_span.set_output(str(exc))
            tool_msg = ToolMessage(
                content=json.dumps({'error': str(exc)}), tool_call_id=tc_id
            )
        finally:
            tool_span.end()
            self.agent_metrics.record_query(outcome=outcome, source=source_id)

        return tool_msg, activity

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
    agent_metrics: Annotated[AgentMetrics, Depends(get_agent_metrics)],
) -> ChatService:
    return ChatService(
        session, registry, tracer, callbacks, agent_metrics=agent_metrics
    )
