# Tasks

## 1. Dependências

- [x] 1.1 Adicionar `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-http`, `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-sqlalchemy` e `openinference-instrumentation-langchain`; verificar com `poetry install` e import dos módulos

## 2. Instrumentação da aplicação

- [x] 2.1 Criar `observability/telemetry.py` com `setup_telemetry(app, engine)` (providers OTLP de traces, métricas e logs; instrumentação de FastAPI, SQLAlchemy e LangChain; respeito a `OTEL_SDK_DISABLED`) e chamá-la no `app.py`; verificar com teste de que, desligada, nenhum provider é configurado e a API funciona
- [x] 2.2 Criar `GenAIMetricsHandler` e a dependência `get_llm_callbacks`; verificar com teste usando `InMemoryMetricReader` (tokens por tipo, duração, erro)
- [x] 2.3 Envolver a resposta no `ChatService` com span `maria.chat` (OITracer), `using_session` e `logger.exception` na falha, com tracer e callbacks injetados; verificar com testes em memória: hierarquia `maria.chat` → LLM, `session.id`, status de erro, ocultação de conteúdo e `trace_id` no log de falha

## 3. Stack local

- [x] 3.1 Criar `observability/compose.yaml` e as configurações de Collector, Tempo, Loki, Prometheus e Grafana (datasources correlacionados e dashboard); verificar com `docker compose up` e todos os serviços saudáveis
- [x] 3.2 Validar ponta a ponta enviando mensagens pela API: trace no Tempo (HTTP → banco → LLM) e no Phoenix (sessão), métricas no Prometheus, logs no Loki e navegação trace → logs no Grafana; ajustar o pipeline do Phoenix se necessário

## 4. Documentação

- [x] 4.1 Atualizar o README e o `.env.example` (variáveis `OTEL_*` e `OPENINFERENCE_*`, como subir a stack, URLs e o que observar em cada ferramenta); verificar `task test` sem falhas
