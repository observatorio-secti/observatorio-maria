# demo-page Specification Delta

## Requirements

### MODIFIED Requirement: Feedback durante a geração
Enquanto aguarda a resposta, a página SHALL indicar que a Maria está respondendo até o primeiro fragmento chegar e exibir o texto progressivamente. Caso a API retorne HTTP 429 por teto de tokens da conversa excedido, a página MUST exibir banner com mensagem explicativa e orientação para criar uma nova conversa.

#### Scenario: Banner de limite de tokens
- **WHEN** o usuário tenta enviar mensagem para conversa com cota de tokens esgotada
- **THEN** a página exibe banner informando que o teto de tokens da conversa foi atingido e orientando a iniciar uma nova conversa
