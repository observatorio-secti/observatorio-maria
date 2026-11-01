# Tasks

## 1. Séries por categoria

- [x] 1.1 Escrever os testes de "Séries por categoria em gráficos", "Chaves das séries por categoria", "Recusa de pedidos de gráfico ambíguos" e "Limite de grupos em gráficos" e confirmar que falham
- [x] 1.2 Adicionar `group_by` a `ShowChartInput`, `show_chart` e à chamada em `services/chat.py`, com o pivô, as recusas e o limite
- [x] 1.3 Adicionar `group` a `ChartBlock` em `schemas.py`
- [x] 1.4 Orientar o modelo em `llm/prompts.py` a usar `group_by` e a passar `labels` ao reapresentar
- [x] 1.5 Registrar `group_by`, recusas e `group` no contrato de blocos do `README.md`

## 2. Histórico e demo

- [x] 2.1 Escrever os testes de "Gráficos agrupados no histórico" e confirmar que falham
- [x] 2.2 Ajustar `summarize_chart` para não citar rótulos de gráficos agrupados fora da quarentena
- [x] 2.3 Ajustar o aviso de corte de gráficos agrupados em `demo/app.js`
- [x] 2.4 Aumentar a altura do gráfico em telas estreitas em `demo/styles.css`, onde a legenda de várias séries espremia a área do gráfico

## 3. Verificação

- [x] 3.1 Rodar `poetry run task test` sem falhas
- [x] 3.2 Na demo, perguntar "Como varia por ano a publicação de artigos Qualis A1 entre as modalidades de bolsa?" contra o banco real e confirmar uma linha por modalidade, legenda e CSV, em desktop e a 375px

## Workflow follow-up

- Arquivar depois da implementação, com commits no padrão do histórico.
