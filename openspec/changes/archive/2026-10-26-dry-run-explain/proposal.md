# Proposal: Dry-run de Consultas com EXPLAIN

## Why

Atualmente, o Observatório Maria possui proteções em nível de sintaxe e validação estática de consultas (somente `SELECT`, colunas visíveis, funções permitidas, teto de `LIMIT` e `statement_timeout` de 15 segundos).

No entanto, o `statement_timeout` é uma salvaguarda **reativa**: o banco de dados de origem (PostgreSQL) chega a iniciar a execução da consulta e pode consumir 15 segundos de CPU, I/O de disco e conexões ativas até ser cancelado. Consultas sem filtros seletivos, com cruzamentos volumosos ou com buscas amplas em tabelas de milhões de registros podem degradar o banco da instituição antes de disparar o timeout.

Com um **dry-run preventivo via `EXPLAIN`**, o sistema passa a consultar o planejador do banco de dados antes da execução real:
1. **Proteção proativa do banco de origem:** O plano de execução é gerado em ~1-2 milissegundos na memória do PostgreSQL sem ler dados em disco. Se o `Total Cost` estimado ultrapassar um teto seguro (`QUERY_MAX_ESTIMATED_COST`), a consulta é barrada imediatamente.
2. **Feedback pedagógico para a IA:** A Maria recebe uma recusa estruturada informando que o custo estimado é muito alto e orientando a restringir a busca com filtros específicos (ano, status, termos em colunas pesquisáveis com `MATCH_TEXT`). Como a Maria dispõe de orçamento de chamadas, ela pode reescrever a consulta de forma mais eficiente na chamada seguinte.

## What Changes

- **Verificação de Custo Estimado via EXPLAIN:** No PostgreSQL, antes de executar a consulta em `execute_readonly_query`, executar `EXPLAIN (FORMAT JSON) <query>` e extrair o `Total Cost` do nó raiz do plano.
- **Configuração de Custo Máximo (`QUERY_MAX_ESTIMATED_COST`):** Nova variável em `Settings` (padrão `50000.0`, onde `0` desativa a verificação).
- **Tratamento de Exceção `QueryCostExceededError`:** Nova exceção especializada em `src/observatorio_maria/query/errors.py`, tratada no `QueryRunner` para retornar uma mensagem amigável e instrutiva à Maria em `query_data`.
- **Compatibilidade entre Dialetos:** No PostgreSQL, o custo é validado numericamente contra o teto. No SQLite (usado em testes e desenvolvimento), `EXPLAIN QUERY PLAN` é validado estruturalmente ou opera em modo bypass transparente para não quebrar compatibilidade, já que SQLite não fornece custo numérico absoluto.
- **Instruções de Sistema Atualizadas (`TOOL_RULES_PROMPT`):** Orientar a Maria sobre a necessidade de formular consultas seletivas com filtros eficientes para não estourar o custo estimado do banco.
- **Documentação e Telemetria:** Documentar a nova configuração no `.env.example` e `README.md`.

### Fora do escopo

- Não utilizar `EXPLAIN ANALYZE` (que executa a consulta de verdade). O dry-run deve ser estritamente `EXPLAIN` sem execução.
- Não implementar otimizadores de índices ou regras automáticas de reescrita de SQL via heurísticas sintáticas.
- Não alterar schemas nem tabelas do banco da Maria ou dos bancos externos.

## Capabilities

### Modified Capabilities

- `data-querying`: Antes de executar a consulta na origem, o sistema passa a realizar um dry-run via `EXPLAIN` no PostgreSQL e recusa consultas cujo custo estimado supere o teto configurado.

## Impact

- **Bancos externos:** Redução drástica de sobrecarga em consultas mal calibradas geradas por IA.
- **Latência:** Acréscimo residual de 1 a 3ms para o round-trip do `EXPLAIN` antes de cada consulta válida.
- **Segredos e infraestrutura:** Nenhuma dependência externa nova ou alteração de credenciais.
