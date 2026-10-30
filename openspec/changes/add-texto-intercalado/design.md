# Design

## Context

Motivação em `proposal.md`. `stream_message` envia cada chunk de texto como delta de índice 0, acumula em `accumulated_text` e só depois do loop emite `pending_blocks`. Uma mensagem gravada tem no máximo um bloco `text`. `blocks_to_text` e `answer_texts` já lidam com vários blocos `text`. A demo junta todo o texto e todos os blocos e redesenha a mensagem a cada delta.

## Goals / Non-Goals

**Goals:**
- Sem marcador, a resposta é idêntica à de hoje.
- Nenhum fragmento de marcador chega ao cliente.

**Non-Goals:**
- Corrigir marcadores mal escritos pelo modelo além do formato exato.

## Decisions

### D1. Marcador simples no texto

O modelo escreve `[[bloco:N]]`, depois de receber o `block_index`.

Descartada: passar a posição como argumento de `show_*`. O texto ainda não existe quando o bloco é pedido.

### D2. `ResponseAssembler` em módulo próprio

`services/assembly.py` guarda a lista de blocos da resposta e o texto retido. `add_text` devolve os deltas a emitir, e `finish` emite o resto. `ContentDelta` passa a morar nesse módulo. A classe é testável sem modelo nem API.

Descartada: lógica dentro do loop de `stream_message`, que já tem aninhamento no limite do lint.

### D3. Reter só o que pode ser marcador

Depois de cada chunk, o último `[` e o que vem depois ficam retidos se ainda puderem formar `[[bloco:N]]`. O resto é emitido na hora, para o streaming seguir fluido.

Descartada: reter até o fim do parágrafo. Atrasaria todo o texto.

### D4. Blocos só existem depois de pedidos

Só `pending_blocks` no momento do marcador são válidos. Com a chamada dedicada à explicação, todos já existem. Texto na mesma chamada do `show_*` chega antes da execução, e o marcador é removido.

Descartada: reter o texto até o fim da chamada. Quebraria o streaming para evitar um caso que a regra do prompt já proíbe.

### D5. Limpeza ao final

`finish` remove espaços nas pontas de cada bloco `text` e descarta os vazios. Os deltas já enviados podem ter espaços, mas a versão gravada substitui a mensagem ao final.

Descartada: limpar cada delta, que perderia as quebras de linha do Markdown.

### D6. Demo anexa em vez de redesenhar

`sendMessage` mantém o nó do texto atual e troca só esse nó. Cada bloco é anexado uma vez.

Descartada: manter `replaceChildren`. Com texto depois de gráfico, cada fragmento recriaria o gráfico.

## Risks / Trade-offs

- [Risco] O modelo errar o número do bloco → O gráfico fica fora de posição, mas com a explicação no texto; a validação aceita só números reais.
- [Risco] Clientes que usam só o primeiro `text` perderem parte da resposta → Documentado no README e no Impact; `observatorio-front` precisa acompanhar.
- [Risco] O marcador aparecer dentro de uma tabela Markdown → A tabela fica dividida; a regra pede o marcador numa linha própria.
- [Risco] Texto de usuário ou de dados com `[[bloco:1]]` citado pelo modelo → O marcador é tratado como posição; o efeito é só mover um bloco da própria resposta.
