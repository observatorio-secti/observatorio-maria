# Proposal

## Why

Como mantenedor da Maria, é essencial assegurar a previsibilidade de custos de operação dos modelos de linguagem e garantir a proteção operacional e a estabilidade dos bancos de dados relacionais consultados (como o banco do módulo de fomento).

Hoje identificamos três lacunas de contenção de recursos:
1. **Ausência de limite a nível de servidor de banco (`statement_timeout`):** Embora exista timeout assíncrono no cliente (`QUERY_TIMEOUT_SECONDS`), se uma consulta SQL demorada ou travada for disparada contra um banco externo PostgreSQL, a consulta pode continuar executando em background no servidor PostgreSQL consumindo CPU, memória e conexões. É necessário assegurar que `statement_timeout` seja configurado e aplicado diretamente no motor do banco de dados na transação somente leitura, e que seu cancelamento seja tratado adequadamente como timeout sem derrubar a aplicação.
2. **Falta de validação determinística de `LIMIT` na AST:** O executor da Maria envolve a consulta em `LIMIT max_rows + 1`, mas a consulta interna gerada pelo modelo pode conter cláusulas `LIMIT` arbitrárias ou abusivas (por exemplo, `LIMIT 100000`), forçando ordenações custosas ou violando o princípio de limitação estrita de linhas. O validador SQL (`sqlglot`) precisa validar explicitamente qualquer cláusula `LIMIT`, rejeitando consultas cujo `LIMIT` solicitado supere o teto configurado (`QUERY_MAX_ROWS`, padrão 100) ou que contenham valores inválidos/negativos.
3. **Ausência de teto de tokens por conversa:** Não há limite para a quantidade total de tokens consumidos ao longo do ciclo de vida de uma conversa. Conversas excessivamente longas geram aumento linear no tamanho do contexto enviado nas mensagens subsequentes, elevando custos e latência de inferência. É indispensável introduzir um teto configurável de tokens por conversa (`CONVERSATION_TOKEN_CEILING`), contabilizando tokens de entrada e saída gastos em cada resposta e bloqueando novas mensagens com HTTP 429 quando a cota for atingida.

## What Changes

- **Aplicação de `statement_timeout` no banco relacional:** Configurar explicitamente `statement_timeout` no PostgreSQL na transação efêmera de consulta somente leitura, mapeando o erro de cancelamento retornado pelo PostgreSQL (`57014` / `canceling statement due to statement timeout`) como `QueryTimeoutError` limpo ("Tempo limite de execução esgotado"), sem vazar credenciais ou detalhes de conexão.
- **Validação de cláusula `LIMIT` no validador SQL:** Inspecionar nós de limite na AST (`exp.Limit`). Se uma cláusula `LIMIT` for informada, validar se o valor é positivo e menor ou igual a `QUERY_MAX_ROWS`. Caso o `LIMIT` exceda `QUERY_MAX_ROWS`, recusar determinística e preventivamente a consulta com mensagem instrutiva ao modelo antes do envio à origem.
- **Teto e persistência de tokens por conversa:**
  - Adicionar o campo `total_tokens` (inteiro, padrão 0) à tabela `conversations` via migração Alembic.
  - Expor `total_tokens` no schema `ConversationPublic`.
  - Configurar `CONVERSATION_TOKEN_CEILING` em `Settings` (padrão 100.000 tokens; 0 para desligado).
  - No fluxo de geração de mensagens (`ChatService`), somar os tokens utilizados na resposta (input_tokens e output_tokens) ao `total_tokens` da conversa.
  - Bloquear novas mensagens em conversas cujo `total_tokens` já atingiu ou superou `CONVERSATION_TOKEN_CEILING`, respondendo HTTP 429 Too Many Requests tanto em `POST /conversations/{id}/messages` quanto em `POST /conversations/{id}/messages/stream`.
- **Aviso na interface de demonstração (`/demo`):** Tratar status HTTP 429 na página `/demo` com mensagem explicativa no banner e no chat informando que o limite de tokens da conversa foi atingido e orientando a iniciar uma nova conversa.

### Fora do escopo

- Rate limiting global por endereço IP ou cliente externo (será responsabilidade do gateway ou do `observatorio-idp`).
- Sumarização ou compactação automática de mensagens antigas da conversa (quando a cota é atingida, a conversa é encerrada e uma nova deve ser iniciada).
- Alterações em schemas de bancos de dados externos das fontes do catálogo (permanecem estritamente somente leitura).

## Capabilities

### Modified Capabilities

- `data-querying`: Validação explícita de `LIMIT` na AST prevenindo valores superiores ao teto `QUERY_MAX_ROWS`, e execução de consultas com `statement_timeout` ativo no banco PostgreSQL com tratamento de cancelamento.
- `conversation-messaging`: Verificação preventiva do teto de tokens da conversa antes da execução do modelo, recusa com HTTP 429 para conversas esgotadas e acumulação dos tokens consumidos na resposta.
- `conversation-management`: Persistência de `total_tokens` na entidade de conversa e exposição do campo na consulta e listagem de conversas.
- `demo-page`: Apresentação amigável de erro 429 com orientação ao usuário quando o teto de tokens for atingido.

## Impact

- **Bancos externos:** Nenhum impacto estrutural ou de escrita em bancos externos (permanecem somente leitura). No PostgreSQL, a transação da consulta executa com `SET LOCAL statement_timeout`.
- **Segredos:** Nenhum segredo novo ou alterado. Nova variável de configuração `CONVERSATION_TOKEN_CEILING` documentada no `.env.example` e `README.md`.
- **Endpoints sem autenticação:** Os endpoints de envio e streaming de mensagens (`/conversations/{id}/messages` e `/conversations/{id}/messages/stream`) continuam sem autenticação e passam a responder HTTP 429 quando a conversa exceder o teto de tokens.
- **Dependências entre mudanças:** Nenhuma dependência em andamento. Todas as mudanças anteriores foram devidamente arquivadas.
