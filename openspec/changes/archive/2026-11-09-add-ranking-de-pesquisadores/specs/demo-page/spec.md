# Spec Delta

## ADDED Requirements

### Requirement: Evidências nos cards de pesquisadores
A página SHALL mostrar, em cada card com `evidence`, quantas produções casam com o termo, a contagem por tipo em português e as evidências com tipo, título e ano, tanto no streaming quanto ao reabrir a conversa. Cards sem `evidence` MUST ficar como antes.

#### Scenario: Card com evidências
- **WHEN** um card tem `evidence` com 38 produções e 3 itens
- **THEN** a página mostra "38 produções sobre o tema" e os 3 títulos com tipo e ano

#### Scenario: Evidência de perfil
- **WHEN** a evidência é do tipo perfil
- **THEN** a página mostra "Resumo do currículo" sem título de produção

### Requirement: Aviso sobre a ordem do ranking
Acima dos cards de um bloco com `ranking`, a página SHALL avisar que a ordem é por relevância do termo, listar os campos considerados, dizer que Qualis, citações e índice h não entram na ordem e mostrar a data dos dados em pt-BR quando houver. Blocos sem `ranking` MUST ficar sem aviso.

#### Scenario: Aviso com data
- **WHEN** o bloco tem `ranking` com o termo "dengue" e `data_as_of` em 08/11/2026
- **THEN** a página mostra o critério, os campos, a ressalva sobre Qualis, citações e índice h, e "dados de 08/11/2026"

#### Scenario: Lista sem ranking
- **WHEN** o bloco `researchers` veio de `show_researchers`
- **THEN** nenhum aviso de ordem é mostrado

### Requirement: Ranking no contrato de blocos
O exemplo do bloco `researchers` na aba de contrato SHALL incluir `ranking` e `evidence` em ao menos um card.

#### Scenario: Exemplo do contrato
- **WHEN** o usuário abre a aba de contrato de blocos
- **THEN** o exemplo de pesquisadores mostra o aviso de ordem e as evidências ao lado do JSON

### Requirement: Evidências no CSV de pesquisadores
O CSV baixado de um bloco `researchers` com `evidence` SHALL incluir o total de produções sobre o tema de cada pesquisador.

#### Scenario: CSV do ranking
- **WHEN** o usuário baixa o CSV de um ranking
- **THEN** cada linha tem a coluna com o total de produções sobre o tema
