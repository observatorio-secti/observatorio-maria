# Design

## Overview

Esta mudança resolve as falhas em consultas textuais e compostas da Maria:
1. Permite operadores lógicos (`AND`, `OR`, `XOR`) e predicados `EXISTS` no validador SQL baseado em `sqlglot`.
2. Explicita no prompt do sistema o formato de invocação de `MATCH_TEXT(coluna, 'termo1', 'termo2')` e orienta a evitar operadores de similaridade não padrão (como `%`).
3. Habilita `searchable: true` em colunas normalizadas (`palavras_chave.termo_normalizado` e `areas_conhecimento.termo_normalizado`) em `catalog/fomento.yaml`.
4. Garante a integridade e sincronização do banco local `observatorio.db`.

## Technical Decisions

### Decisão 1: Permitir `exp.Connector` e `exp.Exists` no validador SQL

- **Decisão:** Em `src/observatorio_maria/query/validator.py`, adicionar `exp.Connector` e `exp.Exists` à tupla `ALLOWED_FUNC_CLASSES`. Com isso, `exp.And`, `exp.Or`, `exp.Xor` e subconsultas com `EXISTS (...)` passam pela validação de funções sem serem confundidas com chamadas de funções arbitrárias.
- **Alternativa descartada:** Remover a verificação de funções. Descartada pois permitiria a execução de funções de sistema inseguras (`pg_sleep`, `pg_read_file`, etc.).

### Decisão 2: Explicitar sintaxe de `MATCH_TEXT` nas regras de prompt

- **Decisão:** Em `src/observatorio_maria/llm/prompts.py`, ajustar `TOOL_RULES_PROMPT` para declarar explicitamente a assinatura de função `MATCH_TEXT(coluna, 'termo1', 'termo2', ...)` com exemplo claro (ex.: `MATCH_TEXT(p.resumo, 'dengue', 'arbovirose')`) e instruir que não se deve usar como operador infixo nem recorrer a operadores não padrão como `%`.
- **Alternativa descartada:** Deixar apenas o nome `MATCH_TEXT` sem assinatura. Descartada pois o modelo induz o uso infixo (estilo SQLite FTS `coluna MATCH 'termo'`) ou tenta buscar por similaridade com `%`.

### Decisão 3: Tornar `termo_normalizado` pesquisável além de `termo`

- **Decisão:** Adicionar `searchable: true` em `palavras_chave.termo_normalizado` e `areas_conhecimento.termo_normalizado` no arquivo `catalog/fomento.yaml`. Como a descrição das colunas indica que servem para buscas sem acentos, o modelo frequentemente as seleciona.
- **Alternativa descartada:** Ocultar ou proibir `termo_normalizado`. Descartada porque a normalização léxica é compatível com `MATCH_TEXT`.

## Risks & Mitigations

- **[Risco: Conectores lógicos ou EXISTS mascararem funções perigosas] → Mitigação:** A AST do `sqlglot` continua sendo percorrida recursivamente via `walk()`. Expressões internas a `EXISTS (SELECT ...)` têm suas tabelas, colunas e funções validadas normalmente pelas regras do catálogo.
- **[Risco: Aumento do tamanho do prompt do sistema] → Mitigação:** A adição da assinatura e do exemplo no prompt consome menos de 20 tokens, com impacto nulo na latência.

## Migration Plan

Não há alteração de schema DDL. Os dados de catálogo em `observatorio.db` foram sincronizados e refletem as colunas pesquisáveis com `searchable = 1` e `present = 1`.
