# Design

## Context

`show_chart` monta o bloco `chart` no servidor e valida o pedido em `query/tool.py`. A demo traduz o bloco para o Chart.js em `chartConfig`, em `demo/app.js`. Um gráfico passa por contrato, ferramenta, prompt e renderização, e `services/chat.py` repassa os argumentos da ferramenta um a um. O `observatorio-front` ainda não consome `chart_type` nem `ChartBlock`.

`identity_territory` é uma coluna do vínculo, em `researcher_institution`. Ela está vazia nos bancos locais: 0 de 11.968 linhas em `simcc_write` e 0 de 5 em `simcc`. Nenhum dos projetos de carga do Simcc grava a coluna, e produção não foi verificada.

## Goals / Non-Goals

**Goals:**

- Apresentar categorias numerosas, como os territórios, com legibilidade na tela, no PNG e a 375px.
- Manter o contrato compatível com blocos já gravados.
- Fazer a Maria declarar a falta do dado, e não preencher a lacuna.

**Non-Goals:**

- Reduzir `MAX_CHART_GROUPS`, que continua em 5.
- Criar uma ferramenta separada para gráficos territoriais: território é só uma categoria no eixo.

## Decisions

### Orientação e empilhamento como campos do bloco

`orientation` e `stacking` são campos opcionais de `ChartBlock`, e `chart_type` continua `bar`. As combinações são independentes (vertical ou horizontal, com três modos de empilhamento), e um cliente que ignore os campos ainda desenha barras com os dados corretos.

Alternativa descartada: novos valores como `horizontal_bar` e `stacked_bar_100`. Seriam seis tipos para uma mesma família, e clientes antigos não desenhariam nenhum.

### `donut` como novo valor de `chart_type`

Rosca não tem eixos nem combinações, então um valor próprio é mais simples que um campo. A API passa a devolver um valor novo, e como o front ainda não consome blocos `chart`, ninguém é afetado hoje.

Alternativa descartada: `pie` com um campo `variant`. Criaria um campo com um único uso.

### Valores absolutos em `data` e proporção na renderização

Com `percent`, `data` guarda os valores do resultado e a demo calcula a proporção. O CSV, o detalhe do segmento e a reapresentação usam os números reais, e o histórico do modelo também.

Alternativa descartada: gravar porcentagens em `data`. Perderia os absolutos e arredondaria os valores que o modelo cita no texto.

### Validação do formato numa função única

Uma função nova em `query/tool.py`, ao lado de `check_group_request`, concentra as recusas de orientação, empilhamento, tipo e fatias, e levanta `ValueError` com o motivo. `show_chart` já converte esse erro em resposta ao modelo. O teste de negativos usa as séries finais, depois de `group_by`.

O tipo fora da lista passa a ser recusado com a mesma mensagem ao modelo, em vez de só aparecer na descrição da ferramenta.

Alternativa descartada: deixar a validação ao Pydantic de `ChartBlock`. O modelo receberia um erro genérico, sem orientação para corrigir o pedido.

### Limite de fatias aplicado também a `pie`

O limite vale para `pie` e `donut`, com 5 fatias, o tamanho da paleta. Hoje a pizza repete cores acima disso, e duas fatias iguais enganam a leitura. O limite só vale para gráficos novos: blocos gravados continuam sendo lidos, porque a validação fica em `show_chart`, não no schema.

Alternativa descartada: aumentar a paleta. Cores demais continuam difíceis de distinguir, e a pizza segue ruim para 27 partes.

### Altura pela quantidade de categorias

A demo define a altura de `.canvas-wrap` pelo número de categorias em gráficos horizontais, com cerca de 28px por categoria e a altura atual como mínimo. `chartPng` usa a mesma conta, em vez dos 480px fixos. Os rótulos do eixo vertical ficam com autoSkip desligado.

Alternativa descartada: altura fixa com rolagem interna. Ocultaria parte do ranking e não serviria ao PNG.

### Orientação do território nas instruções do catálogo

A regra de contagem fica nas instruções de `catalog/simcc.yaml`, junto da regra de instituições, com um exemplo few-shot. Conceitos entre fontes não mudam: o território do fomento continua na fonte `fomento`.

Para somar produção por território, a instrução manda partir de pares distintos de `researcher_id` e `identity_territory` numa CTE, para o vínculo duplo na mesma região não contar a produção duas vezes.

Alternativa descartada: criar um conceito `territorio` em `concepts.yaml`. As duas fontes estão vazias aqui, e um conceito só faria sentido com uma política de resposta validada em dados reais.

## Risks / Trade-offs

- [`identity_territory` vazia também em produção] → A mudança é útil do mesmo jeito para outras categorias, e a Maria declara a falta do dado. A task 4.3 confere produção antes de divulgar a função, e o preenchimento fica com o Simcc.
- [Sem dados reais, a orientação de território não é verificável nos bancos locais] → Testar com origem SQLite temporária com territórios preenchidos, sem tocar nos bancos do Simcc.
- [Vínculo duplo faz o total por território passar do total de pesquisadores] → Instruções proíbem somar, e o texto da resposta traz a ressalva.
- [Produção somada por território repete coautores] → A Maria apresenta o número como soma das produções de cada pesquisador, com essa ressalva.
- [Empilhar contagens distintas de grupos que se sobrepõem engana o total] → O prompt restringe empilhamento a partes que não se sobrepõem.
- [`pie` com mais de 5 fatias, antes aceita, passa a ser recusada] → O modelo recebe a orientação de usar barras e refaz o pedido, dentro do orçamento de chamadas.
- [Catálogo já semeado não recebe as novas instruções] → `docs/deploy.md` descreve a atualização pelo `PATCH` ou pelo `--reset`.
- [`chartPng` chama `truncationText` só com a contagem, sem o bloco, e o aviso sai errado no PNG] → A task 3.4 corrige, porque ela reescreve esse trecho.

## Migration Plan

Não há migração de banco: `orientation` e `stacking` têm padrão no schema, e blocos gravados são lidos com esses valores. No deploy, reconstruir a imagem e aplicar as instruções ao catálogo existente, como em `docs/deploy.md`. Para reverter, volte a versão da API. Blocos `donut` já gravados passam a falhar na validação do schema antigo, então o rollback precisa de uma nova conversa ou da remoção dessas mensagens.

## Open Questions

- `identity_territory` está preenchida em produção? A resposta não muda o que será construído, só define se a função de território já entrega valor no lançamento.
