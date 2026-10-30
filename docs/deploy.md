# 🚢 Deploy em produção

A Maria roda no mesmo servidor do observatório de fomento e do Simcc sem alterar nada nos composes deles. Ela sobe em um projeto Docker Compose próprio (`compose.prod.yaml`) e só **lê** o banco do fomento e o banco de leitura do Simcc.

## Como fica

```text
┌──────────── projeto do fomento ─────────────┐   ┌──── projeto observatorio-maria ────┐
│                                             │   │                                    │
│  web ── api ── db (Postgres do fomento) ◄───┼───┼── maria-api ── volume maria_data   │
│                                             │   │    │  │        (SQLite da Maria)   │
└──────────── rede <fomento>_default ─────────┘   └────┼──┼────────────────────────────┘
                                                       │  ▼
┌──────────── projeto simcc-etl ──────────────┐        │  host :11309
│                                             │        │
│  write_db ── etl ── read_db (leitura) ◄─────┼────────┘
│                                             │
└──────────── rede simcc-network ─────────────┘
```

- **Projeto próprio** (`name: observatorio-maria`): containers e volumes não colidem com os do fomento nem com os do Simcc.
- **Banco próprio sem servidor**: conversas e catálogo ficam num arquivo SQLite (`/app/data/maria.db`) no volume `maria_data`. Não há Postgres da Maria em produção.
- **Nome distinto** (`maria-api`): na rede do fomento, `db` continua resolvendo para o Postgres do fomento; na rede do Simcc, `read_db` resolve para o banco de leitura.
- **Acesso às origens**: a `maria-api` entra na rede do fomento e na `simcc-network` como `external` e consulta cada banco com um usuário somente leitura.
- **Porta**: a API fica em `11309` (configurável por `MARIA_API_PORT`).

Ao iniciar, o container aplica as migrações (`alembic upgrade head`) e sobe o uvicorn na porta 8000 interna.

## Arquivos

| Arquivo | Papel |
|---|---|
| `Dockerfile` | Imagem Python 3.13 com as dependências do `poetry.lock`, a extensão `postgres` do DuckDB (consultas entre fontes) e usuário sem privilégios de root |
| `.dockerignore` | Mantém `.env`, `*.db`, `.venv`, testes etc. fora da imagem |
| `compose.prod.yaml` | Serviço `maria-api`, volume `maria_data` com o SQLite e redes externas do fomento e do Simcc |

## Passo a passo

### 1. Descobrir as redes

O fomento e o Simcc precisam estar no ar. A rede do fomento costuma se chamar `<pasta-do-fomento>_default`. A do Simcc tem nome fixo, `simcc-network`, criada na instalação do Simcc com `docker network create simcc-network`:

```bash
docker network ls | grep -E 'default|simcc-network'
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

### 3. Criar um usuário somente leitura no banco de leitura do Simcc

O mesmo cuidado vale para o Simcc. Na pasta `Simcc/simcc-etl`:

```bash
docker compose exec read_db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

```sql
CREATE ROLE maria_leitura LOGIN PASSWORD 'troque-esta-senha';
GRANT CONNECT ON DATABASE <READ_DB_NAME> TO maria_leitura;
GRANT USAGE ON SCHEMA public TO maria_leitura;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO maria_leitura;
-- Tabelas e views materializadas recriadas pelo ETL também ficam legíveis:
ALTER DEFAULT PRIVILEGES FOR ROLE <READ_DB_USER> IN SCHEMA public
  GRANT SELECT ON TABLES TO maria_leitura;
ALTER ROLE maria_leitura SET default_transaction_read_only = on;
```

Troque `<READ_DB_NAME>` (padrão `simcc`) e `<READ_DB_USER>` (padrão `postgres`) pelos valores do `.env` do `simcc-etl`. Os dois bancos são servidores diferentes, então o mesmo nome `maria_leitura` pode existir nos dois com senhas distintas.

### 4. Configurar o `.env` da Maria

```bash
cp .env.example .env
```

Além das variáveis da [Configuração](../README.md#️-configuração), o deploy usa:

| Variável | Descrição | Exemplo |
|---|---|---|
| `MARIA_API_PORT` | Porta da API no host | `11309` (padrão) |
| `FOMENTO_NETWORK` | Rede do compose do fomento (passo 1) | `observatorio-fomento_default` |
| `FOMENTO_DATABASE_URL` | Conexão do usuário somente leitura, pelo host `db` | `postgresql+psycopg://maria_leitura:<senha>@db:5432/<POSTGRES_DB>` |
| `SIMCC_NETWORK` | Rede do Simcc (passo 1). Só precisa ser definida se não for `simcc-network` | `simcc-network` (padrão) |
| `SIMCC_DATABASE_URL` | Conexão do usuário somente leitura do Simcc (passo 3), pelo host `read_db` | `postgresql+psycopg://maria_leitura:<senha>@read_db:5432/simcc` |

Recomendado em produção:

```env
OTEL_SDK_DISABLED=true   # a menos que a stack de observabilidade esteja no ar
DEMO_ENABLED=false       # não expõe /demo/
```

**Nomes de host.** Se o banco de leitura do Simcc estiver em outra rede ou com outro nome, aponte `SIMCC_NETWORK` e `SIMCC_DATABASE_URL` para ele. Quando as duas redes tiverem um serviço chamado `db`, o nome fica ambíguo para a `maria-api`, que está nas duas. Use nesse caso o nome do container nas duas URLs, por exemplo `@modulo-fomento-db-1:5432/...` e `@observatorio-db-1:5432/observatorio`.

O `DATABASE_URL` do `.env` é ignorado: o `compose.prod.yaml` o sobrescreve para apontar para o SQLite no volume (`sqlite+aiosqlite:////app/data/maria.db`).

### 5. Subir

```bash
docker compose -f compose.prod.yaml up -d --build
curl http://localhost:11309/health
# {"status":"ok","database":"connected"}
```

### 6. Carregar o catálogo das fontes

Só na primeira vez, ou com `--reset` para recriar as fontes a partir dos YAML:

```bash
docker compose -f compose.prod.yaml exec maria-api \
  python -m observatorio_maria.catalog.seed catalog/fomento.yaml catalog/simcc.yaml catalog/concepts.yaml
```

O `catalog/concepts.yaml` cria os conceitos que aparecem nas duas fontes (projetos, instituições e pesquisadores), com a política de resposta, e é aplicado depois das fontes.

Depois do seed, **sincronize** as duas fontes. O seed cria as entidades como ausentes (`present: false`), e só a sincronização, que lê o schema real de cada banco, as marca como presentes. Sem esse passo, a Maria não recebe a ferramenta de consulta e responde que não tem acesso aos dados.

```bash
curl -X POST http://localhost:11309/catalog/datasources/fomento/sync
curl -X POST http://localhost:11309/catalog/datasources/simcc/sync
```

A sincronização do Simcc também lê os valores das colunas categóricas (`SELECT DISTINCT` somente leitura) e pode levar mais tempo que a do fomento, porque as tabelas de produção são maiores.

### Atualizar um catálogo que já existe

O seed não sobrescreve o que já está no catálogo. Quando um YAML de fonte muda, como na troca dos exemplos few-shot e na entrada de `researcher_institution` no Simcc (issue #2), um catálogo já semeado precisa receber a mudança de outra forma:

- **Sem edições feitas à mão** nas fontes: recrie tudo a partir dos arquivos e sincronize de novo, como no passo 6.

  ```bash
  docker compose -f compose.prod.yaml exec maria-api \
    python -m observatorio_maria.catalog.seed --reset catalog/fomento.yaml catalog/simcc.yaml catalog/concepts.yaml
  ```

- **Com edições feitas à mão:** rode o seed só com `catalog/concepts.yaml` (sem `--reset`), que cria os conceitos e vincula as entidades, e aplique o resto pela demo (aba "Catálogo de dados") ou pela API:
  - os exemplos e as instruções de `fomento` e `simcc` (`PATCH /catalog/datasources/{id}` com `examples` e `instructions`, copiando dos YAML);
  - no `simcc`, `researcher_institution` visível e consultável, com as colunas `researcher_id`, `institution_id`, `workload` e `identity_territory` visíveis (`PATCH /catalog/entities/{id}` e `PATCH /catalog/columns/{id}`);
  - `researcher.institution_id` oculta (`PATCH /catalog/columns/{id}` com `{"visible": false}`).

  Confira o resultado em `GET /catalog/concepts/context` e `GET /catalog/datasources/simcc/context`.

Consultas entre fontes dependem da ligação pelo Lattes, criada pelo mesmo `catalog/concepts.yaml`. A ligação só vale com as duas colunas visíveis, e a imagem precisa ser reconstruída com `--build` para levar a extensão do DuckDB. Sem ligação ativa, a Maria simplesmente não recebe a ferramenta. As conexões do DuckDB usam os mesmos `FOMENTO_DATABASE_URL` e `SIMCC_DATABASE_URL`, com tempo limite no próprio Postgres.

### 7. Liberar a porta

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

O `--remove-orphans` remove o container `maria-db`, que não está mais no compose. Depois, refaça o seed e a sincronização do passo 6. O volume antigo continua no servidor até ser apagado à mão, depois de conferir que a Maria está funcionando:

```bash
docker volume rm observatorio-maria_maria_postgres_data
```

## A Maria diz que não tem acesso aos dados

A ferramenta de consulta só é entregue ao modelo quando alguma fonte está ativa (`enabled`) e tem ao menos uma entidade visível, consultável e presente ao mesmo tempo. Cada fonte só entra no contexto do modelo quando cumpre essa condição. Verifique nesta ordem, com `FONTE` igual a `fomento` ou `simcc`:

```bash
API=http://localhost:11309
FONTE=fomento

# 1. A fonte existe, está ativa e qual o estado do schema?
curl -s $API/catalog/datasources/$FONTE | jq '{enabled, schema_status}'

# 2. Alguma entidade está visível, consultável e presente?
curl -s $API/catalog/datasources/$FONTE/entities \
  | jq '[.entities[] | select(.visible and .queryable and .present) | .name]'

# 3. O que o modelo recebe sobre a fonte
curl -s $API/catalog/datasources/$FONTE/context | jq -r .content
```

| Sintoma | Causa | Correção |
|---|---|---|
| Passo 1 dá 404 | Seed não rodou para essa fonte | Passo 6 do deploy |
| Passo 2 devolve `[]` | Fonte nunca sincronizada | `POST /catalog/datasources/$FONTE/sync` |
| Sync devolve 422 | `FOMENTO_DATABASE_URL` ou `SIMCC_DATABASE_URL` ausente no container | Conferir o `.env` e recriar com `up -d` |
| Sync devolve 502 | Banco inacessível: rede, host (`db` no fomento, `read_db` no Simcc), usuário, senha ou nome do banco | `docker compose -f compose.prod.yaml logs maria-api` e os passos 2 e 3 do deploy |
| `schema_status: error` | A verificação ao iniciar não conectou à origem | Mesma causa do 502 |

Depois de corrigir, teste em uma **conversa nova**: o histórico da conversa anterior, com a recusa, vai para o modelo e pode induzir a mesma resposta.

## Cuidados

- **Ordem de inicialização:** suba o fomento e o Simcc antes da Maria, porque as redes externas precisam existir. Se o fomento for derrubado com `down`, a rede dele é recriada e a Maria precisa de um novo `up -d`. A `simcc-network` é externa ao próprio Simcc e não some com o `down` dele.
- **Porta 5432 do PostgreSQL:** o compose da raiz expõe o Postgres no host na porta 5432. A Maria acessa os bancos pelas redes internas (`simcc-network` e rede do fomento) ou via `localhost:5432` em desenvolvimento local. Em produção externa, se nada mais usar a porta no host, vale fechá-la no firewall.
- **Segredos:** o `.env` fica fora da imagem (`.dockerignore`) e do Git (`.gitignore`).
