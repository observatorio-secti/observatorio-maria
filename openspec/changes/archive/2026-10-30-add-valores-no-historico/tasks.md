# Tasks

## 1. Valores no histórico

- [x] 1.1 Acrescentar `HISTORY_MAX_ROWS` a `settings.py`, ao `.env.example` e à tabela **⚙️ Configuração** do README.
- [x] 1.2 Em `services/chat.py`, incluir os valores em quarentena nos resumos (D1, D2, D3). Testes em `tests/test_agent_chat.py`: 40 registros mandam 20, zero manda só o resumo, célula longa é cortada, CPF mascarado, delimitador escapado e tag presente. Atualizar a seção de blocos em **🌐 API** do README.
- [x] 1.3 Em `llm/prompts.py`, acrescentar a regra de uso (D4). Teste: o prompt de sistema contém a regra.

## 2. Verificação integrada

- [x] 2.1 Rodar `poetry run task test` sem falhas e `openspec validate add-valores-no-historico --strict`.
- [x] 2.2 Com o modelo real, perguntar sobre um gráfico anterior e confirmar a resposta sem nova consulta, medindo os tokens da conversa, e remover depois a conversa de teste.
