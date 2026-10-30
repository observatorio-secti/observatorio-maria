# Spec Delta

## ADDED Requirements

### Requirement: Nível das perguntas de continuação
As perguntas de continuação SHALL ser geradas com o nível `fast`, sem ferramentas e sem o contexto completo das fontes. O nível da resposta gravada MUST continuar sendo o do chat.

#### Scenario: Níveis usados numa resposta
- **WHEN** a Maria responde usando uma consulta
- **THEN** a resposta é gerada no nível do chat, as sugestões no nível `fast`, e a mensagem gravada registra o nível do chat
