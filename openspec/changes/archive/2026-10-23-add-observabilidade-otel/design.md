# Design

## Context

Os requisitos estão em `specs/observability/spec.md` e a motivação em `proposal.md`. A aplicação concentra todas as chamadas ao LLM no `ChatService` e já injeta dependências via `Depends`, o que dá pontos naturais de instrumentação. As restrições são: somente software livre e sem assinatura, OpenTelemetry como padrão, e a stack Prometheus, Tempo, Loki e Grafana, com o Phoenix para LLM.

## Goals / Non-Goals

**Goals:**
- Um único protocolo de saída da aplicação (OTLP). O roteamento entre backends fica no Collector, que é a peça desenhada para isso.
- Cada ferramenta no seu papel:
  - Tempo guarda traces.
  - Prometheus guarda métricas.
  - Loki guarda logs.
  - Grafana visualiza e correlaciona.
  - Phoenix analisa o comportamento do LLM (caminho, prompts, tokens, avaliações).
- Instrumentação por bibliotecas oficiais e convenções semânticas, sem atributos inventados.

**Non-Goals:**
- Deploy da stack em produção, retenção e alertas.
- Avaliações automáticas (evals) no Phoenix. A stack as permite, mas configurá-las é outra mudança.

## Decisions

### 1. Aplicação → OTLP/HTTP → Collector
O SDK é configurado programaticamente em `observability/telemetry.py` (`setup_telemetry(app, engine)`):
- `TracerProvider` com `BatchSpanProcessor` + `OTLPSpanExporter`;
- `MeterProvider` com `PeriodicExportingMetricReader` + `OTLPMetricExporter`;
- `LoggerProvider` com `BatchLogRecordProcessor` + `OTLPLogExporter`, e `LoggingHandler` no logger raiz.

Os exporters leem as variáveis padrão (`OTEL_EXPORTER_OTLP_ENDPOINT`), e o `Resource` lê `OTEL_SERVICE_NAME`/`OTEL_RESOURCE_ATTRIBUTES` (padrão `observatorio-maria`). Com `OTEL_SDK_DISABLED=true` a função retorna sem configurar nada. Os processadores em lote exportam em segundo plano, então um coletor fora do ar só gera avisos no log e nunca falha a requisição.

*Alternativa:* `opentelemetry-instrument` (instrumentação automática por CLI). Descartada porque esconde a configuração, não convive bem com o `fastapi dev --reload` e dificulta os testes.

### 2. Instrumentação por bibliotecas oficiais
- `FastAPIInstrumentor.instrument_app(app, excluded_urls='health,demo')` gera spans HTTP e as métricas `http.server.request.duration`.
- `SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)` gera spans de consulta. O engine assíncrono delega ao `sync_engine`.
- `LangChainInstrumentor().instrument(tracer_provider=...)` (OpenInference) gera spans de LLM com mensagens, modelo e tokens no esquema que o Phoenix entende. Como são spans OTel, eles também vão para o Tempo, no mesmo trace da requisição.

### 3. Span de cadeia `maria.chat` e sessão
O `ChatService` abre um span `maria.chat` com `openinference.span.kind=CHAIN` usando o `OITracer` do OpenInference, que respeita `OPENINFERENCE_HIDE_INPUTS/OUTPUTS`. O span registra a entrada (a mensagem) e a saída (a resposta). A chamada ao modelo roda dentro de `using_session(str(conversation.id))`, então o span de cadeia e os de LLM levam `session.id`, e o Phoenix agrupa as respostas por conversa. Em caso de falha, o span registra a exceção e o status de erro.

O tracer chega ao serviço por `Depends(get_tracer)`, e nos testes ele é substituído por um tracer de um provider em memória. Quando a Maria ganhar ferramentas (consultas a bancos), cada ferramenta aparece como span `TOOL` filho de `maria.chat`. Esse é o caminho que a IA percorreu.

### 4. Métricas GenAI via callback do LangChain
`GenAIMetricsHandler(BaseCallbackHandler)` é o ponto de extensão que o LangChain oferece para observar execuções:
- `on_chat_model_start` guarda o instante de início e os metadados `ls_provider`/`ls_model_name` do LangChain;
- `on_llm_end` registra `gen_ai.client.token.usage` (histograma, `gen_ai.token.type=input|output`) a partir de `usage_metadata` e `gen_ai.client.operation.duration`;
- `on_llm_error` registra a duração com `error.type`.

Os atributos seguem as convenções GenAI (`gen_ai.operation.name`, `gen_ai.provider.name`, `gen_ai.request.model`). Os callbacks entram no serviço por `Depends(get_llm_callbacks)` e são passados em `ainvoke(..., config={'callbacks': ...})`.

*Alternativa:* derivar métricas dos spans no Collector (`spanmetrics`). Descartada porque gera métricas genéricas de span, não as métricas de tokens da convenção GenAI.

### 5. Logs
O logging da stdlib (`logging.getLogger(__name__)`), via `LoggingHandler`, segue para o OTLP. Dentro de um span ativo, o SDK preenche `trace_id`/`span_id` automaticamente. O serviço registra a falha do modelo com `logger.exception`.

### 6. Collector como roteador
O `observability/otel-collector.yaml` define estes pipelines:
- `traces`: otlp → batch → `otlp/tempo`.
- `traces/phoenix`: otlp → `filter` (descarta spans sem `openinference.span.kind`) → batch → `otlphttp/phoenix`. O Phoenix recebe só o que é de LLM.
- `metrics`: otlp → batch → `prometheus` (endpoint `:8889`), e o Prometheus faz o scrape. É o modelo pull, nativo do Prometheus.
- `logs`: otlp → batch → `otlphttp/loki` (endpoint OTLP nativo do Loki, `/otlp`).

No pipeline do Phoenix, um `transform` zera o `parent_span_id` dos spans `maria.chat`. A verificação mostrou que, sem isso, as sessões do Phoenix ficam sem a primeira entrada, porque o Phoenix monta sessões a partir de spans raiz. O Tempo recebe o trace original.

### 7. Stack Docker Compose (`observability/compose.yaml`)
Imagens com versões fixas:

| Componente | Imagem | Portas |
|---|---|---|
| Collector | `otel/opentelemetry-collector-contrib:0.163.2` | 4317 e 4318 (expostas) |
| Tempo | `grafana/tempo:2.10.10` | — |
| Loki | `grafana/loki:3.7.9` | — |
| Prometheus | `prom/prometheus:v3.15.1` | 9090 |
| Grafana | `grafana/grafana:13.2.4` | 3000 (acesso anônimo de admin, só para dev) |
| Phoenix | `arizephoenix/phoenix:20.25.0` | 6006 |

O Grafana provisiona os datasources Prometheus, Tempo e Loki com correlação:
- Tempo → Loki por `trace_id` (traces-to-logs);
- Loki → Tempo (derived field);
- Tempo → Prometheus.

Também provisiona um dashboard "Maria" com taxa e latência HTTP e uso de tokens. O Tempo usa armazenamento local e o Loki, filesystem. Os volumes são nomeados.

### 8. Testes
A suíte padrão roda com `OTEL_SDK_DISABLED=true`, definido no `conftest` antes do import da app. Os testes de telemetria religam o SDK via `monkeypatch` e usam `InMemorySpanExporter`, `InMemoryMetricReader` e `InMemoryLogExporter`, instrumentando o LangChain com o provider de teste (e desinstrumentando ao final). A integração com FastAPI e SQLAlchemy é verificada na stack real.

### 9. Faixa de Python
O `openinference-instrumentation-langchain` declara `requires-python <3.15`. O `requires-python` do projeto passa de `>=3.12,<4.0` para `>=3.12,<3.15`; o ambiente atual usa 3.14. A faixa é ampliada quando o OpenInference suportar versões novas.

### 10. SQLAlchemy na série 2.0
O `opentelemetry-instrumentation-sqlalchemy` só suporta `sqlalchemy <2.1` e se recusa a instrumentar a 2.1. A dependência passa a `sqlalchemy[asyncio]>=2.0.35,<2.1` em vez de forçar a instrumentação com `skip_dep_check`. O limite é removido quando a instrumentação suportar a 2.1.

## Risks / Trade-offs

- [Prompts e respostas com dados pessoais vão para o Tempo e o Phoenix] → Variáveis `OPENINFERENCE_HIDE_INPUTS/OUTPUTS`. A stack é local ou self-hosted, então os dados não saem da infraestrutura.
- [O volume de spans de banco no Tempo] → É baixo nesta fase. Amostragem por `OTEL_TRACES_SAMPLER` se necessário.
- [A API de logs do SDK Python ainda é marcada como em desenvolvimento (`_logs`)] → Ela fica isolada em `telemetry.py`, então ajustes futuros se limitam a um arquivo.
- [Seis containers para desenvolvimento] → São opcionais. Sem a stack, basta `OTEL_SDK_DISABLED=true`.

## Migration Plan

1. `poetry install`.
2. `docker compose -f observability/compose.yaml up -d`.
3. No `.env`: `OTEL_SDK_DISABLED=false` e `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318`.
4. Rollback: `OTEL_SDK_DISABLED=true` (sem mudança de código).
