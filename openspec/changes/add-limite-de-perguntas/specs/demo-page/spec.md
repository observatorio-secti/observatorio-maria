## ADDED Requirements

### Requirement: Banner de limite de perguntas
Quando a API recusar uma mensagem com HTTP 429 porque a conversa atingiu o limite de perguntas, a página SHALL remover a pergunta não enviada e exibir um banner com a mensagem da API e a orientação de criar uma nova conversa.

#### Scenario: Conversa no limite de perguntas
- **WHEN** o usuário envia uma pergunta numa conversa que atingiu o limite de perguntas
- **THEN** a página exibe o banner com a mensagem de limite de perguntas e a orientação para usar "+ Nova conversa", e a pergunta não fica na conversa
