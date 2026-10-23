"""Configuração do OpenTelemetry: traces, métricas e logs via OTLP.

Os exporters leem as variáveis padrão (OTEL_EXPORTER_OTLP_ENDPOINT, etc.)
e enviam tudo ao OpenTelemetry Collector, que roteia cada sinal ao seu
backend (Tempo, Prometheus, Loki e Phoenix).
"""

# A API de logs do OpenTelemetry para Python ainda é experimental e seu
# caminho oficial de import é `_logs`.
# ruff: noqa: PLC2701

import logging
import os

from fastapi import FastAPI
from openinference.instrumentation.langchain import LangChainInstrumentor
from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import (
    OTLPLogExporter,
)
from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
    OTLPMetricExporter,
)
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.environment_variables import OTEL_SDK_DISABLED
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from sqlalchemy.ext.asyncio import AsyncEngine

DEFAULT_SERVICE_NAME = 'observatorio-maria'
INSTRUMENTATION_NAME = 'observatorio_maria'

# Rotas sem valor diagnóstico (sondas e arquivos estáticos da demo).
EXCLUDED_URLS = 'health,demo'


def telemetry_disabled() -> bool:
    return os.getenv(OTEL_SDK_DISABLED, 'false').strip().lower() == 'true'


def build_resource() -> Resource:
    # Resource.create também incorpora OTEL_RESOURCE_ATTRIBUTES.
    service_name = os.getenv('OTEL_SERVICE_NAME', DEFAULT_SERVICE_NAME)
    return Resource.create({SERVICE_NAME: service_name})


def instrument(
    app: FastAPI,
    engine: AsyncEngine,
    tracer_provider: TracerProvider,
    meter_provider: MeterProvider,
):
    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
        excluded_urls=EXCLUDED_URLS,
    )
    # O engine assíncrono executa sobre o sync_engine.
    SQLAlchemyInstrumentor().instrument(
        engine=engine.sync_engine,
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
    )
    LangChainInstrumentor().instrument(tracer_provider=tracer_provider)


def setup_telemetry(app: FastAPI, engine: AsyncEngine):
    """Configura os provedores globais e instrumenta a aplicação.

    Com OTEL_SDK_DISABLED=true nada é configurado. Os processadores em lote
    exportam em segundo plano: coletor indisponível não afeta requisições.
    """
    if telemetry_disabled():
        return

    # Usa as convenções semânticas HTTP estáveis (ex.: métrica
    # http.server.request.duration em segundos), base do dashboard.
    os.environ.setdefault('OTEL_SEMCONV_STABILITY_OPT_IN', 'http')

    resource = build_resource()

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(tracer_provider)

    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[PeriodicExportingMetricReader(OTLPMetricExporter())],
    )
    metrics.set_meter_provider(meter_provider)

    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(
        BatchLogRecordProcessor(OTLPLogExporter())
    )
    set_logger_provider(logger_provider)
    logging.getLogger().addHandler(
        LoggingHandler(logger_provider=logger_provider)
    )
    logging.getLogger(INSTRUMENTATION_NAME).setLevel(logging.INFO)

    instrument(app, engine, tracer_provider, meter_provider)
