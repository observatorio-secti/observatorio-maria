# Tasks

## 1. Parar

- [x] 1.1 Em `demo/app.js`, passar `signal` a `streamEvents` (D1), trocar o botão para Parar durante a geração (D2), desligar o cancelamento em `message.assistant` (D3) e tratar `AbortError` com aviso, mantendo a pergunta no campo. Atualizar a seção **🎬 Demo** do README.

## 2. Tentar novamente

- [x] 2.1 Em `demo/app.js`, mostrar "Tentar novamente" no banner em erros temporários (D4), sem o botão em 429 e 503.

## 3. Verificação integrada

- [x] 3.1 Rodar `poetry run task test` sem falhas e `openspec validate add-parar-e-tentar-novamente --strict`.
- [x] 3.2 Na demo, com o modelo real, parar uma resposta e confirmar que nada foi gravado; simular um erro e usar "Tentar novamente"; conferir em desktop e a 375px e remover depois as conversas de teste.
