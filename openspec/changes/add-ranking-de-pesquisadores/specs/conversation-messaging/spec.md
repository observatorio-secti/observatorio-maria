# Spec Delta

## ADDED Requirements

### Requirement: Ranking no bloco de pesquisadores
O bloco `researchers` SHALL aceitar o campo opcional `ranking` com o termo buscado, a descrição do critério, os campos considerados na ordem e a data dos dados (`data_as_of`, opcional). Cada card SHALL aceitar o campo opcional `evidence` com `total`, `by_type` e `items` (tipo, título e ano). Blocos sem esses campos MUST continuar válidos.

#### Scenario: Bloco de ranking
- **WHEN** a resposta lista pesquisadores por `search_researchers`
- **THEN** o bloco `researchers` traz `ranking` e cada card traz `evidence`

#### Scenario: Bloco antigo
- **WHEN** uma conversa gravada antes da mudança é reaberta
- **THEN** o bloco `researchers` sem `ranking` e sem `evidence` é aceito como antes

### Requirement: Bloco criado pelo ranking
Uma chamada bem-sucedida a `search_researchers` SHALL criar o bloco `researchers` na ordem do ranking, sem exigir `show_researchers`, e MUST devolver ao modelo o `block_index` do bloco para a explicação.

#### Scenario: Cards na ordem do ranking
- **WHEN** o ranking devolve três pesquisadores
- **THEN** o bloco tem três cards na mesma ordem, com os dados de perfil e métricas de `show_researchers`

### Requirement: Busca temática de pesquisadores pelo agente
O prompt de regras SHALL orientar o modelo a usar `search_researchers` quando o usuário pede pesquisadores, especialistas ou grupos que trabalham com um tema, e a dizer na explicação que a ordem é por relevância do tema nos textos do currículo e das produções, com a data dos dados.

#### Scenario: Especialistas em um tema
- **WHEN** o usuário pergunta "Quem são os especialistas em dengue na Bahia?"
- **THEN** o modelo chama `search_researchers` com o termo "dengue" em vez de uma consulta sem ordem

#### Scenario: Pergunta que não é temática
- **WHEN** o usuário pergunta "Quais pesquisadores têm mais artigos?"
- **THEN** o modelo continua usando uma consulta comum ordenada pelo número de artigos

### Requirement: Limitação do ranking na explicação
Quando o usuário pede uma ordem que o ranking não oferece (por Qualis, citações ou índice h), o modelo SHALL dizer que a lista está ordenada por relevância do tema e que esse critério não está disponível nela.

#### Scenario: Pedido por citações
- **WHEN** o usuário pede "os especialistas em dengue mais citados"
- **THEN** a resposta diz que a ordem é por relevância do tema e não por citações
