# Spec Delta

## ADDED Requirements

### Requirement: Perguntas de período entre fontes
As perguntas de referência SHALL cobrir a contagem de artigos publicados durante a bolsa, com conferência por consulta entre fontes, e uma pergunta sobre todos os bolsistas em que a resposta não pode alegar limite de pesquisadores no cruzamento.

#### Scenario: Contagem durante a bolsa
- **WHEN** a avaliação roda a pergunta de artigos publicados durante a bolsa
- **THEN** o resultado confere as fontes `fomento` e `simcc`, os números esperados e a cobertura

#### Scenario: Sem limite inventado
- **WHEN** a avaliação roda a pergunta sobre todos os bolsistas
- **THEN** o modelo-juiz reprova resposta que alegue limite de pesquisadores no cruzamento
