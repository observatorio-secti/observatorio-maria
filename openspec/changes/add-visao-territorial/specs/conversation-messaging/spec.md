# Spec Delta

## ADDED Requirements

### Requirement: Orientação de gráficos de barras
O modelo SHALL poder pedir `orientation` igual a `horizontal` em gráficos `bar`. O bloco `chart` SHALL trazer `orientation`, com padrão `vertical`. O sistema MUST recusar `horizontal` em outros tipos e SHALL enviar o motivo ao modelo. Mensagens gravadas sem o campo MUST voltar com `vertical`.

#### Scenario: Ranking na horizontal
- **WHEN** o modelo pede um gráfico `bar` com `territorio` no eixo x, a série `pesquisadores` e `orientation` igual a `horizontal`
- **THEN** o bloco `chart` traz `orientation` igual a `horizontal` e um registro por território

#### Scenario: Orientação em tipo inválido
- **WHEN** o modelo pede um gráfico `line` com `orientation` igual a `horizontal`
- **THEN** o gráfico não é incluído e o modelo recebe o motivo

#### Scenario: Mensagem antiga
- **WHEN** uma mensagem gravada sem `orientation` é lida pela API
- **THEN** o bloco volta com `orientation` igual a `vertical`

### Requirement: Empilhamento de gráficos de barras
O modelo SHALL poder pedir `stacking` igual a `absolute` ou `percent` em gráficos `bar` com ao menos duas séries, informadas em `series` ou geradas por `group_by`. O bloco SHALL trazer `stacking`, nulo por padrão. O sistema MUST recusar o pedido em outros tipos ou com uma só série e SHALL enviar o motivo ao modelo.

#### Scenario: Barras empilhadas por categoria
- **WHEN** o modelo pede um gráfico `bar` com `territorio` no eixo x, `total` como série, `group_by` em `tipo` e `stacking` igual a `absolute`
- **THEN** o bloco tem uma série por tipo e `stacking` igual a `absolute`

#### Scenario: Empilhamento com uma série
- **WHEN** o modelo pede `stacking` num gráfico `bar` com uma só série
- **THEN** o gráfico não é incluído e o modelo recebe o motivo

#### Scenario: Empilhamento em linha
- **WHEN** o modelo pede `stacking` num gráfico `line`
- **THEN** o gráfico não é incluído e o modelo recebe o motivo

### Requirement: Valores absolutos no empilhamento 100%
Com `stacking` igual a `percent`, `data` MUST guardar os valores absolutos do resultado, e a proporção SHALL ser calculada por quem renderiza. O sistema MUST recusar o pedido quando alguma série tiver valor negativo e SHALL enviar o motivo ao modelo.

#### Scenario: Dados preservados
- **WHEN** o modelo pede um gráfico com `stacking` igual a `percent` e valores 30 e 10 no mesmo `x`
- **THEN** `data` guarda 30 e 10

#### Scenario: Valor negativo
- **WHEN** uma série do pedido com `stacking` igual a `percent` tem valor negativo
- **THEN** o gráfico não é incluído e o modelo recebe o motivo

### Requirement: Gráfico de rosca
O sistema SHALL aceitar o tipo `donut` em `chart_type`, com as mesmas regras de `pie`: uma série, `x` sem repetição e sem `group_by`. O sistema MUST recusar `orientation` e `stacking` nesse tipo.

#### Scenario: Rosca criada
- **WHEN** o modelo pede um gráfico `donut` com 4 linhas, `x` sem repetição e uma série
- **THEN** o bloco `chart` tem `chart_type` igual a `donut` e 4 registros

#### Scenario: Rosca com group_by
- **WHEN** o modelo pede um gráfico `donut` com `group_by`
- **THEN** o gráfico não é incluído e o modelo recebe o motivo

### Requirement: Limite de fatias em pizza e rosca
O sistema MUST recusar gráficos `pie` e `donut` com mais de 5 registros. O motivo enviado ao modelo SHALL orientar a usar barras ou a reduzir as fatias na consulta, reunindo as demais em "Outros" só quando a medida for aditiva.

#### Scenario: Pizza com muitas fatias
- **WHEN** o modelo pede um gráfico `pie` a partir de um resultado com 27 territórios
- **THEN** o gráfico não é incluído e o modelo recebe a orientação de usar barras ou reduzir as fatias

#### Scenario: Limite exato
- **WHEN** o modelo pede um gráfico `donut` a partir de um resultado com 5 linhas
- **THEN** o bloco `chart` é criado

### Requirement: Escolha do formato pelo modelo
As instruções do modelo SHALL orientar: barras horizontais para rankings com muitas categorias ou rótulos longos; empilhamento só quando as partes não se sobrepõem e a soma tem sentido; `percent` para comparar composição; e pizza ou rosca só com até 5 partes de um mesmo todo.

#### Scenario: Instruções no prompt
- **WHEN** o prompt de sistema da Maria é montado
- **THEN** ele traz a orientação sobre barras horizontais, empilhamento e o limite de partes em pizza e rosca

### Requirement: Reapresentação com novos formatos
Ao reapresentar um gráfico anterior a partir de um resultado `h1`, `h2`…, o modelo SHALL poder usar `orientation`, `stacking` e `donut`, com as mesmas validações, sem nova consulta.

#### Scenario: Gráfico agrupado passa a empilhado
- **WHEN** o modelo reapresenta um gráfico agrupado com duas séries, informando as chaves delas em `series` e `stacking` igual a `percent`
- **THEN** o novo bloco é criado sem consultar as origens e herda `truncated` e `origin`
