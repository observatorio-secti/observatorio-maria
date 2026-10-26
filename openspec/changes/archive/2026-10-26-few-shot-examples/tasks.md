# Tasks: Exemplos de Consulta Validados (Few-shot) no Catálogo

## 1. Modelo, Schemas e Migração Alembic

- [x] 1.1 Adicionar a coluna `examples` em `CatalogDataSource` em `src/observatorio_maria/models.py`.
- [x] 1.2 Adicionar schema `QueryExample` e incluir `examples` em `DataSourceCreate`, `DataSourceUpdate` e `DataSourcePublic` em `src/observatorio_maria/schemas.py`.
- [x] 1.3 Criar migração Alembic adicionando a coluna `examples` na tabela `catalog_datasources`.

## 2. Seed YAML, Exportação e Renderização de Contexto

- [x] 2.1 Atualizar `load_datasource` e `dump_datasource` em `src/observatorio_maria/catalog/yaml_io.py` para suportar `examples`.
- [x] 2.2 Adicionar exemplos canônicos curados no arquivo `catalog/fomento.yaml`.
- [x] 2.3 Atualizar `render_context` em `src/observatorio_maria/catalog/context.py` para formatar e incluir a seção `## Exemplos de consultas (few-shot)`.

## 3. Testes e Verificação

- [x] 3.1 Adicionar testes de serialização YAML e renderização de contexto em `tests/test_catalog_yaml.py` e `tests/test_catalog_context.py`.
- [x] 3.2 Adicionar testes de API para CRUD de fontes com `examples` em `tests/test_catalog_api.py`.
- [x] 3.3 Adicionar teste em `tests/test_agent_chat.py` verificando a presença de exemplos few-shot no prompt de sistema enviado ao modelo.
- [x] 3.4 Executar verificação completa com `task lint` e `task test`, assegurando conformidade de código e cobertura mínima de 90%.
