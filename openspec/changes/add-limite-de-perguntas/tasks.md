# Tasks

## 1. Limite de perguntas e teto de tokens opcional

- [x] 1.1 Em `settings.py`, acrescentar `CONVERSATION_MAX_QUESTIONS: int = Field(10, ge=0)` e mudar o padrão de `CONVERSATION_TOKEN_CEILING` para `0` (D3). Atualizar `.env.example`, a tabela de configuração do README e a seção de segurança, que hoje descreve o teto de tokens como bloqueio padrão. Teste: um valor negativo de `CONVERSATION_MAX_QUESTIONS` é recusado na criação de `Settings`.
- [x] 1.2 No `ChatService`, criar a checagem assíncrona dos dois limites (D1, D2): contagem das mensagens `user` da conversa contra `CONVERSATION_MAX_QUESTIONS` e o teto de tokens quando ligado. Criar `ConversationQuestionLimitExceededError`, com a mensagem "Limite de N perguntas da conversa atingido. Inicie uma nova conversa para continuar." Usar a checagem no início de `stream_message` e na dependência do router, que passa a ser assíncrona e traduz os dois erros em 429. Testes em `tests/test_messages.py` e `tests/test_streaming.py`:
  - com 10 perguntas gravadas e limite 10, a resposta é 429, e nada é gravado nem o modelo é chamado;
  - com 9 perguntas, a resposta é normal;
  - com limite 3 e 3 perguntas, a resposta é 429;
  - com limite 0 e 50 perguntas, a resposta é normal;
  - o streaming é recusado com 429 antes de começar.
- [x] 1.3 Fazer os testes do teto de tokens (`test_send_message_rejects_when_token_ceiling_reached` e `test_stream_rejects_when_token_ceiling_reached`) configurarem `CONVERSATION_TOKEN_CEILING` explicitamente. Acrescentar o cenário do teto desligado por padrão: com 500.000 tokens e 2 perguntas, a resposta é normal.

## 2. Demo e verificação

- [x] 2.1 Verificar no navegador, no desktop e a 375px, com `CONVERSATION_MAX_QUESTIONS=1` só na API de dev: a segunda pergunta de uma conversa mostra o banner com a mensagem de limite de perguntas e a orientação de usar "+ Nova conversa", e a pergunta não fica na conversa. Se a mensagem não couber bem no banner, ajustar `demo/app.js`. Voltar a configuração de dev ao padrão no fim.
- [x] 2.2 Rodar `task test` (lint, testes e cobertura) sem falhas.

## Resultados da verificação (2026-10-28)

- **2.1:** com `CONVERSATION_MAX_QUESTIONS=1` só na API de dev, uma nova mensagem numa conversa com uma pergunta foi recusada com 429. Isso foi verificado no desktop e a 375px, sem rolagem horizontal.
  - A pergunta não entrou na conversa; o texto ficou na caixa para reenviar.
  - O banner juntava a mensagem da API, que já termina em ponto, com um "." e a orientação da demo, e saía "...para continuar.. Crie uma nova conversa...". O `demo/app.js` passou a tirar a pontuação final da mensagem e a orientação do 429 virou "Use o botão "+ Nova conversa"."
  - O banner ficou: "Erro 429: Limite de 1 pergunta da conversa atingido. Inicie uma nova conversa para continuar. Use o botão "+ Nova conversa"."
  - A configuração de dev voltou ao padrão.
- **2.2:** `task test` passou com 243 testes, lint limpo e 96% de cobertura.

## Workflow follow-up

- Sincronizar as specs e arquivar com `/opsx:archive`. Pode ser antes ou depois da `add-fonte-simcc`, porque nenhuma das duas depende da outra.
- Commits no padrão do histórico: `docs(openspec): planeja add-limite-de-perguntas`, depois `feat: ...` com "Implementa openspec/changes/add-limite-de-perguntas." e por fim `docs(openspec): arquiva add-limite-de-perguntas`.
