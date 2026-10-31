# Spec Delta

## ADDED Requirements

### Requirement: Contagem de perguntas da conversa
`GET /conversations/{id}` SHALL devolver `questions_asked`, com o número de mensagens do usuário gravadas, e `questions_limit`, com o valor de `CONVERSATION_MAX_QUESTIONS`. Com o limite desligado, `questions_limit` MUST ser nulo. A consulta MUST funcionar sem modelo de linguagem configurado.

#### Scenario: Conversa com perguntas
- **WHEN** a conversa tem 3 perguntas gravadas, o limite é 10 e o cliente envia `GET /conversations/{id}`
- **THEN** a resposta traz `questions_asked` igual a 3 e `questions_limit` igual a 10

#### Scenario: Conversa nova
- **WHEN** o cliente consulta uma conversa sem mensagens
- **THEN** a resposta traz `questions_asked` igual a 0

#### Scenario: Limite desligado
- **WHEN** `CONVERSATION_MAX_QUESTIONS` é 0 e a conversa tem 5 perguntas gravadas
- **THEN** a resposta traz `questions_asked` igual a 5 e `questions_limit` nulo

#### Scenario: Pergunta interrompida
- **WHEN** o usuário interrompe a resposta e nada é gravado
- **THEN** `questions_asked` não muda

#### Scenario: Sem chave de modelo
- **WHEN** nenhum modelo de linguagem está configurado e o cliente consulta uma conversa
- **THEN** o sistema responde 200 com a contagem
