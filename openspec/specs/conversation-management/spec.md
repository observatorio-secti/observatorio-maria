# conversation-management Specification

## Purpose
Permite criar, listar, consultar, renomear e excluir as conversas mantidas com a Maria, servindo de base para o histórico exibido no frontend.

## Requirements

### Requirement: Criar conversa
O sistema SHALL permitir criar uma conversa com título opcional, retornando HTTP 201 com `id`, `title`, `created_at` e `updated_at`. Sem título informado, o título SHALL ser nulo. Títulos informados MUST ter entre 1 e 200 caracteres.

#### Scenario: Criação com título
- **WHEN** o cliente envia `POST /conversations` com `{"title": "Pesquisa em Salvador"}`
- **THEN** o sistema responde 201 com a conversa criada e `title` igual a "Pesquisa em Salvador"

#### Scenario: Criação sem título
- **WHEN** o cliente envia `POST /conversations` com corpo `{}`
- **THEN** o sistema responde 201 com a conversa criada e `title` nulo

#### Scenario: Título inválido
- **WHEN** o cliente envia `POST /conversations` com `{"title": ""}`
- **THEN** o sistema responde 422

### Requirement: Listar conversas
O sistema SHALL listar as conversas paginadas por `offset` (padrão 0) e `limit` (padrão 20, máximo 100), ordenadas pela última atualização, contendo para cada conversa seus campos públicos incluindo `total_tokens`. A resposta SHALL conter `conversations` e `total`.

#### Scenario: Listagem ordenada
- **WHEN** existem duas conversas e a segunda foi atualizada por último
- **THEN** `GET /conversations` retorna a segunda conversa antes da primeira e `total` igual a 2

#### Scenario: Paginação
- **WHEN** existem três conversas e o cliente envia `GET /conversations?offset=1&limit=1`
- **THEN** o sistema retorna apenas uma conversa e `total` igual a 3

#### Scenario: Listagem inclui contagem de tokens
- **WHEN** o cliente lista conversas via `GET /conversations`
- **THEN** cada conversa listada contém `total_tokens`

### Requirement: Consultar conversa
O sistema SHALL retornar os dados de uma conversa pelo seu identificador, incluindo `total_tokens` (inteiro maior ou igual a zero), e SHALL responder 404 quando ela não existir.

#### Scenario: Conversa existente
- **WHEN** o cliente envia `GET /conversations/{id}` para uma conversa existente
- **THEN** o sistema responde 200 com os dados da conversa

#### Scenario: Conversa inexistente
- **WHEN** o cliente envia `GET /conversations/{id}` para um identificador que não existe
- **THEN** o sistema responde 404

#### Scenario: Conversa com contagem de tokens
- **WHEN** o cliente consulta uma conversa existente via `GET /conversations/{id}`
- **THEN** a resposta 200 contém `total_tokens`

### Requirement: Renomear conversa
O sistema SHALL permitir alterar o título de uma conversa existente, atualizando `updated_at`, e SHALL responder 404 quando ela não existir.

#### Scenario: Renomeação bem-sucedida
- **WHEN** o cliente envia `PATCH /conversations/{id}` com `{"title": "Novo título"}`
- **THEN** o sistema responde 200 com `title` igual a "Novo título"

#### Scenario: Renomear conversa inexistente
- **WHEN** o cliente envia `PATCH /conversations/{id}` para um identificador que não existe
- **THEN** o sistema responde 404

### Requirement: Excluir conversa
O sistema SHALL excluir uma conversa e todas as suas mensagens, respondendo 204, e SHALL responder 404 quando ela não existir.

#### Scenario: Exclusão bem-sucedida
- **WHEN** o cliente envia `DELETE /conversations/{id}` para uma conversa com mensagens
- **THEN** o sistema responde 204 e um `GET /conversations/{id}` posterior responde 404

#### Scenario: Excluir conversa inexistente
- **WHEN** o cliente envia `DELETE /conversations/{id}` para um identificador que não existe
- **THEN** o sistema responde 404
