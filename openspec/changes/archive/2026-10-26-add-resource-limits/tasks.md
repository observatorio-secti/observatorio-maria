# Tasks: Limites de Recurso

## 1. Limites de consulta SQL (statement_timeout e validação de LIMIT)

- [x] 1.1 Implementar validação de cláusula `LIMIT` em `src/observatorio_maria/query/validator.py`, rejeitando limites superiores a `QUERY_MAX_ROWS` ou menores/iguais a zero.
- [x] 1.2 Assegurar a configuração de `SET LOCAL statement_timeout` dentro de transação explícita no PostgreSQL em `src/observatorio_maria/query/execution.py` e tratar erros `57014` como `QueryTimeoutError`.
- [x] 1.3 Adicionar testes unitários cobrindo consultas com `LIMIT` válido, `LIMIT` excessivo e cancelamento por `statement_timeout` em `tests/test_query_validation.py` e `tests/test_query_execution.py`.

## 2. Teto de tokens por conversa e persistência

- [x] 2.1 Criar migração Alembic para adicionar a coluna `total_tokens` na tabela `conversations` e atualizar `src/observatorio_maria/models.py` e `src/observatorio_maria/schemas.py`.
- [x] 2.2 Adicionar `CONVERSATION_TOKEN_CEILING` em `src/observatorio_maria/settings.py` e atualizar documentação no `.env.example` e no `README.md`.
- [x] 2.3 Implementar acumulação de tokens do modelo e checagem de teto de conversa no `ChatService` em `src/observatorio_maria/services/chat.py`.
- [x] 2.4 Mapear bloqueio por teto de tokens para resposta HTTP 429 em `src/observatorio_maria/routers/conversations.py` para envio comum e streaming.
- [x] 2.5 Adicionar testes cobrindo bloqueio de envio comum e streaming em conversas com teto atingido e acumulação de tokens em `tests/test_messages.py` e `tests/test_streaming.py`.

## 3. Interface da demo e verificação

- [x] 3.1 Atualizar `src/observatorio_maria/demo/app.js` para exibir banner amigável com orientação para criar nova conversa ao receber erro HTTP 429.
- [x] 3.2 Realizar verificação visual da resposta de limite de tokens no navegador em desktop e celular a 375px.
- [x] 3.3 Executar bateria de verificação com `task lint` e `task test`, garantindo conformidade e cobertura completa.
