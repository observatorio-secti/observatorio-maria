# Design

## Context

Motivação em `proposal.md`. `stream_message` conclui o loop, emite os blocos e monta `content_blocks` antes de gravar. `blocks_to_text` faz `json.dumps` em tipos desconhecidos. `query_runner.total_queries` conta as consultas da resposta. Os testes usam o mesmo modelo fake em todos os níveis.

## Goals / Non-Goals

**Goals:**
- A resposta nunca depende das sugestões.
- Custo pequeno: a chamada não leva o contexto das fontes.

**Non-Goals:**
- Garantir que toda sugestão tenha dados: a checagem exigiria consultar as fontes.

## Decisions

### D1. Bloco gravado, não evento SSE

`SuggestionsBlock` entra em `ContentBlock`, e o delta usa `type: 'suggestions'`. Assim as sugestões reaparecem ao reabrir a conversa e valem também no envio comum.

Descartada: evento SSE próprio. Sumiria ao recarregar e não chegaria a `POST /messages`.

### D2. Chamada separada ao nível `fast`, depois da resposta

`_suggest_followups` usa `ainvoke` com o nome das fontes, a pergunta e a resposta, com tempo limite de 10 segundos e o mesmo contador de tokens.

Descartada: pedir as sugestões na resposta principal. Exigiria texto estruturado no meio do streaming, e uma falha afetaria a resposta.

### D3. Uma pergunta por linha

`parse_suggestions` remove marcadores e numeração, exige `?`, limita o tamanho, descarta repetições e a própria pergunta atual, e fica com três.

Descartada: saída estruturada do LangChain. Nem todo provedor oferece, e o formato simples basta.

### D4. Critérios determinísticos para omitir

Só há chamada quando `total_queries > 0` e a pergunta atual não é a última da conversa. A primeira condição cobre saudações e perguntas fora do tema sem gastar tokens.

Descartada: pedir ao modelo que decida. Gastaria uma chamada para concluir que não há o que sugerir.

### D5. Visibilidade por CSS

`.message:not(:last-child) .block-suggestions` oculta os botões. O indicador de resposta entra como última mensagem, então os botões somem também durante a geração.

Descartada: remover blocos ao renderizar. Exigiria acompanhar as mensagens anteriores a cada envio.

## Risks / Trade-offs

- [Risco] Sugestão sem dados nas fontes → A instrução pede perguntas sobre as fontes consultadas, e a Maria diz quando não há dados.
- [Risco] Texto vindo do modelo em botões → Entra por `textContent`, e o clique só preenche uma pergunta.
- [Risco] Dados da resposta chegarem à chamada `fast` → A resposta já passou pelas mesmas proteções, e a instrução manda tratá-la como dado.
- [Risco] Espera extra antes de `message.assistant` → O texto já está na tela, e o tempo limite é de 10 segundos.
- [Risco] Clicar em Parar durante as sugestões descarta a resposta já visível, porque nada foi gravado ainda → A espera é curta, e a pergunta volta ao campo.
