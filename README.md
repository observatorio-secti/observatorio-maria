# Observatório Maria · API

API da **Maria**, agente de IA do Observatório Maria voltado à pesquisa científica, tecnológica e de inovação na Bahia. A API gerencia conversas, gera respostas com modelos de linguagem via LangChain (inclusive em streaming) e é observável de ponta a ponta com OpenTelemetry.

---

## ✨ O que já existe

| Área | Funcionalidade |
|---|---|
| **Conversas** | Criar, listar (paginado, mais recentes primeiro), detalhar, renomear e excluir (as mensagens vão junto). Título automático a partir da primeira pergunta. |
| **Chat** | Envio de mensagem com resposta completa ou em **streaming (SSE)**, com o texto chegando enquanto é gerado. O histórico da conversa é enviado como contexto ao modelo. |
| **Contrato de conteúdo** | Mensagens em **blocos tipados** (`text`, `chart`, `table`), prontos para gráficos e tabelas no frontend. |
| **Modelos de IA** | Três níveis internos (`fast`, `medium`, `advanced`), configuráveis por ambiente e independentes de provedor. Não são expostos nem escolhidos pelo cliente. |
| **Confiabilidade** | Persistência atômica: pergunta e resposta só são gravadas quando a geração termina. Falhas e interrupções não deixam registros parciais. |
| **Observabilidade** | Traces, métricas e logs via OpenTelemetry. O caminho de cada resposta da IA fica visível no Arize Phoenix. Stack local com Grafana, Tempo, Loki e Prometheus. |
| **Demo** | Página em `/demo/` para conversar com a Maria e visualizar o contrato de blocos. |

---

## 🧱 Stack

- **Python** 3.12–3.14, **FastAPI** (SSE nativo), **Pydantic Settings**.
- **LangChain** (`init_chat_model`, independente de provedor), começando com **OpenAI**.
- **SQLAlchemy 2.0 assíncrono** (`aiosqlite` em dev, `psycopg` para PostgreSQL) e **Alembic**.
- **OpenTelemetry** + **OpenInference**. Na stack local: **Collector**, **Grafana Tempo**, **Loki**, **Prometheus**, **Grafana** e **Arize Phoenix** (todos open source, sem assinatura).
- **Pytest** + **pytest-asyncio**, **Ruff**, **Taskipy** e **Poetry**.

---

## 🏗️ Arquitetura

```text
Cliente (frontend / demo)
   │  HTTP JSON  ·  SSE
   ▼
routers/            ← HTTP: validação, códigos de status, tradução para SSE
   │  Depends(...)
   ▼
services/chat.py    ← regra de negócio: contexto, geração em stream, persistência atômica
   │                    │
   ▼                    ▼
models.py (banco)   llm/registry.py (ModelRegistry → BaseChatModel do LangChain)
                        │
observability/  ◄───────┘ span maria.chat, métricas GenAI e logs → OTLP → Collector
```

- **As rotas são finas** e tudo é injetado via `Depends`: sessão do banco, registro de modelos, tracer e callbacks. Nos testes, cada peça é trocada por um fake.
- **O fluxo de geração é um só:** `ChatService.stream_message` gera os eventos, e o envio comum (`send_message`) consome esse mesmo fluxo.
- **O código depende apenas da interface `BaseChatModel` do LangChain**, então trocar de provedor é questão de configuração.

### Estrutura de diretórios

```text
.
├── pyproject.toml / poetry.lock     # Dependências, Ruff, Pytest e Taskipy
├── alembic.ini · migrations/        # Migrações do banco (Alembic async)
├── observability/                   # Stack local de observabilidade (Docker Compose)
│   ├── compose.yaml
│   ├── otel-collector.yaml          # Roteamento: Tempo, Phoenix, Prometheus e Loki
│   ├── tempo.yaml · loki.yaml · prometheus.yml
│   └── grafana/                     # Datasources correlacionados e dashboard "Maria · API e IA"
├── openspec/                        # Specs do sistema e mudanças (planejamento)
├── src/observatorio_maria/
│   ├── app.py                       # FastAPI, routers, handler 503, demo e telemetria
│   ├── settings.py                  # Configurações (Pydantic Settings)
│   ├── database.py                  # Engine async e get_session
│   ├── models.py                    # Tabelas Conversation e Message
│   ├── schemas.py                   # Schemas da API, blocos e eventos SSE
│   ├── llm/
│   │   ├── registry.py              # ModelTier, ModelRegistry e get_model_registry
│   │   └── prompts.py               # Prompt de sistema da Maria
│   ├── services/chat.py             # ChatService (stream_message / send_message)
│   ├── routers/
│   │   ├── health.py                # /health
│   │   └── conversations.py         # /conversations, mensagens e streaming
│   ├── observability/
│   │   ├── telemetry.py             # Setup do OpenTelemetry (OTLP)
│   │   └── genai.py                 # Métricas GenAI (callback) e tracer OpenInference
│   └── demo/                        # Página de demonstração (HTML, CSS e JS)
└── tests/                           # Testes assíncronos com fakes do LangChain
```

---

## 🚀 Começando

### Pré-requisitos

- Python 3.12, 3.13 ou 3.14 e [Poetry](https://python-poetry.org/) 2.x.
- Uma chave da OpenAI (`OPENAI_API_KEY`).
- Docker com Compose, opcional, para a stack de observabilidade.

### 1. Instalar

```bash
poetry install
```

O `poetry.toml` já cria o `.venv` dentro do projeto. Use `poetry run <comando>` ou ative com `source .venv/bin/activate`.

### 2. Configurar

```bash
cp .env.example .env
```

Preencha ao menos o `OPENAI_API_KEY`. Sem a stack de observabilidade rodando, defina `OTEL_SDK_DISABLED=true` (veja [Configuração](#️-configuração)).

### 3. Criar o banco

```bash
alembic upgrade head
```

### 4. Rodar

```bash
task run
```

- API: http://localhost:8000
- Documentação interativa: http://localhost:8000/docs
- Demo: http://localhost:8000/demo/

### 5. Observabilidade (opcional)

```bash
docker compose -f observability/compose.yaml up -d
```

Com a stack no ar e `OTEL_SDK_DISABLED=false`, a API passa a enviar telemetria automaticamente (veja [Observabilidade](#-observabilidade)).

---

## ⚙️ Configuração

As variáveis são lidas do ambiente e do `.env`.

| Variável | Descrição | Padrão |
|---|---|---|
| `DATABASE_URL` | URL do banco com **driver assíncrono** | `sqlite+aiosqlite:///./observatorio.db` |
| `ENVIRONMENT` | Nome do ambiente | `development` |
| `DEMO_ENABLED` | Serve a demo em `/demo/` | `true` |
| `OPENAI_API_KEY` | Credencial da OpenAI, lida pelo SDK do provedor | — |
| `LLM_FAST_MODEL` / `LLM_MEDIUM_MODEL` / `LLM_ADVANCED_MODEL` | Modelo de cada nível interno, no formato `provedor:modelo` | `openai:gpt-6-luna` |
| `LLM_*_MODEL_KWARGS` | Parâmetros extras do modelo, em JSON | `{"reasoning_effort": "low"}` |
| `OTEL_SDK_DISABLED` | Desliga toda a telemetria | `false` |
| `OTEL_SERVICE_NAME` | Nome do serviço nos sinais | `observatorio-maria` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Endpoint OTLP/HTTP do Collector | `http://localhost:4318` |
| `OPENINFERENCE_HIDE_INPUTS` / `OPENINFERENCE_HIDE_OUTPUTS` | Oculta o texto das mensagens nos traces (LGPD) | `false` |

---

## 🌐 API

| Método | Rota | Descrição |
|---|---|---|
| GET | `/health` | Verifica a API e o banco |
| POST | `/conversations` | Cria uma conversa (`title` opcional) |
| GET | `/conversations?offset=0&limit=20` | Lista conversas, mais recentes primeiro (`limit` ≤ 100) |
| GET | `/conversations/{id}` | Detalha uma conversa |
| PATCH | `/conversations/{id}` | Renomeia (`{"title": "..."}`) |
| DELETE | `/conversations/{id}` | Exclui a conversa e as mensagens (204) |
| GET | `/conversations/{id}/messages` | Histórico em ordem cronológica |
| POST | `/conversations/{id}/messages` | Envia `{"content": "..."}` e retorna `{user_message, assistant_message}` |
| POST | `/conversations/{id}/messages/stream` | Igual ao anterior, mas a resposta chega em **Server-Sent Events** |

O corpo de envio aceita **somente** `content` (1 a 10.000 caracteres). Campos extras, como tentar escolher o modelo, são rejeitados com 422.

### Mensagens e blocos de conteúdo

```json
{
  "id": "…", "conversation_id": "…", "role": "assistant",
  "content": [{"type": "text", "text": "Markdown…"}],
  "created_at": "2026-10-23T08:00:00Z"
}
```

`content` é uma lista de blocos discriminados por `type`. O frontend renderiza cada bloco conforme o tipo e **deve ignorar tipos desconhecidos**. Assim, novos blocos não quebram clientes antigos.

```json
[
  {"type": "text", "text": "Em 2024 houve aumento nas bolsas:"},
  {"type": "chart", "chart_type": "bar", "title": "Bolsas por ano",
   "x": {"key": "ano", "label": "Ano", "type": "category"},
   "series": [{"key": "bolsas", "label": "Bolsas", "unit": "un"}],
   "data": [{"ano": "2023", "bolsas": 120}, {"ano": "2024", "bolsas": 150}]},
  {"type": "table", "title": "Detalhe",
   "columns": [{"key": "ano", "label": "Ano"}, {"key": "bolsas", "label": "Bolsas", "type": "number"}],
   "rows": [{"ano": "2023", "bolsas": 120}]}
]
```

Hoje a Maria produz blocos `text`. `chart` e `table` já fazem parte do contrato (estão no OpenAPI), então o frontend pode ser preparado desde já.

### Streaming (Server-Sent Events)

`POST /conversations/{id}/messages/stream` emite os eventos nesta ordem:

| Evento | Dados | Quando |
|---|---|---|
| `message.user` | `MessagePublic` da pergunta | Logo no início |
| `content.delta` | `{"index": 0, "type": "text", "text": "…"}` | A cada fragmento gerado (`index` é a posição do bloco no `content` final) |
| `message.assistant` | `MessagePublic` da resposta, **já persistida** | Ao final |
| `error` | `{"detail": "…"}` | Se o modelo falhar depois de iniciado o stream; nada é gravado |

```bash
curl -N -X POST http://localhost:8000/conversations/<id>/messages/stream \
  -H 'Content-Type: application/json' -d '{"content": "O que é a FAPESB?"}'
```

Como o `EventSource` do navegador só faz `GET`, o cliente usa `fetch` e lê o corpo como stream. A demo (`src/observatorio_maria/demo/app.js`, função `streamEvents`) tem um exemplo completo.

Se o cliente fechar a conexão no meio, a geração é interrompida e nada é gravado. Em produção, configure o proxy reverso para não fazer buffer (por exemplo, `X-Accel-Buffering: no` no Nginx), senão o efeito de streaming se perde.

### Erros

| Status | Quando |
|---|---|
| 404 | Conversa inexistente |
| 422 | Corpo inválido ou campos extras |
| 502 | O modelo falhou no envio comum; nada é gravado |
| 503 | Os modelos não puderam ser configurados (ex.: falta `OPENAI_API_KEY`) |

---

## 🤖 Modelos de IA

- Os níveis `fast`, `medium` e `advanced` são **internos**: a aplicação decide qual usar, e hoje o chat usa `medium` (`CHAT_MODEL_TIER` em `services/chat.py`). O nível e o modelo de cada resposta ficam gravados no banco, para auditoria, mas não aparecem na API.
- Para trocar o modelo de um nível, altere a variável e reinicie. Para outro provedor, instale o pacote do LangChain correspondente e use o prefixo dele, por exemplo `LLM_ADVANCED_MODEL="anthropic:<modelo>"` com `langchain-anthropic`.
- O prompt de sistema da Maria fica em `src/observatorio_maria/llm/prompts.py`.

---

## 🗄️ Banco de dados

- Em desenvolvimento, o banco é SQLite (`observatorio.db`). Para PostgreSQL:
  ```bash
  DATABASE_URL="postgresql+psycopg://usuario:senha@localhost:5432/observatorio"
  ```
- Para aplicar as migrações:
  ```bash
  alembic upgrade head
  ```
- Depois de alterar `models.py`, gere uma nova migração:
  ```bash
  alembic revision --autogenerate -m "descrição"
  ```
- Tabelas:
  - `conversations`: `id`, `title`, `created_at` e `updated_at`;
  - `messages`: `id`, `conversation_id`, `role`, `content` (JSON com os blocos), `model_tier`, `model_name` e `created_at`. Excluir a conversa apaga as mensagens em cascata.

---

## 🔭 Observabilidade

A aplicação emite traces, métricas e logs com **OpenTelemetry** e envia tudo via OTLP ao **Collector**, que roteia cada sinal para a ferramenta feita para ele:

| Ferramenta | Papel | Acesso |
|---|---|---|
| **Grafana Tempo** | Todos os traces: HTTP → banco → IA, no mesmo trace | Grafana → Explore → Tempo |
| **Prometheus** | Métricas HTTP e de IA | http://localhost:9090 |
| **Loki** | Logs da aplicação, com `trace_id` | Grafana → Explore → Loki |
| **Grafana** | Visualização e correlação (do trace para os logs e de volta); dashboard **Maria · API e IA** | http://localhost:3000 |
| **Arize Phoenix** | Análise da IA: caminho de cada resposta, prompts, tokens e sessões (= conversas) | http://localhost:6006 |

Para subir e parar a stack:

```bash
docker compose -f observability/compose.yaml up -d
```

```bash
docker compose -f observability/compose.yaml down
```

### O que é emitido

- **Caminho da IA:** cada resposta, completa ou em streaming, gera um span `maria.chat` (OpenInference `CHAIN`) com a pergunta, a resposta e o `session.id` da conversa. Dentro dele ficam as chamadas ao modelo (`LLM`), com mensagens, modelo e tokens. Ferramentas futuras, como consultas a bancos, aparecerão como passos dentro desse span.
- **Métricas GenAI** (convenções semânticas do OpenTelemetry): `gen_ai.client.token.usage` (por tipo de token) e `gen_ai.client.operation.duration` (com `error.type` em falhas).
- **Métricas HTTP:** `http.server.request.duration` por rota e status.
- **Logs:** "Resposta gerada" e falhas do modelo, correlacionados ao trace. Logs de bibliotecas também são enviados.

O Phoenix recebe só os spans de IA: o Collector filtra o resto e trata `maria.chat` como raiz, para montar as sessões. O Tempo recebe o trace completo, sem alterações.

### Como investigar uma resposta

1. **Phoenix → Sessions:** abra a conversa e veja cada pergunta, a resposta e as mensagens exatas enviadas ao modelo.
2. **Grafana → dashboard "Maria · API e IA":** volume, latência, tokens e falhas. A tabela de traces abre o trace no Tempo.
3. **No trace do Tempo:** "Related logs" leva aos logs do mesmo `trace_id` no Loki.

> **LGPD:** as mensagens podem conter dados pessoais. Use `OPENINFERENCE_HIDE_INPUTS/OUTPUTS=true` para manter só a estrutura, o modelo, os tokens e a latência. A stack é local ou self-hosted, então os dados não saem da sua infraestrutura.

---

## 🎬 Demo

Acesse `/demo/` com a API rodando. A página consome os endpoints reais:

- **Chat:** digite e envie logo ao abrir (a conversa é criada automaticamente). A resposta aparece enquanto é gerada, renderizada em Markdown. Também dá para renomear e excluir conversas, e o título é gerado automaticamente.
- **Contrato de blocos:** uma resposta de exemplo com `text`, `chart` (Chart.js) e `table`, mais um tipo desconhecido ignorado, ao lado do JSON.

Para desligar a demo, use `DEMO_ENABLED=false`. Ela carrega Chart.js, marked e DOMPurify de CDN.

---

## 🧪 Testes e qualidade

| Comando | Descrição |
|---|---|
| `task run` | Servidor de desenvolvimento com reload |
| `task test` | Lint + testes com cobertura (gera `htmlcov/`) |
| `task lint` | Ruff (estilo e boas práticas) |
| `task format` | Corrige e formata o código |

- **Assíncronos:** `pytest-asyncio` e `httpx.AsyncClient` com `ASGITransport`, sobre SQLite em memória recriado a cada teste.
- **Sem chamadas a LLMs reais:** o `ModelRegistry` é substituído por fakes do LangChain:
  - `GenericFakeChatModel`;
  - `UsageReportingFakeChatModel`, que informa o uso de tokens no stream, como a OpenAI;
  - `FailingChatModel`, que simula a falha do provedor.

  Um callback de gravação confere as mensagens enviadas ao modelo.
- **Telemetria em memória:** a suíte roda com `OTEL_SDK_DISABLED=true`, e os testes de observabilidade usam `InMemorySpanExporter`, `InMemoryMetricReader` e `InMemoryLogRecordExporter`.

---

## 📐 Desenvolvimento com OpenSpec

Toda mudança segue o fluxo do [OpenSpec](https://github.com/Fission-AI/OpenSpec):

1. **Propor:** `/opsx:propose` cria `openspec/changes/<nome>/` com `proposal.md`, specs delta, `design.md` e `tasks.md`.
2. **Aplicar:** `/opsx:apply` implementa as tarefas, com testes em cada grupo.
3. **Arquivar:** `/opsx:archive` sincroniza as specs principais e move a mudança para `openspec/changes/archive/`.

Especificações atuais do sistema, em `openspec/specs/`:

| Capacidade | Cobre |
|---|---|
| `conversation-management` | Ciclo de vida das conversas |
| `conversation-messaging` | Envio (completo e streaming), contexto, falhas, título e histórico |
| `llm-model-tiers` | Níveis internos de modelo e configuração |
| `demo-page` | Página de demonstração |
| `observability` | Traces, métricas, logs e stack |

---

## 📌 Restrições conhecidas

- **Python < 3.15:** o `openinference-instrumentation-langchain` ainda não declara suporte a versões mais novas.
- **SQLAlchemy < 2.1:** a instrumentação oficial do OpenTelemetry para SQLAlchemy ainda não suporta a 2.1.
- **Grafana 13.2:** abrir os logs em tela dividida estreita pode disparar um erro visual do próprio Grafana (React #185). A consulta funciona normalmente.
