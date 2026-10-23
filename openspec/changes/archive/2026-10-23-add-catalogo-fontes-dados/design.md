# Design

## Context

A motivação está em `proposal.md` e os requisitos em `specs/`. A Maria já tem banco próprio via SQLAlchemy 2.0 assíncrono (SQLite com `aiosqlite` em dev, `psycopg` previsto para PostgreSQL), modelos em dataclass (`table_registry`), migrações Alembic e rotas finas com `Depends`. O banco do fomento é um PostgreSQL 17 (banco `fomento`) com 15 tabelas e a view materializada `mv_bolsas_metricas`. Os bancos de outros sistemas não podem ser alterados: nada de views, roles ou comentários criados por nós.

## Goals / Non-Goals

**Goals:**
- Um modelo de catálogo que já sirva à próxima mudança (a IA consultando os bancos): a prévia do contexto é o mesmo código que vai montar o prompt.
- Separação clara entre dados **técnicos** (vindos da origem, sobrescritos pela sincronização) e **editoriais** (vindos de pessoas, nunca sobrescritos automaticamente).

**Non-Goals:**
- Executar consultas na origem ou ler dados (valores de exemplo, contagens). Só o schema é lido.
- Autenticação e trilha de auditoria das edições.
- Criar relacionamentos manuais pela API. Por enquanto, só pelo YAML.

## Decisions

### 1. Catálogo no banco da própria Maria
As tabelas `catalog_datasources`, `catalog_entities`, `catalog_columns` e `catalog_relationships` ficam no mesmo banco das conversas, com o mesmo engine, sessão e migrações. Em dev isso já é SQLite, então não há servidor extra.

*Alternativa:* um arquivo SQLite só para o catálogo. Descartada: exigiria um segundo engine, outra cadeia de migrações e outra configuração, sem ganho. Se a Maria for para PostgreSQL em produção, o catálogo vai junto sem mudança de código.

### 2. Conexão por nome de variável de ambiente
A fonte guarda `connection_env` (ex.: `FOMENTO_DATABASE_URL`), não a URL. Segredos ficam no ambiente, o catálogo pode ser exportado e versionado sem vazar credenciais, e a API nunca devolve a URL.

### 3. Introspecção somente leitura e efêmera
`catalog/introspection.py` cria um engine assíncrono por sincronização (`NullPool`, descartado ao fim) e garante somente leitura no nível da sessão:
- PostgreSQL: `default_transaction_read_only=on` nas opções de conexão;
- SQLite (testes): `PRAGMA query_only=ON`.

A leitura usa o `Inspector` do SQLAlchemy dentro de `run_sync`: tabelas, views, views materializadas (quando o dialeto suporta), colunas, chave primária e chaves estrangeiras de cada schema configurado. O resultado é uma estrutura imutável (`SchemaSnapshot`), e a fusão com o catálogo é uma função pura sobre ela. Assim os testes usam um SQLite real em arquivo temporário como origem.

O router recebe a função de introspecção por `Depends`, como já é feito com modelos e tracer.

### 4. Fusão por chave natural e indicador `present`
- **Entidade:** chave `(fonte, schema, nome)`. **Coluna:** `(entidade, nome)`. **Relacionamento:** `(entidade origem, colunas origem, entidade destino, colunas destino)`.
- A sincronização:
  - atualiza os campos técnicos (`kind`, `data_type`, `nullable`, `primary_key`, `position`);
  - cria o que falta com `visible=False` e `queryable=False`;
  - marca `present=False` no que sumiu e `present=True` no que reapareceu.
- Relacionamentos têm `origin`:
  - `foreign_key`: encontrados ou confirmados pela sincronização;
  - `manual`: declarados no YAML sem chave estrangeira correspondente. A sincronização nunca os marca como ausentes.
- Tudo ocorre num único commit. Se a introspecção falhar, nada é gravado.

### 5. Regra visível ⇒ consultável no domínio
A regra fica no PATCH da entidade:
- `visible=false` força `queryable=false`;
- se o estado resultante tiver `queryable=true` com `visible=false`, a resposta é 422.

Colunas têm `visible` e `access` (`full` | `aggregate`). Não existe "coluna consultável": quem decide se dá para consultar é a entidade, e a coluna define como os valores podem aparecer.

### 6. YAML validado por Pydantic, em formato compartilhado entre seed e exportação
`catalog/yaml_io.py` define o formato como modelos Pydantic (`CatalogFile`). O seed valida o arquivo inteiro antes de abrir a transação, e a exportação serializa a partir do mesmo modelo, o que garante a ida e volta. Formato:

```yaml
datasource:
  id: fomento
  name: Fomento à pesquisa
  connection_env: FOMENTO_DATABASE_URL
  schemas: [public]
  instructions: |
    As métricas de bolsas incluem as pendentes de revisão...
entities:
  - name: bolsas            # schema padrão: o primeiro de `schemas`
    label: Bolsas
    description: ...
    synonyms: [fomento, auxílio]
    queryable: true         # padrão true para entidades listadas
    columns:
      - name: status
        description: ...
        values:
          - {value: REGULAR, description: ...}
      - name: cep_referencia
        access: aggregate
relationships:
  - from: bolsas.pesquisador_id
    to: pesquisadores.id
    description: Pesquisador bolsista
```

Seed:
- `python -m observatorio_maria.catalog.seed ARQUIVO... [--reset]`, também disponível como `task seed`;
- cria apenas a fonte, as entidades, as colunas e os relacionamentos que faltam;
- `--reset` apaga a fonte do catálogo e a recria a partir do arquivo.

Itens criados pelo seed antes de qualquer sincronização ficam com `present=False` e campos técnicos vazios até a primeira sincronização.

*Alternativa:* o YAML como fonte de verdade, reaplicado a cada início. Descartada pelo usuário: as edições feitas pelo frontend seriam sobrescritas.

### 7. Prévia em Markdown determinístico
`catalog/context.py` monta o texto, ordenado por schema, entidade e posição de coluna:
- cabeçalho da fonte e instruções;
- uma seção por entidade, com rótulo, descrição, sinônimos e a marca "(somente referência, não consultável)" quando for o caso;
- lista de colunas com tipo, descrição, `aggregate` como "(somente agregação)" e valores conhecidos;
- relacionamentos ligados entre entidades incluídas.

É uma função pura sobre os objetos do catálogo, reutilizável no prompt da próxima mudança.

### 8. API plana por UUID
- Fontes, por slug: `/catalog/datasources/{id}`, com `/sync`, `/entities`, `/relationships`, `/context` e `/export`.
- Entidades, colunas e relacionamentos, por UUID: `/catalog/entities/{id}`, `/catalog/columns/{id}` e `/catalog/relationships/{id}`.

URLs aninhadas por nome de tabela seriam frágeis com schemas e nomes repetidos.

### 9. Demo em arquivo separado
A aba "Catálogo de dados" entra em `demo/index.html` com lógica em `demo/catalog.js`, reaproveitando `styles.css`. O `app.js` do chat fica intocado, exceto pela troca de abas, que já é genérica.

## Risks / Trade-offs

- **[Endpoints sem autenticação]:** qualquer um com acesso à API altera o catálogo. Mitigação: aceitável em dev, e a autenticação está em andamento noutro repositório. A API não expõe credenciais nem lê dados da origem.
- **[Usuário com permissão de escrita na origem]:** em dev, a conexão usa o usuário dono do banco. Mitigação: somente leitura forçada na sessão. Recomendação documentada: um role somente leitura criado pelos responsáveis do banco de origem.
- **[Seed antes da sincronização]:** itens aparecem como ausentes até a primeira sincronização. Mitigação: a demo e o README indicam sincronizar após o seed.
- **[Renomeação na origem]:** uma coluna renomeada vira "ausente" mais "nova", e a configuração não migra. Mitigação: o item ausente continua visível na configuração para ser copiado. A reconciliação automática fica fora do escopo.

## Migration Plan

1. `alembic upgrade head` cria as tabelas do catálogo.
2. Definir `FOMENTO_DATABASE_URL` no `.env`.
3. `task seed` carrega `catalog/fomento.yaml`. Depois, sincronizar pela API ou pela demo.

Rollback: `alembic downgrade -1` remove as tabelas do catálogo, sem impacto nas conversas.
