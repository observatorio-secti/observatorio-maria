## ADDED Requirements

### Requirement: Várias fontes no contexto
Com mais de uma fonte ativa e consultável, o prompt de sistema SHALL trazer o contexto de cada uma, na ordem do identificador, com o mesmo texto da prévia de cada fonte. Fontes desativadas ou sem entidades consultáveis MUST ficar de fora.

#### Scenario: Fomento e Simcc ativos
- **WHEN** as fontes `fomento` e `simcc` estão ativas e têm entidades consultáveis
- **THEN** o prompt de sistema contém os textos de `GET /catalog/datasources/fomento/context` e de `GET /catalog/datasources/simcc/context`

#### Scenario: Simcc desativado
- **WHEN** a fonte `simcc` está desativada e a `fomento` está ativa
- **THEN** o prompt de sistema contém só o contexto do fomento
