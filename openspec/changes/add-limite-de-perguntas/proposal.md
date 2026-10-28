# Proposal

## Why

Com o fomento e o Simcc no contexto, cada resposta da Maria passou a gastar de 27 a 50 mil tokens. Uma pergunta só com o fomento gastava 8 mil. Os números foram medidos na verificação da `add-fonte-simcc`. Com o teto padrão de 100 mil tokens por conversa, a conversa é bloqueada na terceira pergunta. Subir o teto para manter cerca de 10 perguntas exigiria 400 mil tokens, e o usuário preferiu não fazer isso: um limite em perguntas é previsível para quem conversa e não depende do tamanho do contexto.

## What Changes

- **Limite de perguntas por conversa:** a nova configuração `CONVERSATION_MAX_QUESTIONS` (padrão 10, `0` desliga) limita quantas perguntas uma conversa recebe. Ao atingir o limite, o envio de uma nova mensagem responde HTTP 429 com orientação para iniciar uma nova conversa, sem chamar o modelo e sem gravar nada. Vale tanto para o envio comum quanto para o streaming, como o teto de tokens.
- **Teto de tokens desligado por padrão:** `CONVERSATION_TOKEN_CEILING` continua existindo e funcionando, mas o padrão passa de 100.000 para `0`. Quem opera pode ligá-lo como trava de custo. **BREAKING** para ambientes que dependiam do padrão sem defini-lo no `.env`.
- **Tokens continuam contados:** `total_tokens` segue acumulado em cada conversa, para observação e para o teto opcional.
- **Demo:** o banner de HTTP 429 passa a cobrir também o limite de perguntas, com a mensagem da API.
- **Documentação:** `.env.example`, a tabela de configuração do README e a seção de segurança passam a descrever o limite de perguntas e o teto de tokens opcional.

### Fora do escopo

- Reduzir o consumo de tokens por resposta, por exemplo enviando ao modelo só as fontes relevantes para cada pergunta. Isso vai ser explorado e proposto numa mudança própria.
- Mostrar na API ou na demo quantas perguntas ainda restam na conversa.
- Limites por usuário ou por período: ainda não há autenticação.

## Capabilities

### New Capabilities

Nenhuma.

### Modified Capabilities

- `conversation-messaging`: novo limite de perguntas por conversa; teto de tokens passa a ser opcional e desligado por padrão.
- `demo-page`: banner de HTTP 429 também para o limite de perguntas.

## Impact

- **Código:**
  - `settings.py` ganha `CONVERSATION_MAX_QUESTIONS` e muda o padrão de `CONVERSATION_TOKEN_CEILING`;
  - `services/chat.py` passa a checar os dois limites antes de chamar o modelo;
  - `routers/conversations.py` é a dependência que responde 429 no envio comum;
  - `demo/app.js` recebe ajuste no texto do banner, se necessário.
- **Testes:** `tests/test_messages.py` e `tests/test_streaming.py`. Os testes do teto de tokens passam a configurá-lo explicitamente.
- **Banco da Maria:** nenhuma migração. As perguntas são contadas a partir das mensagens de usuário já gravadas.
- **Bancos externos:** nenhum acesso novo.
- **Segredos:** nenhum.
- **Endpoints sem autenticação:** nenhum novo. Os endpoints de envio de mensagem passam a responder 429 também pelo limite de perguntas.
- **Dependências:** não depende de mudança em andamento. Corrige um efeito da `add-fonte-simcc`, ainda não arquivada, mas pode ser arquivada antes ou depois dela.
