# Spec Delta

## ADDED Requirements

### Requirement: Rótulos das visualizações
O modelo SHALL poder informar rótulos por coluna ao pedir um gráfico ou uma tabela. Coluna sem rótulo MUST usar a chave com `_` trocado por espaço e inicial maiúscula. Rótulo de coluna que não faz parte do bloco MUST ser ignorado, sem recusar a visualização.

#### Scenario: Gráfico com rótulos
- **WHEN** o modelo pede um gráfico com `ano_inicio` no eixo x, a série `total_bolsas` e os rótulos "Ano de início" e "Bolsas concedidas"
- **THEN** o bloco `chart` traz esses textos em `x.label` e em `series[].label`, e as chaves continuam `ano_inicio` e `total_bolsas`

#### Scenario: Tabela com rótulos
- **WHEN** o modelo pede uma tabela com a coluna `nome` e o rótulo "Instituição"
- **THEN** a coluna do bloco `table` tem `key` igual a `nome` e `label` igual a "Instituição"

#### Scenario: Sem rótulo
- **WHEN** o modelo pede um gráfico sem rótulos, com a série `total_bolsas`
- **THEN** o rótulo da série é "Total bolsas"

#### Scenario: Rótulo de coluna fora do bloco
- **WHEN** o modelo informa um rótulo para uma coluna que não está na visualização
- **THEN** a visualização é gerada normalmente, sem esse rótulo

### Requirement: Unidades das séries
O modelo SHALL poder informar a unidade de cada série de um gráfico, gravada em `series[].unit`. Série sem unidade MUST ficar com `unit` nulo. As instruções do modelo MUST pedir rótulos legíveis em português e proibir inventar unidade sem base nos dados ou no catálogo.

#### Scenario: Série com unidade
- **WHEN** o modelo pede um gráfico com a série `orcamento` e a unidade "R$"
- **THEN** a série do bloco `chart` tem `unit` igual a "R$"

#### Scenario: Instrução presente
- **WHEN** o modelo recebe as instruções de sistema com fontes consultáveis
- **THEN** elas pedem rótulos legíveis em português e proíbem inventar unidades
