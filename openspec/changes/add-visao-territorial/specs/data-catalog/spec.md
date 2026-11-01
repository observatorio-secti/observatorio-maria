# Spec Delta

## ADDED Requirements

### Requirement: Pesquisadores por território no Simcc
As instruções da fonte `simcc` SHALL dizer que o território de identidade é do vínculo em `researcher_institution`, que um pesquisador pode contar em mais de um território e que a contagem usa `COUNT(DISTINCT researcher_id)`. MUST dizer para não somar os territórios como total geral de pesquisadores.

#### Scenario: Orientação no contexto
- **WHEN** a prévia do contexto da fonte `simcc` é gerada a partir do seed
- **THEN** ela orienta a contagem distinta por território e proíbe usar a soma dos territórios como total geral

### Requirement: Território não preenchido no Simcc
As instruções da fonte `simcc` SHALL mandar conferir `identity_territory` com `COUNT(coluna)` quando a consulta vier vazia ou só com nulos, e dizer ao usuário que o dado não está disponível. MUST proibir inferir o território por cidade, instituição ou conhecimento próprio.

#### Scenario: Orientação sobre dado ausente
- **WHEN** a prévia do contexto da fonte `simcc` é gerada a partir do seed
- **THEN** ela manda declarar a ausência do dado e proíbe inferir o território

#### Scenario: Coluna toda nula
- **WHEN** o usuário pede pesquisadores por território e todos os vínculos têm `identity_territory` nulo
- **THEN** a Maria diz que o dado não está disponível, sem apresentar territórios inventados

### Requirement: Exemplo de pesquisadores por território
O seed do Simcc SHALL trazer um exemplo de consulta com pesquisadores por território de identidade, com contagem distinta e sem linhas de território nulo. O exemplo MUST passar pelas validações de consulta.

#### Scenario: Exemplo válido
- **WHEN** a fonte `simcc` é semeada e sincronizada
- **THEN** a prévia traz o exemplo de pesquisadores por território, sem exemplos recusados

### Requirement: Filtro por nome de território no Simcc
O seed do Simcc SHALL marcar `researcher_institution.identity_territory` com `list_values: never` e como pesquisável, como as demais colunas de nomes.

#### Scenario: Coluna no seed
- **WHEN** o seed do Simcc roda num catálogo vazio
- **THEN** `identity_territory` fica com `list_values` igual a `never` e pesquisável
