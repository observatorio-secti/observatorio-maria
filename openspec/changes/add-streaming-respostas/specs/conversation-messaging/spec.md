# Spec Delta

## ADDED Requirements

### Requirement: Envio com streaming
O sistema SHALL oferecer `POST /conversations/{id}/messages/stream`, com o mesmo corpo do envio comum, respondendo em Server-Sent Events na ordem: um `message.user`, zero ou mais `content.delta` e um `message.assistant` com a mensagem persistida. Validação, conversa inexistente e indisponibilidade dos modelos MUST responder antes do stream, com os mesmos códigos HTTP do envio comum.

#### Scenario: Resposta transmitida em partes
- **WHEN** o cliente envia `{"content": "Oi"}` para o endpoint de streaming
- **THEN** recebe `message.user`, depois eventos `content.delta` cuja concatenação é o texto da resposta e, por fim, `message.assistant` com a resposta completa

#### Scenario: Mensagem final persistida
- **WHEN** o stream termina com `message.assistant`
- **THEN** o histórico da conversa contém a pergunta e a resposta, com os mesmos ids enviados nos eventos

#### Scenario: Conversa inexistente no streaming
- **WHEN** o cliente envia uma mensagem ao endpoint de streaming de uma conversa que não existe
- **THEN** o sistema responde 404 sem iniciar o stream

### Requirement: Fragmentos por bloco
Cada evento `content.delta` SHALL conter `index` (posição do bloco no `content` final), `type` (o tipo do bloco) e o fragmento. Para blocos `text`, o fragmento vem em `text`.

#### Scenario: Delta de texto
- **WHEN** o modelo gera o fragmento "Olá"
- **THEN** o cliente recebe `content.delta` com `{"index": 0, "type": "text", "text": "Olá"}`

### Requirement: Falha durante o streaming
Se o modelo falhar depois de iniciado o stream, o sistema SHALL enviar um evento `error` com `detail` e encerrar o stream, e MUST NOT persistir a pergunta nem a resposta parcial.

#### Scenario: Modelo falha no meio da geração
- **WHEN** o modelo falha após o início do stream
- **THEN** o cliente recebe `error` e o histórico da conversa permanece igual ao anterior ao envio

### Requirement: Interrupção pelo cliente
Se o cliente encerrar a conexão antes do fim da geração, o sistema SHALL interromper a geração e MUST NOT persistir a pergunta nem a resposta parcial.

#### Scenario: Cliente desconecta
- **WHEN** o cliente fecha a conexão após receber parte da resposta
- **THEN** nenhuma mensagem é gravada na conversa
