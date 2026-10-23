# Tasks

## 1. Valores de enum

- [x] 1.1 Ler `enum_values` na introspecção, guardar em `CatalogColumn.enum_values` (migração junto com a task 2.1), relatar `new_enum_values` na sincronização e expor `undescribed_values`/`obsolete_values`; verificar com testes da extração do tipo enum, da fusão (primeira leitura sem "novo", valor novo relatado) e das propriedades
- [x] 1.2 Renderizar no contexto os valores do enum com descrições editoriais, sem os obsoletos; verificar com testes de valor sem descrição e valor obsoleto

## 2. Defasagem

- [x] 2.1 Adicionar à fonte `schema_fingerprint`, `schema_status`, `last_checked_at`, `drift`, `check_error` e `auto_sync` (migração Alembic) e gravar impressão digital e estado na sincronização; verificar `alembic upgrade`/`downgrade` e teste de estado após sincronizar
- [x] 2.2 Implementar `fingerprint` e `diff_schema`; verificar com testes de impressão digital estável, diff de entidades, colunas, tipos, enums e relacionamentos, e diff igual ao relatório da sincronização seguinte
- [x] 2.3 Implementar `check_datasource` (em dia, desatualizada, erro e sincronização automática); verificar com testes de cada estado sem alterar o catálogo editorial
- [x] 2.4 Implementar o laço periódico e o `lifespan` com `CATALOG_CHECK_INTERVAL_SECONDS`; verificar com testes de ciclo com fonte com falha, fonte desativada e intervalo `0`

## 3. API e YAML

- [x] 3.1 Expor estado, diff e `auto_sync` nos schemas da fonte, `enum_values`/`undescribed_values`/`obsolete_values` nas colunas, `POST /catalog/datasources/{id}/check` e `auto_sync` no YAML; verificar com testes de API e de ida e volta do YAML

## 4. Demo

- [x] 4.1 Mostrar estado, verificação, sincronização automática, quadro de defasagem e edição de valores na aba do catálogo; verificar no navegador contra o fomento, inclusive com defasagem simulada

## 5. Integração

- [x] 5.1 Verificar contra o banco real do fomento (enums lidos, impressão digital, estado `up_to_date`), documentar no README e `.env.example`, e rodar `task test` sem falhas
