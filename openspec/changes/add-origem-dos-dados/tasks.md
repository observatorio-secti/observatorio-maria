# Tasks

## 1. Origem nos blocos

- [x] 1.1 Em `schemas.py`, criar `BlockOrigin` e `BlockCoverage` e acrescentar `origin` a `ChartBlock` e `TableBlock` (D2). Em `query/execution.py`, acrescentar `origin` a `QueryResult` e `ResultStore.add`. Em `query/tool.py`, montar a origem em `_run_query_data` (D1, D3) e copiá-la em `show_chart` e `show_table`. Testes em `tests/test_agent_chat.py`: fonte, descrição e data no bloco; descrição padrão; duas consultas com origens diferentes; mensagem gravada sem o campo volta com `origin` nulo. Atualizar a seção de blocos em **🌐 API** no README.
- [x] 1.2 Montar a origem em `_run_across_sources`, com as duas fontes e `coverage` só com `keys` e `found` quando disponível. Testes em `tests/test_agent_across_sources.py`: cobertura disponível e indisponível.
- [x] 1.3 Garantir os limites de privacidade (D3, D4) e ajustar a descrição de `purpose` em `QueryDataInput` e `QueryAcrossSourcesInput`. Testes: e-mail mascarado, `SELECT` trocado pela descrição padrão, e o bloco serializado não contém o SQL nem o `result_id`.

## 2. Demo

- [x] 2.1 Em `demo/app.js`, criar `originFooter` (D5) e usá-lo em `blockRenderers.chart` e `table`, reaproveitando o estilo de `.block-notice`. Acrescentar `origin` ao exemplo da aba "Contrato de blocos" e atualizar a seção **🎬 Demo** do README.

## 3. Verificação integrada

- [x] 3.1 Rodar `poetry run task test` sem falhas e `openspec validate add-origem-dos-dados --strict`.
- [x] 3.2 Com o modelo real, fazer uma pergunta de uma fonte e uma entre fontes, conferir o rodapé e a cobertura em desktop e a 375px, reabrir a conversa e remover depois as conversas de teste.

## Workflow follow-up

- Arquivar com `/opsx:archive`, nos commits `docs(openspec): planeja`, `feat:` e `docs(openspec): arquiva`, sem incluir a alteração local de `.env.example`.
