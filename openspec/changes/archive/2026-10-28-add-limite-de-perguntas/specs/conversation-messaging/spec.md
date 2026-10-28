## ADDED Requirements

### Requirement: Limite de perguntas por conversa
Quando a conversa já tiver `CONVERSATION_MAX_QUESTIONS` perguntas gravadas, o sistema SHALL recusar uma nova mensagem com HTTP 429 e uma mensagem que oriente a iniciar uma nova conversa. A recusa MUST NOT chamar o modelo nem gravar mensagens, tanto no envio comum quanto no streaming. Conta como pergunta cada mensagem do usuário gravada na conversa.

#### Scenario: Envio comum bloqueado na pergunta seguinte ao limite
- **WHEN** a conversa tem 10 perguntas gravadas, o limite é 10 e o cliente envia `POST /conversations/{id}/messages`
- **THEN** o sistema responde 429 com detalhe informando que o limite de perguntas foi atingido, e a conversa continua com 10 perguntas

#### Scenario: Streaming bloqueado antes do início
- **WHEN** a conversa atingiu o limite de perguntas e o cliente envia mensagem ao endpoint de streaming
- **THEN** o sistema responde 429 sem iniciar o stream e sem chamar o modelo

#### Scenario: Última pergunta permitida
- **WHEN** a conversa tem 9 perguntas gravadas e o limite é 10
- **THEN** a nova mensagem é respondida normalmente

### Requirement: Configuração do limite de perguntas
O limite de perguntas SHALL ser configurado por `CONVERSATION_MAX_QUESTIONS`, com padrão 10. O valor `0` MUST desligar o limite. Valores negativos MUST impedir a inicialização da aplicação.

#### Scenario: Limite desligado
- **WHEN** `CONVERSATION_MAX_QUESTIONS` é 0 e a conversa tem 50 perguntas gravadas
- **THEN** a nova mensagem é respondida normalmente

#### Scenario: Limite configurado
- **WHEN** `CONVERSATION_MAX_QUESTIONS` é 3 e a conversa tem 3 perguntas gravadas
- **THEN** a nova mensagem é recusada com 429

## MODIFIED Requirements

### Requirement: Teto de tokens por conversa
Quando `CONVERSATION_TOKEN_CEILING` for maior que zero e a conversa atingir ou exceder esse teto de tokens, o sistema SHALL recusar o envio de novas mensagens respondendo HTTP 429 com mensagem instrutiva e MUST NOT chamar o modelo nem persistir novas mensagens, tanto no envio comum quanto no endpoint de streaming. O padrão de `CONVERSATION_TOKEN_CEILING` SHALL ser `0`, que desliga o teto.

#### Scenario: Envio comum bloqueado por teto de tokens
- **WHEN** o cliente envia `POST /conversations/{id}/messages` para uma conversa cujo `total_tokens` atingiu ou superou o teto
- **THEN** o sistema responde 429 com detalhe informando que o teto de tokens foi atingido

#### Scenario: Streaming bloqueado antes do início
- **WHEN** o cliente envia mensagem ao endpoint de streaming para conversa com teto atingido
- **THEN** o sistema responde 429 sem iniciar o stream

#### Scenario: Teto desligado por padrão
- **WHEN** `CONVERSATION_TOKEN_CEILING` não está definido e a conversa acumulou 500.000 tokens com 2 perguntas
- **THEN** a nova mensagem é respondida normalmente
