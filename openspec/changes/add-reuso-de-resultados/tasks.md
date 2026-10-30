# Tasks

## 1. Resultados restaurados

- [x] 1.1 Em `query/execution.py`, criar `result_from_block` e `ResultStore.restore` (D1, D3). Em `services/chat.py`, restaurar os blocos do histórico antes da primeira chamada e citar `Resultado` e `Chaves` nos resumos (D2, D4). Testes em `tests/test_agent_chat.py`: gráfico a partir de `h1`, sem consulta; tabela a partir de gráfico; coluna ausente e id inexistente recusados; ids no histórico; `truncated` e `origin` herdados.
- [x] 1.0 Normalizar os tipos das colunas (D6). Testes: gráfico com eixo de texto no envio comum e no streaming; bloco gravado com `x.type` `string` abre no histórico; gráfico anterior vira tabela.
- [x] 1.2 Em `llm/prompts.py`, acrescentar a regra de reapresentação. Teste: o prompt de sistema contém a regra. Atualizar a seção de blocos em **🌐 API** do README.

## 2. Verificação integrada

- [x] 2.1 Rodar `poetry run task test` sem falhas e `openspec validate add-reuso-de-resultados --strict`.
- [x] 2.2 Com o modelo real, pedir um gráfico e depois "mostra em pizza", conferindo que não há nova consulta, e remover depois a conversa de teste.
