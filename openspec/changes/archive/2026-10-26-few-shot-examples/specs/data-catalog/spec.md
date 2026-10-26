# data-catalog Specification Delta

## Requirements

### ADDED Requirement: Exemplos de consulta validados no catálogo
O sistema SHALL permitir associar a cada fonte de dados uma lista de exemplos canônicos de consulta (pares contendo `question` e `sql`), cadastráveis e editáveis via API nos endpoints da fonte. O modelo de dados SHALL guardar os exemplos no banco da própria Maria.

#### Scenario: Cadastrar exemplos na criação da fonte
- **WHEN** o cliente cria uma fonte incluindo lista de exemplos com pergunta e SQL
- **THEN** a fonte é criada e retorna os exemplos cadastrados

#### Scenario: Atualizar exemplos da fonte
- **WHEN** o cliente atualiza os exemplos de uma fonte via `PATCH /catalog/datasources/{id}`
- **THEN** os novos exemplos substituem os anteriores e ficam persistidos

### ADDED Requirement: Exemplos no seed e exportação YAML
O sistema SHALL ler a seção `examples:` sob `datasource:` nos arquivos de seed YAML e persistir os pares `question` e `sql`. A exportação (`GET /catalog/datasources/{id}/export`) SHALL incluir os exemplos cadastrados no documento YAML gerado.

#### Scenario: Seed com exemplos
- **WHEN** o comando de seed é executado com um arquivo YAML contendo `examples:`
- **THEN** os exemplos são carregados no catálogo da fonte

#### Scenario: Ida e volta pelo YAML
- **WHEN** uma fonte com exemplos cadastrados é exportada em YAML
- **THEN** o YAML resultante contém a seção `examples` correspondente

### ADDED Requirement: Exemplos na prévia do contexto do modelo
A prévia do contexto de uma fonte (`GET /catalog/datasources/{id}/context` e `render_context`) SHALL incluir a seção `## Exemplos de consultas (few-shot)` listando as perguntas e os blocos de código SQL correspondentes quando a fonte contiver exemplos cadastrados. Fontes sem exemplos cadastrados MUST NOT exibir a seção.

#### Scenario: Fonte com exemplos renderiza seção few-shot
- **WHEN** uma fonte ativa possui exemplos cadastrados
- **THEN** o contexto gerado contém a seção `## Exemplos de consultas (few-shot)` com as perguntas e blocos SQL formatados

#### Scenario: Fonte sem exemplos omite a seção
- **WHEN** a fonte ativa não possui exemplos
- **THEN** a seção de exemplos não aparece no contexto gerado
