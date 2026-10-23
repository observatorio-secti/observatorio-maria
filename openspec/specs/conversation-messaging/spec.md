# conversation-messaging Specification

## Purpose
Define como o usuário conversa com a Maria: envio de mensagens, resposta do modelo com o contexto da conversa, histórico persistido e o contrato de blocos tipados que o frontend usa para renderizar texto, gráficos e tabelas.

## Requirements

### Requirement: Conteúdo em blocos tipados
Toda mensagem SHALL expor `content` como uma lista ordenada de blocos. Cada bloco MUST ter o campo discriminador `type`. Os tipos do contrato são `text` (`text` em Markdown), `chart` (`chart_type`, `title`, `x`, `series`, `data`) e `table` (`title`, `columns`, `rows`). Novos tipos SHALL ser adicionados sem alterar os existentes.

#### Scenario: Resposta textual
- **WHEN** o modelo responde "Olá, sou a Maria"
- **THEN** a mensagem do assistente tem `content` igual a `[{"type": "text", "text": "Olá, sou a Maria"}]`

#### Scenario: Contrato publicado
- **WHEN** o cliente consulta o esquema OpenAPI da API
- **THEN** os schemas dos blocos `text`, `chart` e `table` estão presentes, discriminados por `type`

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

### Requirement: Contexto da conversa
Ao gerar uma resposta, o sistema SHALL enviar ao modelo as instruções de sistema da Maria seguidas do histórico da conversa em ordem cronológica e da nova mensagem do usuário.

#### Scenario: Histórico enviado ao modelo
- **WHEN** a conversa já tem uma troca anterior e o usuário envia uma nova mensagem
- **THEN** o modelo recebe a instrução de sistema, a mensagem anterior do usuário, a resposta anterior do assistente e a nova mensagem, nessa ordem

### Requirement: Falha do modelo
Quando o modelo falhar, o sistema SHALL responder 502 e MUST NOT persistir a mensagem do usuário nem uma resposta parcial, mantendo a conversa inalterada.

#### Scenario: Provedor indisponível
- **WHEN** o modelo lança um erro durante a geração
- **THEN** o sistema responde 502 e o histórico da conversa continua igual ao anterior ao envio

### Requirement: Título automático
Quando a conversa não tiver título, o sistema SHALL definir o título a partir da primeira mensagem do usuário, limitado a 60 caracteres.

#### Scenario: Primeira mensagem define o título
- **WHEN** uma conversa sem título recebe a mensagem "Quantas bolsas de pesquisa a FAPESB concedeu em 2024?"
- **THEN** o título da conversa passa a ser o início dessa mensagem, com no máximo 60 caracteres

#### Scenario: Título existente preservado
- **WHEN** uma conversa com título "Bolsas" recebe uma mensagem
- **THEN** o título continua "Bolsas"

### Requirement: Histórico de mensagens
O sistema SHALL listar as mensagens de uma conversa em ordem cronológica, com `id`, `conversation_id`, `role`, `content` e `created_at`, sem metadados internos de modelo, e SHALL responder 404 para conversa inexistente.

#### Scenario: Listagem do histórico
- **WHEN** a conversa tem uma troca de mensagens e o cliente envia `GET /conversations/{id}/messages`
- **THEN** o sistema responde 200 com a mensagem do usuário seguida da mensagem do assistente, sem `model_tier` nem `model_name`

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
