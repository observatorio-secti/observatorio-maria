# 🚢 Deploy em produção

A Maria roda no mesmo servidor do observatório de fomento sem alterar nada no compose dele. Ela sobe em um projeto Docker Compose próprio (`compose.prod.yaml`) e só **lê** o banco do fomento.

## Como fica

```text
┌──────────── projeto do fomento ─────────────┐   ┌──── projeto observatorio-maria ────┐
│                                             │   │                                    │
│  web ── api ── db (Postgres do fomento) ◄───┼───┼── maria-api ── volume maria_data   │
│                                             │   │       │        (SQLite da Maria)   │
└──────────── rede <fomento>_default ─────────┘   └───────┼────────────────────────────┘
                                                          ▼
                                                    host :11309
```

- **Projeto próprio** (`name: observatorio-maria`): containers e volumes não colidem com os do fomento.
- **Banco próprio sem servidor**: conversas e catálogo ficam num arquivo SQLite (`/app/data/maria.db`) no volume `maria_data`. Não há Postgres da Maria em produção.
- **Nome distinto** (`maria-api`): na rede do fomento, `db` continua resolvendo para o Postgres do fomento.
- **Acesso ao fomento**: a `maria-api` entra na rede do fomento como `external` e consulta o banco com um usuário somente leitura.
- **Porta**: a API fica em `11309` (configurável por `MARIA_API_PORT`).

Ao iniciar, o container aplica as migrações (`alembic upgrade head`) e sobe o uvicorn na porta 8000 interna.

## Arquivos

| Arquivo | Papel |
|---|---|
| `Dockerfile` | Imagem Python 3.13 com as dependências do `poetry.lock`, usuário sem privilégios de root |
| `.dockerignore` | Mantém `.env`, `*.db`, `.venv`, testes etc. fora da imagem |
| `compose.prod.yaml` | Serviço `maria-api`, volume `maria_data` com o SQLite e rede externa do fomento |

## Passo a passo

### 1. Descobrir a rede do fomento

O fomento precisa estar no ar. A rede costuma se chamar `<pasta-do-fomento>_default`:

```bash
docker network ls | grep default
```

### 2. Criar um usuário somente leitura no banco do fomento

A Maria já abre as conexões com o fomento em modo somente leitura (`default_transaction_read_only=on` e `SET TRANSACTION READ ONLY`). Um usuário que só tem `SELECT` protege mesmo se esse controle falhar.

Na pasta do fomento:

```bash
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

```sql
CREATE ROLE maria_leitura LOGIN PASSWORD 'troque-esta-senha';
GRANT CONNECT ON DATABASE <POSTGRES_DB> TO maria_leitura;
GRANT USAGE ON SCHEMA public TO maria_leitura;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO maria_leitura;
-- Tabelas criadas depois (migrações do fomento) também ficam legíveis:
ALTER DEFAULT PRIVILEGES FOR ROLE <POSTGRES_USER> IN SCHEMA public
  GRANT SELECT ON TABLES TO maria_leitura;
ALTER ROLE maria_leitura SET default_transaction_read_only = on;
```

Troque `<POSTGRES_DB>` e `<POSTGRES_USER>` pelos valores do `.env` do fomento.

### 3. Configurar o `.env` da Maria

```bash
cp .env.example .env
```

Além das variáveis da [Configuração](../README.md#️-configuração), o deploy usa:

| Variável | Descrição | Exemplo |
|---|---|---|
| `MARIA_API_PORT` | Porta da API no host | `11309` (padrão) |
| `FOMENTO_NETWORK` | Rede do compose do fomento (passo 1) | `observatorio-fomento_default` |
| `FOMENTO_DATABASE_URL` | Conexão do usuário somente leitura, pelo host `db` | `postgresql+psycopg://maria_leitura:<senha>@db:5432/<POSTGRES_DB>` |

Recomendado em produção:

```env
OTEL_SDK_DISABLED=true   # a menos que a stack de observabilidade esteja no ar
DEMO_ENABLED=false       # não expõe /demo/
```

O `DATABASE_URL` do `.env` é ignorado: o `compose.prod.yaml` o sobrescreve para apontar para o SQLite no volume (`sqlite+aiosqlite:////app/data/maria.db`).

### 4. Subir

```bash
docker compose -f compose.prod.yaml up -d --build
curl http://localhost:11309/health
# {"status":"ok","database":"connected"}
```

### 5. Carregar o catálogo do fomento

Só na primeira vez, ou com `--reset` para recriar a fonte a partir do YAML:

```bash
docker compose -f compose.prod.yaml exec maria-api \
  python -m observatorio_maria.catalog.seed catalog/fomento.yaml
```

Depois do seed, **sincronize** a fonte. O seed cria as entidades como ausentes (`present: false`), e só a sincronização, que lê o schema real do fomento, as marca como presentes. Sem esse passo, a Maria não recebe a ferramenta de consulta e responde que não tem acesso aos dados.

```bash
curl -X POST http://localhost:11309/catalog/datasources/fomento/sync
```

### 6. Liberar a porta

Libere a porta `11309` no firewall, ou aponte o proxy reverso para ela.

## Operação

| Ação | Comando |
|---|---|
| Atualizar após `git pull` | `docker compose -f compose.prod.yaml up -d --build` (migrações rodam sozinhas) |
| Logs | `docker compose -f compose.prod.yaml logs -f maria-api` |
| Parar | `docker compose -f compose.prod.yaml down` |
| Backup do banco da Maria | Ver abaixo |

Não use `down -v` sem querer apagar o banco: a opção remove o volume `maria_data`.

### Backup

O SQLite usa WAL, então copiar só o `maria.db` com a API no ar pode perder as últimas escritas. Use a API de backup do próprio SQLite, que gera uma cópia consistente sem parar a Maria:

```bash
docker compose -f compose.prod.yaml exec maria-api python -c \
  "import sqlite3; b = sqlite3.connect('/app/data/maria-backup.db'); sqlite3.connect('/app/data/maria.db').backup(b); b.execute('PRAGMA journal_mode=DELETE'); b.close()"
docker compose -f compose.prod.yaml cp maria-api:/app/data/maria-backup.db ./maria-backup.db
```

### Migração do Postgres para o SQLite

Versões anteriores deste compose subiam um Postgres próprio (`maria-db`). Os dados dele não são migrados: conversas antigas se perdem, e o catálogo é recriado pelo seed. Para trocar:

```bash
docker compose -f compose.prod.yaml up -d --build --remove-orphans
```

O `--remove-orphans` remove o container `maria-db`, que não está mais no compose. Depois, refaça o seed e a sincronização do passo 5. O volume antigo continua no servidor até ser apagado à mão, depois de conferir que a Maria está funcionando:

```bash
docker volume rm observatorio-maria_maria_postgres_data
```

## A Maria diz que não tem acesso aos dados

A ferramenta de consulta só é entregue ao modelo quando alguma fonte está ativa (`enabled`) e tem ao menos uma entidade visível, consultável e presente ao mesmo tempo. Verifique nesta ordem:

```bash
API=http://localhost:11309

# 1. A fonte existe, está ativa e qual o estado do schema?
curl -s $API/catalog/datasources/fomento | jq '{enabled, schema_status}'

# 2. Alguma entidade está visível, consultável e presente?
curl -s $API/catalog/datasources/fomento/entities \
  | jq '[.entities[] | select(.visible and .queryable and .present) | .name]'

# 3. O que o modelo recebe sobre a fonte
curl -s $API/catalog/datasources/fomento/context | jq -r .content
```

| Sintoma | Causa | Correção |
|---|---|---|
| Passo 1 dá 404 | Seed não rodou | Passo 5 do deploy |
| Passo 2 devolve `[]` | Fonte nunca sincronizada | `POST /catalog/datasources/fomento/sync` |
| Sync devolve 422 | `FOMENTO_DATABASE_URL` ausente no container | Conferir o `.env` e recriar com `up -d` |
| Sync devolve 502 | Banco do fomento inacessível: rede, host `db`, usuário, senha ou nome do banco | `docker compose -f compose.prod.yaml logs maria-api` e o passo 2 do deploy |
| `schema_status: error` | A verificação ao iniciar não conectou ao fomento | Mesma causa do 502 |

Depois de corrigir, teste em uma **conversa nova**: o histórico da conversa anterior, com a recusa, vai para o modelo e pode induzir a mesma resposta.

## Cuidados

- **Ordem de inicialização:** suba o fomento antes da Maria, porque a rede externa precisa existir. Se o fomento for derrubado com `down`, a rede é recriada e a Maria precisa de um novo `up -d`.
- **Porta 5432 do fomento:** o compose do fomento expõe o Postgres no host. A Maria não precisa disso, porque acessa o banco pela rede interna. Se nada mais usar essa porta, vale fechá-la no firewall.
- **Segredos:** o `.env` fica fora da imagem (`.dockerignore`) e do Git (`.gitignore`).
