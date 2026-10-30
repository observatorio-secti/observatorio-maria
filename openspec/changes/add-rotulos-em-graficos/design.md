# Design

## Context

Motivação em `proposal.md`. Estado atual:

- **`QueryRunner.show_chart` e `show_table`:** usam a chave como `label` e não preenchem `unit`.
- **`_execute_tool_call`:** repassa os argumentos um a um, então campo novo precisa entrar ali.
- **Blocos:** `ChartAxis.label`, `ChartSeries.label`, `ChartSeries.unit` e `TableColumn.label` já existem no contrato.
- **Demo:** a legenda já junta rótulo e unidade, e o eixo X já mostra `x.label`. O eixo Y não tem título. Cabeçalhos de tabela já usam `label`.

## Goals / Non-Goals

**Goals:**
- Nenhuma mudança no contrato de blocos nem nas mensagens gravadas.
- Pedido sem rótulos continua válido e já fica mais legível.

**Non-Goals:**
- Garantir a qualidade do rótulo escolhido pelo modelo: fica com a regra do prompt e a verificação na demo.

## Decisions

### D1. `labels` e `units` como mapas opcionais

As duas ferramentas ganham `labels: dict[str, str] | None`, de coluna para rótulo, e `show_chart` ganha `units` no mesmo formato. Um único `labels` cobre o eixo `x`, as séries e as colunas da tabela.

Descartada: `series` como lista de objetos, prevista no plano. Exigiria aceitar dois formatos no mesmo campo, e o eixo `x` e as tabelas precisariam de campos próprios.

### D2. Reserva calculada no servidor

Um helper `column_label(key, labels)` em `query/tool.py` devolve o rótulo informado ou a chave com `_` trocado por espaço e inicial maiúscula. Rótulo vazio conta como ausente.

Descartada: rótulo do catálogo como reserva. Colunas calculadas não têm rótulo, e relacionar um alias à coluna de origem exigiria analisar o SQL.

### D3. Rótulos fora do bloco são ignorados

Só as colunas do bloco são consultadas, então chaves a mais no mapa não têm efeito.

Descartada: recusar o pedido. Gastaria uma chamada do orçamento por um erro sem efeito para quem lê.

### D4. Título do eixo Y derivado no cliente

`blockRenderers.chart` calcula o título a partir de `series`: uma série usa rótulo e unidade; várias com a mesma unidade usam a unidade; caso contrário, nenhum título.

Descartada: novo campo `y` no bloco. Ampliaria o contrato por um dado que já se deduz de `series`.

## Risks / Trade-offs

- [Risco] O modelo inventar uma unidade errada, como `R$` numa contagem → A regra do prompt proíbe, e o rótulo é só apresentação: os valores vêm do resultado.
- [Risco] Rótulo longo apertar o gráfico a 375px → Verificação em celular; o Chart.js quebra ou reduz a legenda.
- [Risco] Texto do modelo renderizado na página → Na demo, os rótulos entram por `textContent` e no canvas, sem HTML.
