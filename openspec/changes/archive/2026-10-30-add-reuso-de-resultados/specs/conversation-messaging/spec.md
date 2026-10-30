# Spec Delta

## ADDED Requirements

### Requirement: Reapresentação de dados anteriores
O histórico SHALL citar o identificador e as chaves das colunas de cada gráfico e tabela anteriores. As instruções do modelo MUST mandar usar esse identificador, sem nova consulta, para mudar a apresentação. O novo bloco MUST herdar `truncated` e `origin` do bloco original.

#### Scenario: Mudar o tipo do gráfico
- **WHEN** o usuário pede "mostra em pizza" depois de um gráfico de barras
- **THEN** a Maria gera um gráfico de pizza com os mesmos dados, sem consulta, e escreve a explicação

#### Scenario: Procedência preservada
- **WHEN** o modelo gera um bloco a partir de `h1`, com `origin` de uma consulta de ontem e `truncated` verdadeiro
- **THEN** o novo bloco traz a mesma origem, com a data de ontem, e `truncated` verdadeiro

#### Scenario: Identificador no histórico
- **WHEN** uma resposta anterior tem um gráfico e uma tabela
- **THEN** o histórico cita `h1` no gráfico e `h2` na tabela, com as chaves das colunas

### Requirement: Tipos das colunas nos blocos
Colunas de texto MUST gerar eixo do tipo `category` em gráficos e coluna do tipo `string` em tabelas. Blocos já gravados com o eixo `string` ou a coluna `category` MUST ser lidos com esses tipos, sem erro.

#### Scenario: Gráfico por categoria
- **WHEN** o modelo pede um gráfico com uma coluna de texto no eixo x
- **THEN** o bloco tem `x.type` igual a `category`, e a resposta é devolvida normalmente, no envio comum e no streaming

#### Scenario: Conversa com bloco antigo
- **WHEN** a conversa tem um gráfico gravado com `x.type` igual a `string`
- **THEN** o histórico abre normalmente, com o tipo `category`

#### Scenario: Gráfico anterior vira tabela
- **WHEN** o modelo gera uma tabela a partir de um gráfico anterior com eixo `category`
- **THEN** a coluna da tabela tem o tipo `string`

