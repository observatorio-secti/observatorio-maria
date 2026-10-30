# Spec Delta

## ADDED Requirements

### Requirement: Botões de continuação
A página SHALL mostrar os blocos `suggestions` como botões, apenas na última mensagem da conversa. Clicar num botão SHALL enviar a pergunta como mensagem. Enquanto uma resposta é gerada, os botões MUST ficar ocultos.

#### Scenario: Última resposta
- **WHEN** a conversa tem duas respostas com sugestões
- **THEN** só a última mostra os botões

#### Scenario: Enviar uma continuação
- **WHEN** o usuário clica num botão de continuação
- **THEN** a pergunta é enviada e os botões da resposta anterior somem

#### Scenario: Conversa reaberta
- **WHEN** o usuário reabre uma conversa cuja última resposta tem sugestões
- **THEN** os botões aparecem
