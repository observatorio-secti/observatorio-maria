# Spec Delta

## ADDED Requirements

### Requirement: Aviso de dados parciais
A página SHALL mostrar, abaixo de um bloco `chart` ou `table` com `truncated` verdadeiro, um aviso com a quantidade de linhas mostradas, tanto no streaming quanto ao reabrir a conversa. Blocos sem o campo ou com valor falso MUST ficar sem aviso.

#### Scenario: Tabela cortada
- **WHEN** a resposta tem uma tabela com 100 linhas e `truncated` verdadeiro
- **THEN** a página mostra, abaixo da tabela, que são exibidas só as primeiras 100 linhas

#### Scenario: Gráfico cortado em conversa reaberta
- **WHEN** o usuário reabre uma conversa com um gráfico cortado
- **THEN** o aviso aparece abaixo do gráfico

#### Scenario: Bloco completo
- **WHEN** o bloco tem `truncated` falso ou não tem o campo
- **THEN** nenhum aviso é mostrado
