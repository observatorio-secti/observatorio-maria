# Design: Limites de Recurso

## Arquitetura e Decisões

### 1. Aplicação de `statement_timeout` no motor do banco de dados (PostgreSQL)

- **Abordagem:** Na execução de consultas contra fontes externas do catálogo no backend PostgreSQL (`src/observatorio_maria/query/execution.py`), executar `SET LOCAL statement_timeout = <timeout_ms>` dentro de um bloco transacional explícito (`async with conn.begin():`).
- **Tratamento de timeout no servidor:** Capturar cancelamentos emitidos pelo PostgreSQL (código SQLSTATE `57014` ou mensagem contendo `canceling statement due to statement timeout`) e convertê-los em `QueryTimeoutError('Tempo limite de execução esgotado')`, garantindo que URLs ou segredos de conexão continuem devidamente sanitizados.
- **Alternativa descartada:** Configurar `statement_timeout` na URL de conexão ou globalmente no banco de dados.
- **Motivo do descarte:** Bancos externos são mantidos por terceiros e estritamente somente leitura para a Maria; alterar configurações de usuário ou banco violaria o princípio de não modificar bancos externos. O uso de `SET LOCAL` tem escopo restrito à transação atual e não afeta outras conexões.

### 2. Validação determinística de `LIMIT` no validador SQL

- **Abordagem:** No módulo `src/observatorio_maria/query/validator.py`, inspecionar nós de limite na AST (`exp.Limit`). Caso a cláusula `LIMIT` esteja presente:
  1. Extrair o valor da expressão limite.
  2. Verificar se é um número inteiro válido maior que 0.
  3. Se o limite exceder `QUERY_MAX_ROWS` (padrão 100), rejeitar com `QueryValidationError(f'O limite solicitado na consulta ({limit}) excede o máximo permitido ({max_rows})')`.
- **Alternativa descartada:** Reescrever silenciosamente o `LIMIT` na AST para `QUERY_MAX_ROWS`.
- **Motivo do descarte:** Alterar o limite silenciosamente pode gerar confusão ou mascarar suposições incorretas do modelo de linguagem. Recusar com explicação permite que a IA compreenda o teto e reformule a consulta dentro do orçamento.

### 3. Teto e acumulação de tokens por conversa

- **Abordagem:**
  - Adicionar a coluna `total_tokens` (INTEGER, not null, padrão 0) na tabela `conversations`.
  - Configurar `CONVERSATION_TOKEN_CEILING` em `Settings` (padrão 100.000 tokens; 0 desativa a restrição).
  - No `ChatService`, ao final da resposta acumulada, extrair os tokens usados (`input_tokens + output_tokens`) reportados em `usage_metadata` do LangChain e somá-los ao `total_tokens` da conversa no commit final da mensagem.
  - No início de `send_message` e `stream_message`, se `conversation.total_tokens >= settings.CONVERSATION_TOKEN_CEILING` (e ceiling > 0), levantar exceção `ConversationTokenLimitExceededError`.
- **Alternativa descartada:** Estimar tokens em runtime rodando biblioteca de tokenização (ex.: `tiktoken`) em cada requisição.
- **Motivo do descarte:** A estimativa local é custosa computacionalmente, não reflete o faturamento exato do provedor e desconsidera tokens de tool calls intermediárias. O uso de `usage_metadata` reportado pelo provedor fornece a métrica canônica sem overhead.

### 4. Código de resposta HTTP 429 para teto de tokens

- **Abordagem:** Tanto o endpoint síncrono (`POST /conversations/{id}/messages`) quanto o de streaming (`POST /conversations/{id}/messages/stream`) retornam HTTP 429 Too Many Requests com `detail='Limite de tokens da conversa atingido. Inicie uma nova conversa para continuar.'` quando a cota estiver esgotada antes do processamento.
- **Alternativa descartada:** Responder HTTP 400 Bad Request ou HTTP 403 Forbidden.
- **Motivo do descarte:** HTTP 429 é o status canônico do protocolo HTTP para esgotamento de cotas de uso. HTTP 400 sugeriria payload malformado e HTTP 403 sugeriria falta de autenticação/permissão de acesso.

## Migration Plan

- **Migração Alembic:** Adiciona `total_tokens` à tabela `conversations`.
  - Operação de upgrade:
    ```python
    op.add_column(
        'conversations',
        sa.Column('total_tokens', sa.Integer(), server_default=sa.text('0'), nullable=False),
    )
    ```
  - Operação de downgrade (rollback):
    ```python
    op.drop_column('conversations', 'total_tokens')
    ```
- **Efeito sobre dados existentes:** Todas as conversas existentes no banco recebem `total_tokens = 0` via default no banco, sem quebra de integridade ou valores nulos.

## Riscos e Mitigações

- `[Risco: Modelos falsos (fakes) em testes que não fornecem usage_metadata quebrarem a acumulação] → Mitigação:` Tratar `usage_metadata` como opcional defensivamente: se não houver metadados de uso, assumir 0 tokens consumidos sem lançar erro.
- `[Risco: Consulta legítima com LIMIT menor ou igual ao máximo ser rejeitada] → Mitigação:` Permitir qualquer valor de limite inteiro positivo menor ou igual a `QUERY_MAX_ROWS`.
- `[Risco: Erro de statement_timeout vazar dados ou conexão no PostgreSQL] → Mitigação:` Passar a exceção pelo filtro de sanitização `_clean_error` e convertê-la em `QueryTimeoutError` amigável sem expor detalhes internos.
- `[Risco: Bloqueio do streaming produzir resposta SSE parcial ou quebrada] → Mitigação:` A verificação do teto de tokens é executada antes do primeiro `yield` no FastAPI, retornando HTTP 429 antes de iniciar o stream SSE.
