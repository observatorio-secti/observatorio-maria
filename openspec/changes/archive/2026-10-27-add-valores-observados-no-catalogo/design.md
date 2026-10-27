# Design

## Context

Motivação em `proposal.md`. Estado atual relevante:

- `catalog/introspection.py` lê só estrutura e produz um `SchemaSnapshot` sem conhecer o catálogo (visibilidade, acesso). `ColumnSnapshot.enum_values` é o único valor técnico de coluna.
- `CatalogColumn` separa `enum_values` (técnico) de `values` (editorial). `undescribed_values` e `obsolete_values` só funcionam com enum. `catalog/context.py::_known_values` escolhe enum ou editorial.
- A verificação (`drift.check_datasource`) compara impressões digitais e, se nada mudou, só grava o estado. A sincronização roda por API, pela verificação com `auto_sync` e pelo seed.
- `query/validator.py::build_query_schema` + `validate_query` já recusam entidades, colunas e funções fora do catálogo, sem tocar a origem.
- `query/execution.py` já aplica `statement_timeout` (PostgreSQL) e `asyncio.timeout` numa conexão somente leitura.
- No fomento real, `modalidade` tem 4 valores distintos em `bolsas` (45 mil linhas) e na view materializada.

## Goals / Non-Goals

**Goals:**
- Os valores categóricos que o modelo vê vêm da origem, não de quem escreveu o YAML.
- Exemplos few-shot quebrados não chegam ao modelo, e quem cuida do catálogo vê o motivo.
- O agente tem orçamento e sinal para corrigir um filtro errado na mesma resposta.

**Non-Goals:**
- Detectar categorias em colunas numéricas, de data ou booleanas.
- Corrigir automaticamente o valor do filtro (ex.: casar `Doutorado` com `Doutorado - Cotas`): o modelo decide com base nos valores.

## Decisions

### D1. `SELECT DISTINCT ... LIMIT max+1` por coluna, e não `pg_stats`
Para cada coluna elegível: `SELECT DISTINCT "col" FROM "schema"."entidade" WHERE "col" IS NOT NULL LIMIT :max + 1`. Se voltar mais que `max`, o resultado é nulo (texto livre). Roda na conexão somente leitura, com o mesmo timeout por consulta de `query/execution.py` (`QUERY_TIMEOUT_SECONDS`).
- *Descartado:* `pg_stats.most_common_vals`. Não varre a tabela, mas depende de `ANALYZE` ter rodado (view materializada recém-criada não tem estatística), pode omitir valores raros e só existe no PostgreSQL. Isso deixaria os testes em SQLite sem cobertura real. A lista precisa ser completa para justificar marcar valores editoriais como obsoletos.

### D2. Leitura em módulo próprio, guiada pelo catálogo, fora do `SchemaSnapshot`
Novo `catalog/observed.py` com `refresh_observed_values(session, datasource, engine_factory)`. Ele carrega as entidades do catálogo, filtra as colunas elegíveis (texto, sem enum, visível, presente, `access=full`, entidade visível, presente e consultável) e grava `CatalogColumn.observed_values`. Chamado depois de `sync_datasource` nos pontos que têm conexão com a origem: o endpoint `POST .../sync` e a verificação (ramo `up_to_date` e auto-sync). `sync_datasource` continua uma fusão pura de snapshot, sem I/O; o seed não toca a origem e não lê valores. O `PATCH` de coluna para `aggregate` apaga os valores guardados.
- *Descartado:* ler valores dentro de `introspect`. A introspecção não sabe o que é visível ou `aggregate`, então leria colunas ocultas e pessoais. Além disso, os valores entrariam no snapshot, e a impressão digital mudaria a cada mudança de dados.

### D3. Tipo "texto" decidido pelo `data_type` já catalogado
Elegível se `data_type` (string compilada pelo dialeto) começa com `VARCHAR`, `TEXT`, `CHAR`, `CHARACTER`, `CITEXT` ou `NAME`, sem diferenciar maiúsculas. Isso cobre as colunas da view materializada, que chegam como `VARCHAR`/`TEXT`.
- *Descartado:* novo campo técnico de "família de tipo" no snapshot. Mudaria a impressão digital de todas as fontes e forçaria uma defasagem sem mudança real.

### D4. "Valores atuais da origem" = enum ou observados
Uma propriedade `CatalogColumn.source_values` devolve `enum_values` se houver, senão `observed_values`. `undescribed_values`, `obsolete_values`, `_known_values` (contexto) e a demo passam a usá-la. Enum tem precedência porque é definição de tipo, não amostra.
- *Descartado:* manter as duas listas separadas no contexto. O modelo veria duas fontes de verdade para a mesma coluna.

### D5. Sincronização não relata valores observados novos
O `SyncReport` continua relatando só `new_enum_values`. Os valores observados mudam com os dados (a view materializada é atualizada pelo fomento), e relatá-los a cada verificação geraria ruído. Os pendentes aparecem pela API (`undescribed_values`).
- *Descartado:* `new_observed_values` no relatório e no diff. Não é defasagem de schema.

### D6. Exemplos conferidos na renderização do contexto, sem guardar estado
`render_context` recebe o `QuerySchema` da fonte (o mesmo de `query_data`, montado com `build_query_schema`) e roda `validate_query` em cada exemplo. Os inválidos saem da seção few-shot. A prévia (`GET /catalog/datasources/{id}/context`) passa a devolver também `rejected_examples: [{question, reason}]`. A montagem do `QuerySchema` (detecção do dialeto pela URL) sai de `QueryRunner._get_query_schema` para uma função reutilizável.
- *Descartado:* recusar exemplos inválidos com 422 no `POST`/`PATCH` da fonte. A fonte costuma ser criada antes da primeira sincronização, quando nada é visível, e todo exemplo seria recusado. O catálogo também muda depois (coluna ocultada), e o exemplo quebraria sem aviso.
- *Descartado:* `EXPLAIN` na origem para cada exemplo. Abriria uma conexão externa a cada prévia ou montagem de prompt. A validação do catálogo já pega o caso real (`ano`).

### D7. Aviso de resultado vazio decidido pelo resultado, sem analisar o SQL
Em `QueryRunner.query_data`, se `rows == []` ou se há uma linha e todos os valores são `None`, o retorno ganha `hint` com um texto fixo em português, orientando `SELECT DISTINCT` nas colunas filtradas. O aviso vai fora do `untrusted_data`, porque é texto do sistema.
- *Descartado:* detectar filtros de igualdade em texto pelo AST. É mais preciso, mas o aviso em falso positivo custa pouco (o modelo ignora quando a ausência é real), e a análise acrescentaria código frágil.
- *Descartado:* tratar `0` como vazio. `COUNT(*) = 0` é uma resposta válida frequente; só `NULL` indica soma sem linhas.

### D8. Orçamento padrão de 3 para 6
Só o padrão de `Settings.MARIA_AGENT_MAX_MODEL_CALLS` muda. O laço já informa as chamadas restantes e reserva a última para a resposta. Com 6, sobram até 5 rodadas de consulta: a do filtro errado, a de `DISTINCT`, a corrigida e duas de folga.
- *Descartado:* 4 (o mínimo para filtro errado → `DISTINCT` → corrigida → resposta). Não sobra folga para perguntas com mais de um filtro, e o usuário pediu +3.

## Risks / Trade-offs

- [`DISTINCT` em tabela grande sem índice pode ser caro na origem] → só colunas visíveis de entidades consultáveis, `LIMIT max+1`, timeout por coluna, e a falha mantém os valores anteriores sem interromper as demais.
- [Coluna visível com acesso `full` que tenha poucos valores pessoais (ex.: tabela pequena de nomes) teria esses valores no prompt] → é o mesmo dado que o modelo já pode listar com `query_data` numa coluna `full`. Colunas pessoais devem ser `aggregate`, que não são lidas.
- [Valor editorial descrito fica obsoleto por um erro de grafia na origem] → continua visível na API como obsoleto, com a descrição preservada. Quem cuida do catálogo decide.
- [Valores observados ficam defasados entre verificações] → a verificação roda a cada `CATALOG_CHECK_INTERVAL_SECONDS` (1 h). Um valor novo não listado ainda pode ser descoberto com o aviso de resultado vazio.
- [Validar exemplos a cada montagem de prompt acrescenta latência] → `validate_query` é análise local com sqlglot, sem I/O. Poucos exemplos por fonte.
- [Mais chamadas ao modelo aumentam custo e tempo de resposta] → o laço para assim que o modelo responde sem ferramentas. As 6 chamadas só acontecem quando o modelo continua consultando, e o teto de tokens por conversa continua valendo.
- [`.env` existente com `MARIA_AGENT_MAX_MODEL_CALLS=3` ignora o novo padrão] → registrar no README e no `.env.example`, e avisar no resumo da implementação.
- [Endpoints do catálogo seguem sem autenticação e agora expõem valores lidos da origem] → mesmo risco já registrado para o catálogo até o observatorio-idp. Só colunas `full` e visíveis são lidas.

## Migration Plan

1. Migração Alembic (autogenerate, nome ASCII) adiciona `catalog_columns.observed_values` (JSON, nulo, sem `server_default`). As linhas existentes ficam nulas e o comportamento não muda até a próxima sincronização ou verificação.
2. Deploy. Na verificação de inicialização, as fontes ativas preenchem os valores observados. `bolsas.modalidade` passa a mostrar `Doutorado` etc. como obsoletos, e o contexto lista os valores reais.
3. **Rollback:** `alembic downgrade -1` remove a coluna. Os valores observados se perdem (são recalculáveis), e os editoriais ficam intactos. O código anterior volta a usar só enum e editorial.

## Open Questions

- Os valores obsoletos de `bolsas.modalidade` no banco já semeado podem ser apagados pela API depois de conferidos. Isso fica a critério de quem cuida do catálogo e não muda esta implementação.
