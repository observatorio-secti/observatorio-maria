# Design

## Context

`show_chart` copia as linhas do resultado para `data`, mantendo só `x` e `series`. A demo desenha um ponto por linha. Com um resultado em formato longo (ano, modalidade, total), a categoria se perde e os pontos de modalidades diferentes são ligados entre si. Ver proposal.md para a motivação.

## Goals / Non-Goals

**Goals:**

- Comparar categorias ao longo de `x` com uma série por categoria.
- Impedir que um gráfico misture linhas diferentes em silêncio.
- Manter o contrato de `series` e `data`, para clientes atuais funcionarem sem mudança.

**Non-Goals:**

- Agregar valores no servidor.
- Alterar gráficos já gravados.

## Decisions

**Pivô no servidor.** `show_chart` transforma o formato longo em uma linha por `x` e uma chave por grupo. Alternativa descartada: enviar as linhas longas e agrupar em cada cliente, porque demo e `observatorio-front` repetiriam a regra e o CSV exigiria tratamento próprio.

**Chave derivada do valor, em ASCII.** `Bolsa PQ-1A` vira `bolsa_pq_1a`, com sufixo em caso de colisão, e o rótulo guarda o valor original. Assim o modelo reconhece a série em `h1` e pode reapresentá-la. Alternativa descartada: o valor bruto como chave, porque as Chaves do histórico ficam fora da quarentena. Chaves opacas como `serie_1` também foram descartadas, porque o modelo não saberia a qual grupo cada uma corresponde.

**Recusar em vez de agregar.** `x` repetido, par `x` e grupo repetido e mais de 5 grupos devolvem um erro com a orientação ao modelo, que refaz a consulta. Alternativa descartada: somar no servidor, porque médias e percentuais somados dão valores errados sem aviso. O limite segue as 5 cores da paleta da demo.

**Dispersão e pizza sem `group_by`.** Dispersão aceita `x` repetido e não passa pelo pivô, que perderia pontos. Pizza mostra uma só medida por categoria. Alternativa descartada: anéis ou cores por grupo, sem uso nas perguntas atuais.

**Ausência continua nula.** Uma combinação sem linha fica `null`, sem virar zero. Alternativa descartada: preencher com zero, que só é correto em contagens.

**Ordem de `x`.** Eixos `number` e `date` são ordenados, com nulos no fim; em categorias vale a ordem do resultado. Sem isso, `ORDER BY modalidade, ano` embaralharia o eixo. Alternativa descartada: ordenar categorias, o que quebraria sequências como meses por nome.

**Campo `group` no bloco.** `summarize_chart` o usa para trocar os rótulos, vindos do banco, por "uma por <rótulo>" fora da quarentena; os valores seguem nela. Alternativa descartada: sanitizar os rótulos no resumo, porque escapar delimitadores não impede texto que tenta instruir o modelo.

## Risks / Trade-offs

- [Risco] Um gráfico legítimo com `x` repetido, como homônimos num ranking, passa a ser recusado → O erro orienta o modelo a agregar ou usar outra coluna.
- [Risco] A recusa consome uma chamada do orçamento → O prompt pede `group_by` já na primeira tentativa, e a resposta segue com texto ou tabela se o orçamento acabar.
- [Risco] Formato longo atinge `QUERY_MAX_ROWS` antes e corta anos ou grupos → `truncated` segue no bloco e a demo avisa o corte.
- [Risco] Ao reapresentar um gráfico agrupado sem `labels`, a série usa o rótulo vindo da chave → O prompt pede `labels`, e o rótulo continua legível.
