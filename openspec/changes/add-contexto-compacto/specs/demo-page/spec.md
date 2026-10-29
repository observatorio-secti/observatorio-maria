## ADDED Requirements

### Requirement: Listagem de valores na página
Na tabela de colunas da entidade, a aba "Catálogo de dados" SHALL permitir escolher, por coluna, se os valores entram no contexto: automático, sempre ou nunca.

#### Scenario: Deixar de listar
- **WHEN** o usuário escolhe "nunca" para uma coluna com valores listados
- **THEN** a prévia do contexto da fonte deixa de listar os valores dessa coluna
