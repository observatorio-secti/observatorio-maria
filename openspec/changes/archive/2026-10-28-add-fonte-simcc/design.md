# Design

## Context

Motivação em `proposal.md`. Estado atual relevante:

- **Catálogo:**
  - A introspecção (`catalog/introspection.py`) já lê tabelas, views e views materializadas, com chaves estrangeiras.
  - Na sincronização, entidades e colunas novas entram ocultas. Só o que o YAML lista fica visível.
  - O seed (`catalog/seed.py`) aceita vários arquivos e não sobrescreve edições.
- **Valores observados:** `catalog/observed.py` faz um `SELECT DISTINCT … LIMIT CATALOG_OBSERVED_VALUES_MAX + 1` em cada coluna de texto visível com acesso `full`. Roda na sincronização e a cada verificação (`CATALOG_CHECK_INTERVAL_SECONDS`, padrão 1 hora).
- **Chat:** `services/chat.py::get_consultable_sources_and_contexts` já monta um contexto por fonte ativa e consultável, ordenado pelo identificador. O `query_data` recebe o identificador da fonte, e cada consulta acessa uma só fonte.
- **Banco de leitura do Simcc:**
  - Roda em `localhost:5434/simcc`, no serviço `read_db` (container `simcc_read_db`) do compose `Simcc/simcc-etl`, na rede externa `simcc-network`.
  - É PostgreSQL 17, com as extensões `unaccent` e `pg_trgm`.
  - As tabelas base ligam cada produção a um pesquisador por `researcher_id`, com uma linha por pesquisador autor.
  - As views `mv_canonical_*` agrupam por DOI, ISBN, código ou título normalizado, e guardam os pesquisadores em arrays (`researcher_ids uuid[]`) e em JSON (`platform_authors`).
- **Dados:** quando esta proposta foi escrita, o banco estava sendo populado pelo ETL. O planejamento usou só o schema.

## Goals / Non-Goals

**Goals:**
- O modelo responde sobre os seis temas a partir do Simcc, por pesquisador ou em totais, sem contar o mesmo item uma vez por coautor.
- A ligação com o fomento já funciona para grupos pequenos e é honesta sobre o limite nos grupos grandes.
- A mudança não altera código do catálogo nem das consultas: só configuração, seed, instruções e deploy.

**Non-Goals:**
- Filtrar as views canônicas por pesquisador ou por instituição. As chaves estão em arrays, que o validador não aceita.
- Detectar a cobertura automaticamente. Fica para a mudança de consultas entre fontes.

## Decisions

### D1. Tabelas base e views canônicas, com papéis diferentes
As tabelas base respondem perguntas por pesquisador: "artigos A1 da pesquisadora X" ou "patentes dos bolsistas desta lista". As views `mv_canonical_*` respondem totais: "artigos por ano" ou "patentes concedidas desde 2020". As instruções e os exemplos dizem qual usar.
- *Descartado:* só as tabelas base. Os totais contariam um artigo de três coautores da plataforma três vezes.
- *Descartado:* só as views canônicas. Sem acesso aos arrays, o modelo não conseguiria filtrar por pesquisador.

### D2. Listar as colunas visíveis em vez de esconder as técnicas
O YAML lista só as colunas úteis, e todas as outras entram ocultas pela regra da sincronização. Isso inclui arrays, JSON, `tsvector`, `sequence_code`, `is_new`, `stars`, `has_image`, `relevance`, `abstract_en`, `abstract_ai`, `extra_field`, `year` (texto, duplicado de `year_`) e URLs.
- *Descartado:* listar todas as colunas com `visible: false` nas técnicas. O arquivo dobraria de tamanho, e colunas novas do ETL já entram ocultas de qualquer forma.

Também não entram colunas cujo significado não está claro no schema, como `researcher.status`, `docente`, `classification` e `citations` (texto). Descrever o significado delas é regra de negócio, e elas podem ser ligadas depois pela API ou pela demo.

### D3. Nome, ORCID e resumo com acesso `full`
Decisão do usuário: o Lattes é público, e citar pesquisadores é parte do valor da fonte. Nome e resumo são pesquisáveis.
- *Descartado:* `aggregate` ou oculto. As respostas cruzadas ficariam só em números. A classificação pode mudar a qualquer momento pela API ou pela demo, sem deploy.

### D4. Ligação com o fomento por instruções, em duas etapas
As instruções das duas fontes descrevem a equivalência do Lattes. O modelo consulta uma fonte, que devolve no máximo `QUERY_MAX_ROWS` linhas, e filtra a outra com `lattes_id IN (...)`. Precisa dizer quantos Lattes encontrou e declarar que agregações sobre grupos maiores ainda não são possíveis. Isso usa só o que o `query_data` já faz: `IN` com literais passa no validador.
- *Descartado:* esperar a mudança de consultas entre fontes para expor o Simcc. As perguntas sobre um único Simcc, como totais por ano ou produções de um pesquisador, não dependem do cruzamento.
- *Descartado:* um relacionamento entre fontes no catálogo agora. O modelo de dados e a ferramenta que o usariam são escopo da próxima mudança.

### D5. Sem valores editoriais e sem relacionamentos manuais
O YAML não declara `values`: `type`, `qualis`, `nature`, `category`, `status` e afins vêm da origem como valores observados. Os relacionamentos das tabelas base vêm das chaves estrangeiras do Simcc. As views canônicas não ganham relacionamentos, porque não têm coluna de junção escalar visível.
- *Descartado:* declarar os tipos (`ARTICLE`, `BOOK`…) no YAML. Seria o mesmo erro de `bolsas.modalidade` corrigido na mudança anterior.

### D6. A Maria entra na rede do Simcc
A `maria-api` passa a ficar também na rede externa do Simcc, `${SIMCC_NETWORK:-simcc-network}`. `SIMCC_DATABASE_URL` aponta para o host `read_db`, porta 5432, com um usuário somente leitura.
- *Descartado:* acessar a porta 5434 publicada no host. Isso exige expor o banco fora da rede Docker e depende do endereço do host.
- O padrão `simcc-network` vem do compose do Simcc, que declara essa rede como externa com nome fixo. Já o fomento continua obrigatório (`:?`), porque o nome da rede dele depende da pasta.

### D7. Nenhuma mudança de código para várias fontes
O requisito de várias fontes no contexto já é atendido por `get_consultable_sources_and_contexts`. A mudança acrescenta testes com duas fontes, um ativo e outro desativado, para garantir o comportamento.
- *Descartado:* separar as fontes no prompt com cabeçalhos próprios. O `render_context` já começa cada fonte com o nome e o identificador dela.

## Risks / Trade-offs

- [A leitura de valores observados varre as tabelas grandes do Simcc a cada verificação. Para colunas com poucos valores, como `type`, o `SELECT DISTINCT` percorre a tabela inteira] → Medir o tempo da sincronização e da verificação com os dados reais quando o ETL terminar. Uma coluna que estoura o timeout mantém os valores anteriores e não derruba as outras. Se o custo for alto, a coluna pode passar para `aggregate` (que não é lida), ou uma mudança própria cria uma opção de desligar a leitura por coluna.
- [O modelo pode somar tabelas base para totais e contar o mesmo item uma vez por coautor] → As instruções e os exemplos de totais usam as views canônicas, e um exemplo por pesquisador usa as tabelas base.
- [As views canônicas podem estar defasadas em relação às tabelas] → As instruções avisam. A atualização é responsabilidade do Simcc.
- [Até `QUERY_MAX_ROWS` Lattes por vez não respondem "artigos de todos os bolsistas de doutorado"] → A instrução manda dizer isso ao usuário. A mudança de consultas entre fontes resolve.
- [O cruzamento com o fomento identifica bolsistas pelo nome] → A decisão do usuário fica registrada. Dá para reverter pela API ou pela demo (acesso `aggregate` ou coluna oculta), sem deploy.
- [O formato do Lattes pode divergir entre fomento e Simcc, por zeros à esquerda ou pelo `lattes_10_id`] → No fomento os Lattes têm 16 dígitos, e o Simcc usa `lattes_id` com o mesmo formato. Conferir a correspondência com os dados reais antes de fechar a mudança.
- [As migrações do ETL do Simcc podem mudar o schema] → A verificação de defasagem já existente detecta, e uma coluna do YAML que sumir fica ausente sem quebrar a fonte.
- [O compose da Maria passa a depender da rede `simcc-network`] → O guia de deploy coloca o Simcc na ordem de inicialização, como já faz com o fomento.

## Migration Plan

Não há migração do banco da Maria.
- **Em dev:** `task seed` cria a fonte `simcc` sem tocar o fomento. A instrução nova do fomento é aplicada pela API (`PATCH /catalog/datasources/fomento`), porque o seed não sobrescreve.
- **Em produção:** o banco foi recriado na troca para SQLite, e o seed dos dois arquivos já cria tudo.
- **Rollback:** `DELETE /catalog/datasources/simcc`, e reverter `compose.prod.yaml` e as instruções do fomento.

## Open Questions

Nenhuma.
