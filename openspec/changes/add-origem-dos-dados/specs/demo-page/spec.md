# Spec Delta

## ADDED Requirements

### Requirement: Rodapé de origem nas respostas
A página SHALL mostrar, abaixo de um bloco `chart` ou `table` com `origin`, as fontes, a descrição e a data da consulta e, quando houver, a cobertura, tanto no streaming quanto ao reabrir a conversa. Blocos sem `origin` MUST ficar sem rodapé.

#### Scenario: Gráfico com origem
- **WHEN** a resposta tem um gráfico com `origin`
- **THEN** a página mostra abaixo dele a fonte, a descrição e a data da consulta no formato pt-BR

#### Scenario: Consulta entre fontes
- **WHEN** a resposta tem uma tabela com duas fontes e cobertura de 1 em 19
- **THEN** o rodapé mostra as duas fontes e que 1 de 19 foi encontrado

#### Scenario: Conversa reaberta
- **WHEN** o usuário reabre uma conversa com um bloco com `origin`
- **THEN** o rodapé aparece abaixo do bloco

#### Scenario: Bloco antigo
- **WHEN** o bloco não tem `origin`
- **THEN** nenhum rodapé é mostrado
