"""Execução das perguntas de referência pelo fluxo real da Maria."""

import sqlite3
import tempfile
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, closing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openinference.instrumentation import OITracer
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from observatorio_maria.database import configure_sqlite
from observatorio_maria.evaluation.checks import (
    CheckResult,
    CheckStatus,
    answer_texts,
    check_list,
    check_numbers,
    check_sources,
)
from observatorio_maria.evaluation.judge import judge_answer
from observatorio_maria.evaluation.reference import (
    JudgeCheck,
    ListCheck,
    NumbersCheck,
    ReferenceQuestion,
    SourcesCheck,
)
from observatorio_maria.llm.registry import ModelRegistry, ModelTier
from observatorio_maria.models import Conversation
from observatorio_maria.observability.genai import AgentMetrics, get_tracer
from observatorio_maria.query.tool import QueryObservation
from observatorio_maria.services.chat import ChatService
from observatorio_maria.settings import Settings

# Nível do modelo-juiz: ao menos tão capaz quanto o da resposta.
JUDGE_MODEL_TIER = ModelTier.ADVANCED

SessionFactory = async_sessionmaker[AsyncSession]


class EvaluationError(Exception):
    """A avaliação não pode ser executada."""


@asynccontextmanager
async def maria_database_copy(
    database_url: str,
) -> AsyncIterator[SessionFactory]:
    """Sessões numa cópia temporária do banco SQLite da Maria.

    A cópia leva o catálogo como está (com as edições feitas pela demo) e
    recebe as conversas da avaliação, que somem com ela.
    """
    url = make_url(database_url)
    if url.get_backend_name() != 'sqlite' or url.database in {
        None,
        '',
        ':memory:',
    }:
        raise EvaluationError(
            'A avaliação exige o banco da Maria em arquivo SQLite '
            '(DATABASE_URL).'
        )
    source = Path(url.database)
    if not source.is_file():
        raise EvaluationError(f'Banco da Maria não encontrado: {source}')

    with tempfile.TemporaryDirectory(prefix='maria-eval-') as tmp:
        copy = Path(tmp) / 'maria.db'
        # A API de backup gera uma cópia consistente mesmo com o WAL ativo.
        with (
            closing(
                sqlite3.connect(f'file:{source}?mode=ro', uri=True)
            ) as origin,
            closing(sqlite3.connect(copy)) as target,
        ):
            origin.backup(target)
        engine = create_async_engine(f'sqlite+aiosqlite:///{copy}')
        configure_sqlite(engine)
        try:
            yield async_sessionmaker(engine, expire_on_commit=False)
        finally:
            await engine.dispose()


class _RunMetrics(AgentMetrics):
    """Guarda as chamadas ao modelo da resposta em vez de exportá-las."""

    def __init__(self):  # noqa: PLW0231
        self.model_calls = 0

    def record_model_calls(self, count: int) -> None:
        self.model_calls = count

    def record_query(self, outcome: str, source: str) -> None:
        pass


@dataclass
class QuestionRun:
    question_id: str
    repetition: int
    status: CheckStatus
    checks: list[CheckResult] = field(default_factory=list)
    tokens: int = 0
    model_calls: int = 0
    queries: list[QueryObservation] = field(default_factory=list)
    answer: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    duration_seconds: float = 0.0


def overall_status(checks: list[CheckResult]) -> CheckStatus:
    """Certa só quando todos os critérios passam."""
    statuses = {c.status for c in checks}
    if 'failed' in statuses:
        return 'failed'
    if 'error' in statuses:
        return 'error'
    return 'passed'


async def evaluate_checks(
    question: ReferenceQuestion,
    answer: list[dict[str, Any]],
    queries: list[QueryObservation],
    registry: ModelRegistry,
) -> list[CheckResult]:
    texts = answer_texts(answer)
    results = []
    for check in question.checks:
        match check:
            case NumbersCheck():
                results.append(check_numbers(check, texts))
            case ListCheck():
                results.append(check_list(check, texts))
            case SourcesCheck():
                results.append(check_sources(check, queries))
            case JudgeCheck():
                judge = registry.get(JUDGE_MODEL_TIER).model
                results.append(
                    await judge_answer(
                        judge, question.question, '\n\n'.join(texts), check
                    )
                )
    return results


async def run_question(  # noqa: PLR0913, PLR0917
    session_factory: SessionFactory,
    registry: ModelRegistry,
    question: ReferenceQuestion,
    repetition: int,
    settings: Settings,
    tracer: OITracer,
) -> QuestionRun:
    """Responde a pergunta numa conversa nova e avalia os critérios."""
    run = QuestionRun(question.id, repetition, status='error')
    started = time.perf_counter()
    async with session_factory() as session:
        conversation = Conversation(title=f'Avaliação: {question.id}')
        session.add(conversation)
        await session.commit()
        metrics = _RunMetrics()
        service = ChatService(
            session,
            registry,
            tracer,
            [],
            settings=settings,
            agent_metrics=metrics,
            query_observer=run.queries.append,
        )
        try:
            _, assistant = await service.send_message(
                conversation, question.question
            )
        except Exception as exc:  # noqa: BLE001
            run.error = f'{type(exc).__name__}: {exc}'
            run.duration_seconds = time.perf_counter() - started
            return run
        run.answer = assistant.content
        run.tokens = conversation.total_tokens or 0
        run.model_calls = metrics.model_calls

    run.checks = await evaluate_checks(
        question, run.answer, run.queries, registry
    )
    run.status = overall_status(run.checks)
    run.duration_seconds = time.perf_counter() - started
    return run


async def run_evaluation(  # noqa: PLR0913
    questions: list[ReferenceQuestion],
    *,
    registry: ModelRegistry,
    database_url: str,
    settings: Settings,
    repeat: int = 1,
    on_run: Callable[[QuestionRun, int, int], None] | None = None,
) -> list[QuestionRun]:
    """Roda cada pergunta `repeat` vezes; falhas não interrompem as demais."""
    tracer = get_tracer()
    total = len(questions) * repeat
    runs: list[QuestionRun] = []
    async with maria_database_copy(database_url) as session_factory:
        for question in questions:
            for repetition in range(1, repeat + 1):
                run = await run_question(
                    session_factory,
                    registry,
                    question,
                    repetition,
                    settings,
                    tracer,
                )
                runs.append(run)
                if on_run:
                    on_run(run, len(runs), total)
    return runs
