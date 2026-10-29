# Observatório Maria · API

API da **Maria**, agente de IA do Observatório Maria voltado à pesquisa científica, tecnológica e de inovação na Bahia. A API gerencia conversas, gera respostas com modelos de linguagem via LangChain (inclusive em streaming), mantém o catálogo dos bancos de dados que a IA vai consultar e é observável de ponta a ponta com OpenTelemetry.

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
| **Catálogo de dados** | Descreve bancos externos para a IA: o que o modelo **enxerga**, como interpreta cada tabela e coluna e o que pode **consultar**. Seed via YAML, sincronização somente leitura com o schema real, exportação e prévia do contexto. Primeira fonte: o banco do módulo de fomento. |
| **Defasagem do schema** | Verificação periódica (e sob demanda) se a origem mudou desde a última sincronização, com o diff do que mudou, sincronização automática opcional e leitura dos valores de enum, apontando os que ainda não têm descrição. |
| **Segurança e Privacidade** | Quarentena semântica contra prompt injection indireto (`<untrusted_database_data>`), mascaramento preventivo de PII (CPF e e-mail via LGPD), limites de consulta (timeout, teto de linhas, consultas por chamada), limite de perguntas por conversa e teto opcional de tokens. |
| **Demo** | Página em `/demo/` para conversar com a Maria, visualizar o contrato de blocos e configurar o catálogo de dados. |

---

## 🧱 Stack

- **Python** 3.12–3.14, **FastAPI** (SSE nativo), **Pydantic Settings**.
- **LangChain** (`init_chat_model`, independente de provedor), começando com **OpenAI**.
- **SQLAlchemy 2.0 assíncrono** (`aiosqlite` em dev, `psycopg` para PostgreSQL) e **Alembic**. A introspecção dos bancos externos usa o `Inspector` do SQLAlchemy.
- **PyYAML** para o seed e a exportação do catálogo.
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

routers/catalog.py  ← configuração do catálogo de dados
   │
   ▼
catalog/            ← introspecção somente leitura → banco de origem (ex.: fomento)
                       seed/exportação YAML · prévia do contexto do modelo
```

- **As rotas são finas** e tudo é injetado via `Depends`: sessão do banco, registro de modelos, tracer e callbacks. Nos testes, cada peça é trocada por um fake.
- **O fluxo de geração é um só:** `ChatService.stream_message` gera os eventos, e o envio comum (`send_message`) consome esse mesmo fluxo.
- **O código depende apenas da interface `BaseChatModel` do LangChain**, então trocar de provedor é questão de configuração.

### Estrutura de diretórios

```text
.
├── pyproject.toml / poetry.lock     # Dependências, Ruff, Pytest e Taskipy
├── alembic.ini · migrations/        # Migrações do banco (Alembic async)
├── Dockerfile · compose.prod.yaml   # Imagem e deploy em produção
├── docs/deploy.md                   # Guia de deploy ao lado do fomento e do Simcc
├── catalog/                         # Seeds YAML do catálogo (um arquivo por fonte)
│   ├── fomento.yaml
│   └── simcc.yaml
├── evals/
│   ├── reference.yaml               # Perguntas de referência para `task eval`
│   └── results/                     # Relatórios JSON das avaliações (fora do git)
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
│   ├── models.py                    # Conversas, mensagens e tabelas do catálogo
│   ├── schemas.py                   # Schemas da API, blocos, eventos SSE e catálogo
│   ├── catalog/
│   │   ├── introspection.py         # Leitura somente leitura do schema de origem
│   │   ├── sync.py                  # Fusão do schema com o catálogo
│   │   ├── drift.py                 # Impressão digital, diff, verificação e ciclo periódico
│   │   ├── yaml_io.py               # Formato YAML, seed e exportação
│   │   ├── seed.py                  # Comando `task seed`
│   │   └── context.py               # Texto que o modelo recebe sobre uma fonte
│   ├── llm/
│   │   ├── registry.py              # ModelTier, ModelRegistry e get_model_registry
│   │   └── prompts.py               # Prompt de sistema da Maria
│   ├── services/chat.py             # ChatService (stream_message / send_message)
│   ├── evaluation/                  # Comando `task eval` (avaliação com modelo real)
│   │   ├── reference.py             # Formato e carregamento das perguntas de referência
│   │   ├── checks.py                # Critérios numbers, list e sources
│   │   ├── judge.py                 # Critério judge (modelo-juiz)
│   │   ├── runner.py                # Execução pelo ChatService numa cópia do banco
│   │   ├── verify.py                # Conferência das respostas esperadas (--check-expected)
│   │   └── report.py                # Relatório no terminal e em JSON
│   ├── routers/
│   │   ├── health.py                # /health
│   │   ├── conversations.py         # /conversations, mensagens e streaming
│   │   └── catalog.py               # /catalog: fontes, entidades, colunas e relacionamentos
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

Para carregar o catálogo das fontes, defina `FOMENTO_DATABASE_URL` e `SIMCC_DATABASE_URL` e rode o seed (veja [Catálogo de dados](#-catálogo-de-dados)):

```bash
task seed
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

## 🚢 Deploy em produção

A Maria sobe em um projeto Docker Compose próprio (`compose.prod.yaml`), ao lado do observatório de fomento e do Simcc, sem alterar os composes deles. Guarda conversas e catálogo num SQLite dentro de um volume Docker, sem servidor de banco próprio, só **lê** o banco do fomento e o banco de leitura do Simcc pelas redes Docker deles e expõe a API na porta `11309`.

```bash
docker compose -f compose.prod.yaml up -d --build
```

Antes de subir, crie os usuários somente leitura nos bancos do fomento e do Simcc e configure `FOMENTO_NETWORK`, `FOMENTO_DATABASE_URL` e `SIMCC_DATABASE_URL` (e `SIMCC_NETWORK`, se a rede do Simcc não for `simcc-network`). O passo a passo completo, com operação e cuidados, está em [docs/deploy.md](docs/deploy.md).

---

## ⚙️ Configuração

As variáveis são lidas do ambiente e do `.env` pelo `Settings` (pydantic-settings), e o ambiente tem prioridade. As variáveis do `.env` que não são campos do `Settings`, como as credenciais dos provedores (`OPENAI_API_KEY`), as URLs das fontes (`*_DATABASE_URL`) e as do OpenTelemetry, são exportadas para o ambiente na inicialização da API e do `task eval`, porque esses componentes leem o ambiente diretamente.

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
| `CATALOG_CHECK_INTERVAL_SECONDS` | Intervalo da verificação de defasagem do catálogo (também roda ao iniciar). `0` desliga | `3600` |
| `CATALOG_OBSERVED_VALUES_MAX` | Máximo de valores distintos para uma coluna de texto ter seus valores lidos da origem; acima disso é texto livre | `50` |
| `CATALOG_CONTEXT_VALUES_MAX` | Máximo de valores observados para uma coluna com listagem `auto` listá-los no contexto do modelo. Acima disso, os valores continuam guardados, mas não vão para o prompt | `20` |
| `QUERY_MAX_ROWS` | Limite máximo de linhas devolvidas por consulta | `100` |
| `QUERY_TIMEOUT_SECONDS` | Limite de tempo de execução por consulta na origem | `15` |
| `QUERY_MAX_PER_CALL` | Máximo de consultas SQL executadas por chamada do modelo | `4` |
| `QUERY_MAX_ESTIMATED_COST` | Custo estimado máximo de consulta via EXPLAIN no PostgreSQL (0 desliga) | `50000` |
| `MARIA_AGENT_MAX_MODEL_CALLS` | Orçamento máximo de chamadas ao modelo por resposta da Maria | `6` |
| `CONVERSATION_MAX_QUESTIONS` | Perguntas por conversa. Na seguinte, a API responde 429 e orienta a iniciar uma nova conversa. `0` desliga | `10` |
| `CONVERSATION_TOKEN_CEILING` | Teto opcional de tokens acumulados por conversa, como trava de custo. `0` desliga | `0` |
| `FOMENTO_DATABASE_URL` | URL do banco do fomento, com driver assíncrono (`postgresql+psycopg://…`). O nome da variável é definido por fonte no catálogo | — |
| `SIMCC_DATABASE_URL` | URL do banco de leitura do Simcc (`postgresql+psycopg://…/simcc`), usada pela fonte `simcc` | — |

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

Os endpoints do catálogo estão em [Catálogo de dados](#-catálogo-de-dados).

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

Hoje a Maria produz blocos `text`, `chart` e `table` a partir de consultas a fontes de dados ativas do catálogo.

### Streaming (Server-Sent Events)

`POST /conversations/{id}/messages/stream` emite os eventos nesta ordem:

| Evento | Dados | Quando |
|---|---|---|
| `message.user` | `MessagePublic` da pergunta | Logo no início |
| `activity` | `{"kind": "query", "source": "…", "description": "…"}` | Antes de cada consulta a uma fonte de dados |
| `content.delta` | Fragmento de texto (`type: "text", text: "…"`) ou bloco inteiro (`type: "chart"` / `"table"`, `block: {…}`) | Conforme texto é gerado ou blocos de dados são entregues |
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

## 🗂️ Catálogo de dados

O catálogo descreve os bancos de outros sistemas que a Maria vai consultar. Ele fica no banco da própria Maria, e os bancos de origem **nunca são alterados**: a sincronização abre uma conexão somente leitura e só lê o schema.

```text
catalog/fomento.yaml  ┐
catalog/simcc.yaml    │
catalog/concepts.yaml ┴─task seed────────┐
                                          ▼
bancos de origem ──sincronizar──▶  catálogo (banco da Maria)  ◀── API / demo
                   (só leitura)           │
                                          ▼
                                 prévia do contexto do modelo
```

Há duas fontes:

| Fonte | Banco | Conteúdo |
|---|---|---|
| `fomento` | Banco do módulo de fomento (`FOMENTO_DATABASE_URL`) | Bolsas, projetos, bolsistas, instituições, áreas e territórios |
| `simcc` | Banco de leitura do Simcc (`SIMCC_DATABASE_URL`) | Currículo Lattes: artigos, livros, capítulos, patentes, softwares, participação em eventos e projetos de pesquisa |

**Simcc.** As tabelas base do Simcc têm uma linha por pesquisador autor e servem para perguntas sobre pesquisadores. As views `mv_canonical_*` têm uma linha por produção, sem repetir coautores, e servem para totais. As instruções da fonte explicam isso ao modelo. Arrays, JSON, `tsvector` e campos internos do ETL do Simcc ficam ocultos. Nome, ORCID e resumo do currículo têm acesso `full`, por decisão do projeto: a Maria pode citar pesquisadores, inclusive ao relacionar com bolsistas do fomento. Para mudar isso, passe as colunas para `aggregate` ou oculte-as pela API ou pela demo. Um pesquisador pode ter várias instituições, ligadas por `researcher_institution`; o antigo `researcher.institution_id` fica fora do contexto, e as instruções orientam `COUNT(DISTINCT ...)` ao contar pesquisadores por instituição.

**Fomento × Simcc.** `pesquisadores.lattes` (fomento) e `researcher.lattes_id` (Simcc) são o mesmo identificador, mas cada consulta acessa uma só fonte. As instruções orientam o modelo a consultar uma fonte e filtrar a outra com até 100 Lattes por vez (o teto de linhas de `QUERY_MAX_ROWS`), informando quantos foram encontrados. Agregações sobre grupos maiores ainda não são possíveis. Se `QUERY_MAX_ROWS` mudar, ajuste o número nas instruções do `catalog/simcc.yaml` ou pela API.

**Conceitos em várias fontes.** O mesmo nome aparece nas duas fontes com significados diferentes: projetos com bolsa (fomento) e projetos do currículo Lattes (Simcc); instituições das bolsas e afiliações dos pesquisadores; bolsistas e pesquisadores com currículo. Um **conceito** reúne as entidades de cada fonte e guarda a **política de resposta**: o que o conceito é em cada fonte, qual responde pelo sentido da pergunta e, sem sentido definido, qual é a padrão, dizendo a origem do número e mencionando a outra fonte numa frase, nunca somando as duas. O prompt recebe a seção "Conceitos em várias fontes" antes das fontes, só com conceitos que têm entidades visíveis em pelo menos duas fontes incluídas, e cada entidade vinculada indica o conceito no contexto da sua fonte. Conceitos são dado editorial: a sincronização nunca os altera, e excluir um conceito só desvincula as entidades. `catalog/concepts.yaml` traz `projetos`, `instituicoes` e `pesquisadores`, com as entidades no formato `fonte:schema.entidade`.

| Nível | Configuração |
|---|---|
| **Fonte** | Nome, descrição, **instruções de negócio** para a IA, variável de ambiente com a conexão (nunca a URL), schemas a ler e liga/desliga |
| **Entidade** (tabela, view ou view materializada) | Rótulo, descrição, sinônimos, **visível** (o modelo enxerga) e **consultável** (o modelo pode consultar). Consultável exige visível |
| **Coluna** | Rótulo, descrição, sinônimos, valores conhecidos com significado, **visível**, **pesquisável** (habilita busca textual via `MATCH_TEXT`), **listar valores** no contexto (`auto`, `always` ou `never`) e **acesso**: `full` (pode ler valores) ou `aggregate` (só filtrar, agrupar e contar; para dados pessoais) |
| **Relacionamento** | Liga/desliga e descrição. Vêm das chaves estrangeiras ou, quando não há chave (views), do YAML |
| **Conceito** | Identificador (slug, imutável), rótulo, descrição, sinônimos e política de resposta. Cada entidade aponta para no máximo um conceito |

**Dados técnicos e editoriais.** A sincronização só atualiza tipo, chaves, ordem e presença. Rótulos, descrições e interruptores vêm de pessoas e nunca são sobrescritos. O que é novo na origem entra **oculto**; o que sumiu fica **ausente**, com a configuração guardada, e volta se reaparecer.

**YAML é seed, não fonte de verdade.** `task seed` carrega `catalog/*.yaml` e cria apenas o que ainda não existe. Para recriar uma fonte a partir do arquivo, descartando as edições:

```bash
task seed -- --reset
```

O arquivo de conceitos é aplicado depois das fontes: cria só os conceitos que faltam e vincula só entidades sem conceito, avisando sobre entidades que não estão no catálogo. Com `--reset`, ele recria os conceitos do arquivo e seus vínculos. Recriar uma fonte com `--reset` apaga as entidades e, com elas, os vínculos; inclua `catalog/concepts.yaml` no mesmo seed (o `task seed` já inclui) para vinculá-las de novo.

No YAML, entidades e colunas listadas ficam visíveis (e as entidades, consultáveis) por padrão. O que não é listado entra oculto na sincronização. `GET /catalog/datasources/{id}/export` devolve a configuração atual no mesmo formato, pronta para versionar.

**Defasagem do schema.** Cada sincronização guarda uma impressão digital da estrutura da origem: entidades, colunas, tipos, chaves e valores de enum. A ordem das colunas não entra, para não gerar alarme por reordenação. A API compara essa impressão com o schema atual ao iniciar, a cada `CATALOG_CHECK_INTERVAL_SECONDS` e sob demanda (`POST .../check`). A fonte fica com um destes estados:

| Estado | Significado |
|---|---|
| `up_to_date` | A origem não mudou desde a última sincronização |
| `outdated` | A origem mudou. `drift` lista o que a próxima sincronização aplicaria: entidades e colunas novas ou removidas, colunas alteradas, valores de enum novos ou removidos e relacionamentos |
| `error` | Não foi possível ler a origem (`check_error`) |
| `unknown` | Nunca verificada |

Com `auto_sync` ligado na fonte (API, YAML ou demo), uma defasagem é sincronizada na hora. É seguro: o que é novo entra oculto e o que sumiu fica ausente. O resumo vai para os logs. Fontes desativadas não são verificadas.

**Valores de enum.** A sincronização lê os valores dos tipos enum nativos (ex.: `bolsa_status`). O contexto do modelo lista os valores **atuais** da origem, com as descrições do catálogo. Cada coluna expõe `undescribed_values` (sem descrição, para revisar) e `obsolete_values` (descritos, mas que não existem mais, e que ficam fora do contexto). 
**Valores observados.** Colunas de texto sem enum têm os valores lidos dos próprios dados (`SELECT DISTINCT ... LIMIT`, somente leitura, com `QUERY_TIMEOUT_SECONDS` por coluna) na sincronização e em toda verificação, mesmo sem defasagem. Só são lidas colunas visíveis, presentes e com acesso `full`, de entidades visíveis, presentes e consultáveis. Colunas ocultas, `aggregate` ou de outros tipos nunca são lidas, e passar uma coluna para `aggregate` apaga os valores guardados. Com até `CATALOG_OBSERVED_VALUES_MAX` valores distintos (nulos não contam), a lista fica em `observed_values`; acima disso, a coluna é texto livre e o campo fica nulo. Esses valores funcionam como os de enum: o contexto do modelo lista os da origem, e valores do YAML que não existem nos dados viram `obsolete_values` e saem do contexto. Eles não entram na impressão digital, porque mudança de dados não é defasagem. Se a leitura de uma coluna falhar, ela mantém os valores anteriores.

**Valores no contexto.** Nem todo valor lido vai para o prompt. Cada coluna tem o campo editorial `list_values`: `always` (sempre lista), `never` (nunca lista) ou `auto` (padrão). Em `auto`, a coluna lista os valores quando tem enum, quando algum valor tem descrição editorial ou quando os valores observados parecem uma categoria: coluna não pesquisável, com até `CATALOG_CONTEXT_VALUES_MAX` valores (padrão 20) e valores de até 30 caracteres em média. ORCID, nomes, títulos, datas e indicadores numéricos guardados como texto ficam de fora, e os seeds os marcam como `never`. Os valores lidos continuam guardados e aparecem na demo para revisão. No prompt, o rótulo é só "Valores:"; a regra de usar os valores exatamente como estão fica uma vez nas regras da Maria, que também mandam conferir com `SELECT DISTINCT` antes de filtrar por valor exato uma coluna sem valores listados.

**Relacionamentos no contexto.** Cada relacionamento ligado aparece na linha da coluna de origem (`` - `researcher_id` (UUID): Pesquisador autor. → public.researcher.id ``), e só quando as duas entidades e as colunas das duas pontas estão visíveis.

**Exemplos few-shot.** Cada fonte pode ter exemplos de pergunta e SQL (`examples` no YAML ou na API), que entram no contexto do modelo. Antes disso, cada exemplo passa pelas mesmas regras de `query_data` (entidades, colunas e funções permitidas). Um exemplo que cita uma coluna inexistente ou oculta fica fora do contexto, e a prévia (`GET .../context`) o lista em `rejected_examples`, com o motivo.

**Fluxo para uma nova fonte:** escrever o YAML (ou criar a fonte pela API) → `task seed` → sincronizar → revisar na demo, olhando a aba "O que a Maria enxerga".

| Método | Rota | Descrição |
|---|---|---|
| GET | `/catalog/datasources` | Lista fontes com totais de entidades, visíveis e consultáveis |
| POST | `/catalog/datasources` | Cria uma fonte (`id` em slug; 409 se já existir) |
| GET · PATCH · DELETE | `/catalog/datasources/{id}` | Detalha, edita ou exclui a fonte (e todo o seu catálogo) |
| POST | `/catalog/datasources/{id}/sync` | Sincroniza com o schema da origem e devolve o resumo |
| POST | `/catalog/datasources/{id}/check` | Verifica a defasagem sem alterar o catálogo (ou sincroniza, com `auto_sync`) |
| GET | `/catalog/datasources/{id}/entities` | Lista as entidades |
| GET · PATCH | `/catalog/entities/{id}` | Detalha (com colunas) ou edita uma entidade, inclusive o conceito (`concept_id`; 422 se não existir) |
| PATCH | `/catalog/columns/{id}` | Edita uma coluna |
| GET | `/catalog/datasources/{id}/relationships` | Lista os relacionamentos |
| PATCH | `/catalog/relationships/{id}` | Liga, desliga ou descreve um relacionamento |
| GET | `/catalog/datasources/{id}/context` | Texto em Markdown que o modelo receberá sobre a fonte e os exemplos recusados |
| GET | `/catalog/datasources/{id}/export` | Configuração atual em YAML |
| GET | `/catalog/concepts` | Lista os conceitos com as entidades vinculadas |
| POST | `/catalog/concepts` | Cria um conceito (`id` em slug; 409 se já existir) |
| GET · PATCH · DELETE | `/catalog/concepts/{id}` | Detalha, edita ou exclui um conceito (as entidades ficam sem conceito) |
| GET | `/catalog/concepts/context` | Seção "Conceitos em várias fontes" que o modelo receberá |
| GET | `/catalog/concepts/export` | Conceitos e vínculos em YAML, no formato do seed |

Na sincronização, 422 indica a variável de conexão não definida e 502 indica origem inacessível ou URL inválida. Nos dois casos o catálogo não muda, e as mensagens de erro nunca repetem a URL.

> **Sem autenticação por enquanto:** qualquer cliente com acesso à API altera o catálogo. Não exponha estes endpoints fora do ambiente de desenvolvimento antes da autenticação.
>
> **Conexão com a origem:** em desenvolvimento, use o usuário que já existe no banco do fomento. A sessão é forçada a somente leitura (`default_transaction_read_only`). Em produção, prefira um usuário somente leitura criado pelos responsáveis por aquele banco.

---

## 🤖 Modelos de IA

- Os níveis `fast`, `medium` e `advanced` são **internos**: a aplicação decide qual usar, e hoje o chat usa `medium` (`CHAT_MODEL_TIER` em `services/chat.py`). O nível e o modelo de cada resposta ficam gravados no banco, para auditoria, mas não aparecem na API.
- Para trocar o modelo de um nível, altere a variável e reinicie. Para outro provedor, instale o pacote do LangChain correspondente e use o prefixo dele, por exemplo `LLM_ADVANCED_MODEL="anthropic:<modelo>"` com `langchain-anthropic`.
- O prompt de sistema da Maria fica em `src/observatorio_maria/llm/prompts.py`.

---

## 🛡️ Segurança e Privacidade

A Maria implementa múltiplas camadas de proteção para salvaguardar dados de cidadãos e manter a integridade operacional do agente:

1. **Quarentena Semântica de Dados Não Confiáveis:**
   - Todos os dados retornados de consultas a bancos externos são universalmente empacotados em delimitadores estruturados `<untrusted_database_data>`.
   - Delimitadores de fechamento contidos nos textos são escapados (`&lt;/untrusted_database_data&gt;`), neutralizando tentativas de fuga do bloco de quarentena.
   - O prompt de sistema define precedência estrita: o modelo é orientado a tratar os dados como meramente documentais e a ignorar qualquer tentativa de injeção de comandos (ex.: "ignore diretrizes anteriores", redefinição de papel ou chamadas falsas de ferramentas).

2. **Privacidade e LGPD:**
   - **Mascaramento leve de PII:** Padrões identificáveis de CPF e endereços de e-mail são mascarados preventivamente (`[CPF MASCARADO]`, `[E-MAIL MASCARADO]`) pelo `QueryRunner` antes de serem passados ao contexto do modelo. Os bancos de dados de origem permanecem intactos.
   - **Colunas com acesso agregado:** Colunas sensíveis (como CEPs e identificadores) podem ser configuradas no catálogo com acesso estrito a agregações (`aggregate`), impedindo a leitura direta de valores individuais.
   - **Ocultação em telemetria:** Parâmetros `OPENINFERENCE_HIDE_INPUTS` e `OPENINFERENCE_HIDE_OUTPUTS` permitem omitir textos em traces de observabilidade.

3. **Limites de Recursos e Proteção contra DoS:**
   - **Dry-run com EXPLAIN:** Antes da execução no PostgreSQL, um dry-run via `EXPLAIN (FORMAT JSON)` inspeciona o custo estimado (`Total Cost`). Se ultrapassar `QUERY_MAX_ESTIMATED_COST`, a consulta é barrada preventivamente sem tocar nos dados, devolvendo mensagem orientativa para a Maria refinar os filtros.
   - **Truncamento defensivo por célula:** Textos de células longas são limitados a 2.000 caracteres, prevenindo esgotamento intencional da janela de contexto (*Context Flooding*).
   - **Limites de execução:** Teto máximo de linhas por consulta (`QUERY_MAX_ROWS`), timeout de banco (`QUERY_TIMEOUT_SECONDS`), máximo de consultas SQL por chamada (`QUERY_MAX_PER_CALL`) e orçamento de chamadas ao modelo (`MARIA_AGENT_MAX_MODEL_CALLS`).
   - **Limite de perguntas por conversa:** Depois de `CONVERSATION_MAX_QUESTIONS` perguntas (padrão 10), a conversa recusa novas mensagens com HTTP 429 e orienta a iniciar outra. O limite não depende do tamanho do contexto das fontes, que com fomento e Simcc leva cada resposta a gastar de 27 a 50 mil tokens.
   - **Teto de tokens por conversa (opcional):** Com `CONVERSATION_TOKEN_CEILING` maior que zero, a conversa também é bloqueada ao atingir esse total de tokens, como trava de custo. Vem desligado por padrão; `total_tokens` continua sendo contado em toda conversa.

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
  - `messages`: `id`, `conversation_id`, `role`, `content` (JSON com os blocos), `model_tier`, `model_name` e `created_at`. Excluir a conversa apaga as mensagens em cascata;
  - `catalog_datasources`, `catalog_entities`, `catalog_columns` e `catalog_relationships`: o catálogo de dados. Excluir uma fonte apaga o catálogo dela em cascata.

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
- **Catálogo de dados:** escolha a fonte, sincronize, ligue e desligue entidades, colunas e relacionamentos, edite descrições e instruções, veja **o que a Maria enxerga** e baixe o YAML. A barra da fonte mostra o estado do schema, com "Verificar agora", o interruptor de sincronização automática e um quadro com as mudanças detectadas. Em cada coluna com valores conhecidos, "valores" abre a edição do significado de cada um, destacando os sem descrição e os obsoletos.

Para desligar a demo, use `DEMO_ENABLED=false`. Ela carrega Chart.js, marked e DOMPurify de CDN.

---

## 🧪 Testes e qualidade

| Comando | Descrição |
|---|---|
| `task run` | Servidor de desenvolvimento com reload |
| `task seed` | Carrega `catalog/*.yaml` no catálogo (`-- --reset` recria as fontes) |
| `task test` | Lint + testes com cobertura (gera `htmlcov/`) |
| `task lint` | Ruff (estilo e boas práticas) |
| `task format` | Corrige e formata o código |
| `task eval` | Avalia a Maria com o **modelo real** contra `evals/reference.yaml` (veja abaixo) |

- **Assíncronos:** `pytest-asyncio` e `httpx.AsyncClient` com `ASGITransport`, sobre SQLite em memória recriado a cada teste.
- **Sem chamadas a LLMs reais:** o `ModelRegistry` é substituído por fakes do LangChain:
  - `GenericFakeChatModel`;
  - `UsageReportingFakeChatModel`, que informa o uso de tokens no stream, como a OpenAI;
  - `FailingChatModel`, que simula a falha do provedor.

  Um callback de gravação confere as mensagens enviadas ao modelo.
- **Catálogo contra um banco real:** os testes sincronizam com um SQLite de origem em arquivo temporário (tabelas, view e chaves estrangeiras), inclusive tabelas e colunas que somem e voltam. Os testes de defasagem alteram essa origem e conferem que o diff bate com o relatório da sincronização seguinte. Os enums, que o SQLite não tem, são testados com snapshots montados à mão.
- **Telemetria em memória:** a suíte roda com `OTEL_SDK_DISABLED=true`, e os testes de observabilidade usam `InMemorySpanExporter`, `InMemoryMetricReader` e `InMemoryLogRecordExporter`.

### Avaliação com modelo real (`task eval`)

Os testes nunca chamam LLMs, então não medem se o modelo escolhe a fonte, a tabela e o filtro certos. O `task eval` mede isso: envia as perguntas de `evals/reference.yaml` à Maria, pelo mesmo `ChatService` da API, com os modelos e as fontes do `.env`, e confere cada resposta. Serve de linha de base antes e depois de mudanças no contexto enviado ao modelo.

```bash
poetry run task eval                                   # todas as perguntas, uma vez
poetry run task eval -- --tag entre-fontes --repeat 3  # um subconjunto, três vezes
poetry run task eval -- --question artigos-por-ano     # uma pergunta (repetível)
poetry run task eval -- --check-expected               # confere as respostas esperadas, sem modelo
```

Cada pergunta do arquivo tem `id`, `question`, `tags`, critérios (`checks`) e consultas de conferência (`verify`):

| Critério | Passa quando |
|---|---|
| `numbers` | todos os `values` aparecem no texto, nas tabelas ou nos gráficos da resposta (aceita "3.653" e "1.234,5") |
| `list` | a fração `min_ratio` (padrão 1) dos `items` aparece na resposta, sem diferença de maiúsculas, acentos e espaços |
| `sources` | as consultas sem erro incluem todas as fontes `required` e nenhuma `forbidden` |
| `judge` | o modelo do nível `advanced` julga que a resposta atende ao `criterion` (só para critérios textuais) |

- **Resultado:** a pergunta acerta só se todos os critérios passam. Falha do modelo conta como erro e não interrompe as demais. O terminal mostra acertos por pergunta, tokens, chamadas ao modelo, consultas e fontes; o JSON completo (modelos, respostas e SQL) vai para `evals/results/`, fora do git.
- **Banco da Maria intacto:** a avaliação roda numa cópia temporária do SQLite de `DATABASE_URL`, com o catálogo como está; nenhuma conversa de avaliação fica no banco nem na demo.
- **Conferência:** `--check-expected` executa as etapas `verify` pelo validador e pela conexão somente leitura do agente, sem modelo, e aponta as respostas esperadas que não batem mais com os dados (código de saída 1). O arquivo nunca é reescrito. Numa etapa, `{previous}` vira a lista de valores da primeira coluna da etapa anterior e `{previous_count}`, o número de linhas dela; a última etapa é comparada pela coluna `column` (ou por todas, nos números).
- **Tags:** cada pergunta tem a tag da categoria; `exemplo` marca as que repetem um exemplo few-shot do catálogo, e `issue-2` as de conceitos repetidos entre fontes, que falham até a política da issue #2 existir.
- **Custo:** cada pergunta gasta de 30 a 50 mil tokens com as duas fontes, mais o juiz. Não roda no `task test` nem na CI.

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
| `data-catalog` | Catálogo de fontes de dados, sincronização, defasagem do schema, valores de enum, seed/exportação YAML e prévia do contexto |
| `demo-page` | Página de demonstração |
| `observability` | Traces, métricas, logs e stack |

---

## 📌 Restrições conhecidas

- **Python < 3.15:** o `openinference-instrumentation-langchain` ainda não declara suporte a versões mais novas.
- **SQLAlchemy < 2.1:** a instrumentação oficial do OpenTelemetry para SQLAlchemy ainda não suporta a 2.1.
- **Grafana 13.2:** abrir os logs em tela dividida estreita pode disparar um erro visual do próprio Grafana (React #185). A consulta funciona normalmente.
