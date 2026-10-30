# Proposal

## Why

Pedir "mostra em pizza" ou "agora como tabela" obriga a Maria a refazer a consulta, porque os resultados só valem dentro de uma resposta. Com os valores já no histórico, os blocos gravados bastam para reapresentar os mesmos dados, sem custo nem espera na origem.

## What Changes

- **Blocos anteriores como resultados:** ao iniciar a resposta, gráficos e tabelas de mensagens anteriores viram resultados com ids `h1`, `h2`…, citados no histórico.
- **`show_chart` e `show_table` com esses ids:** a validação de colunas continua a mesma, e só as colunas do bloco anterior estão disponíveis.
- **Procedência mantida:** o novo bloco herda `truncated` e `origin` do original, inclusive a data da consulta.
- **Instrução do modelo:** para mudar a apresentação de dados anteriores, usar o id `hN` sem nova consulta.
- **Correção de tipos das colunas:** gráficos com eixo de texto recebiam o tipo `string`, fora do contrato do bloco, e a resposta falhava ao ser devolvida, depois de gravada. O eixo de texto passa a ser `category`, a coluna de tabela vinda de categoria passa a ser `string`, e blocos já gravados são lidos com a mesma regra. A reapresentação depende disso, porque converte um tipo no outro.

### Fora do escopo

- Filtrar, somar ou recalcular sobre resultados anteriores: nesses casos a Maria consulta de novo.
- Reaproveitar dados de outras conversas.
- Persistir resultados completos: só o que foi gravado nos blocos pode ser reusado.
- Perguntas de continuação em respostas sem consulta.

## Capabilities

### New Capabilities

Nenhuma.

### Modified Capabilities

- `data-querying`: resultados restaurados de blocos anteriores.
- `conversation-messaging`: reapresentação de dados no histórico.

## Impact

- **Código:** `query/execution.py`, `services/chat.py`, `llm/prompts.py`.
- **API:** contrato igual. Blocos novos podem trazer data de consulta anterior à resposta.
- **Custo:** menos consultas às origens.
- **Testes:** `tests/test_agent_chat.py`.
- **Documentação:** seção de blocos em **🌐 API** no README.
- **Bancos externos, segredos e endpoints sem autenticação:** não são tocados. A reapresentação não abre conexão com as origens.
- **Dependências:** nenhuma mudança pendente; `add-valores-no-historico` já foi arquivada.
