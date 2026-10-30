# Tasks

## 1. Rótulos e unidades nos blocos

- [x] 1.1 Em `query/tool.py`, criar `column_label` (D2) e acrescentar `labels` a `ShowChartInput`, `ShowTableInput`, `show_chart` e `show_table`, e repassar o campo em `_execute_tool_call` (`services/chat.py`). Testes em `tests/test_agent_chat.py`: gráfico e tabela com rótulos mantêm as chaves, gráfico sem rótulo usa a reserva, rótulo fora do bloco é ignorado.
- [x] 1.2 Acrescentar `units` a `ShowChartInput` e `show_chart`, com repasse em `_execute_tool_call`. Testes: série com unidade grava `unit`; série sem unidade fica com `unit` nulo.
- [x] 1.3 Em `llm/prompts.py`, acrescentar a regra de rótulos legíveis e de não inventar unidades. Teste: o prompt de sistema contém a regra. Atualizar a seção de blocos em **🌐 API** no README.

## 2. Demo

- [x] 2.1 Em `demo/app.js`, calcular o título do eixo Y (D4), sem título em pizza e em unidades diferentes. Conferir na aba "Contrato de blocos", que já tem gráfico com unidade, e atualizar a seção **🎬 Demo** do README, se preciso.

## 3. Verificação integrada

- [x] 3.1 Rodar `poetry run task test` sem falhas e `openspec validate add-rotulos-em-graficos --strict`.
- [x] 3.2 Com o modelo real, pedir um gráfico na demo e conferir legenda e eixos em português, em desktop e a 375px, removendo depois a conversa de teste.

## Workflow follow-up

- Arquivar com `/opsx:archive`, nos commits `docs(openspec): planeja`, `feat:` e `docs(openspec): arquiva`, sem incluir a alteração local de `.env.example`.
