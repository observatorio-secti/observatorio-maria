# Tasks

## 1. Conectores lógicos e EXISTS no validador SQL

- [x] 1.1 Incluir `exp.Exists` em `ALLOWED_FUNC_CLASSES` em `src/observatorio_maria/query/validator.py`, permitir `*` dentro de subconsultas `EXISTS` em `_check_stars` e utilizar `traverse_scope` para resolução correta de tabelas em subconsultas.
- [x] 1.2 Adicionar testes unitários em `tests/test_query_validation.py` verificando que consultas com subconsultas `EXISTS (...)` e conectores lógicos são aceitas com sucesso.
- [x] 1.3 Garantir que funções não permitidas continuem sendo rejeitadas dentro ou fora de `EXISTS`.

## 2. Prompt e sintaxe do MATCH_TEXT

- [x] 2.1 Atualizar `TOOL_RULES_PROMPT` em `src/observatorio_maria/llm/prompts.py` explicitando a sintaxe funcional `MATCH_TEXT(coluna, 'termo1', 'termo2', ...)` e instruindo a não usar operadores infixos ou `%`.
- [x] 2.2 Garantir que a geração do prompt de sistema e os testes de mensagens continuam passando em conformidade.

## 3. Catálogo e colunas pesquisáveis

- [x] 3.1 Marcar `termo_normalizado` como `searchable: true` em `palavras_chave` e `areas_conhecimento` no arquivo `catalog/fomento.yaml`.
- [x] 3.2 Reexecutar o seed e sincronizar via API, verificando que as colunas pesquisáveis possuem `searchable = 1` e `present = 1` no banco `observatorio.db`.

## 4. Verificação ponta a ponta e qualidade

- [x] 4.1 Executar a suíte de testes (`PATH=.venv/bin:$PATH pytest`) e o linter (`PATH=.venv/bin:$PATH task lint`) com 100% de sucesso (170 testes aprovados).
- [x] 4.2 Validar a execução com simulação direta no banco PostgreSQL e inspecionar que queries geradas com `EXISTS` e `MATCH_TEXT` funcionam sem falhas (retornando 150 bolsas e 140 projetos reais de dengue).
