"""Métricas e tracer para as chamadas de IA.

As métricas seguem as convenções semânticas GenAI do OpenTelemetry e são
coletadas por um callback do LangChain, o ponto de extensão que a biblioteca
oferece para observar execuções de modelos.
"""

import time
from functools import lru_cache
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from openinference.instrumentation import OITracer, TraceConfig
from opentelemetry import metrics, trace
from opentelemetry.metrics import Meter

from observatorio_maria.observability.telemetry import INSTRUMENTATION_NAME

# Fronteiras recomendadas pelas convenções GenAI.
TOKEN_BUCKETS = [1, 4, 16, 64, 256, 1024, 4096, 16384, 65536, 262144]
DURATION_BUCKETS = [
    0.01, 0.02, 0.04, 0.08, 0.16, 0.32, 0.64, 1.28, 2.56, 5.12, 10.24,
    20.48, 40.96, 81.92,
]  # fmt: skip


class GenAIMetricsHandler(BaseCallbackHandler):
    """Registra as métricas GenAI de uso de tokens e de duração."""

    run_inline = True

    def __init__(self, meter: Meter):
        self._token_usage = meter.create_histogram(
            'gen_ai.client.token.usage',
            unit='{token}',
            description='Tokens usados por operação de IA.',
            explicit_bucket_boundaries_advisory=TOKEN_BUCKETS,
        )
        self._duration = meter.create_histogram(
            'gen_ai.client.operation.duration',
            unit='s',
            description='Duração das operações de IA.',
            explicit_bucket_boundaries_advisory=DURATION_BUCKETS,
        )
        self._runs: dict[UUID, tuple[float, dict[str, str]]] = {}

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list,
        *,
        run_id: UUID,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ):
        # O LangChain informa provedor e modelo nos metadados ls_*.
        metadata = metadata or {}
        attributes = {'gen_ai.operation.name': 'chat'}
        if provider := metadata.get('ls_provider'):
            attributes['gen_ai.provider.name'] = provider
        if model := metadata.get('ls_model_name'):
            attributes['gen_ai.request.model'] = model
        self._runs[run_id] = (time.perf_counter(), attributes)

    def on_llm_end(self, response: LLMResult, *, run_id: UUID, **kwargs):
        run = self._runs.pop(run_id, None)
        if run is None:
            return
        started_at, attributes = run
        self._duration.record(time.perf_counter() - started_at, attributes)

        message = getattr(response.generations[0][0], 'message', None)
        usage = getattr(message, 'usage_metadata', None)
        if not usage:
            return
        for token_type, key in (
            ('input', 'input_tokens'),
            ('output', 'output_tokens'),
        ):
            self._token_usage.record(
                usage[key], {**attributes, 'gen_ai.token.type': token_type}
            )

    def on_llm_error(self, error: BaseException, *, run_id: UUID, **kwargs):
        run = self._runs.pop(run_id, None)
        if run is None:
            return
        started_at, attributes = run
        self._duration.record(
            time.perf_counter() - started_at,
            {**attributes, 'error.type': type(error).__qualname__},
        )


@lru_cache
def get_genai_metrics_handler() -> GenAIMetricsHandler:
    # O meter global é um proxy até o MeterProvider ser configurado.
    return GenAIMetricsHandler(metrics.get_meter(INSTRUMENTATION_NAME))


class AgentMetrics:
    """Métricas de execução do agente (chamadas ao modelo e consultas)."""

    def __init__(self, meter: Meter):
        self._model_calls = meter.create_histogram(
            'maria.agent.model_calls',
            unit='{call}',
            description='Número de chamadas ao modelo por resposta.',
            explicit_bucket_boundaries_advisory=[1, 2, 3, 4, 5],
        )
        self._query_count = meter.create_counter(
            'maria.query.count',
            unit='{query}',
            description='Total de consultas a fontes do catálogo.',
        )

    def record_model_calls(self, count: int) -> None:
        self._model_calls.record(count)

    def record_query(self, outcome: str, source: str) -> None:
        self._query_count.add(1, {'outcome': outcome, 'source': source})


@lru_cache
def get_agent_metrics() -> AgentMetrics:
    return AgentMetrics(metrics.get_meter(INSTRUMENTATION_NAME))


def get_llm_callbacks(
    metrics_handler: Annotated[
        GenAIMetricsHandler, Depends(get_genai_metrics_handler)
    ],
) -> list[BaseCallbackHandler]:
    return [metrics_handler]


def get_tracer() -> OITracer:
    # OITracer aplica as regras de ocultação (OPENINFERENCE_HIDE_*).
    return OITracer(
        trace.get_tracer(INSTRUMENTATION_NAME), config=TraceConfig()
    )
