# Proposal

## Why

O catálogo só acompanha o schema de origem quando alguém sincroniza manualmente. Quando o módulo de fomento roda uma migração, o catálogo fica defasado sem aviso: pode descrever ao modelo colunas que não existem mais e não conhece valores novos de enum. Esse último caso é o mais perigoso, porque gera contagens erradas sem nenhum erro. A defasagem precisa ser detectada sem depender de alguém lembrar de verificar.

## What Changes

- **Impressão digital do schema:** cada sincronização guarda um hash da estrutura lida (entidades, colunas, tipos, chaves e valores de enum).
- **Verificação de defasagem:** um endpoint lê o schema atual da origem (somente leitura), compara com a impressão digital e devolve o estado da fonte (`em dia`, `desatualizada`, `erro` ou `não verificada`) e o diff do que mudou: entidades e colunas novas ou removidas, colunas alteradas, valores de enum novos ou removidos e relacionamentos.
- **Verificação periódica:** a API verifica as fontes ativas ao iniciar e depois em intervalo configurável (`CATALOG_CHECK_INTERVAL_SECONDS`; `0` desliga). Falhas ficam registradas na fonte e não interrompem o ciclo.
- **Sincronização automática opcional:** novo interruptor `auto_sync` por fonte, desligado por padrão. Quando ligado, uma defasagem detectada é sincronizada na hora. É seguro, porque o que é novo entra oculto e o que sumiu fica ausente.
- **Valores de enum:** a introspecção passa a ler os valores dos tipos enum nativos. No contexto do modelo entram todos os valores atuais, com as descrições editoriais quando existirem. A API aponta os valores **sem descrição** (para revisão) e os **obsoletos** (descritos mas que não existem mais), e estes saem do contexto.
- **Demo:** estado do schema na barra da fonte, botão "Verificar agora", interruptor de sincronização automática, quadro com as mudanças detectadas e edição das descrições dos valores de cada coluna.

Fora do escopo: inferir valores de colunas texto com `CHECK ... IN (...)` (ex.: `areas_conhecimento.tipo`), reconciliar renomeações e notificar por canais externos.

## Capabilities

### New Capabilities
<!-- Nenhuma. -->

### Modified Capabilities
- `data-catalog`: impressão digital, verificação de defasagem (manual e periódica), sincronização automática e valores de enum.
- `demo-page`: estado do schema e edição de valores na aba do catálogo.

## Impact

- API: `POST /catalog/datasources/{id}/check`. A fonte passa a expor `schema_status`, `last_checked_at`, `drift`, `check_error` e `auto_sync`. As colunas passam a expor `enum_values`, `undescribed_values` e `obsolete_values`.
- Banco da Maria: novas colunas em `catalog_datasources` e `catalog_columns` (migração Alembic).
- Código: `catalog/introspection.py` (enums), novo `catalog/drift.py` (impressão digital, diff, verificação e ciclo periódico), `catalog/sync.py`, `catalog/context.py`, `catalog/yaml_io.py` (`auto_sync`), `routers/catalog.py`, `app.py` (lifespan), demo.
- Configuração: `CATALOG_CHECK_INTERVAL_SECONDS` (padrão 3600).
- Dependências: nenhuma nova. A mudança depende de `add-catalogo-fontes-dados` e só adiciona requisitos.
