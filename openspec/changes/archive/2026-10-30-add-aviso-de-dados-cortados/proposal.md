# Proposal

## Why

Consultas devolvem no máximo `QUERY_MAX_ROWS` linhas (padrão 100). O modelo recebe a indicação `truncated`, mas ela não chega aos blocos, e nenhuma regra manda avisar. Um gráfico ou uma tabela com só parte dos dados parece completo, e num observatório isso pode levar a conclusões erradas.

## What Changes

- **Campo nos blocos:** `chart` e `table` ganham `truncated`, com padrão `false`, preenchido a partir do resultado da consulta.
- **Instrução do modelo:** quando um resultado vier cortado, o modelo deve dizer que os dados são parciais e preferir uma consulta agregada, sem apresentar totais ou rankings do recorte como completos.
- **Demo:** aviso discreto abaixo do bloco cortado, com a quantidade de linhas mostradas.

### Fora do escopo

- Aumentar `QUERY_MAX_ROWS` ou paginar resultados.
- Detectar corte por `LIMIT` escrito na consulta: pode ser intencional, como em "top 5".
- Levar a indicação ao histórico do modelo: entra com `add-valores-no-historico`.
- Limitar o número de fatias ou categorias de um gráfico.

## Capabilities

### New Capabilities

Nenhuma.

### Modified Capabilities

- `conversation-messaging`: indicação de corte nos blocos e regra na instrução do modelo.
- `demo-page`: aviso de dados parciais nas respostas.

## Impact

- **Código:** `schemas.py`, `query/tool.py`, `llm/prompts.py`, `demo/app.js` e `demo/styles.css`.
- **API:** campo novo e opcional nos blocos. Clientes que não o conhecem continuam funcionando, e mensagens gravadas valem como `false`.
- **Testes:** `tests/test_agent_chat.py`.
- **Documentação:** seção de blocos em **🌐 API** no README.
- **Bancos externos, segredos e endpoints sem autenticação:** não são tocados.
- **Dependências:** nenhuma mudança pendente; `add-rotulos-em-graficos` já foi arquivada.
