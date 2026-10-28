# Design

## Context

Motivação em `proposal.md`. Estado atual relevante:

- **Teto de tokens:** `ChatService.check_token_ceiling` compara `conversation.total_tokens` com `CONVERSATION_TOKEN_CEILING` e lança `ConversationTokenLimitExceededError`. A checagem acontece em dois pontos:
  - no envio comum, pela dependência `check_conversation_token_ceiling` de `routers/conversations.py`, que traduz o erro em HTTP 429;
  - no início de `stream_message`, antes de chamar o modelo.
- **Mensagens:** pergunta e resposta só são gravadas ao final de uma resposta bem-sucedida. Uma falha ou interrupção não grava nada. `messages.conversation_id` tem índice, e `role` distingue as mensagens do usuário.
- **Demo:** `demo/app.js` já trata qualquer HTTP 429: remove a pergunta não enviada e mostra um banner com a mensagem da API e a orientação de usar "+ Nova conversa".
- **Testes:** `test_send_message_rejects_when_token_ceiling_reached` e `test_stream_rejects_when_token_ceiling_reached` gravam 100.000 tokens e contam com o padrão atual do teto.

## Goals / Non-Goals

**Goals:**
- A conversa recebe até 10 perguntas, qualquer que seja o tamanho do contexto das fontes.
- O teto de tokens continua disponível como trava de custo, desligado por padrão.

**Non-Goals:**
- Reduzir os tokens por resposta: fica para a mudança de fontes relevantes por pergunta.
- Informar quantas perguntas restam.

## Decisions

### D1. Contar as mensagens do usuário já gravadas
A contagem é `COUNT(*)` em `messages`, filtrando por `conversation_id` e `role = 'user'`. Como só respostas bem-sucedidas gravam a pergunta, falhas não consomem o limite.
- *Descartado:* uma coluna `questions` em `conversations`, incrementada a cada resposta. Exigiria migração e duplicaria uma informação que já está nas mensagens. A consulta usa o índice de `conversation_id`, e uma conversa tem no máximo algumas dezenas de mensagens.

### D2. Checar os dois limites nos mesmos pontos de hoje
O `ChatService` ganha uma checagem assíncrona dos dois limites: perguntas, pela contagem, e tokens, se o teto estiver ligado. Ela roda onde hoje só se checa o teto de tokens: na dependência do router, que passa a ser assíncrona e recebe a sessão, e no início de `stream_message`. O limite de perguntas lança `ConversationQuestionLimitExceededError`, que também é traduzido em 429.
- *Descartado:* checar só no router. O streaming também precisa recusar sem chamar o modelo, e hoje ele já repete a checagem por conta própria.
- *Descartado:* juntar os dois erros numa classe genérica. Classes separadas deixam a mensagem e os testes de cada limite independentes, com uma mudança menor no código existente.

### D3. Teto de tokens com padrão `0`
O padrão de `CONVERSATION_TOKEN_CEILING` passa de 100.000 para `0`, que desliga o teto. `total_tokens` segue sendo acumulado.
- *Descartado:* subir o padrão para 400.000, o equivalente a cerca de 10 perguntas com as duas fontes. O usuário recusou: o número mudaria a cada fonte nova e não diz nada a quem conversa.
- *Descartado:* remover o teto. O usuário preferiu mantê-lo como trava opcional de custo.

### D4. Demo sem código novo
O tratamento atual de 429 na demo já mostra a mensagem da API e a orientação de criar uma conversa. A mensagem do limite de perguntas é escrita para funcionar nesse banner: "Limite de N perguntas da conversa atingido. Inicie uma nova conversa para continuar." A verificação no navegador confirma isso.
- *Descartado:* um banner próprio para o limite de perguntas. Duplicaria o mesmo comportamento.

## Risks / Trade-offs

- [Sem teto de tokens por padrão, uma conversa pode custar mais: com 10 perguntas de até ~50 mil tokens, chega perto de 500 mil] → O limite de perguntas é o controle padrão, e quem opera pode ligar `CONVERSATION_TOKEN_CEILING`. A redução por resposta fica para a mudança de fontes relevantes.
- [Ambientes que dependiam do padrão de 100.000 sem defini-lo perdem o teto] → A mudança está marcada como BREAKING na proposta, e o `.env.example` e o README explicam como ligá-lo.
- [Conversas antigas com mais de 10 perguntas ficam bloqueadas logo após o deploy] → É o comportamento esperado do limite: a orientação de criar uma nova conversa resolve, e nada é apagado.
- [Dois envios simultâneos na mesma conversa podem passar do limite em uma pergunta] → A demo já impede envios duplicados. O limite é de uso, não de segurança, então a tolerância de uma pergunta é aceitável.

## Open Questions

Nenhuma.
