# data-querying Specification Delta

## Requirements

### ADDED Requirement: Dry-run de custo estimado com EXPLAIN
Em bancos de dados PostgreSQL, o sistema SHALL executar um dry-run via `EXPLAIN (FORMAT JSON)` antes da execução da consulta e inspecionar o custo total estimado (`Total Cost`). Quando o custo ultrapassar `QUERY_MAX_ESTIMATED_COST` (e o limite for maior que zero), a consulta MUST ser recusada antes de ser executada na origem, devolvendo ao modelo uma explicação com os custos e orientação para restringir a busca.

#### Scenario: Custo estimado dentro do limite aceito
- **WHEN** o modelo envia consulta com custo estimado de 1.200 em relação a um teto de 50.000
- **THEN** a consulta é validada pelo dry-run e executada normalmente

#### Scenario: Custo estimado excessivo recusado
- **WHEN** o modelo envia consulta sem filtros cujo custo estimado pelo PostgreSQL atinge 85.000 (acima do teto de 50.000)
- **THEN** a execução é interrompida antes de tocar nas tabelas e o modelo recebe mensagem explicando que o custo foi excedido com sugestão de filtros

#### Scenario: Verificação desativada com teto zero
- **WHEN** `QUERY_MAX_ESTIMATED_COST` é configurado como 0
- **THEN** a consulta é executada sem bloqueio por custo de dry-run

#### Scenario: Compatibilidade com dialeto SQLite
- **WHEN** a consulta é executada contra uma fonte SQLite
- **THEN** o sistema executa o dry-run compatível ou prossegue para execução sem exigir o formato numérico do PostgreSQL
