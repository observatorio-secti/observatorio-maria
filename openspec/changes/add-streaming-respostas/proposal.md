# Proposal

## Why

Hoje a resposta da Maria só aparece depois de gerada por completo, o que leva vários segundos. Exibir o texto enquanto ele é gerado (streaming) reduz a espera percebida e deixa a conversa natural. A API precisa oferecer isso sem abrir mão das garantias atuais: persistência atômica, contrato de blocos e observabilidade.

## What Changes

- Novo endpoint `POST /conversations/{id}/messages/stream`, que responde com **Server-Sent Events** (SSE):
  - `message.user`: a mensagem do usuário;
  - `content.delta`: fragmentos de texto, cada um com o índice do bloco a que pertence;
  - `message.assistant`: a mensagem final, já persistida;
  - `error`: falha do modelo durante a geração.
- O fluxo de geração passa a ser único: o envio sem streaming (`POST .../messages`) consome o mesmo fluxo interno e mantém o contrato atual.
- Persistência continua atômica: pergunta e resposta só são gravadas quando a geração termina com sucesso. Uma falha ou a desconexão do cliente não deixam registros parciais.
- A demo passa a usar o streaming: o texto aparece progressivamente, renderizado em Markdown.
- As respostas em streaming geram os mesmos traces, métricas e logs das respostas completas.

## Capabilities

### New Capabilities
<!-- Nenhuma. -->

### Modified Capabilities
- `conversation-messaging`: novo envio com streaming via SSE, com eventos e regras de falha e interrupção.
- `demo-page`: o feedback durante a geração passa a ser o próprio texto aparecendo progressivamente.
- `observability`: o caminho da IA também é rastreado nas respostas em streaming.

## Impact

- API: novo endpoint SSE. O envio sem streaming não muda.
- Código: `services/chat.py` (fluxo de geração como gerador assíncrono), `routers/conversations.py`, `schemas.py` (eventos), `demo/app.js`.
- Testes: novos testes do endpoint SSE, incluindo falha no meio do stream e telemetria em streaming.
- Dependências: nenhuma nova (SSE nativo do FastAPI).
