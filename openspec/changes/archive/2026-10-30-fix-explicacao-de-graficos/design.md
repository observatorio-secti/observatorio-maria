# Design

## Context

Motivação em `proposal.md`. Estado atual em `ChatService.stream_message`:

- **Fim do loop:** depois das ferramentas, `if not has_query: break`. Só quem consulta volta ao modelo, então o `ToolMessage` de `show_*`, inclusive o de erro, nunca é lido.
- **Última chamada:** recebe `build_presentation_tools()`. Se o modelo só pedir um gráfico ali, não sobra chamada para o texto.
- **Texto:** `accumulated_text` soma os chunks de todas as chamadas, sem separador, e os deltas já saíram para o cliente, sem como desfazer.
- **Blocos:** ficam em `query_runner.pending_blocks` e só são emitidos depois do loop, depois de todo o texto.
- **Testes:** `ScriptedToolChatModel` devolve `AIMessage('Fim')` quando o roteiro acaba, e `bind_tools` registra as ferramentas em `bound_tools`.

## Goals / Non-Goals

**Goals:**
- Toda resposta com visualização aceita tem uma chamada dedicada à explicação, sempre que o orçamento permitir.
- O número de rodadas de consulta disponíveis não diminui.

**Non-Goals:**
- Medir a qualidade da explicação em testes: fica com o `task eval`.
- Mudar a ordem texto + blocos ou o momento em que os blocos são emitidos.

## Decisions

### D1. Sempre voltar ao modelo depois de apresentação aceita

Depois de uma chamada sem consultas, com todos os `show_*` aceitos, a geração continua em vez de `break`. O sucesso é medido pelo crescimento de `pending_blocks` frente ao número de chamadas de ferramenta da rodada.

Descartada: encerrar quando o modelo já escreveu texto naquela chamada. O texto pode ser só "Veja o resumo a seguir:", e um limite de tamanho seria um palpite frágil. O custo de sempre voltar é uma chamada por resposta com visualização.

### D2. Chamada da explicação sem ferramentas

Uma variável `text_only` faz a chamada seguinte usar o modelo sem `bind_tools`, como a resposta sem fontes. Assim a resposta termina depois dela.

Descartada: manter as ferramentas e confiar no prompt. O modelo poderia pedir outro gráfico ou consulta, gastando orçamento sem produzir texto.

### D3. Só a última chamada fica sem ferramentas

`is_last_call` passa a usar o modelo sem ferramentas, e `build_presentation_tools` sai do código. A penúltima chamada continua com todas as ferramentas.

Descartada: reservar a penúltima chamada só para apresentação, como previa o plano. Com orçamento 3, sobraria uma única rodada de consulta, quebrando o cenário de retentativa depois de uma consulta que falha, e com orçamento 6 perderia uma rodada em toda resposta longa.

Consequência: se o modelo consultar até a penúltima chamada, a última não pode gerar gráfico, e a resposta sai só em texto. A regra do prompt pede para apresentar quando `calls_left` chegar a 2.

### D4. Evitar duplicação com instrução, não com filtro

A chamada da explicação recebe uma `SystemMessage` temporária, como o aviso de última chamada: as visualizações já estão visíveis, escreva a explicação e não repita o que já foi escrito. A regra geral também manda não escrever na chamada que pede a visualização.

No primeiro chunk de texto de uma chamada, se já houver texto acumulado, o sistema insere `\n\n` no acumulado e no delta. A regra vale para qualquer par de chamadas.

Descartada: descartar o texto da chamada de apresentação. Os deltas já foram enviados, e o cliente veria o texto sumir.

### D5. Recusa segue o fluxo normal

Se algum `show_*` falhar, `text_only` fica falso e a próxima chamada recebe `query_tools`, que já incluem `show_chart` e `show_table`. A correção pode exigir outra consulta, e o orçamento limita as tentativas.

Descartada: oferecer só as ferramentas de apresentação. Elas não resolvem o caso em que falta a coluna no resultado.

## Risks / Trade-offs

- [Risco] Uma chamada a mais em cada resposta com gráfico aumenta tokens e latência → Fica dentro do orçamento, e o `task eval` mede o custo antes e depois.
- [Risco] Provedor recusar `ToolMessage` no histórico de uma chamada sem ferramentas declaradas → Conferir com o modelo real na verificação; hoje isso só ocorria com ferramentas ligadas.
- [Risco] O modelo repetir o texto mesmo com a instrução → Teste confere a instrução; o `task eval` com `judge` observa o resultado real.
- [Risco] Espera sem indicação visual entre o último `activity` e a explicação → A demo já mantém "Maria está respondendo" até o primeiro texto.
