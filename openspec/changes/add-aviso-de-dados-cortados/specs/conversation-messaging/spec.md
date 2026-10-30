# Spec Delta

## ADDED Requirements

### Requirement: Indicação de dados cortados nos blocos
Os blocos `chart` e `table` SHALL ter o campo `truncated`, verdadeiro quando o resultado usado foi cortado pelo limite de linhas da consulta. Mensagens gravadas sem o campo MUST ser devolvidas com o valor falso.

#### Scenario: Resultado cortado
- **WHEN** o modelo pede um gráfico e uma tabela a partir de um resultado cortado em `QUERY_MAX_ROWS` linhas
- **THEN** os dois blocos têm `truncated` igual a verdadeiro

#### Scenario: Resultado completo
- **WHEN** o modelo pede um gráfico a partir de um resultado que não foi cortado
- **THEN** o bloco tem `truncated` igual a falso

#### Scenario: Mensagem gravada antes do campo
- **WHEN** o cliente lê uma resposta antiga com um bloco `table` sem `truncated`
- **THEN** a API devolve o bloco com `truncated` igual a falso

### Requirement: Resposta sobre dados cortados
As instruções do modelo MUST mandar dizer que os dados são parciais quando um resultado vier cortado, preferir uma consulta agregada e não apresentar totais ou rankings do recorte como completos.

#### Scenario: Instrução presente
- **WHEN** o modelo recebe as instruções de sistema com fontes consultáveis
- **THEN** elas tratam de resultados cortados, com as três orientações
