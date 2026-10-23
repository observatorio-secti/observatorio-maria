# Proposal

## Why

A API do Observatório Maria hoje expõe apenas um healthcheck. O primeiro entregável da Maria é permitir que o usuário mantenha conversas persistentes com um modelo de linguagem. Por decisão da gestão, a orquestração do LLM usa LangChain. A base precisa nascer assíncrona, independente de provedor e com um contrato de resposta que suporte gráficos e tabelas no futuro sem quebrar o frontend.

## What Changes

- **BREAKING** Migração da camada de banco para SQLAlchemy assíncrono (`AsyncSession`, drivers `aiosqlite`/`psycopg` async). O formato de `DATABASE_URL` passa a exigir driver assíncrono (ex.: `sqlite+aiosqlite:///./observatorio.db`).
- Suíte de testes migrada para `pytest-asyncio` + `httpx.AsyncClient` com banco SQLite em memória.
- Adoção do Alembic (template async) para versionar o esquema, com migração inicial das tabelas `conversations` e `messages`.
- Novos endpoints de gestão de conversas: criar, listar (paginado), detalhar, renomear (editar título) e excluir.
- Novos endpoints de mensagens: listar o histórico de uma conversa e enviar uma mensagem, recebendo a resposta do modelo.
- Registro de modelos com três níveis simultâneos (`fast`, `medium`, `advanced`), escolhidos por mensagem. Cada nível é configurado por variável de ambiente no formato `provedor:modelo` (via `init_chat_model` do LangChain) e injetado nas rotas por `Depends`. Inicialmente os três apontam para `openai:gpt-6-luna` com raciocínio reduzido (`reasoning_effort=low`).
- Endpoint `GET /models` lista os níveis disponíveis para o frontend.
- Contrato de mensagem baseado em **blocos tipados** (`text`, `chart`, `table`), discriminados pelo campo `type`. Neste entregável o modelo produz apenas blocos `text`; os schemas `chart` e `table` já fazem parte do contrato público.
- Testes do fluxo de chat usam os fake chat models do LangChain (`GenericFakeChatModel`), sem chamadas de rede.

Fora de escopo: streaming (SSE), ferramentas/consultas a bancos externos, geração efetiva de gráficos pelo modelo, autenticação e geração de títulos por IA.

## Capabilities

### New Capabilities
- `conversation-management`: ciclo de vida das conversas (criação, listagem, detalhe, renomeação e exclusão).
- `conversation-messaging`: envio de mensagens a uma conversa, obtenção da resposta do modelo, histórico e contrato de blocos de conteúdo.
- `llm-model-tiers`: catálogo de modelos por nível (rápido, médio, avançado), configuração independente de provedor e exposição dos níveis disponíveis.

### Modified Capabilities
<!-- Nenhuma: ainda não há specs no projeto. -->

## Impact

- Código: `database.py`, `settings.py`, `app.py`, `routers/health.py` (async); novos `models.py`, `routers/conversations.py`, `routers/models.py`, `services/chat.py`, `llm/`.
- Testes: reescrita de `tests/conftest.py` e `tests/test_db.py`; novos testes de conversas, mensagens e modelos.
- Dependências: `langchain`, `langchain-openai`, `aiosqlite`, `alembic`, `pytest-asyncio`.
- Configuração: novas variáveis `LLM_*_MODEL`, `LLM_*_MODEL_KWARGS` e `OPENAI_API_KEY` no `.env.example`. A `DATABASE_URL` muda de formato.
- API: novos endpoints `/conversations`, `/conversations/{id}/messages` e `/models`.
