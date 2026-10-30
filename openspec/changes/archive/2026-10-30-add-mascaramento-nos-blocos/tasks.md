# Tasks

## 1. Mascaramento

- [x] 1.1 Em `query/sanitization.py`, criar `mask_value` e tornar `sanitize_untrusted_text` recursivo (D3, D4). Testes em `tests/test_sanitization.py`: lista, objeto, chave e tipos não textuais.
- [x] 1.2 Em `query/tool.py`, mascarar os blocos de `show_chart` e `show_table` (D1, D2). Testes em `tests/test_agent_chat.py`: delta, mensagem gravada e leitura sem os valores, gráfico, título, texto longo inteiro, mensagem antiga intacta e reapresentação mascarada. Atualizar as seções de segurança e de blocos do README.

## 2. Verificação integrada

- [x] 2.1 Rodar `poetry run task test` sem falhas e `openspec validate add-mascaramento-nos-blocos --strict`.
