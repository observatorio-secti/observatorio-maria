# Proposal

## Why

A pergunta "Como varia por ano a publicação de artigos Qualis A1 entre as modalidades de bolsa?" gerou um gráfico com uma única linha em forma de serra. O resultado tinha uma linha por ano e modalidade, mas `show_chart` não sabe separar séries por uma coluna de categoria: ele descarta a modalidade e desenha vários pontos por ano, na ordem das linhas. O gráfico sugere quedas anuais que não existem, e o CSV sai sem a modalidade.

## What Changes

- **`group_by` em `show_chart`:** o modelo informa a coluna de categoria, e o servidor gera uma série por valor, com uma linha por valor de `x` em `data`.
- **Recusa de `x` repetido:** sem `group_by`, um gráfico de barras, linha, área ou pizza com `x` repetido é recusado, e o modelo recebe o motivo.
- **Limite de 5 grupos:** acima disso o gráfico é recusado, e o modelo é orientado a reduzir os grupos na consulta.
- **Campo `group` no bloco `chart`:** opcional, com a coluna que separou as séries.
- **Histórico:** em gráficos agrupados, os valores do banco não aparecem no resumo fora de `<untrusted_database_data>`.
- **Demo:** o aviso de corte de gráficos agrupados deixa de citar número de linhas, que já não corresponde ao resultado.

### Fora do escopo

- Somar grupos menores em "Outras" no servidor: a soma só vale para medidas aditivas.
- Corrigir gráficos já gravados: a modalidade não foi guardada neles.
- Título do eixo y em gráficos com várias séries.
- Mudanças no `observatorio-front`: gráficos agrupados chegam como várias séries comuns.

## Capabilities

### New Capabilities

Nenhuma.

### Modified Capabilities

- `conversation-messaging`: novos requisitos para séries por categoria, `x` repetido, limite de grupos e histórico de gráficos agrupados.

## Impact

- **Código:** `query/tool.py`, `services/chat.py`, `schemas.py`, `llm/prompts.py`, `demo/app.js` e `demo/styles.css`.
- **API:** novo campo opcional `group` no bloco `chart`. Mensagens gravadas voltam com `group` nulo.
- **Documentação:** seção do contrato de blocos no `README.md`.
- **Bancos externos:** não toca.
- **Segredos:** não toca.
- **Endpoints sem autenticação:** nenhum endpoint novo.
