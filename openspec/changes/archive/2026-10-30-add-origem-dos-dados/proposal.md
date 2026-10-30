# Proposal

## Why

Gráficos e tabelas não dizem de onde vieram os dados. A atividade da consulta some ao fim da resposta e não é gravada, e a citação da fonte depende do texto do modelo. Num observatório, quem lê precisa saber a origem e a data de cada número para citar e confiar no dado.

## What Changes

- **Campo nos blocos:** `chart` e `table` ganham `origin` opcional, com os nomes das fontes, a descrição da consulta, a data e hora da consulta e, entre fontes, a cobertura.
- **Registro automático:** a origem vem do resultado usado no bloco, não de um argumento do modelo. Quando o bloco usa uma consulta, é essa consulta que aparece.
- **Privacidade:** a descrição passa pelo mascaramento de CPF e e-mail. O SQL e os nomes de tabelas ficam de fora do bloco.
- **Instrução da ferramenta:** o `purpose` das consultas passa a pedir linguagem de quem lê, sem nomes de tabelas ou colunas.
- **Demo:** rodapé abaixo do bloco, com fonte, descrição, data e cobertura. O exemplo da aba "Contrato de blocos" mostra o campo.

### Fora do escopo

- Exibir o SQL: fica nos traces do Phoenix, para quem audita.
- Data de atualização dos dados na origem: os catálogos não têm essa informação.
- Links para os sistemas de origem.
- Levar a origem ao histórico do modelo.
- Exportar a origem junto com os dados: entra com `add-exportar-respostas`.

## Capabilities

### New Capabilities

Nenhuma.

### Modified Capabilities

- `conversation-messaging`: origem dos dados nos blocos.
- `demo-page`: rodapé de origem nas respostas.

## Impact

- **Código:** `schemas.py`, `query/execution.py`, `query/tool.py`, `demo/app.js` e `demo/styles.css`.
- **API:** campo novo e opcional nos blocos. Clientes que não o conhecem continuam funcionando, e mensagens gravadas voltam com `origin` nulo.
- **Testes:** `tests/test_agent_chat.py` e `tests/test_agent_across_sources.py`.
- **Documentação:** seção de blocos em **🌐 API** e seção **🎬 Demo** no README.
- **LGPD:** a descrição fica gravada no bloco, por isso é mascarada.
- **Bancos externos, segredos e endpoints sem autenticação:** não são tocados. Nenhuma consulta nova é feita às origens.
- **Dependências:** nenhuma mudança pendente; `add-aviso-de-dados-cortados` já foi arquivada.
