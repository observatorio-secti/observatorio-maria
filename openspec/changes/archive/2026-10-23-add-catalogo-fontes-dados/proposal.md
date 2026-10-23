# Proposal

## Why

A Maria vai responder perguntas consultando bancos de dados de outros sistemas do Observatório, começando pelo banco do módulo de fomento. Antes de a IA consultar qualquer coisa, é preciso um **catálogo** que diga o que cada banco contém, o que o modelo pode enxergar, como deve interpretar cada tabela e coluna e o que pode ser consultado. Esse catálogo precisa ser editável sem mexer em código e sem alterar os bancos de origem.

## What Changes

- Novo **catálogo de fontes de dados**, guardado no banco da própria Maria (SQLite em desenvolvimento, sem servidor extra):
  - **Fonte de dados:** nome, descrição, instruções de negócio para a IA, variável de ambiente com a conexão e liga/desliga.
  - **Entidade (tabela, view ou view materializada):** rótulo, descrição, sinônimos e dois interruptores: **visível** (o modelo enxerga) e **consultável** (o modelo pode consultar).
  - **Coluna:** rótulo, descrição, sinônimos, valores conhecidos com significado, **visível** e **acesso** (`full`, que permite ler valores, ou `aggregate`, que só permite filtrar e agregar, para dados pessoais).
  - **Relacionamento:** ligações entre entidades vindas das chaves estrangeiras, com liga/desliga e descrição.
- **Sincronização de schema:** lê a estrutura do banco de origem por introspecção, somente leitura. O que é novo entra oculto, o que sumiu é marcado como ausente e a configuração editorial é preservada.
- **Seed via YAML:** um arquivo por fonte (`catalog/fomento.yaml`) carrega a configuração inicial **sem sobrescrever** o que já foi editado. O YAML é ponto de partida, não fonte de verdade. O catálogo atual pode ser exportado de volta para YAML.
- **Prévia do contexto:** um endpoint mostra exatamente o texto que o modelo vai receber sobre uma fonte, considerando todos os interruptores.
- **Endpoints REST** em `/catalog` para listar, detalhar e editar fontes, entidades, colunas e relacionamentos, sincronizar, exportar e pré-visualizar. Ainda **sem autenticação**, que está em desenvolvimento em outro repositório.
- **Demo:** nova aba "Catálogo de dados" na página `/demo/` para configurar tudo isso visualmente.
- Os bancos de origem **nunca são alterados**: a conexão é aberta em modo somente leitura e só lê o schema.

Fora do escopo: a IA ainda não consulta os bancos (próxima mudança), consultas nomeadas e autenticação.

## Capabilities

### New Capabilities
- `data-catalog`: catálogo de fontes de dados externas (fontes, entidades, colunas, relacionamentos), sincronização de schema, seed e exportação em YAML e prévia do contexto que o modelo recebe.

### Modified Capabilities
- `demo-page`: a página ganha uma aba para configurar o catálogo de dados.

## Impact

- API: novos endpoints em `/catalog`.
- Banco da Maria: novas tabelas do catálogo (migração Alembic).
- Código: `models.py`, `schemas.py`, novo pacote `catalog/` (introspecção, seed/exportação, prévia), novo router `routers/catalog.py`, demo.
- Configuração: nova variável `FOMENTO_DATABASE_URL` (o nome é definido por fonte no catálogo).
- Dependências: `psycopg[binary]` (conexão com PostgreSQL) e `pyyaml` (seed).
- Bancos de origem: somente leitura, nenhuma alteração.
