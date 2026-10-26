# data-querying Specification Delta

## Requirements

### MODIFIED Requirement: Limite de linhas
Toda consulta SHALL devolver no máximo `QUERY_MAX_ROWS` linhas (padrão 100). Caso a consulta contenha cláusula `LIMIT`, o valor MUST ser inteiro positivo e MUST NOT exceder `QUERY_MAX_ROWS`; caso exceda, a consulta MUST ser recusada antes da execução. Se omitido, o limite máximo continua aplicado pelo executor, e o resultado MUST informar se foi truncado.

#### Scenario: Limite excessivo recusado
- **WHEN** o modelo envia consulta com `LIMIT 500` e `QUERY_MAX_ROWS` é 100
- **THEN** a consulta é recusada informando que o limite solicitado excede o máximo permitido

#### Scenario: Limite aceito
- **WHEN** o modelo envia consulta com `LIMIT 10`
- **THEN** a consulta é aceita e executada

#### Scenario: Resultado truncado
- **WHEN** a consulta produziria 500 linhas sem cláusula `LIMIT` e `QUERY_MAX_ROWS` é 100
- **THEN** o resultado tem 100 linhas e indica que foi truncado

### MODIFIED Requirement: Limite de tempo
Toda consulta SHALL ser interrompida após `QUERY_TIMEOUT_SECONDS` (padrão 15). Em bancos PostgreSQL, a execução MUST definir `statement_timeout` correspondente na sessão da transação para cancelamento no servidor. A interrupção por timeout de cliente ou cancelamento de statement no banco MUST virar uma recusa por tempo esgotado e MUST NOT derrubar a resposta.

#### Scenario: Consulta lenta interrompida no cliente
- **WHEN** a consulta passa do limite de tempo no cliente
- **THEN** ela é cancelada e o modelo recebe que o tempo se esgotou

#### Scenario: Consulta cancelada por statement_timeout
- **WHEN** o servidor PostgreSQL interrompe a consulta por statement_timeout
- **THEN** ela é tratada como recusa por tempo esgotado sem expor dados de conexão
