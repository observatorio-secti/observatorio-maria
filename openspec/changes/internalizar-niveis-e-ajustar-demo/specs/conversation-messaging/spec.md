# Spec Delta

## MODIFIED Requirements

### Requirement: Enviar mensagem
O sistema SHALL aceitar uma mensagem de texto (1 a 10.000 caracteres) como único campo do corpo, responder 201 com a mensagem do usuário e a resposta do assistente, e persistir ambas na conversa. Campos adicionais MUST ser rejeitados com 422.

#### Scenario: Mensagem respondida
- **WHEN** o cliente envia `POST /conversations/{id}/messages` com `{"content": "Oi"}`
- **THEN** o sistema responde 201 com `user_message` (role `user`) e `assistant_message` (role `assistant`)

#### Scenario: Escolha de nível
- **WHEN** o cliente envia a mensagem com `{"content": "Oi", "model": "fast"}`
- **THEN** o sistema responde 422 e nada é gravado

#### Scenario: Nível inválido
- **WHEN** o cliente envia a mensagem com `{"content": "Oi", "model": "ultra"}`
- **THEN** o sistema responde 422, da mesma forma que para qualquer outro campo extra

#### Scenario: Conversa inexistente
- **WHEN** o cliente envia uma mensagem para uma conversa que não existe
- **THEN** o sistema responde 404

### Requirement: Histórico de mensagens
O sistema SHALL listar as mensagens de uma conversa em ordem cronológica, com `id`, `conversation_id`, `role`, `content` e `created_at`, sem metadados internos de modelo, e SHALL responder 404 para conversa inexistente.

#### Scenario: Listagem do histórico
- **WHEN** a conversa tem uma troca de mensagens e o cliente envia `GET /conversations/{id}/messages`
- **THEN** o sistema responde 200 com a mensagem do usuário seguida da mensagem do assistente, sem `model_tier` nem `model_name`
