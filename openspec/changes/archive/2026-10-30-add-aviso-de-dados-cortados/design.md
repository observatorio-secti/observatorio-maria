# Design

## Context

Motivação em `proposal.md`. Estado atual:

- **Execução:** `execute_readonly_query` lê uma linha além do limite e marca `truncated` quando ela existe. O resultado chega a `QueryResult.truncated`.
- **Modelo:** recebe `truncated` no JSON da ferramenta e no atributo de `<untrusted_database_data>`, sem regra sobre o que fazer com ele.
- **Blocos:** `show_chart` e `show_table` não copiam `truncated`. Na leitura, `ChartBlock` e `TableBlock` validam o JSON gravado.
- **Demo:** `.message .meta` já define o estilo discreto usado na hora da mensagem.

## Goals / Non-Goals

**Goals:**
- O corte fica visível no bloco, sem depender do texto do modelo.
- Mensagens gravadas seguem válidas, sem migração.

**Non-Goals:**
- Informar o total real de linhas: exigiria um `COUNT` a mais na origem.

## Decisions

### D1. Booleano no bloco, com padrão falso

`truncated: bool = False` em `ChartBlock` e `TableBlock`. O padrão resolve as mensagens antigas na leitura.

Descartada: migrar `messages.content`. Reescrever JSON gravado não traz ganho, porque a ausência já significa que não há aviso a mostrar.

### D2. Aviso também no bloco, além da regra do prompt

O bloco leva o dado, e o cliente mostra o aviso mesmo que o modelo o omita.

Descartada: confiar só no texto do modelo. A regra pode falhar, e o gráfico continuaria parecendo completo.

### D3. Texto do aviso sem o total

A demo mostra "Mostrando só as primeiras N linhas: o resultado foi cortado pelo limite da consulta.", com N vindo de `data` ou `rows`. Um helper `truncationNotice(block, count)` em `demo/app.js` atende os dois renderizadores.

Descartada: contar o total na origem. Seria uma consulta a mais por resposta, sobre um banco de outro sistema.

## Risks / Trade-offs

- [Risco] Uma consulta com `LIMIT` igual a `QUERY_MAX_ROWS` escrito pelo modelo corta dados sem marcar `truncated` → Fica fora desta mudança, porque não dá para distinguir de um limite intencional sem contar as linhas.
- [Risco] O modelo citar total do recorte como completo → A regra proíbe, e o aviso no bloco fica como segunda proteção.
