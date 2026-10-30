## ADDED Requirements

### Requirement: Consulta entre fontes
O modelo SHALL poder consultar duas fontes numa só consulta pela ferramenta `query_across_sources`, citando as tabelas como `fonte.schema.tabela`. As duas fontes MUST estar ativas e ter uma ligação ativa entre si. Consulta com uma fonte só, com mais de duas fontes ou com tabela sem o nome completo MUST ser recusada, com o motivo.

#### Scenario: Agregação entre fontes
- **WHEN** o modelo conta artigos por modalidade de bolsa juntando `fomento.public.pesquisadores` e `simcc.public.researcher` pelo Lattes
- **THEN** a consulta é validada e executada, e o resultado volta como o de `query_data`

#### Scenario: Uma fonte só
- **WHEN** a consulta entre fontes cita tabelas só do fomento
- **THEN** ela é recusada, com a orientação de usar `query_data`

#### Scenario: Fonte desativada
- **WHEN** a consulta cita uma fonte desativada
- **THEN** ela é recusada sem acessar nenhuma origem

### Requirement: Junção entre fontes por ligação declarada
Toda igualdade entre colunas de fontes diferentes MUST corresponder a uma ligação ativa do catálogo, e a consulta MUST ter ao menos uma. Comparação entre fontes por outras colunas, com outro operador ou produto cartesiano entre fontes MUST ser recusada, com o motivo.

#### Scenario: Ligação pelo Lattes
- **WHEN** a consulta junta `pesquisadores.lattes` e `researcher.lattes_id`
- **THEN** a consulta é aceita

#### Scenario: Instituições por nome
- **WHEN** a consulta junta `fomento.public.instituicoes.nome` e `simcc.public.institution.name`
- **THEN** a consulta é recusada porque não há ligação entre essas colunas

#### Scenario: Ligação desligada
- **WHEN** a única ligação entre as fontes está desligada
- **THEN** a consulta é recusada

### Requirement: Regras de consulta valem entre fontes
A consulta entre fontes SHALL seguir as regras de `query_data`: uma instrução `SELECT`, entidades consultáveis, colunas visíveis, lista de funções permitidas, colunas `aggregate`, busca só em colunas pesquisáveis e limite de linhas. Cada regra MUST valer para a fonte da tabela, mesmo com tabelas de mesmo nome.

#### Scenario: Coluna somente agregação
- **WHEN** a consulta entre fontes seleciona `bolsas.cep_referencia` sem agregar
- **THEN** a consulta é recusada

#### Scenario: Funções de acesso externo
- **WHEN** a consulta usa `postgres_query`, `read_csv` ou lê um arquivo no `FROM`
- **THEN** a consulta é recusada sem ser executada

#### Scenario: Busca textual
- **WHEN** a consulta usa `MATCH_TEXT(a.title, 'covid')` numa coluna pesquisável
- **THEN** a busca funciona como numa fonte só, sem diferenciar maiúsculas e acentos

### Requirement: Isolamento da execução entre fontes
Cada consulta entre fontes SHALL rodar num banco em memória próprio, com as origens em modo somente leitura. Depois de anexar as origens, o acesso externo MUST ser desligado e a configuração travada. A consulta MUST NOT criar arquivos, ler arquivos locais nem baixar extensões.

#### Scenario: Configuração travada
- **WHEN** uma consulta tenta mudar uma configuração da sessão
- **THEN** a mudança é recusada

#### Scenario: Escrita na origem
- **WHEN** o executor recebe uma instrução de escrita numa origem anexada
- **THEN** a escrita é recusada, porque a origem está em modo somente leitura

### Requirement: Limites da execução entre fontes
A execução SHALL respeitar `QUERY_TIMEOUT_SECONDS`, interrompendo a consulta e encerrando-a em cada origem, e os limites `QUERY_FEDERATED_MEMORY_LIMIT` (padrão `512MB`), `QUERY_FEDERATED_THREADS` (padrão 2) e `QUERY_FEDERATED_MAX_CONCURRENT` (padrão 2). Consultas além do limite de concorrência SHALL aguardar, dentro do mesmo tempo limite.

#### Scenario: Tempo esgotado
- **WHEN** a consulta passa de `QUERY_TIMEOUT_SECONDS`
- **THEN** ela é interrompida e o modelo recebe a mensagem de tempo limite

#### Scenario: Memória excedida
- **WHEN** a consulta passa de `QUERY_FEDERATED_MEMORY_LIMIT`
- **THEN** ela falha com uma mensagem de erro que orienta filtrar mais

#### Scenario: Concorrência
- **WHEN** três consultas entre fontes chegam ao mesmo tempo com o limite 2
- **THEN** a terceira só começa quando uma das outras termina

### Requirement: Credenciais fora dos erros entre fontes
Mensagens de erro da execução entre fontes MUST NOT conter URLs, senhas, usuários ou hosts das origens. As URLs SHALL ficar só em memória, durante a consulta.

#### Scenario: Origem inacessível
- **WHEN** uma origem está fora do ar ao anexar
- **THEN** o modelo recebe "A fonte 'simcc' está indisponível", sem detalhes da conexão

### Requirement: Cobertura de consultas entre fontes
Numa consulta que usa uma ligação, o resultado SHALL trazer `coverage`: a fonte de origem, quantas chaves distintas ela tem depois dos filtros dessa fonte e quantas existem na outra. Se a consulta não permitir o cálculo, `coverage` SHALL ser nulo, com o motivo. A falha do cálculo MUST NOT derrubar a consulta.

#### Scenario: Cobertura parcial
- **WHEN** a consulta soma artigos de 19 bolsistas e só 1 está no Simcc
- **THEN** o resultado traz `coverage` com 19 chaves e 1 encontrada

#### Scenario: Filtro na outra fonte
- **WHEN** a consulta filtra artigos Qualis A1 no Simcc
- **THEN** a cobertura conta as chaves pela ligação, sem aplicar esse filtro

#### Scenario: Consulta com subconsulta
- **WHEN** a consulta usa CTE ou subconsulta na origem da ligação
- **THEN** `coverage` é nulo, com o motivo, e os dados voltam normalmente

## MODIFIED Requirements

### Requirement: Consulta apenas a fontes do catálogo
O modelo SHALL poder consultar apenas fontes ativas do catálogo que tenham ao menos uma entidade visível, consultável e presente, identificando a fonte pelo seu `id`. Cada chamada de `query_data` MUST se referir a uma única fonte; duas fontes só pela consulta entre fontes. Consulta a fonte inexistente, desativada ou sem entidades consultáveis MUST ser recusada.

#### Scenario: Fonte ativa consultada
- **WHEN** o modelo consulta a fonte `fomento`, ativa e com entidades consultáveis
- **THEN** a consulta é validada e executada nessa fonte

#### Scenario: Fonte desativada
- **WHEN** o modelo consulta uma fonte desativada
- **THEN** a consulta é recusada sem acessar a origem
