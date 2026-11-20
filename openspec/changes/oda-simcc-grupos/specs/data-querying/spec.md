## ADDED Requirements

### Requirement: Escopo dos grupos ODA do SIMCC
Consultas à fonte `oda` SHALL incluir somente grupos cuja instituição vinculada como sede seja uma das 11 instituições SIMCC. Pesquisadores, linhas e setores SHALL ser limitados aos grupos elegíveis. Tabelas ODA sem política explícita MUST ser recusadas.

#### Scenario: Grupo com sede SIMCC
- **WHEN** a consulta lê um grupo cuja relação de sede aponta para uma instituição SIMCC
- **THEN** o grupo e seus dados relacionados podem ser retornados

#### Scenario: Grupo sem sede SIMCC
- **WHEN** a consulta tenta ler grupo de outra instituição ou cuja instituição SIMCC é apenas parceira
- **THEN** o grupo e seus dados relacionados não são retornados

#### Scenario: Entidade ODA sem escopo
- **WHEN** a consulta referencia uma tabela ODA sem política explícita
- **THEN** a consulta é recusada antes de acessar a origem


### Requirement: Proteções específicas da fonte ODA
Consultas ODA SHALL usar o critério institucional da API ODA, preservar aliases e junções e validar literais de enum pelos valores sincronizados. Categorias observadas MUST respeitar o recorte. Consultas ODA federadas MUST ser recusadas. Pesquisadores ODA SHALL ser apresentados a partir do resultado ODA, sem hidratação no Simcc.

#### Scenario: Alias de busca e enum físico
- **WHEN** a consulta ODA usa alias com MATCH_TEXT ou enum com rótulo inválido
- **THEN** a busca válida funciona e o literal inválido é recusado antes da execução

#### Scenario: Categorias somente do recorte
- **WHEN** a sincronização lê valores observados ODA
- **THEN** somente categorias associadas ao recorte SIMCC são guardadas; em falha, valores antigos são descartados

#### Scenario: Consulta ODA entre fontes
- **WHEN** a consulta federada referencia ODA
- **THEN** a consulta é recusada antes de abrir conexão com as fontes

#### Scenario: Apresentação de pesquisadores ODA
- **WHEN** show_researchers recebe resultado ODA
- **THEN** a apresentação usa os dados já consultados em tabela, sem abrir conexão Simcc
