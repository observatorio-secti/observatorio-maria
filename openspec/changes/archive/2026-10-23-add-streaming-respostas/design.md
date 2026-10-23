# Design

## Context

Os requisitos estão em `specs/` e a motivação em `proposal.md`. O `ChatService.send_message` chama `model.ainvoke` dentro do span `maria.chat` e grava pergunta e resposta num único commit. O FastAPI instalado (0.161) tem suporte nativo a SSE: uma path operation com `yield` e `response_class=EventSourceResponse` emite `ServerSentEvent`s. As dependências com `yield` (a sessão do banco) usam por padrão o escopo `request`, ou seja, ficam abertas até o fim da resposta, durante todo o stream.

## Goals / Non-Goals

**Goals:**
- Um único fluxo de geração para os dois endpoints, sem duplicar regras de contexto, persistência, título e telemetria.
- Eventos SSE desenhados para o contrato de blocos: fragmentos endereçados por índice de bloco, prontos para futuros blocos não textuais.

**Non-Goals:**
- Retomada de stream (`Last-Event-ID`). Cada envio é uma geração nova.
- Streaming de blocos `chart`/`table`. Quando existirem, chegarão como bloco completo.

## Decisions

### 1. O serviço gera eventos de domínio; o router os traduz para SSE
`ChatService.stream_message(conversation, content)` é um gerador assíncrono de eventos de domínio:
- `UserMessageCreated(message)`;
- `ContentDelta(index, text)`;
- `AssistantMessageCompleted(message)`.

`send_message` consome esse mesmo gerador e devolve `(user, assistant)`, então o envio comum continua idêntico para o cliente. A tradução para `ServerSentEvent` (nomes `message.user`, `content.delta`, `message.assistant` e payloads `MessagePublic`/`ContentDeltaPublic`) fica no router, que é uma preocupação HTTP.

*Alternativa:* o serviço produzir SSE diretamente. Descartada porque acoplaria a regra de negócio ao transporte.

### 2. Geração com `astream` e agregação de chunks
O modelo é chamado com `model.astream(prompt, config)`. Cada `AIMessageChunk` com texto vira um `ContentDelta(index=0, text=...)`, e os chunks são somados (`full = full + chunk`) para obter a mensagem final, com `usage_metadata`. O `ChatOpenAI` já pede o uso de tokens no streaming por padrão (`stream_usage`), e o callback `GenAIMetricsHandler` recebe esse uso no `on_llm_end`, como antes.

### 3. Persistência no fim e nada em caso de falha ou interrupção
As mensagens só são adicionadas à sessão e commitadas depois que o stream do modelo termina. O `message.user` é enviado no início com o id e o `created_at` já definidos na criação do objeto, que são os mesmos persistidos no fim.

- **Falha do modelo:** gera `ModelInvocationError`. No endpoint de streaming, o router a converte num evento `error` e encerra o stream. No envio comum, ela continua virando 502.
- **Desconexão do cliente:** cancela o gerador (`CancelledError`/`GeneratorExit`). Como nada foi adicionado à sessão, nada é gravado. O bloco `finally` fecha o stream do modelo.

### 4. Span `maria.chat` sem manter contexto entre `yield`s
Num gerador assíncrono, um `with` que ativa contexto e atravessa `yield`s deixa o span "ativo" no código de quem consome o gerador, e o desanexar pode ocorrer em outro contexto. Por isso:
- o span é criado com `OITracer.start_span` (não fica corrente);
- cada avanço do stream do modelo (`await anext(stream)`) roda dentro de `trace.use_span(span, end_on_exit=False)` e `using_session(...)`.

O span do LLM, criado pela instrumentação no primeiro avanço, nasce filho de `maria.chat`. O span é finalizado explicitamente:
- no sucesso: com a saída completa;
- na falha: com exceção e status de erro;
- na interrupção: com status de erro "interrompida pelo cliente".

### 5. Demo consome SSE via `fetch`
O `EventSource` só faz `GET`, então a demo usa `fetch` + `ReadableStream` com um parser SSE mínimo, que separa eventos por linha em branco e lê `event:`/`data:`. Fluxo na tela:
1. O indicador "Maria está respondendo…" aparece até o primeiro `content.delta`.
2. A partir daí, o balão do assistente re-renderiza o Markdown acumulado.
3. O `message.assistant` substitui o balão pela versão persistida.

## Risks / Trade-offs

- [Proxies que fazem buffer cortam o efeito de streaming] → O SSE do FastAPI envia comentários de keep-alive. Em produção, o proxy deve desabilitar buffering (ex.: `X-Accel-Buffering: no` no Nginx).
- [Erro depois do início do stream não muda o status HTTP (já 200)] → O cliente trata o evento `error`. Erros detectáveis antes do stream (422, 404 e 503) continuam com status HTTP.
- [Re-renderizar o Markdown a cada fragmento] → O custo é desprezível para respostas de chat. Dá para otimizar com `requestAnimationFrame` se necessário.
