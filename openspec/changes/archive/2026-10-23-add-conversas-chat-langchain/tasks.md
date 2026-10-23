# Tasks

## 1. Dependências e configuração

- [x] 1.1 Adicionar `langchain`, `langchain-openai`, `aiosqlite` e `alembic` às dependências e `pytest-asyncio` ao grupo dev; verificar com `poetry install` sem erros
- [x] 1.2 Configurar pytest (`asyncio_mode = auto`) no `pyproject.toml`; verificar que `pytest --collect-only` funciona

## 2. Banco assíncrono

- [x] 2.1 Migrar `database.py` para `create_async_engine` + `async_sessionmaker` com `get_session` assíncrono, e `/health` para rota async; atualizar `DATABASE_URL` padrão e `.env.example`
- [x] 2.2 Reescrever `tests/conftest.py` (engine aiosqlite em memória, `AsyncClient` com `ASGITransport`) e `tests/test_db.py`/`tests/test_app.py` para async; verificar com `task test`
- [x] 2.3 Criar `models.py` (`Conversation`, `Message` com cascade) no estilo `mapped_as_dataclass`; verificar com teste de criação e exclusão em cascata
- [x] 2.4 Configurar Alembic com template async lendo `Settings` e gerar a migração inicial; verificar com `alembic upgrade head` em um SQLite temporário

## 3. Registro de modelos (LLM)

- [x] 3.1 Criar `llm/registry.py` com `ModelTier`, `ModelRegistry`, `build_model_registry` (via `init_chat_model`) e a dependência `get_model_registry`; adicionar `LLM_*` ao `Settings` e ao `.env.example`; verificar com teste unitário do builder usando um fake
- [x] 3.2 Criar `routers/models.py` com `GET /models`; verificar com teste usando o registro fake

## 4. Gestão de conversas

- [x] 4.1 Criar schemas de conversa (`ConversationCreate`, `ConversationUpdate`, `ConversationPublic`, `ConversationList`)
- [x] 4.2 Implementar `routers/conversations.py` com criar, listar paginado, detalhar, renomear e excluir; verificar com testes de cada cenário da spec `conversation-management`

## 5. Mensagens e chat

- [x] 5.1 Criar schemas de blocos (`TextBlock`, `ChartBlock`, `TableBlock` discriminados por `type`), `MessageCreate`, `MessagePublic`, `MessageList` e `ChatExchange`; verificar que aparecem no `/openapi.json`
- [x] 5.2 Criar `llm/prompts.py` com o prompt de sistema da Maria e `services/chat.py` com `ChatService` (montagem do contexto, chamada ao modelo, persistência atômica, título automático)
- [x] 5.3 Adicionar `GET` e `POST /conversations/{id}/messages`, convertendo falhas do modelo em 502; verificar com testes de cada cenário da spec `conversation-messaging` usando `GenericFakeChatModel` e o callback de gravação

## 6. Documentação e verificação final

- [x] 6.1 Atualizar o README (estrutura, variáveis, Alembic, endpoints e contrato de blocos)
- [x] 6.2 Rodar `task lint` e `task test` sem falhas e validar o fluxo real subindo a API com `task run` e acessando `/docs`

## Workflow follow-up

- Arquivar a mudança com `/opsx:archive` após revisão.
