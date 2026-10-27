# Proposal

## Why

A Maria só enxerga o banco do fomento, que tem bolsas, projetos e pesquisadores, mas nenhuma produção científica. Perguntas sobre artigos, livros, capítulos, patentes, softwares, participação em eventos e projetos de pesquisa dos pesquisadores da Bahia dependem do Simcc, que guarda o currículo Lattes de cada pesquisador num banco de leitura próprio. O fomento já liga cada bolsista ao Lattes (`pesquisadores.lattes`), e o Simcc usa o mesmo identificador (`researcher.lattes_id`). Falta cadastrar o Simcc como segunda fonte do catálogo.

## What Changes

- **Seed do Simcc (`catalog/simcc.yaml`):** cria a fonte `simcc` com a variável `SIMCC_DATABASE_URL`, expondo:
  - `researcher` e as tabelas de apoio `institution`, `city`, `state` e `researcher_production`;
  - as tabelas base dos seis temas, para perguntas por pesquisador: `bibliographic_production` com as tabelas de artigo, livro e capítulo, além de `patent`, `software`, `participation_events`, `research_project` e as tabelas de componentes, financiamento e produções do projeto;
  - as views `mv_canonical_*` de artigos, livros, capítulos, patentes, softwares, eventos e projetos, para totais sem contar o mesmo item uma vez por coautor.
- **Colunas técnicas ocultas:** arrays, JSON, `tsvector` e campos internos do ETL (`researcher_ids`, `platform_authors`, `search_vector`, `sequence_code`, `is_new`, `stars`…) não entram no catálogo visível.
- **Dados pessoais:** nome, ORCID e resumo do currículo do pesquisador ficam com acesso `full`. A decisão é do usuário, ciente de que o cruzamento com o fomento identifica bolsistas.
- **Busca textual:** títulos das produções, patentes, softwares, eventos e projetos, a descrição dos projetos, o nome e o resumo do pesquisador, e o resumo e as palavras-chave dos artigos canônicos passam a aceitar `MATCH_TEXT`.
- **Instruções e exemplos do Simcc:**
  - explicam quando usar as tabelas base e quando usar as views canônicas, e que o ano está em `year_`;
  - trazem exemplos few-shot conferidos com o catálogo;
  - não declaram valores para `type`, `qualis`, `nature` e afins, que vêm da origem como valores observados.
- **Ligação com o fomento, ainda em duas etapas:** as instruções das duas fontes dizem que `researcher.lattes_id` equivale a `pesquisadores.lattes`. Como cada consulta acessa uma só fonte, o modelo consulta uma delas, filtra a outra com até `QUERY_MAX_ROWS` Lattes e informa quantos foram encontrados. Agregações sobre grupos maiores são declaradas como ainda indisponíveis.
- **Contexto com duas fontes:** com fomento e Simcc ativos, o prompt de sistema traz o contexto das duas.
- **Deploy:** o `compose.prod.yaml` passa a colocar a `maria-api` também na rede do Simcc (`SIMCC_NETWORK`, padrão `simcc-network`). O guia de deploy ensina a criar o usuário somente leitura no banco de leitura do Simcc (`read_db`) e inclui `simcc.yaml` no seed.

### Fora do escopo

- Consultas que juntam fomento e Simcc num único SQL e a contagem automática de cobertura: ficam para a próxima mudança, de consultas entre fontes com DuckDB.
- Outras partes do Simcc: dados do OpenAlex por produção (`openalex_article`), grupos de pesquisa, programas de pós-graduação, orientações, produções técnicas e artísticas, marcas e ODS.
- Descrever o significado dos valores de `type`, `qualis`, `nature`, `category` e afins: é regra de negócio e fica pendente para quem conhece o domínio.
- Popular o banco do Simcc: isso é feito pelo ETL do próprio Simcc.

## Capabilities

### New Capabilities

Nenhuma.

### Modified Capabilities

- `data-catalog`: seed do Simcc (entidades, colunas visíveis, ocultas, pesquisáveis e com dados pessoais), instruções e exemplos do Simcc e ligação com o fomento descrita nas instruções das duas fontes.
- `conversation-messaging`: o prompt de sistema traz o contexto de todas as fontes ativas consultáveis, com fomento e Simcc juntos.

## Impact

- **Código e configuração:**
  - novo `catalog/simcc.yaml`, e ajuste nas instruções de `catalog/fomento.yaml`;
  - `compose.prod.yaml`, `.env.example`, README e `docs/deploy.md`;
  - testes do seed (`tests/test_catalog_yaml.py`) e do contexto do chat.
  - O código do catálogo e das consultas não muda: a introspecção já lê views materializadas, e o seed já aceita vários arquivos.
- **Banco da Maria:** nenhuma migração.
- **Bancos externos:**
  - A Maria passa a ler o banco de leitura do Simcc. A introspecção lê só o schema; a leitura de valores observados roda `SELECT DISTINCT … LIMIT` nas colunas de texto visíveis, na sincronização e a cada verificação.
  - O guia de deploy pede um usuário somente leitura no Simcc. Ele é criado por quem administra o Simcc, nunca pela Maria.
- **Segredos:** nova variável `SIMCC_DATABASE_URL`, só no `.env`, fora do banco e do Git.
- **Endpoints sem autenticação:** nenhum novo. Os do catálogo passam a listar a fonte `simcc`.
- **Dependências:** não depende de mudança em andamento. A próxima mudança, de consultas entre fontes, depende desta.
- **Dados de teste:** o banco de leitura do Simcc ainda está sendo populado. O planejamento usou só o schema, e a verificação com dados reais espera o ETL terminar.
