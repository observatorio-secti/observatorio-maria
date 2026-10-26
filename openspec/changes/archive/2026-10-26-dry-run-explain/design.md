# Design: Dry-run de Consultas com EXPLAIN

## Arquitetura e Decisões

### 1. Ponto de Interceptação do Dry-run

- **Abordagem:** O dry-run é executado dentro de `execute_readonly_query` em `src/observatorio_maria/query/execution.py`, antes de executar a consulta embrulhada (`SELECT * FROM (...) AS q LIMIT ...`).
- **Execução no PostgreSQL:**
  ```python
  explain_sql = f'EXPLAIN (FORMAT JSON) {wrapped_sql}'
  result = await conn.execute(text(explain_sql))
  raw_plan = result.scalar()
  # psycopg/asyncpg pode entregar string JSON ou estrutura nativa (list/dict)
  plan_data = json.loads(raw_plan) if isinstance(raw_plan, str) else raw_plan
  total_cost = float(plan_data[0]['Plan']['Total Cost'])
  ```
  Se `max_cost > 0` e `total_cost > max_cost`:
  Lançar `QueryCostExceededError(total_cost=total_cost, max_cost=max_cost)`.
- **Alternativa descartada:** Executar o `EXPLAIN` em um método separado no `QueryRunner` antes de abrir a conexão de execução.
- **Motivo do descarte:** Fazer o `EXPLAIN` na mesma conexão/sessão garante que o `SET LOCAL statement_timeout` e `SET TRANSACTION READ ONLY` já protejam o próprio `EXPLAIN`, e reutiliza o mesmo pool de conexões sem abrir duas conexões sucessivas.

### 2. Tratamento de Exceções e Resposta à IA

- **Abordagem:**
  Criar a classe de erro em `src/observatorio_maria/query/errors.py`:
  ```python
  class QueryCostExceededError(QueryExecutionError):
      def __init__(self, total_cost: float, max_cost: float):
          self.total_cost = total_cost
          self.max_cost = max_cost
          super().__init__(
              f'Custo estimado excessivo ({total_cost:.0f} > limite {max_cost:.0f})'
          )
  ```
  No `QueryRunner.query_data` em `src/observatorio_maria/query/tool.py`:
  ```python
  except QueryCostExceededError as exc:
      return {
          'error': (
              f'Consulta recusada por custo estimado excessivo '
              f'({exc.total_cost:.0f} > limite {exc.max_cost:.0f}). '
              'Refine os filtros usando colunas indexadas, anos específicos '
              'ou MATCH_TEXT para reduzir o espaço de busca.'
          ),
          'calls_left': self.calls_left,
      }
  ```
  Isso não quebra a conversa, não dispara erro HTTP 500/502 e devolve a mensagem à ferramenta para que a Maria tente uma consulta mais cirúrgica dentro de seu orçamento.

### 3. Diferenciação de Dialetos (PostgreSQL vs SQLite)

- **PostgreSQL:** Suporte completo com extração do nó `Total Cost`.
- **SQLite:** Em ambiente SQLite (testes locais e SQLite de origem de mock), o comando `EXPLAIN QUERY PLAN` retorna linhas textuais (`id`, `parent`, `notused`, `detail`) sem um número arbitrário de custo. Nesses casos, o sistema executa o `EXPLAIN QUERY PLAN` para assegurar que a sintaxe e o plano são avaliados sem erro, mas não impõe o teto numérico, permitindo que os testes existentes em SQLite continuem rápidos e compatíveis.

### 4. Configuração e Variáveis de Ambiente

- Adicionar em `src/observatorio_maria/settings.py`:
  ```python
  QUERY_MAX_ESTIMATED_COST: float = Field(
      default=50000.0,
      description='Custo estimado máximo de consulta via EXPLAIN (0 desliga).',
  )
  ```
- Passar `max_cost` das configurações para o `QueryRunner` e para `execute_readonly_query`.
- Atualizar `.env.example` e `README.md`.

## Riscos e Mitigações

- `[Risco: Estatísticas desatualizadas no PostgreSQL gerarem estimativas distorcidas de custo] → Mitigação:` O valor padrão `50000.0` é generoso o suficiente para consultas analíticas comuns com filtros razoáveis (que tipicamente custam entre 10 e 5.000 unidades de custo), barrando apenas varreduras massivas e joins descontrolados (geralmente > 100.000). Além disso, pode ser desligado definindo `QUERY_MAX_ESTIMATED_COST=0`.
- `[Risco: Sobrecarga de latência na chamada de EXPLAIN] → Mitigação:` No PostgreSQL, `EXPLAIN` sem `ANALYZE` leva menos de 2ms no servidor de banco de dados por não acessar páginas de dados no disco.
