# Tasks

## 1. Bloco e geração

- [x] 1.1 Em `schemas.py`, criar `SuggestionsBlock`, incluí-lo em `ContentBlock` e no tipo do delta. Em `llm/prompts.py`, criar a instrução e `parse_suggestions` (D3). Testes de `parse_suggestions`: numeração, sem `?`, repetição, tamanho e limite de 3.
- [x] 1.2 Em `services/chat.py`, criar `_suggest_followups` (D2) com os critérios de D4 e emitir o bloco por último. Ignorar o bloco em `blocks_to_text`. Testes em `tests/test_agent_chat.py`: resposta com consulta, sem consulta, última pergunta, falha do modelo, ordem no streaming, histórico sem sugestões e nível gravado. Atualizar a seção **🌐 API** do README.

## 2. Demo

- [x] 2.1 Em `demo/app.js`, renderizar `suggestions` como botões, reaproveitando `.suggestion`, e ocultá-los fora da última mensagem (D5). Atualizar a seção **🎬 Demo** do README.

## 3. Verificação integrada

- [x] 3.1 Rodar `poetry run task test` sem falhas e `openspec validate add-perguntas-de-continuacao --strict`.
- [x] 3.2 Com o modelo real, fazer uma pergunta, clicar numa sugestão, reabrir a conversa, conferir em desktop e a 375px e remover depois a conversa de teste.
