# Design

## Context

A mudança `add-catalogo-fontes-dados` criou o catálogo e a sincronização manual. A introspecção produz um `SchemaSnapshot` imutável e `sync_datasource` funde esse snapshot com o catálogo num commit. O banco do fomento tem 7 tipos enum nativos (ex.: `bolsa_status`, `pesquisador_status`); hoje a coluna guarda só o nome do tipo (`bolsa_status`), sem os valores. A Maria não tem `lifespan` nem tarefas em segundo plano.

## Goals / Non-Goals

**Goals:**
- Detectar defasagem barata e frequentemente, sem tocar no catálogo editorial.
- Mostrar *o que* mudou antes de sincronizar, com o mesmo vocabulário do relatório de sincronização.

**Non-Goals:**
- Fila de tarefas ou agendador externo: um laço `asyncio` no processo da API basta para o volume atual.
- Ler dados da origem. Valores de enum vêm do catálogo do banco (tipos), não das tabelas.

## Decisions

### 1. Impressão digital = SHA-256 de uma forma canônica do snapshot
`drift.fingerprint(snapshot)` serializa em JSON ordenado:
- por entidade: schema, nome, tipo;
- por coluna, ordenadas por nome: tipo, nulabilidade, chave primária e valores de enum;
- chaves estrangeiras ordenadas.

O resultado é o hash dessa serialização. A posição das colunas fica fora, para que reordenações não gerem alarme. A impressão digital só é gravada pela sincronização, e a verificação apenas compara.

*Alternativa:* comparar o `version_num` do `alembic_version` da origem. Descartada: é leitura de dado, só funciona para bancos com Alembic e não mostra o que mudou.

### 2. Diff como função pura, separada da fusão
`drift.diff_schema(entities, relationships, snapshot)` compara o catálogo atual com o snapshot sem mutar nada e devolve um `SchemaDiff`:
- `added_entities` / `missing_entities`;
- `added_columns` / `missing_columns`;
- `changed_columns` (`public.bolsas.status: VARCHAR(20) -> bolsa_status`);
- `new_enum_values` / `removed_enum_values` (`public.bolsas.status=SUSPENSA`);
- `added_relationships` / `missing_relationships`.

*Alternativa:* rodar a sincronização em modo "ensaio" e dar rollback. Descartada: o rollback expira os objetos da sessão assíncrona (acessos posteriores falhariam) e misturaria leitura com escrita. A consistência entre diff e sincronização fica garantida por teste: o diff calculado antes de sincronizar bate com o relatório da sincronização.

### 3. Estado guardado na fonte
Novas colunas em `catalog_datasources`:
- `schema_fingerprint`;
- `schema_status` (`unknown` | `up_to_date` | `outdated` | `error`);
- `last_checked_at`;
- `drift` (JSON do diff ou nulo);
- `check_error`;
- `auto_sync` (padrão falso).

A sincronização grava a impressão digital, `up_to_date`, `last_checked_at` e limpa `drift` e `check_error`. A verificação (`drift.check_datasource`):
1. introspecta;
2. em caso de erro, grava `error` com a mensagem já sanitizada pela introspecção;
3. se a impressão digital for igual, grava `up_to_date`;
4. se for diferente, sincroniza quando `auto_sync` está ligado; caso contrário, grava `outdated` com o diff.

Fonte nunca sincronizada (sem impressão digital) conta como defasada. A rota `POST .../check` devolve o estado e, se houve sincronização automática, o relatório.

### 4. Laço periódico no `lifespan`
`drift.run_periodic_checks(interval, session_factory, introspect)`:
- verifica as fontes ativas, cada uma na sua sessão, com `try/except` por fonte e log;
- dorme `interval` segundos e repete.

O `lifespan` da app cria a tarefa quando `CATALOG_CHECK_INTERVAL_SECONDS > 0` e a cancela no desligamento. Os testes usam `ASGITransport`, que não dispara o `lifespan`, então o laço é testado diretamente com um intervalo curto e um introspector falso.

*Alternativa:* APScheduler ou cron externo. Descartada por ora: dependência a mais para um único trabalho. Com várias réplicas da API, cada uma verificaria por conta própria, o que é inofensivo (só leitura, e as escritas no catálogo são idempotentes).

### 5. Valores de enum: técnico separado de editorial
- `ColumnSnapshot` ganha `enum_values: tuple[str, ...] | None`, lido do atributo `enums` do tipo refletido (`ENUM` do PostgreSQL).
- `CatalogColumn` ganha `enum_values` (JSON, técnico, escrito pela sincronização). O campo editorial `values` (`[{value, description}]`) não muda.
- Propriedades do modelo calculam:
  - `undescribed_values`: no enum, sem descrição editorial;
  - `obsolete_values`: descritos, mas fora do enum.
- No contexto, se `enum_values` existe, a lista vem dele, na ordem do enum, com as descrições editoriais. Senão, vem de `values`, como hoje.
- O relatório da sincronização ganha `new_enum_values`, só para colunas cujo enum já era conhecido. Na primeira leitura não há "novo".

### 6. Demo
- Barra da fonte:
  - pílula de estado;
  - data da última verificação;
  - botão "Verificar agora";
  - interruptor "Sincronizar automaticamente".
- Quadro de defasagem com o diff e um botão "Sincronizar".
- Na tabela de colunas, uma linha expansível "Valores" com uma descrição editável por valor, destacando os sem descrição e os obsoletos. Salvar envia o `values` completo pelo `PATCH` de coluna existente.

## Risks / Trade-offs

- **[Enums por `CHECK` não são detectados]:** colunas como `areas_conhecimento.tipo` continuam dependendo do YAML. Mitigação: documentado. Pode virar uma extensão que lê constraints `IN (...)`.
- **[Verificação frequente em muitos bancos]:** cada ciclo abre uma conexão por fonte. Mitigação: padrão de 1 hora, `NullPool` e timeout de conexão de 5 s.
- **[Auto-sync esconde mudanças]:** com `auto_sync`, a fonte volta a `up_to_date` e o diff some do estado. Mitigação: o relatório fica nos logs (OpenTelemetry → Loki), e os itens novos entram ocultos, aguardando revisão.

## Migration Plan

1. `alembic upgrade head`: as colunas novas têm `server_default`, e as fontes existentes ficam `unknown` com `auto_sync` falso.
2. Na primeira verificação, as fontes já sincronizadas aparecem como `outdated` (ainda sem impressão digital). Basta sincronizar uma vez.

Rollback: `alembic downgrade -1`.
