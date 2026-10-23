# Spec Delta

## ADDED Requirements

### Requirement: Andamento das consultas na página
Enquanto a Maria consulta dados, a página SHALL exibir na mensagem do assistente a descrição de cada evento `activity` recebido, mantendo o indicador de resposta em andamento até o primeiro fragmento de texto ou bloco.

#### Scenario: Consulta em andamento
- **WHEN** a página recebe `activity` com "Buscando projetos sobre dengue"
- **THEN** a mensagem do assistente mostra essa descrição até a resposta começar a aparecer

### Requirement: Gráficos e tabelas nas respostas
A página SHALL renderizar os blocos `chart` e `table` das respostas, tanto no streaming quanto ao reabrir a conversa, da mesma forma que na aba de contrato, e SHALL funcionar a 375px de largura sem rolagem horizontal da página.

#### Scenario: Resposta com gráfico
- **WHEN** a resposta da Maria tem um texto e um gráfico
- **THEN** a página mostra o texto renderizado seguido do gráfico

#### Scenario: Conversa reaberta
- **WHEN** o usuário reabre uma conversa com uma tabela numa resposta anterior
- **THEN** a tabela aparece renderizada no histórico

### Requirement: Colunas pesquisáveis na página
A aba do catálogo SHALL permitir alternar o interruptor **pesquisável** de cada coluna da entidade selecionada.

#### Scenario: Alternar pesquisável
- **WHEN** o usuário liga **pesquisável** na coluna `resumo`
- **THEN** a prévia do contexto passa a indicar que a coluna aceita busca textual
