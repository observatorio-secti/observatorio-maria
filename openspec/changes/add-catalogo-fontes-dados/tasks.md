# Tasks

## 1. Fundação

- [x] 1.1 Adicionar `psycopg[binary]` e `pyyaml` às dependências e `FOMENTO_DATABASE_URL` ao `.env.example`; verificar `poetry install` e importação dos pacotes
- [x] 1.2 Criar os modelos `CatalogDataSource`, `CatalogEntity`, `CatalogColumn` e `CatalogRelationship` e a migração Alembic; verificar `alembic upgrade head` e `downgrade -1` no SQLite local

## 2. Núcleo do catálogo

- [x] 2.1 Implementar a introspecção somente leitura (`SchemaSnapshot`) e a fusão com o catálogo (técnico vs editorial, `present`, novos ocultos, relacionamentos `foreign_key`/`manual`); verificar com testes contra um SQLite de origem em arquivo temporário (primeira sincronização, preservação, tabela removida e reaparecida, origem em modo somente leitura)
- [x] 2.2 Implementar o formato YAML (`CatalogFile`), o seed (criar só o que falta, `--reset`, validação antes de gravar), a exportação e o comando `task seed`; verificar com testes de seed inicial, não sobrescrita, reset, arquivo inválido e ida e volta
- [x] 2.3 Implementar a prévia do contexto em Markdown; verificar com testes de itens ocultos/ausentes fora do texto, entidade não consultável, coluna `aggregate`, valores conhecidos, relacionamento desligado e fonte desativada

## 3. API

- [x] 3.1 Criar os schemas e o router `/catalog` (CRUD de fontes com contagens, sincronização com 422/502, entidades, colunas, relacionamentos, prévia e exportação); verificar com testes de API cobrindo os cenários da spec `data-catalog`

## 4. Fomento

- [x] 4.1 Escrever `catalog/fomento.yaml` com instruções, entidades de domínio, colunas, valores dos enums, colunas pessoais como `aggregate` e relacionamentos; verificar com seed e sincronização contra o banco real do fomento e leitura da prévia

## 5. Demo

- [x] 5.1 Criar a aba "Catálogo de dados" (fonte, sincronização, entidades, colunas, relacionamentos, prévia e download do YAML, com erros exibidos); verificar no navegador com o banco do fomento, incluindo falha de conexão

## 6. Documentação e integração

- [x] 6.1 Documentar no README o catálogo, o YAML, o seed, a sincronização e os endpoints; verificar `task test` sem falhas
