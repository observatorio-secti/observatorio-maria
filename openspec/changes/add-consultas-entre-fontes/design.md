# Design

## Context

Motivação em `proposal.md`. Estado atual relevante:

- **Validador:** `validate_query` trabalha com um `QuerySchema` de uma fonte. `_check_tables` confere nomes de tabela; `_check_functions` só aceita funções da lista, o que já recusa `postgres_query` e `read_csv`. Colunas `aggregate` e pesquisáveis são indexadas por `(tabela, coluna)`, sem a fonte. `rewrite_match_text` gera `translate(lower(...)) LIKE ... ESCAPE`.
- **Execução:** `execute_readonly_query` usa SQLAlchemy assíncrono, `statement_timeout`, `SET TRANSACTION READ ONLY` e, no Postgres, teto de custo por `EXPLAIN`, e limita linhas com `LIMIT max_rows + 1`. `_clean_error` limpa URLs e IPs.
- **Agente:** `QueryRunner` guarda `ResultStore`, sanitiza linhas e monta `untrusted_data`. `build_query_tools` registra `query_data` e os blocos. `_execute_tool_call` trata só `query_data`, `show_chart` e `show_table`. `QueryObservation` tem uma `source`.
- **Catálogo:** relacionamentos são por fonte. Conceitos ficam em `catalog/concepts.yaml`, aplicado depois das fontes.
- **Protótipo da issue #4:** com o fomento real e 2,5 milhões de produções sintéticas, ~1 s por pergunta e 1,4 s no pior caso, com 200–350 MB.
- **Produção:** 8 núcleos e 21 GB disponíveis. As origens são Postgres; o maior volume é `bibliographic_production`, com 638 mil linhas e 884 MB. O banco do Simcc atende também o observatório.
- **DuckDB 2.0:** tem pacote `abi3` para Python 3.12 em diante, o que cobre o 3.13 da imagem e o 3.14 do dev.

## Goals / Non-Goals

**Goals:**
- Agregações entre fontes sem limite de chaves, com a cobertura vindo da ferramenta.
- Fonte única sem nenhuma mudança de comportamento.
- Uma consulta ruim não pode prejudicar os bancos de origem nem a API.

**Non-Goals:**
- Materializar dados das origens: tudo é lido na hora.
- Usar o DuckDB como banco da Maria, que continua em SQLite.

## Decisions

### D1. Ferramenta própria, `query_across_sources`
Parâmetros: `sql` e `purpose`. Só é registrada com uma ligação ativa entre fontes consultáveis. `query_data` não muda.
- *Descartado:* `source` opcional em `query_data`. Misturaria dois caminhos de validação e execução, e a descrição da ferramenta ficaria ambígua para o modelo.

### D2. DuckDB em memória, um por consulta
`query/federation.py` cria `duckdb.connect(':memory:')` a cada consulta e o fecha ao final, numa thread (`asyncio.to_thread`), porque o DuckDB é síncrono. Sequência:
1. configurar `memory_limit`, `threads` e o diretório de extensões;
2. `LOAD postgres`;
3. `ATTACH` das fontes citadas, em `READ_ONLY`;
4. `SET enable_external_access=false` e `SET lock_configuration=true`;
5. executar `SELECT * FROM (<sql>) AS q LIMIT max_rows + 1`, como o caminho atual.

- *Descartado:* conexão compartilhada ou pool. Anexar a cada consulta custa mais, mas não há estado entre consultas, e a medição dirá se isso pesa.
- *Descartado:* passar as chaves pelo servidor (`ANY(array)` na segunda fonte), sem DuckDB. Resolve filtros, mas não agrupa por atributo da outra fonte, como "artigos por modalidade".

### D3. Validador com vários catálogos
`build_federated_schema` monta um `MappingSchema` `fonte → schema → tabela` com dialeto `duckdb`. Conjuntos de `aggregate`, pesquisáveis e tabelas passam a usar a chave `fonte.schema.tabela`, para tabelas de mesmo nome não se confundirem. Os checks existentes são reaproveitados, recebendo um resolvedor de chave em vez de assumir `(tabela, coluna)`. O caminho de uma fonte continua com as mesmas chaves e os testes atuais não mudam. `_check_tables` exige `exp.Table` com catálogo, schema e nome, o que também recusa `FROM 'arquivo.csv'`.
- *Descartado:* validar cada fonte em separado sobre partes do SQL. Colunas sem qualificador e aliases ficariam sem resolução.

### D4. Junção só por ligação declarada
Depois de `qualify`, o validador percorre os predicados de `JOIN` e `WHERE`. Cada igualdade entre colunas de catálogos diferentes é comparada com as ligações ativas, nos dois sentidos. Exige-se ao menos uma, e qualquer outro predicado que misture as duas fontes é recusado. `CROSS JOIN` entre fontes também.
- *Descartado:* confiar só na política dos conceitos. É texto para o modelo; a regra no validador impede que ele cruze instituições por nome, o que daria números errados com aparência de certos.

### D5. Proteção das origens
A proteção contra carga tem quatro camadas, já que não há `EXPLAIN` para uma consulta federada:
1. **Na origem:** a conexão do `ATTACH` leva `options=-c statement_timeout=<ms> -c default_transaction_read_only=on`. Assim, o Postgres encerra a varredura mesmo se o processo da Maria não conseguir fazê-lo.
2. **No DuckDB:** `con.interrupt()` em `QUERY_TIMEOUT_SECONDS`, a partir de um `asyncio.timeout`.
3. **Concorrência:** um semáforo global com `QUERY_FEDERATED_MAX_CONCURRENT` (padrão 2), para o modelo não multiplicar varreduras.
4. **Memória:** `memory_limit` (padrão `512MB`) e `threads` (padrão 2), sem spill em disco.

- *Descartado:* rodar `EXPLAIN` em cada parte na origem. O DuckDB decide o que empurra para cada origem, e reconstruir essas partes seria frágil.

### D6. Cobertura por reescrita da consulta
Para uma consulta plana (sem CTE nem subconsulta na fonte de origem), o validador devolve também um SQL de cobertura, montado pela AST: usa só as tabelas e os predicados `WHERE`/`JOIN` da fonte de origem da ligação e calcula `COUNT(DISTINCT chave)` e, com `IN (SELECT chave FROM outra_tabela)`, as encontradas. Filtros da outra fonte ficam de fora, para a cobertura medir quem existe lá, e não quem passou no filtro. A fonte de origem é o lado `from` da ligação. O SQL de cobertura roda na mesma conexão, depois do principal e dentro do mesmo tempo limite. Falha ou consulta não plana resulta em `coverage: null` com `reason`, sem derrubar a resposta.
- *Descartado:* pedir ao modelo uma segunda consulta. É exatamente a falha de hoje.
- *Descartado:* trocar `INNER` por `LEFT JOIN` na própria consulta. Filtros da outra fonte no `WHERE` desfariam o efeito.

### D7. Ligações em `catalog_source_links`
Colunas: `id`, `from_entity_id`, `from_column`, `to_entity_id`, `to_column`, `description`, `enabled`, com chaves estrangeiras para as entidades em `ON DELETE CASCADE` e restrição de unicidade. Guardar por entidade e nome de coluna segue o padrão de `CatalogRelationship`. Valem só com as colunas visíveis e presentes. Recriar uma fonte apaga as ligações dela; o seed recria.

O seed fica em `links:` no `catalog/concepts.yaml`, porque ligações, como conceitos, envolvem mais de uma fonte, e precisam ser aplicadas depois delas. As rotas são `GET/POST /catalog/links` e `PATCH/DELETE /catalog/links/{id}`.
- *Descartado:* usar `CatalogRelationship`. Ele pertence a uma fonte e entra na linha da coluna do contexto daquela fonte.
- *Descartado:* um arquivo `catalog/links.yaml`. Criaria um terceiro tipo de seed sem necessidade.

### D8. Contexto
`render_concepts` ganha a seção "Consultas entre fontes", com as ligações e o formato de tabela. Ela fica na mesma prévia de `GET /catalog/concepts/context`. As regras do prompt ganham a obrigação de informar a cobertura e de não apresentar total parcial como completo.

### D9. Resultado e observação
O resultado segue o formato de `query_data` (`result_id`, sanitização, `untrusted_data`) e acrescenta `coverage`. `ResultStore.add` guarda a fonte como `fomento+simcc`. `QueryObservation` ganha `sources`, usado pelo critério `sources` do `task eval`. `Activity` usa os nomes das duas fontes.

### D10. Extensões
O `Dockerfile` instala a extensão `postgres` num diretório fixo (`/app/duckdb_extensions`), como usuário `maria`, depois do `USER`. A versão da extensão acompanha a do pacote fixada no `poetry.lock`. A extensão `sqlite`, usada só nos testes com origens em arquivo, é instalada sob demanda no ambiente de dev e guardada em cache; sem ela, os testes de integração são pulados com um aviso claro. Nenhum teste chama um LLM real.

## Risks / Trade-offs

- [Consulta pesada no banco do observatório] → `statement_timeout` por conexão, concorrência limitada e verificação de carga antes do deploy (task 7.2). Se os números forem ruins, baixar a concorrência ou exigir filtro.
- [DuckDB traz muitas linhas de `bibliographic_production`, porque não empurra todas as junções] → Limite de memória e tempo; o modelo recebe erro que orienta filtrar ou usar as views canônicas.
- [Anexar a cada consulta tem custo de catálogo] → Medir na task 7.2. Só as fontes citadas são anexadas.
- [Atualização do DuckDB muda a extensão] → Versão fixada no `poetry.lock`; a extensão é instalada no build.
- [Cobertura medida no lado errado da ligação] → A fonte de origem é fixa na ligação (`from`), e a resposta nomeia a fonte.
- [Dialeto diferente muda resultados de `date_trunc`, `string_agg` ou `extract`] → O validador reescreve para `duckdb` pelo `sqlglot`, e os testes cobrem as funções da lista.
- [Uma ligação com coluna ausente] → Deixa de valer e a ferramenta sai, se for a única; a demo mostra o alerta.

## Migration Plan

1. A migração (autogenerate, revisada) cria `catalog_source_links`, sem tocar em tabelas existentes.
2. Depois do `alembic upgrade head`, `task seed` cria a ligação pelo Lattes. As instruções das fontes são aplicadas pela API, porque o seed não sobrescreve.
3. Em produção, além disso, é preciso reconstruir a imagem para levar a extensão; isso fica para o pedido de deploy, com os passos em `docs/deploy.md`.
4. **Rollback:** `alembic downgrade -1` remove a tabela. Sem ligações, a ferramenta sai do agente, e voltam as instruções antigas pela API se forem necessárias.
