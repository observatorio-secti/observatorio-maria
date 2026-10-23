# Observatório Maria - API FastAPI

Estrutura inicial de uma aplicação FastAPI baseada nas boas práticas do curso **FastAPI do Zero** (Dunossauro), configurada como um **Mínimo Produto Viável (MVP)** profissional e modular, pronta para expansão.

---

## 🚀 Tecnologias Utilizadas

- **[Python](https://www.python.org/)** >= 3.12
- **[FastAPI](https://fastapi.tiangolo.com/)**: Framework web assíncrono e de alta performance.
- **[Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)**: Gerenciamento robusto de configurações e variáveis de ambiente.
- **[SQLAlchemy 2.0](https://www.sqlalchemy.org/)**: Conexão com banco de dados e injeção de dependência via sessões (`get_session`).
- **[Pytest](https://docs.pytest.org/) & [Coverage](https://coverage.readthedocs.io/)**: Testes automatizados com fixtures e cobertura de código.
- **[Ruff](https://docs.astral.sh/ruff/)**: Linter e formatador de código ultrarrápido configurado no estilo da aula 01/13.
- **[Taskipy](https://github.com/illBeRoy/taskipy)**: Automação de tarefas de desenvolvimento (CLI shortcuts).

---

## 📁 Estrutura de Diretórios

O projeto adota o **`src-layout`**, que isola o pacote da raiz do projeto, prevenindo importações acidentais e garantindo que os testes usem a versão instalada/empacotada:

```text
.
├── pyproject.toml              # Configuração do projeto, dependências, ruff, pytest e taskipy
├── README.md                   # Documentação da aplicação
├── .env                        # Variáveis de ambiente locais
├── .env.example                # Exemplo das variáveis de ambiente necessárias
├── .gitignore                  # Arquivos e diretórios ignorados pelo Git
├── src/
│   └── observatorio_maria/     # Pacote principal da aplicação
│       ├── __init__.py         # Metadados do pacote (versão)
│       ├── app.py              # Instância do FastAPI e rotas raiz
│       ├── database.py         # Engine do SQLAlchemy e gerador de sessões (get_session)
│       ├── settings.py         # Configurações validadas pelo Pydantic Settings
│       ├── schemas.py          # Schemas Pydantic (Message, HealthCheck, etc.)
│       └── routers/            # Módulos de rotas da aplicação
│           ├── __init__.py
│           └── health.py       # Endpoint de verificação de integridade e banco de dados
└── tests/                      # Suíte de testes automatizados com pytest
    ├── __init__.py
    ├── conftest.py             # Fixtures globais (client, session em memória)
    ├── test_app.py             # Testes das rotas da aplicação
    └── test_db.py              # Testes de conexão e integridade do banco de dados
```

---

## ⚙️ Configuração do Ambiente com Poetry

O gerenciamento de dependências e ambientes virtuais é padronizado com o **Poetry**.

### 1. Instalação das Dependências

Para instalar as dependências de produção e desenvolvimento no ambiente virtual local:

```bash
# Configura o Poetry para criar o .venv dentro da pasta do projeto (caso ainda não esteja configurado)
poetry config virtualenvs.in-project true --local

# Instala todas as dependências e o pacote em modo editável
poetry install
```

### 2. Ativação do Ambiente Virtual (Opcional)

Você pode ativar a virtualenv ou executar comandos prefixando com `poetry run`:

```bash
# Entrar no shell do ambiente virtual
poetry shell
# ou:
source .venv/bin/activate
```

### 3. Configurar Variáveis de Ambiente

Copie o `.env.example` para `.env`:
```bash
cp .env.example .env
```

Por padrão, a aplicação utiliza SQLite local:
`DATABASE_URL="sqlite:///./observatorio.db"`

Caso queira usar PostgreSQL, basta alterar no `.env`:
`DATABASE_URL="postgresql+psycopg://usuario:senha@localhost:5432/observatorio"`

---

## 🛠️ Comandos Automatizados (Taskipy)

Graças ao Taskipy configurado no `pyproject.toml`, você pode executar tarefas rotineiras com comandos simplificados:

| Comando | Descrição | Comando subjacente |
|---|---|---|
| `task run` | Inicia o servidor de desenvolvimento com reload | `fastapi dev src/observatorio_maria/app.py` |
| `task test` | Executa a suíte de testes com cobertura | `pytest -s -x --cov=observatorio_maria -vv` |
| `task lint` | Verifica a formatação e boas práticas | `ruff check . && ruff check . --diff` |
| `task format` | Corrige e formata o código automaticamente | `ruff check . --fix && ruff format .` |
| `task post_test`| Gera relatório HTML de cobertura de código | `coverage html` |

> *Nota: Você também pode rodar diretamente com `poetry run task test` ou através do ambiente virtual ativo.*

---

## 🧪 Testes Automatizados

O setup de testes conta com:
- **Banco de dados isolado em memória** (`sqlite:///:memory:` via `StaticPool`), garantindo que nenhum teste afete o banco real.
- **Injeção de dependência mockada** no `conftest.py` com `app.dependency_overrides[get_session]`.
- **TestClient** do FastAPI com suporte a endpoints síncronos e assíncronos.

Para rodar os testes:
```bash
pytest
```
