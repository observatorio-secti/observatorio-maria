# Tasks: Dry-run de Consultas com EXPLAIN

## 1. Configuração e Exceção de Custo

- [x] 1.1 Adicionar `QUERY_MAX_ESTIMATED_COST` em `src/observatorio_maria/settings.py` (padrão `50000.0`, `0` desativa) e documentar no `.env.example`.
- [x] 1.2 Criar classe `QueryCostExceededError` herdando de `QueryExecutionError` em `src/observatorio_maria/query/errors.py`.

## 2. Execução do Dry-run com EXPLAIN

- [x] 2.1 Implementar verificação de custo via `EXPLAIN (FORMAT JSON)` no PostgreSQL e suporte compatível em SQLite em `src/observatorio_maria/query/execution.py`, lançando `QueryCostExceededError` quando o custo ultrapassar o teto.
- [x] 2.2 Integrar parâmetro `max_cost` no `QueryRunner` em `src/observatorio_maria/query/tool.py` e capturar `QueryCostExceededError`, devolvendo mensagem explicativa e instrutiva no retorno da ferramenta.
- [x] 2.3 Atualizar `TOOL_RULES_PROMPT` em `src/observatorio_maria/llm/prompts.py` orientando o agente a utilizar filtros específicos para evitar consultas custosas.

## 3. Testes, Documentação e Verificação

- [x] 3.1 Adicionar testes unitários cobrindo consultas com custo aceitável, custo excedido, teto desativado (`0`) e compatibilidade com SQLite em `tests/test_query_execution.py`.
- [x] 3.2 Adicionar teste de integração no fluxo de chat em `tests/test_agent_chat.py` simulando recusa por custo estimado excessivo e recuperação da Maria.
- [x] 3.3 Atualizar a seção de segurança e limites no `README.md` documentando o dry-run com `EXPLAIN`.
- [x] 3.4 Executar verificação completa com `task lint` e `task test`, assegurando 100% dos testes passando e cobertura mínima de 90%.
