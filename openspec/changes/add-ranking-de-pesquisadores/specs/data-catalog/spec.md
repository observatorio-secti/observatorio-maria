# Spec Delta

## ADDED Requirements

### Requirement: Busca temática de pesquisadores no Simcc
As instruções do seed da fonte `simcc` SHALL orientar o uso de `search_researchers` para encontrar pesquisadores por tema e MUST NOT trazer exemplos de busca temática de pesquisadores sem ordem definida.

#### Scenario: Seed sem exemplo sem ordem
- **WHEN** a prévia do contexto da fonte `simcc` é gerada a partir do seed
- **THEN** ela orienta `search_researchers` para temas e não traz o exemplo `MATCH_TEXT(r.abstract, ...) LIMIT 10`
