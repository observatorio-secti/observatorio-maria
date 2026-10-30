# Spec Delta

## ADDED Requirements

### Requirement: Perguntas de continuação
Uma resposta que consultou dados SHALL terminar com um bloco `suggestions` com até 3 perguntas de continuação, cada uma terminada em `?` e com até 120 caracteres. Sem pergunta válida, o bloco MUST ficar de fora.

#### Scenario: Resposta com consulta
- **WHEN** a Maria responde usando uma consulta e o modelo sugere quatro perguntas
- **THEN** o último bloco é `suggestions`, com as três primeiras

#### Scenario: Linhas inválidas
- **WHEN** o modelo devolve linhas sem `?`, numeradas ou repetidas
- **THEN** o bloco traz só as perguntas válidas, sem numeração nem repetição

#### Scenario: Resposta sem consulta
- **WHEN** a Maria responde sem consultar dados
- **THEN** a resposta não tem bloco `suggestions` e nenhuma chamada extra é feita

#### Scenario: Última pergunta da conversa
- **WHEN** a pergunta atual é a última permitida por `CONVERSATION_MAX_QUESTIONS`
- **THEN** a resposta não tem bloco `suggestions`

### Requirement: Falha nas sugestões não afeta a resposta
Falha, demora acima de 10 segundos ou saída sem perguntas válidas MUST deixar a resposta sem o bloco `suggestions`, sem erro ao cliente. A resposta MUST ser gravada normalmente.

#### Scenario: Modelo falha nas sugestões
- **WHEN** a chamada de sugestões falha depois de a resposta ser gerada
- **THEN** a resposta é gravada sem o bloco, e o cliente não recebe `error`

### Requirement: Sugestões fora do histórico
O bloco `suggestions` MUST NOT ser enviado ao modelo nas perguntas seguintes. No streaming, ele SHALL chegar como `content.delta` depois dos demais blocos.

#### Scenario: Pergunta seguinte
- **WHEN** a conversa tem uma resposta anterior com `suggestions` e o usuário envia outra pergunta
- **THEN** o histórico enviado ao modelo não contém as sugestões

#### Scenario: Ordem no streaming
- **WHEN** a resposta tem texto, um gráfico e sugestões
- **THEN** os deltas chegam nessa ordem, antes de `message.assistant`
