# Observatório Maria - API FastAPI

API da **Maria**, agente de IA do Observatório Maria voltado à pesquisa na Bahia. A aplicação segue as boas práticas do curso **FastAPI do Zero** (Dunossauro): é assíncrona, modular e independente do provedor de LLM.

---

## 🚀 Tecnologias Utilizadas

- **[Python](https://www.python.org/)** >= 3.12
- **[FastAPI](https://fastapi.tiangolo.com/)**: framework web assíncrono.
- **[LangChain](https://python.langchain.com/)**: orquestração dos modelos de linguagem (`init_chat_model`, independente de provedor).
- **[Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)**: configurações e variáveis de ambiente.
- **[SQLAlchemy 2.0 (async)](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)**: acesso assíncrono ao banco via `AsyncSession` (`get_session`).
- **[Alembic](https://alembic.sqlalchemy.org/)**: versionamento do esquema do banco (template async).
- **[Pytest](https://docs.pytest.org/) + [pytest-asyncio](https://pytest-asyncio.readthedocs.io/) & [Coverage](https://coverage.readthedocs.io/)**: testes assíncronos com cobertura.
- **[Ruff](https://docs.astral.sh/ruff/)**: linter e formatador.
- **[Taskipy](https://github.com/illBeRoy/taskipy)**: atalhos de tarefas.

---

## 📁 Estrutura de Diretórios

```text
.
├── pyproject.toml
├── alembic.ini                 # Configuração do Alembic (URL vem do Settings)
├── migrations/                 # Migrações do banco (Alembic async)
├── openspec/                   # Planejamento (propostas, specs, design e tasks)
├── src/
│   └── observatorio_maria/
│       ├── app.py              # Instância do FastAPI, routers e handlers de erro
│       ├── database.py         # Engine async e gerador de sessões (get_session)
│       ├── settings.py         # Configurações (banco e modelos por nível)
│       ├── models.py           # Tabelas: Conversation e Message
│       ├── schemas.py          # Schemas Pydantic (conversas, mensagens, blocos)
│       ├── llm/
│       │   ├── registry.py     # ModelTier, ModelRegistry e get_model_registry
│       │   └── prompts.py      # Prompt de sistema da Maria
│       ├── services/
│       │   └── chat.py         # ChatService: contexto, chamada ao modelo e persistência
│       └── routers/
│           ├── health.py       # /health
│           ├── conversations.py# /conversations e /conversations/{id}/messages
│           └── models.py       # /models
└── tests/
    ├── conftest.py             # Banco em memória, AsyncClient e modelos fake do LangChain
    ├── test_app.py
    ├── test_db.py
    ├── test_conversations.py
    ├── test_messages.py
    └── test_models.py
```

As rotas são finas e delegam ao `ChatService`. O serviço depende apenas de `AsyncSession` e do `ModelRegistry`, ambos injetados via `Depends`, e conhece só a interface `BaseChatModel` do LangChain, nunca um provedor específico.

---

## ⚙️ Configuração do Ambiente

### 1. Dependências

```bash
poetry install
```

### 2. Variáveis de ambiente

```bash
cp .env.example .env
```

| Variável | Descrição | Padrão |
|---|---|---|
| `DATABASE_URL` | URL com **driver assíncrono** | `sqlite+aiosqlite:///./observatorio.db` |
| `OPENAI_API_KEY` | Credencial lida pelo SDK da OpenAI | — |
| `LLM_FAST_MODEL` / `LLM_MEDIUM_MODEL` / `LLM_ADVANCED_MODEL` | Modelo de cada nível, no formato `provedor:modelo` | `openai:gpt-6-luna` |
| `LLM_*_MODEL_KWARGS` | Parâmetros extras do modelo, em JSON | `{"reasoning_effort": "low"}` |

Para PostgreSQL use `postgresql+psycopg://usuario:senha@localhost:5432/observatorio`.

Para trocar o modelo ou o provedor de um nível, basta mudar a variável e reiniciar. Por exemplo, `LLM_ADVANCED_MODEL="anthropic:<modelo>"`, instalando o pacote do provedor (`langchain-anthropic`).

### 3. Banco de dados

```bash
alembic upgrade head
```

Após alterar `models.py`, gere uma nova migração:

```bash
alembic revision --autogenerate -m "descrição"
```

---

## 🌐 Endpoints

| Método | Rota | Descrição |
|---|---|---|
| GET | `/health` | Verifica a API e o banco |
| GET | `/models` | Lista os níveis de modelo (`fast`, `medium`, `advanced`) |
| POST | `/conversations` | Cria uma conversa (`title` opcional) |
| GET | `/conversations?offset=0&limit=20` | Lista conversas, da atualizada mais recentemente para a mais antiga |
| GET | `/conversations/{id}` | Detalha uma conversa |
| PATCH | `/conversations/{id}` | Renomeia uma conversa |
| DELETE | `/conversations/{id}` | Exclui a conversa e suas mensagens |
| GET | `/conversations/{id}/messages` | Histórico em ordem cronológica |
| POST | `/conversations/{id}/messages` | Envia `{"content": "...", "model": "medium"}` e retorna `{user_message, assistant_message}` |

Erros relacionados ao LLM:
- `502`: o modelo falhou; nada é gravado na conversa.
- `503`: os modelos não puderam ser configurados, por exemplo por falta de credencial.

A documentação interativa fica em `/docs`.

### Contrato de conteúdo (blocos tipados)

O `content` de toda mensagem é uma **lista de blocos** discriminados por `type`. O frontend renderiza cada bloco conforme o tipo e **deve ignorar tipos desconhecidos**. Assim, novos tipos podem surgir sem quebrar clientes antigos.

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

Hoje a Maria produz apenas blocos `text`. Os blocos `chart` e `table` já fazem parte do contrato (veja o OpenAPI), então o frontend pode ser preparado desde já.

---

## 🛠️ Comandos Automatizados (Taskipy)

| Comando | Descrição | Comando subjacente |
|---|---|---|
| `task run` | Servidor de desenvolvimento com reload | `fastapi dev src/observatorio_maria/app.py` |
| `task test` | Lint + testes com cobertura | `pytest -s -x --cov=observatorio_maria -vv` |
| `task lint` | Verifica estilo e boas práticas | `ruff check . && ruff check . --diff` |
| `task format` | Corrige e formata o código | `ruff check . --fix && ruff format .` |

---

## 🧪 Testes Automatizados

- **Assíncronos**: `pytest-asyncio` (`asyncio_mode = auto`) e `httpx.AsyncClient` com `ASGITransport`.
- **Banco isolado em memória**: `sqlite+aiosqlite:///:memory:` com `StaticPool`, recriado a cada teste.
- **Sem chamadas a LLMs reais**: o `ModelRegistry` é substituído via `app.dependency_overrides` por `GenericFakeChatModel` do LangChain. Um callback de gravação (`RecordingHandler`) captura as mensagens enviadas ao modelo, e o `FailingChatModel` simula falhas do provedor.

```bash
task test
```
