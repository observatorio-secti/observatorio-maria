# Tasks

## 1. Geração com explicação

- [x] 1.1 Em `services/chat.py`, voltar ao modelo depois de `show_*` aceitos, com a chamada seguinte sem ferramentas (D1, D2) e a mensagem temporária da explicação (D4). Testes em `tests/test_agent_chat.py`: gráfico sem texto ganha explicação, tabela sem texto ganha explicação, a chamada da explicação não recebe ferramentas, e a resposta termina nela. Ajustar `test_server_populates_chart_and_table_blocks` e `test_streaming_emits_activity_and_block_deltas` ao novo fluxo.
- [x] 1.2 Inserir o separador de parágrafo entre textos de chamadas diferentes, no acumulado e nos deltas (D4). Testes: texto na chamada do gráfico mais explicação gera os dois parágrafos no bloco e no streaming, e a chamada da explicação traz a orientação de não repetir.
- [x] 1.3 Fazer a última chamada sem ferramentas e remover `build_presentation_tools` de `query/tool.py` (D3). Testes: gráfico na penúltima chamada tem explicação na última; modelo sem texto na explicação grava só os blocos; os testes de orçamento (`test_budget_exhausted_strips_query_tools_on_last_call`, `test_default_budget_allows_six_model_calls`) continuam passando.
- [x] 1.4 Manter as ferramentas depois de `show_*` recusado (D5). Teste: coluna inexistente, seguida de pedido válido, gera o `chart`, e o `ToolMessage` com o motivo chega à chamada seguinte.

## 2. Instruções e documentação

- [x] 2.1 Em `llm/prompts.py`, acrescentar a regra da explicação, a de não escrever na chamada que pede a visualização e a de apresentar quando `calls_left` chegar a 2. Teste: o prompt de sistema contém essas regras.
- [x] 2.2 Atualizar o README: seção de blocos em **🌐 API**, explicando que o texto da resposta explica as visualizações e que a resposta só com blocos é exceção. Conferir no README que `build_presentation_tools` não é citado.
- [x] 2.3 Acrescentar a `evals/reference.yaml` perguntas com tag `explicacao`, com visualização e critério `judge`, e conferir com `poetry run task eval -- --check-expected`.

## 3. Verificação integrada

- [x] 3.1 Rodar `poetry run task test` sem falhas e `openspec validate fix-explicacao-de-graficos --strict`.
- [x] 3.2 Com o modelo real, perguntar na demo algo que gere gráfico, conferir a explicação antes do gráfico em desktop e a 375px, e confirmar que o provedor aceita a chamada sem ferramentas.
- [x] 3.3 Rodar `poetry run task eval -- --tag explicacao` e registrar acertos, tokens e chamadas ao modelo.

## Workflow follow-up

- Arquivar com `/opsx:archive`, nos commits `docs(openspec): planeja`, `feat:` e `docs(openspec): arquiva`, sem incluir a alteração local de `.env.example`.
