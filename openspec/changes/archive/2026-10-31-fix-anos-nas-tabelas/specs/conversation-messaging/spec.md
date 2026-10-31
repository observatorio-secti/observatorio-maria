# Spec Delta

## ADDED Requirements

### Requirement: Colunas de ano nas tabelas
Uma coluna de bloco `table` MUST ter o tipo `string` quando a chave tiver o termo `ano` ou `year`, separado por `_` ou nas pontas, e todos os valores não nulos forem inteiros de 1900 a 2100. Os valores nas linhas MUST continuar numéricos. A regra SHALL valer para blocos novos, no streaming e nos gravados.

#### Scenario: Tabela por ano
- **WHEN** o modelo gera uma tabela com a coluna `year` e os valores 2020 a 2026
- **THEN** a coluna tem o tipo `string` e as linhas trazem os valores 2020 a 2026 como números

#### Scenario: Ano no streaming
- **WHEN** uma tabela com a coluna `ano_inicio` chega em `content.delta`
- **THEN** o bloco do evento já traz a coluna com o tipo `string`

#### Scenario: Conversa com tabela antiga
- **WHEN** a conversa tem uma tabela gravada com a coluna `ano` do tipo `number` e valores 2019 e 2020
- **THEN** o histórico devolve a coluna com o tipo `string`

#### Scenario: Valor por ano
- **WHEN** a coluna `valor_por_ano` tem valores como 125000
- **THEN** a coluna continua com o tipo `number`

#### Scenario: Nome que só contém o termo
- **WHEN** a coluna `anos_de_vigencia` ou `plano` tem valores entre 1900 e 2100
- **THEN** a coluna continua com o tipo `number`

#### Scenario: Ano com valor nulo
- **WHEN** a coluna `start_year` tem os valores 2021, nulo e 2022
- **THEN** a coluna tem o tipo `string`
