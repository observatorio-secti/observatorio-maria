# Proposal

## Why

Perguntas sobre a distribuição de pesquisadores pelos territórios de identidade da Bahia não têm uma boa apresentação. Os territórios são mais de 25: `group_by` aceita no máximo 5 valores, barras verticais deixam os rótulos ilegíveis e a pizza repete as 5 cores da paleta. Além disso, o catálogo do Simcc expõe `researcher_institution.identity_territory`, mas não orienta a contagem nem o que fazer quando o dado falta.

## What Changes

- **Barra horizontal:** `show_chart` passa a aceitar a orientação horizontal em gráficos `bar`, adequada a rankings com muitas categorias e rótulos longos.
- **Barra empilhada e empilhada 100%:** `show_chart` passa a aceitar empilhamento em gráficos `bar`, para mostrar a composição de cada categoria. Os valores em `data` continuam absolutos.
- **Rosca:** novo tipo `donut`, com as regras da pizza.
- **Limite de fatias:** `pie` e `donut` são recusados com mais de 5 fatias, e o modelo é orientado a reduzi-las na consulta ou usar barras.
- **Bloco `chart`:** novos campos opcionais `orientation` e `stacking`. Mensagens gravadas voltam com os valores padrão.
- **Catálogo do Simcc:** instruções e exemplo para contar pesquisadores por território sem somar territórios como total geral, e para declarar quando o dado não está preenchido.
- **Demo:** renderização, PNG e CSV dos novos formatos e exemplo na aba de contrato.

### Fora do escopo

- Mapa coroplético, treemap e heatmap, que ficam para uma etapa seguinte porque exigem plugin, GeoJSON ou tipo de bloco próprio.
- Preencher `identity_territory`: nada em `simcc-etl`, `simcc-admin` ou `Jade-Extrator-Hop` grava a coluna, e ela está vazia nos bancos locais (`simcc_write` e `simcc`). O preenchimento em produção não foi verificado, e corrigi-lo cabe ao Simcc.
- Inferir o território pela cidade do pesquisador cruzando com o fomento: a cidade de `researcher.city_id` ainda não foi validada como a do vínculo.
- Empilhamento em `line` e `area`.
- Mudanças no `observatorio-front`, que ainda não consome blocos `chart`.

## Capabilities

### New Capabilities

Nenhuma.

### Modified Capabilities

- `conversation-messaging`: novos requisitos para orientação, empilhamento, rosca e limite de fatias.
- `demo-page`: novos requisitos para renderizar e exportar os novos formatos.
- `data-catalog`: novos requisitos para pesquisadores por território no Simcc.

## Impact

- **Código:** `schemas.py`, `query/tool.py`, `services/chat.py`, `llm/prompts.py`, `demo/app.js` e `demo/styles.css`.
- **API:** novos campos opcionais `orientation` e `stacking` e novo valor `donut` em `chart_type`. Quem valida `chart_type` como lista fechada precisa aceitar o novo valor.
- **Catálogo:** `catalog/simcc.yaml`. Catálogos já semeados não recebem a mudança sozinhos, e o `docs/deploy.md` explica como aplicá-la.
- **Documentação:** contrato de blocos e catálogo no `README.md`, além do `docs/deploy.md`.
- **Bancos externos:** somente leitura, como hoje. Nada é criado ou alterado neles.
- **Segredos:** não toca.
- **Endpoints sem autenticação:** nenhum endpoint novo.
- **Dependências:** nenhuma nova. Tudo é coberto pelo Chart.js já carregado.
- **Mudanças em andamento:** não depende de outra mudança não arquivada.
