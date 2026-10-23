# Proposal

## Why

A Maria vai evoluir de um chat simples para um agente que consulta bancos externos. Sem observabilidade não há como saber que caminho a IA percorreu até uma resposta, quanto cada resposta custou em tokens, onde está a latência ou por que algo falhou. Instrumentar agora, enquanto o fluxo é pequeno, é barato. A instrumentação deve usar padrões abertos e ferramentas sem assinatura.

## What Changes

- Instrumentação da aplicação com **OpenTelemetry**: traces (HTTP, banco e LLM no mesmo trace), métricas e logs, exportados via OTLP para um **OpenTelemetry Collector**.
- Spans de LLM no padrão **OpenInference** (instrumentação oficial do LangChain), com prompt, resposta, modelo e tokens, agrupados por sessão (= conversa). Um span de cadeia `maria.chat` envolve cada resposta e mostra o caminho completo.
- Métricas de IA conforme as convenções semânticas GenAI do OpenTelemetry (`gen_ai.client.token.usage` e `gen_ai.client.operation.duration`), registradas por um callback do LangChain.
- Logs da aplicação exportados via OTLP com `trace_id`/`span_id`, correlacionáveis com os traces.
- Stack local via Docker Compose, cada ferramenta no seu papel:
  - **Collector**: recebe e roteia os sinais.
  - **Grafana Tempo**: todos os traces.
  - **Prometheus**: métricas.
  - **Loki**: logs.
  - **Grafana**: visualização e correlação, com datasources e dashboard provisionados.
  - **Arize Phoenix**: análise dos traces de LLM e avaliações.
- Configuração pelas variáveis padrão `OTEL_*`. A telemetria pode ser desligada (`OTEL_SDK_DISABLED=true`) e a captura de conteúdo pode ser ocultada (LGPD).

## Capabilities

### New Capabilities
- `observability`: emissão de traces, métricas e logs da API e do LLM em padrão aberto, com a stack de coleta e visualização.

### Modified Capabilities
<!-- Nenhuma: o comportamento funcional da API não muda. -->

## Impact

- Dependências: `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-http`, `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-sqlalchemy`, `openinference-instrumentation-langchain`.
- Código: novo pacote `observability/`, `app.py` (inicialização), `services/chat.py` (span de cadeia, sessão e callbacks injetados).
- Infra: novo diretório `observability/` na raiz com `compose.yaml` e as configurações de Collector, Tempo, Loki, Prometheus e Grafana.
- Testes: exportadores em memória; a telemetria fica desligada na suíte padrão.
