## ADDED Requirements

### Requirement: Seed do Simcc
O projeto SHALL fornecer `catalog/simcc.yaml`, que cria a fonte `simcc` com a variável `SIMCC_DATABASE_URL` e o schema `public`. O seed SHALL expor `researcher` e as tabelas de apoio `institution`, `city`, `state` e `researcher_production`. Também SHALL expor as tabelas base e as views `mv_canonical_*` de artigos, livros, capítulos, patentes, softwares, participação em eventos e projetos de pesquisa.

#### Scenario: Seed e sincronização
- **WHEN** o seed do Simcc roda num catálogo vazio e a fonte é sincronizada com o banco de leitura do Simcc
- **THEN** `researcher`, `bibliographic_production`, `patent`, `software`, `participation_events`, `research_project` e as sete views `mv_canonical_*` ficam visíveis, consultáveis e presentes

#### Scenario: Colunas do seed existem na origem
- **WHEN** a fonte `simcc` é sincronizada com o banco de leitura do Simcc
- **THEN** nenhuma coluna listada em `catalog/simcc.yaml` fica ausente

### Requirement: Colunas técnicas do Simcc ocultas
O seed do Simcc MUST NOT tornar visíveis colunas de array, JSON ou `tsvector`, nem campos internos do ETL do Simcc, como `sequence_code`, `is_new`, `stars`, `has_image` e `relevance`. Essas colunas SHALL ficar ocultas após a sincronização e fora do contexto do modelo.

#### Scenario: Colunas das views canônicas
- **WHEN** a fonte `simcc` é sincronizada
- **THEN** `search_vector`, `researcher_ids`, `production_ids` e `platform_authors` de `mv_canonical_articles` ficam ocultas e não aparecem na prévia do contexto

### Requirement: Dados pessoais de pesquisadores no Simcc
O seed do Simcc SHALL deixar visíveis, com acesso `full`, o nome, o ORCID e o resumo do currículo de `researcher`, por decisão do usuário. Respostas da Maria SHALL poder citar o nome dos pesquisadores.

#### Scenario: Listagem com nomes
- **WHEN** o modelo consulta `SELECT name, lattes_id FROM public.researcher` na fonte `simcc`
- **THEN** a consulta é aceita pelo validador

### Requirement: Busca textual no Simcc
O seed do Simcc SHALL marcar como pesquisáveis estas colunas: os títulos das produções, patentes, softwares, eventos e projetos; o nome do evento; a descrição dos projetos; o nome e o resumo do pesquisador; e o título, o resumo e as palavras-chave de `mv_canonical_articles`.

#### Scenario: Busca em títulos de artigos
- **WHEN** o modelo usa `MATCH_TEXT(title, 'dengue')` em `mv_canonical_articles`
- **THEN** a consulta é aceita pelo validador

#### Scenario: Coluna não pesquisável
- **WHEN** o modelo usa `MATCH_TEXT` em `bibliographic_production.doi`
- **THEN** a consulta é recusada porque a coluna não aceita busca textual

### Requirement: Instruções do Simcc
As instruções da fonte `simcc` SHALL dizer que as tabelas base têm uma linha por pesquisador autor e servem para perguntas por pesquisador. Para totais de produções, SHALL indicar as views `mv_canonical_*`, que podem estar defasadas. SHALL dizer também que o ano das produções bibliográficas está em `year_`.

#### Scenario: Orientação no contexto
- **WHEN** a prévia do contexto da fonte `simcc` é gerada
- **THEN** ela contém a orientação de usar as views canônicas para totais e `year_` para o ano

### Requirement: Exemplos do Simcc conferidos com o catálogo
O seed do Simcc SHALL trazer exemplos few-shot, e todos MUST passar nas regras de entidades, colunas e funções permitidas do catálogo semeado.

#### Scenario: Nenhum exemplo recusado
- **WHEN** o seed do Simcc roda num catálogo vazio e as colunas do arquivo estão presentes
- **THEN** todos os exemplos são aceitos e nenhum aparece como recusado na prévia

### Requirement: Seed do Simcc sem valores supostos
O seed do Simcc MUST NOT declarar valores para colunas categóricas de texto, como `type`, `qualis`, `nature`, `category`, `status` e `form_participation`. Os valores dessas colunas SHALL vir da origem como valores observados.

#### Scenario: Colunas sem valores declarados
- **WHEN** `catalog/simcc.yaml` é carregado
- **THEN** nenhuma coluna do arquivo declara `values`

### Requirement: Ligação com o fomento nas instruções do Simcc
As instruções da fonte `simcc` SHALL dizer que `researcher.lattes_id` equivale a `pesquisadores.lattes` do fomento e que cada consulta acessa uma só fonte. Para relacionar as fontes, o modelo SHALL filtrar uma com até `QUERY_MAX_ROWS` Lattes obtidos na outra, informar quantos foram encontrados e dizer que agregações sobre grupos maiores ainda não são possíveis.

#### Scenario: Regra no contexto do Simcc
- **WHEN** a prévia do contexto da fonte `simcc` é gerada
- **THEN** ela contém a equivalência entre `lattes_id` e `pesquisadores.lattes`, o limite de Lattes por consulta e a orientação de informar quantos foram encontrados

### Requirement: Fomento aponta para o Simcc
As instruções da fonte `fomento` SHALL dizer que artigos, livros, capítulos, patentes, softwares, eventos e projetos do currículo dos pesquisadores estão na fonte `simcc`, ligada pelo Lattes.

#### Scenario: Regra no contexto do fomento
- **WHEN** a prévia do contexto da fonte `fomento` é gerada a partir do seed
- **THEN** ela indica a fonte `simcc` para produções dos pesquisadores
