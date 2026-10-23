# data-querying Specification

## Purpose
Define como a Maria consulta os dados das fontes do catálogo para responder perguntas: o que pode ser consultado, as garantias de somente leitura e privacidade, a busca textual e os resultados que alimentam gráficos e tabelas.

## Requirements

### Requirement: Consulta apenas a fontes do catálogo
O modelo SHALL poder consultar apenas fontes ativas do catálogo que tenham ao menos uma entidade visível, consultável e presente, identificando a fonte pelo seu `id`. Cada consulta MUST se referir a uma única fonte. Consulta a fonte inexistente, desativada ou sem entidades consultáveis MUST ser recusada.

#### Scenario: Fonte ativa consultada
- **WHEN** o modelo consulta a fonte `fomento`, ativa e com entidades consultáveis
- **THEN** a consulta é validada e executada nessa fonte

#### Scenario: Fonte desativada
- **WHEN** o modelo consulta uma fonte desativada
- **THEN** a consulta é recusada sem acessar a origem

### Requirement: Somente leitura
A consulta MUST ser uma única instrução `SELECT`, opcionalmente com `WITH`. Qualquer outra instrução (inserção, alteração, remoção, DDL, permissões, mais de uma instrução) MUST ser recusada antes de chegar à origem. A execução SHALL ocorrer numa transação somente leitura e MUST NOT alterar objetos ou dados da origem.

#### Scenario: Alteração recusada
- **WHEN** o modelo envia `UPDATE bolsas SET status = 'REGULAR'`
- **THEN** a consulta é recusada e nada é enviado à origem

#### Scenario: Instruções encadeadas
- **WHEN** o modelo envia `SELECT 1; DELETE FROM bolsas`
- **THEN** a consulta inteira é recusada

### Requirement: Entidades permitidas
A consulta SHALL referenciar apenas entidades visíveis, consultáveis e presentes no catálogo da fonte. Entidade oculta, ausente ou inexistente MUST ser recusada com a mesma mensagem, sem revelar se ela existe na origem. Entidade visível mas não consultável MUST ser recusada como somente referência.

#### Scenario: Entidade oculta
- **WHEN** o modelo consulta uma tabela de ingestão oculta no catálogo
- **THEN** a consulta é recusada com a mesma mensagem dada a uma tabela inexistente

#### Scenario: Entidade só de referência
- **WHEN** o modelo consulta uma entidade visível e não consultável
- **THEN** a consulta é recusada informando que a entidade é somente de referência

### Requirement: Colunas permitidas
A consulta SHALL referenciar apenas colunas visíveis e presentes das entidades permitidas. Coluna oculta, ausente ou inexistente MUST ser recusada com a mesma mensagem. `SELECT *` e `entidade.*` MUST ser recusados, para que colunas ocultas nunca sejam lidas.

#### Scenario: Coluna oculta
- **WHEN** o modelo seleciona uma coluna oculta de `bolsas`
- **THEN** a consulta é recusada com a mesma mensagem dada a uma coluna inexistente

#### Scenario: Asterisco
- **WHEN** o modelo envia `SELECT * FROM projetos`
- **THEN** a consulta é recusada pedindo que as colunas sejam listadas

### Requirement: Colunas somente para agregação
Uma coluna com acesso `aggregate` SHALL poder aparecer em filtros, junções, agrupamentos e dentro de funções de agregação, e MUST NOT aparecer, direta ou indiretamente, entre as colunas devolvidas pela consulta.

#### Scenario: Contagem permitida
- **WHEN** o modelo conta bolsas filtrando por `cep_referencia LIKE '40%'`
- **THEN** a consulta é executada

#### Scenario: Valor individual recusado
- **WHEN** o modelo seleciona `cep_referencia`, mesmo com `GROUP BY cep_referencia` ou dentro de outra expressão que não seja agregação
- **THEN** a consulta é recusada informando que a coluna é somente para agregação

### Requirement: Funções permitidas
A consulta SHALL usar apenas funções de uma lista permitida (agregações, datas, texto, conversões e condicionais comuns, além de `MATCH_TEXT`). Qualquer outra função MUST ser recusada, informando as funções disponíveis.

#### Scenario: Função de sistema
- **WHEN** o modelo usa `pg_sleep(10)` ou `pg_read_file('...')`
- **THEN** a consulta é recusada antes de chegar à origem

### Requirement: Limite de linhas
Toda consulta SHALL devolver no máximo `QUERY_MAX_ROWS` linhas (padrão 100), mesmo que peça mais ou não tenha `LIMIT`. O resultado MUST informar se foi truncado.

#### Scenario: Resultado truncado
- **WHEN** a consulta produziria 500 linhas e `QUERY_MAX_ROWS` é 100
- **THEN** o resultado tem 100 linhas e indica que foi truncado

### Requirement: Limite de tempo
Toda consulta SHALL ser interrompida após `QUERY_TIMEOUT_SECONDS` (padrão 15). A interrupção MUST virar uma recusa por tempo esgotado e MUST NOT derrubar a resposta.

#### Scenario: Consulta lenta
- **WHEN** a consulta passa do limite de tempo
- **THEN** ela é cancelada na origem e o modelo recebe que o tempo se esgotou

### Requirement: Recusas e erros explicados ao modelo
Recusa de validação, erro da origem (sintaxe, tipo) e origem inacessível SHALL voltar ao modelo como resultado da consulta, com um motivo curto que permita corrigi-la, e MUST NOT encerrar a resposta com erro. O motivo MUST NOT conter URLs de conexão nem credenciais.

#### Scenario: Erro de sintaxe corrigido
- **WHEN** a primeira consulta tem erro de sintaxe e ainda há chamadas no orçamento
- **THEN** o modelo recebe o erro e pode enviar a consulta corrigida na chamada seguinte

#### Scenario: Origem inacessível
- **WHEN** `FOMENTO_DATABASE_URL` aponta para um banco fora do ar
- **THEN** o modelo recebe que a fonte está indisponível, sem a URL, e a resposta ao usuário diz que não foi possível consultar os dados

### Requirement: Busca textual
A consulta SHALL aceitar `MATCH_TEXT(coluna, 'termo', ...)`, verdadeira quando a coluna contém ao menos um dos termos, sem diferenciar maiúsculas, minúsculas e acentos. Termos vazios MUST ser recusados.

#### Scenario: Tema com sinônimos
- **WHEN** o modelo filtra projetos por `MATCH_TEXT(resumo, 'dengue', 'aedes aegypti', 'arbovirose')`
- **THEN** voltam os projetos cujo resumo contém qualquer um dos termos, inclusive "Dengue" e "ARBOVIROSES"

#### Scenario: Acentos ignorados
- **WHEN** o modelo busca `MATCH_TEXT(nome, 'saude')`
- **THEN** projetos com "Saúde" no título são encontrados

### Requirement: Busca apenas em colunas pesquisáveis
`MATCH_TEXT` SHALL ser aceita apenas em colunas marcadas como pesquisáveis no catálogo. Em outra coluna, a consulta MUST ser recusada, informando as colunas pesquisáveis da entidade.

#### Scenario: Coluna não pesquisável
- **WHEN** o modelo usa `MATCH_TEXT(nome_curso, 'medicina')` e `nome_curso` não é pesquisável
- **THEN** a consulta é recusada listando as colunas pesquisáveis de `bolsas`

### Requirement: Consultas por chamada
Numa mesma chamada, o modelo SHALL poder pedir várias consultas, executadas de forma independente, até `QUERY_MAX_PER_CALL` (padrão 4). As que passarem do limite MUST ser recusadas sem execução.

#### Scenario: Consultas paralelas
- **WHEN** o modelo pede, na mesma chamada, a contagem por modalidade e a lista de projetos
- **THEN** as duas são executadas e os dois resultados voltam ao modelo

#### Scenario: Excesso de consultas
- **WHEN** o modelo pede 6 consultas numa chamada e o limite é 4
- **THEN** as 4 primeiras são executadas e as 2 últimas são recusadas por excesso

### Requirement: Resultados identificados
Cada consulta executada SHALL produzir um resultado com identificador próprio, colunas (nome e tipo), linhas e a indicação de truncamento. O resultado SHALL valer apenas dentro da resposta em que foi gerado e MUST NOT ser persistido no banco da Maria.

#### Scenario: Resultado referenciável
- **WHEN** uma consulta é executada com sucesso
- **THEN** o modelo recebe um identificador do resultado que pode usar para pedir um gráfico ou tabela na mesma resposta
