# Design

## Context

Motivação em `proposal.md`. `streamEvents` usa `fetch` sem sinal de cancelamento. Em erro, `sendMessage` remove a pergunta e o texto parcial, e como o campo só é limpo no sucesso, a pergunta já fica nele. A API interrompe a geração e não grava nada quando a conexão fecha. O envio pelo teclado usa o mesmo formulário.

## Goals / Non-Goals

**Goals:**
- Parar sem deixar registros parciais.

**Non-Goals:**
- Testes automatizados de JavaScript: a demo não tem essa suíte, e a verificação é no navegador.

## Decisions

### D1. `AbortController` no `fetch`

`streamEvents` recebe `signal`, e `state.abort` guarda o controlador durante a geração.

Descartada: rota de cancelamento na API. Fechar a conexão já interrompe e descarta a resposta.

### D2. Parar no clique do botão, não no envio do formulário

O clique em Parar chama `abort` e cancela o envio. O `submit` continua ignorado durante a geração, para Enter não interromper uma resposta por engano.

Descartada: tratar parar dentro de `sendMessage`. Enter passaria a parar a geração.

### D3. Cancelamento desligado ao chegar a resposta gravada

Em `message.assistant`, `state.abort` volta a nulo. Assim um clique tardio não remove da tela uma pergunta já gravada.

Descartada: remover a pergunta sempre que houver abort. A tela ficaria diferente do banco.

### D4. Reenvio pelo próprio fluxo de envio

"Tentar novamente" recoloca a pergunta no campo e chama `requestSubmit`, com todos os cuidados do envio normal.

Descartada: uma função separada de reenvio, que repetiria o tratamento do stream.

## Risks / Trade-offs

- [Risco] Parar no instante em que a API grava → A resposta pode ficar no banco e reaparecer ao reabrir a conversa; é raro e não corrompe dados.
- [Risco] A consulta em andamento na origem seguir até o fim → Continua limitada por `QUERY_TIMEOUT_SECONDS`.
