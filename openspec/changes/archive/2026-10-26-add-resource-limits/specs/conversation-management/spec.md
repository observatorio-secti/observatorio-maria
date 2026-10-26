# conversation-management Specification Delta

## Requirements

### MODIFIED Requirement: Consultar conversa
O sistema SHALL retornar os dados de uma conversa pelo seu identificador, incluindo `total_tokens` (inteiro maior ou igual a zero), e SHALL responder 404 quando ela não existir.

#### Scenario: Conversa com contagem de tokens
- **WHEN** o cliente consulta uma conversa existente via `GET /conversations/{id}`
- **THEN** a resposta 200 contém `total_tokens`

### MODIFIED Requirement: Listar conversas
O sistema SHALL listar as conversas paginadas por `offset` (padrão 0) e `limit` (padrão 20, máximo 100), ordenadas pela última atualização, contendo para cada conversa seus campos públicos incluindo `total_tokens`. A resposta SHALL conter `conversations` e `total`.

#### Scenario: Listagem inclui contagem de tokens
- **WHEN** o cliente lista conversas via `GET /conversations`
- **THEN** cada conversa listada contém `total_tokens`
