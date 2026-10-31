# Proposal

## Why

Cada conversa aceita `CONVERSATION_MAX_QUESTIONS` perguntas, mas quem conversa só descobre o limite quando recebe a recusa (issue #7). Mostrar quantas perguntas restam evita a surpresa e dá tempo de pedir o que falta antes de abrir outra conversa.

## What Changes

- **Contagem na API:** `GET /conversations/{id}` passa a devolver `questions_asked` e `questions_limit`. Com o limite desligado, `questions_limit` é nulo.
- **Contador na demo:** perto do campo de mensagem, a página mostra quantas perguntas restam e atualiza a cada resposta.
- **Aviso:** o contador ganha destaque na última pergunta disponível e, ao zerar, orienta a usar "+ Nova conversa".
- **Documentação:** tabela de rotas do `README.md` e nota sobre o limite de perguntas.

### Fora do escopo

- Contagem na listagem e nas respostas de `POST` e `PATCH`: exigiria uma consulta por conversa, e a demo não precisa dela.
- Contador do teto de tokens (`CONVERSATION_TOKEN_CEILING`).
- Bloquear o envio na demo ao zerar: a recusa continua vindo da API, com o banner atual.
- Evento SSE com a contagem: a demo já relê a conversa ao fim de cada resposta.

## Capabilities

### New Capabilities

Nenhuma.

### Modified Capabilities

- `conversation-management`: `GET /conversations/{id}` passa a informar a contagem e o limite de perguntas.
- `demo-page`: contador de perguntas restantes e aviso da última pergunta.

## Impact

- **Código:** `schemas.py`, `routers/conversations.py`, `services/chat.py`, `demo/app.js`, `demo/index.html` e `demo/styles.css`.
- **API:** dois campos novos em `GET /conversations/{id}`, sem quebra. Os demais endpoints não mudam.
- **Banco da Maria:** sem migração; a contagem usa as mensagens gravadas.
- **Bancos externos:** não toca.
- **Segredos:** não toca.
- **Endpoints sem autenticação:** o endpoint já existente continua sem autenticação e passa a expor o limite configurado, que não é sensível.
