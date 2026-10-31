# Tasks

## 1. Contagem na API

- [x] 1.1 Escrever em `tests/test_conversations.py` os testes de "Contagem de perguntas da conversa" (com perguntas, nova, limite desligado, sem chave de modelo) e confirmar que falham
- [x] 1.2 Extrair `count_questions` em `services/chat.py` e usá-la em `check_conversation_limits`; verificar com os testes de limite já existentes em `tests/test_messages.py` e `tests/test_streaming.py`
- [x] 1.3 Criar `ConversationDetail` e usá-lo em `GET /conversations/{id}`; verificar com os testes da 1.1 e confirmar que listagem, criação e renomeação não trazem os campos
- [x] 1.4 Atualizar a tabela de rotas e a nota de limite de perguntas no `README.md` e conferir o texto contra a spec

## 2. Contador na demo

- [x] 2.1 Adicionar o elemento do contador em `index.html` e o estilo normal e de aviso em `styles.css`, verificando que fica oculto sem conversa aberta
- [x] 2.2 Renderizar o contador em `showCurrentHeader` (`app.js`) com os textos da spec, e verificar no navegador os estados normal, última pergunta, limite atingido e limite desligado

## 3. Verificação

- [x] 3.1 Rodar `poetry run task test` sem falhas
- [x] 3.2 Na demo, fazer perguntas contra a API real com limite baixo e confirmar a atualização do contador, o aviso e o banner 429, em desktop e a 375px; remover no fim a conversa de teste

## Workflow follow-up

- Arquivar depois da implementação, com commits no padrão do histórico.
- `services/chat.py` tem linhas `cost-debug` não commitadas: incluir no commit só as linhas desta mudança.
- Fechar a issue #7.
