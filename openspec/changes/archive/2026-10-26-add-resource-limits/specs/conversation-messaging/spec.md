# conversation-messaging Specification Delta

## Requirements

### ADDED Requirement: Teto de tokens por conversa
Quando a conversa atingir ou exceder o teto configurado de tokens (`CONVERSATION_TOKEN_CEILING`), o sistema SHALL recusar o envio de novas mensagens respondendo HTTP 429 com mensagem instrutiva e MUST NOT chamar o modelo nem persistir novas mensagens, tanto no envio comum quanto no endpoint de streaming.

#### Scenario: Envio comum bloqueado por teto de tokens
- **WHEN** o cliente envia `POST /conversations/{id}/messages` para uma conversa cujo `total_tokens` atingiu ou superou o teto
- **THEN** o sistema responde 429 com detalhe informando que o teto de tokens foi atingido

#### Scenario: Streaming bloqueado antes do início
- **WHEN** o cliente envia mensagem ao endpoint de streaming para conversa com teto atingido
- **THEN** o sistema responde 429 sem iniciar o stream

### ADDED Requirement: Contabilização de tokens da resposta
Ao concluir a geração de uma resposta, o sistema SHALL obter os tokens consumidos na troca (tokens de entrada e de saída informados pelos metadados de uso do modelo) e somá-los ao total acumulado de tokens da conversa (`total_tokens`), persistindo o valor atualizado juntamente com as mensagens.

#### Scenario: Tokens acumulados na conversa
- **WHEN** o modelo gera uma resposta consumindo 150 tokens de entrada e 50 tokens de saída
- **THEN** a conversa tem seu `total_tokens` incrementado em 200
