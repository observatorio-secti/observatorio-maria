# Tasks

## 1. Contrato e validação do `show_chart`

- [x] 1.1 Adicionar `orientation` e `stacking` a `ChartBlock` e `donut` a `chart_type` em `schemas.py`, e verificar com teste que mensagem gravada sem os campos volta com `vertical` e `stacking` nulo.
- [x] 1.2 Adicionar os campos a `ShowChartInput`, ao `show_chart` e ao repasse em `services/chat.py`, e verificar em `tests/test_chart_groups.py` (ou arquivo vizinho) que o bloco criado pelo agente os traz.
- [x] 1.3 Criar a validação de formato em `query/tool.py`: tipo inválido, `horizontal` fora de `bar`, `stacking` fora de `bar` ou com uma série, negativos em `percent`, `donut` com `group_by` e mais de 5 fatias em `pie` e `donut`. Verificar com um teste por cenário de recusa, incluindo o limite exato de 5.
- [x] 1.4 Testar que `percent` preserva os valores absolutos em `data` e que a reapresentação por `h1` aceita os novos formatos sem consultar as origens.
- [x] 1.5 Atualizar a seção do contrato de blocos no `README.md` e conferir o exemplo de JSON contra `ChartBlock`.

## 2. Orientação ao modelo

- [x] 2.1 Adicionar a escolha de formato em `llm/prompts.py` e nas descrições de `ShowChartInput`, e verificar com teste que o prompt traz as orientações.

## 3. Demo

- [x] 3.1 Estender `chartConfig` para orientação e empilhamento, com o título de valores no eixo certo, e verificar no navegador os gráficos vertical e horizontal, com e sem empilhamento.
- [x] 3.2 Implementar `percent` com proporção no eixo, nulo como zero e detalhe com porcentagem e valor absoluto, e verificar no navegador o caso 30 e 10.
- [x] 3.3 Desenhar `donut` sem eixos e aplicar a altura pela quantidade de categorias, e verificar no navegador 27 territórios sem sobreposição.
- [x] 3.4 Ajustar `chartPng` para a mesma altura e formato, corrigir a chamada de `truncationText` e verificar um PNG horizontal com 27 rótulos e um gráfico cortado com o aviso correto.
- [x] 3.5 Confirmar que o CSV traz valores absolutos em gráfico `percent`, baixando o arquivo no navegador.
- [x] 3.6 Adicionar o exemplo horizontal e empilhado à aba de contrato, e verificar streaming, conversa reaberta e os formatos no navegador em desktop e a 375px, nos temas claro e escuro.

## 4. Catálogo do Simcc

- [x] 4.1 Atualizar `catalog/simcc.yaml` com as instruções de território, o exemplo de pesquisadores por território e `identity_territory` com `list_values: never` e pesquisável, e verificar com teste de seed e prévia de contexto que o exemplo não é recusado.
- [x] 4.2 Testar o fluxo com origem SQLite temporária, com territórios preenchidos, vínculo duplo e coluna toda nula, usando fakes do LangChain, e verificar a contagem distinta e o resultado vazio.
- [ ] 4.3 Rodar em produção, somente leitura, a contagem de `identity_territory` por território e registrar o resultado neste change. Se estiver vazia, avisar que o preenchimento depende do Simcc.
- [x] 4.4 Atualizar a seção de catálogo do `README.md` e a atualização de catálogos existentes em `docs/deploy.md`, e conferir `GET /catalog/datasources/simcc/context` depois de seguir os passos num catálogo local.

## 5. Integração

- [x] 5.1 Rodar `poetry run task test` sem falhas e fazer uma pergunta por território na demo com a fonte real, confirmando que a Maria declara a falta do dado enquanto a coluna estiver vazia.

## Workflow follow-up

- Arquivar a mudança depois da implementação, com os commits no padrão do projeto.
- Se a coluna seguir vazia em produção, abrir a discussão com o Simcc sobre quem a preenche.
