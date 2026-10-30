# Spec Delta

## ADDED Requirements

### Requirement: Origem dos dados nos blocos
Os blocos `chart` e `table` gerados a partir de uma consulta SHALL ter o campo `origin`, com os nomes das fontes, a descrição da consulta e a data e hora da consulta. Mensagens gravadas sem o campo MUST ser devolvidas com `origin` nulo.

#### Scenario: Consulta a uma fonte
- **WHEN** o modelo pede um gráfico a partir de uma consulta à fonte "Fomento à Pesquisa" com a descrição "Bolsas por ano"
- **THEN** `origin` traz essa fonte, essa descrição e a data e hora da consulta

#### Scenario: Consulta sem descrição
- **WHEN** a consulta usada não tem descrição
- **THEN** `origin` traz a descrição padrão com o nome da fonte

#### Scenario: Blocos de consultas diferentes
- **WHEN** o modelo faz duas consultas e pede um bloco de cada resultado
- **THEN** cada bloco traz a origem da consulta que o gerou

#### Scenario: Mensagem gravada antes do campo
- **WHEN** o cliente lê uma resposta antiga com um bloco `chart` sem `origin`
- **THEN** a API devolve o bloco com `origin` nulo

### Requirement: Origem de consultas entre fontes
Um bloco gerado por uma consulta entre fontes SHALL trazer em `origin` os nomes das duas fontes e, quando a cobertura estiver disponível, quantas chaves a fonte de origem tem e quantas foram encontradas. Sem cobertura disponível, o campo `coverage` MUST ficar nulo.

#### Scenario: Cobertura disponível
- **WHEN** o modelo pede uma tabela de uma consulta entre fontes com 1 chave encontrada de 19
- **THEN** `origin` traz as duas fontes e `coverage` com `keys` igual a 19 e `found` igual a 1

#### Scenario: Cobertura indisponível
- **WHEN** a consulta entre fontes não tem cobertura disponível
- **THEN** `origin` traz as duas fontes e `coverage` nulo

### Requirement: Origem sem detalhes internos
O campo `origin` MUST NOT conter SQL, nomes de variáveis de conexão ou o identificador do resultado. A descrição MUST passar pelo mascaramento de CPF e e-mail e MUST ser trocada pela descrição padrão quando for um SQL. A instrução da ferramenta de consulta SHALL pedir uma descrição em linguagem de quem lê.

#### Scenario: Descrição com dado pessoal
- **WHEN** a descrição da consulta contém um e-mail
- **THEN** `origin` traz a descrição com o e-mail mascarado

#### Scenario: Descrição com SQL
- **WHEN** o modelo informa um `SELECT` como descrição da consulta
- **THEN** `origin` traz a descrição padrão, sem o SQL
