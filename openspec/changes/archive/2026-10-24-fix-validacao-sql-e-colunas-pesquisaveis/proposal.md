# Proposal

## Why

Perguntas simples de busca textual e filtros combinados (como "Existe fomento na temática de dengue?") estavam falhando na Maria com mensagens de recusa ou de fallback:
> "Não consegui confirmar se há fomento na temática de dengue: a consulta às fontes disponíveis falhou, e não tenho resultados confiáveis para afirmar se existem bolsas ou projetos associados."

Ao analisar os traces do Phoenix e o banco de dados da aplicação, identificamos quatro causas:
1. **Bloqueio indevido de conectores lógicos SQL (`AND` / `OR`):** na biblioteca `sqlglot`, os nós `exp.And`, `exp.Or` e `exp.Xor` herdam de `exp.Connector` -> `exp.Binary` -> `exp.Func`. Por não estarem em `ALLOWED_FUNC_CLASSES`, o validador bloqueava consultas com `Função 'and' não permitida`.
2. **Bloqueio de subconsultas com `EXISTS`:** `exp.Exists` herda de `exp.Func` no `sqlglot` e era barrado com `Função 'exists' não permitida`.
3. **Ausência de colunas `searchable` no banco da Maria:** a migração adicionou o campo com `default=False` e o seed canônico ainda não havia populado as colunas no banco SQLite local. Além disso, `termo_normalizado` não estava marcado como pesquisável.
4. **Instrução insuficiente sobre a sintaxe do `MATCH_TEXT`:** o prompt instruía o uso da função sem detalhar a assinatura `MATCH_TEXT(coluna, 'termo')`, levando o modelo a tentar usá-la como operador infixo (`coluna MATCH_TEXT 'termo'`) ou tentar inventar operadores de similaridade como `%` (`p.nome % 'dengue'`).

## What Changes

- **Permissão explícita de conectores lógicos no validador SQL:** incluir `exp.Connector` (`exp.And`, `exp.Or`, `exp.Xor`) em `ALLOWED_FUNC_CLASSES` no `src/observatorio_maria/query/validator.py`.
- **Permissão de predicados `EXISTS` no validador SQL:** incluir `exp.Exists` em `ALLOWED_FUNC_CLASSES` para aceitar subconsultas de correlação comuns em filtros complexos.
- **Habilitação de colunas pesquisáveis:** marcar `termo_normalizado` e `termo` de `palavras_chave` e `areas_conhecimento` como `searchable: true` em `catalog/fomento.yaml`, e manter o banco sincronizado com `searchable = 1` e `present = 1`.
- **Explicitação da sintaxe de `MATCH_TEXT` no prompt da Maria:** atualizar `TOOL_RULES_PROMPT` em `src/observatorio_maria/llm/prompts.py` fornecendo o formato exato `MATCH_TEXT(coluna, 'termo1', 'termo2')` e orientando a não usar operadores de similaridade não padrão como `%`.
- **Testes automatizados:** adicionar testes cobrindo validação de queries com `AND`, `OR`, `EXISTS` e sintaxe correta de `MATCH_TEXT`.

### Fora do escopo

- Alterações estruturais ou adições de tabelas de schema (não requer nova migração Alembic).
- Modificação na engine de busca textual `MATCH_TEXT` ou tradução para SQLite/PostgreSQL (a função de reescrita já está correta).
- Adição de novos modelos de linguagem ou novas ferramentas ao agente.

## Capabilities

### Modified Capabilities

- `data-querying`: o validador SQL passa a permitir expressamente conectores lógicos (`AND`, `OR`, `XOR`) e subconsultas `EXISTS`, e a instrução no prompt orienta a sintaxe funcional de `MATCH_TEXT`.
- `data-catalog`: colunas de busca textual normalizadas passam a constar canonicamente como pesquisáveis no YAML e no banco de dados.

## Impact

- **Bancos externos:** nenhum impacto sobre schemas externos. As fontes continuam sendo consultadas de forma estritamente somente leitura.
- **Segredos:** nenhum segredo novo ou alterado.
- **Endpoints sem autenticação:** nenhum novo endpoint criado; os endpoints existentes mantêm seus contratos.
- **Código:** `src/observatorio_maria/query/validator.py`, `src/observatorio_maria/llm/prompts.py`, `catalog/fomento.yaml` e suíte de testes.
- **Dependências entre mudanças:** nenhuma dependência em andamento. Todas as mudanças anteriores estão arquivadas.
