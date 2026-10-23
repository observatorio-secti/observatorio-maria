# Design

## Context

Hoje a aplicação tem FastAPI, Pydantic Settings e SQLAlchemy 2 em modo síncrono (`create_engine` + `Session`). Só existe `/health`, e os testes usam `TestClient` com SQLite em memória. O projeto segue o estilo do curso "FastAPI do Zero": src-layout, Ruff com linha de 79 colunas e aspas simples, e Taskipy. A motivação está em `proposal.md`, e os requisitos em `specs/`.

Restrições: LangChain por exigência da gestão; OpenAI no começo, sem acoplamento ao provedor; testes sem rede usando os fakes do LangChain.

## Goals / Non-Goals

**Goals:**
- Camadas finas: rotas (HTTP) → serviço (regra de negócio) → LLM e banco, todos injetados via `Depends`.
- Trocar de modelo ou de provedor apenas por configuração.
- Persistir mensagens num formato (blocos JSON) que suporte gráficos e tabelas sem migração de esquema.

**Non-Goals:**
- Agentes com ferramentas, streaming, autenticação e multiusuário (o desenho só não pode impedi-los).
- Lógica de fallback entre níveis ou retentativas automáticas.

## Decisions

### 1. SQLAlchemy assíncrono + Alembic
- `create_async_engine` + `async_sessionmaker(expire_on_commit=False)`, com `get_session` como gerador assíncrono. Drivers: `sqlite+aiosqlite` (dev/testes) e `postgresql+psycopg` (o psycopg 3 já é assíncrono, então não é preciso trocar para asyncpg).
- Modelos no estilo `registry().mapped_as_dataclass`, o padrão do curso que o projeto segue.
- Alembic com o template `async`; `env.py` lê `DATABASE_URL` de `Settings` e usa `table_registry.metadata`.
- *Alternativa:* `Base.metadata.create_all` no startup. Foi descartada porque não versiona o esquema e já teríamos que migrar no segundo entregável.

### 2. Modelo de dados
- `conversations`: `id` (UUID), `title` (nullable, até 200), `created_at`, `updated_at`.
- `messages`: `id` (UUID), `conversation_id` (FK com `ON DELETE CASCADE` e cascade no ORM), `role` (`user`/`assistant`), `content` (JSON com a lista de blocos), `model_tier` e `model_name` (nullable, só no assistente), `created_at`.
- UUID em vez de inteiro, para não expor ids sequenciais numa API que ainda não tem autenticação.
- Enviar uma mensagem atualiza `conversations.updated_at`, o que mantém a listagem por recência correta.

### 3. Contrato de blocos (pensado para gráficos)
A resposta da IA não é uma string, e sim `content: list[Block]`, uma união discriminada do Pydantic pelo campo `type`:

```json
{"type": "text",  "text": "Markdown..."}
{"type": "chart", "chart_type": "bar|line|area|pie|scatter", "title": "...",
 "x": {"key": "ano", "label": "Ano", "type": "category|number|date"},
 "series": [{"key": "bolsas", "label": "Bolsas", "unit": "un"}],
 "data": [{"ano": 2023, "bolsas": 120}, {"ano": 2024, "bolsas": 150}]}
{"type": "table", "title": "...", "columns": [{"key": "...", "label": "...", "type": "string|number|date"}],
 "rows": [{"...": "..."}]}
```

- `data` em formato "longo por registro" (lista de objetos), com `x.key` e `series[].key` apontando para as chaves. É o formato que Recharts, ECharts, Chart.js e Vega-Lite consomem diretamente: o frontend só mapeia, não transforma.
- O frontend renderiza por `type` e MUST ignorar tipos desconhecidos. Assim, novos blocos (`metric`, `map`, `sources`…) entram sem quebrar clientes antigos.
- Os blocos ficam em uma coluna JSON, então um novo tipo de bloco não exige migração.
- Neste entregável só o bloco `text` é produzido. No futuro, gráficos virão de ferramentas do agente (por exemplo, `gerar_grafico(spec)`), cujo resultado vira um bloco `chart` anexado à resposta. Isso evita depender de o modelo escrever JSON válido em texto livre.
- *Alternativa:* string Markdown com JSON embutido. Descartada porque é frágil de parsear e não tem validação.

### 4. Registro de modelos por nível
- `ModelTier(StrEnum)`: `fast`, `medium`, `advanced`.
- Configuração em `Settings`: `LLM_FAST_MODEL`, `LLM_MEDIUM_MODEL`, `LLM_ADVANCED_MODEL` (formato `provedor:modelo`, padrão `openai:gpt-6-luna`) e `LLM_*_MODEL_KWARGS` (JSON, padrão `{"reasoning_effort": "low"}`, ou seja, sem pensamento profundo).
- `build_model_registry(settings)` chama `langchain.chat_models.init_chat_model(model, **kwargs)` para cada nível e devolve um `ModelRegistry` (mapa `tier → BaseChatModel` + nome do modelo).
- A dependência `get_model_registry()` usa `lru_cache`: é construída uma vez, de forma preguiçosa, só quando uma rota precisa dela. Nos testes ela é substituída via `app.dependency_overrides`, então a OpenAI nunca é instanciada.
- As rotas e o serviço dependem só de `BaseChatModel` (a interface do LangChain). Nada importa `langchain_openai` diretamente; o pacote só é necessário em tempo de execução para o provedor `openai`.
- Credenciais: chaves seguem a convenção de cada provedor (`OPENAI_API_KEY`). Como o Pydantic Settings não exporta o `.env` para `os.environ`, o `app.py` chama `load_dotenv()` para que os SDKs as encontrem.
- *Alternativa:* instanciar `ChatOpenAI` direto. Descartada porque acoplaria o código ao provedor.

### 5. Serviço de chat
`ChatService(session, registry)`, injetado por `Depends`, executa `send_message(conversation, content, tier)`:
1. carrega o histórico e monta `[SystemMessage(prompt da Maria), *histórico, HumanMessage(nova)]`;
2. chama `await model.ainvoke(messages)`;
3. só em caso de sucesso grava a mensagem do usuário e a resposta, atualiza o título automático e o `updated_at`, e faz um único `commit`.

Em caso de exceção do modelo, nada é gravado e a rota converte o erro em 502. Blocos não textuais do histórico viram uma representação JSON compacta quando forem convertidos para o modelo (preparado para o futuro).

O prompt de sistema fica em `llm/prompts.py`, versionado no código.

### 6. Testes
- `pytest-asyncio` (`asyncio_mode = auto`) + `httpx.AsyncClient(transport=ASGITransport(app))`. Não usamos `TestClient` porque ele roda o app em outro event loop, o que é incompatível com a sessão async criada na fixture.
- O engine `sqlite+aiosqlite:///:memory:` com `StaticPool` e `create_all` roda por teste.
- A fixture `model_registry` monta os três níveis com `GenericFakeChatModel` do `langchain_core`. Um `BaseCallbackHandler` de gravação, passado em `callbacks=`, captura as mensagens enviadas ao modelo para validar o contexto. Um fake que lança exceção cobre o caso 502.

### 7. Endpoints

| Método | Rota | Resposta |
|---|---|---|
| POST | `/conversations` | 201 `ConversationPublic` |
| GET | `/conversations?offset&limit` | 200 `ConversationList` |
| GET | `/conversations/{id}` | 200 `ConversationPublic` |
| PATCH | `/conversations/{id}` | 200 `ConversationPublic` |
| DELETE | `/conversations/{id}` | 204 |
| GET | `/conversations/{id}/messages` | 200 `MessageList` |
| POST | `/conversations/{id}/messages` | 201 `ChatExchange {user_message, assistant_message}` |
| GET | `/models` | 200 `ModelList` |

`ChatExchange` devolve as duas mensagens para o frontend substituir a mensagem otimista pela versão persistida, com id e timestamp. Um futuro `POST .../messages/stream` (SSE) pode emitir os mesmos blocos como eventos sem mudar o modelo de dados.

## Risks / Trade-offs

- [O ID `gpt-6-luna` ou o valor `reasoning_effort=low` podem não ser aceitos pela API] → Ambos vêm do `.env` e se corrigem sem deploy de código. O erro aparece como 502 com mensagem clara.
- [SQLite e async têm concorrência limitada] → Aceitável em dev. Em produção, PostgreSQL via `postgresql+psycopg`.
- [O histórico longo cresce sem limite e encarece as chamadas] → Fora deste entregável. O serviço é o ponto único para adicionar truncamento ou resumo depois.
- [Chamadas ao LLM seguram a sessão do banco aberta durante a geração] → Aceitável com pool async. Revisitar quando houver streaming.
- [Quebra do `DATABASE_URL` síncrono existente] → `.env.example` e README atualizados. Em dev, `observatorio.db` está vazio.

## Migration Plan

1. Atualizar o `.env` para `DATABASE_URL="sqlite+aiosqlite:///./observatorio.db"` e definir `OPENAI_API_KEY`.
2. `poetry install`.
3. `alembic upgrade head`.
4. Rollback: `alembic downgrade base` e reverter o commit.
