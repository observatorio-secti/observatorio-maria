# Tasks

## 1. Orçamento de chamadas ao modelo

- [x] 1.1 Mudar o padrão de `MARIA_AGENT_MAX_MODEL_CALLS` para 6 em `settings.py`, `.env.example` e na tabela do README. Ajustar o teste de orçamento em `tests/test_agent_chat.py` para esperar 6 chamadas com o padrão e 3 com o valor configurado. Verificar com `poetry run pytest tests/test_agent_chat.py`.

## 2. Valores observados no catálogo

- [x] 2.1 Adicionar `CatalogColumn.observed_values` (JSON, nulo) e a propriedade `source_values` (enum, senão observados), e fazer `undescribed_values`/`obsolete_values` usarem `source_values`. Gerar a migração Alembic por autogenerate (nome ASCII) e testar upgrade, downgrade e upgrade. Testes em `tests/test_catalog_observed.py` para pendentes e obsoletos com valores observados e precedência do enum.
- [x] 2.2 Criar `catalog/observed.py` com `refresh_observed_values` (D1–D3): colunas elegíveis, `SELECT DISTINCT ... LIMIT max+1` somente leitura com timeout por coluna, nulo acima do limite, valores anteriores mantidos em falha. Adicionar `CATALOG_OBSERVED_VALUES_MAX` (padrão 50, `ge=1`) em `settings.py`, `.env.example` e README (seção do catálogo, explicando quais colunas são lidas). Testes com origem SQLite temporária em `tests/test_catalog_observed.py`: coluna categórica lida, oculta e `aggregate` não lidas, acima do limite fica nula, nulos excluídos, falha mantém valores.
- [x] 2.3 Chamar `refresh_observed_values` depois de `sync_datasource` no endpoint `POST .../sync`, no ramo `up_to_date` e no auto-sync de `check_datasource`, sem alterar a impressão digital, e apagar os valores ao passar uma coluna para `aggregate` no `PATCH`. Testes em `tests/test_catalog_observed.py`: valor novo na origem atualiza os observados e mantém `up_to_date`; sync pela API lê os valores; `PATCH` para `aggregate` apaga.
- [x] 2.4 Expor `observed_values` em `ColumnPublic` (`schemas.py`) e fazer `_known_values` em `catalog/context.py` usar `source_values`, com a indicação de que são os valores existentes na origem. Testes em `tests/test_catalog_observed.py` (API) e `tests/test_catalog_context.py`: obsoleto fora do contexto, valores reais listados, coluna sem enum nem observados mantém os editoriais.
- [x] 2.5 Atualizar `demo/catalog.js` para usar `observed_values` como valores da origem (pendentes, obsoletos e o rótulo "Valores lidos da origem").

## 3. Exemplos few-shot conferidos com o catálogo

- [x] 3.1 Extrair a montagem do `QuerySchema` de `QueryRunner._get_query_schema` para uma função reutilizável, sem mudar o comportamento de `query_data`. Verificar com `poetry run pytest tests/test_query_validation.py tests/test_agent_chat.py`.
- [x] 3.2 Fazer `render_context` conferir cada exemplo com `validate_query` e excluir os inválidos. A prévia `GET /catalog/datasources/{id}/context` passa a devolver `rejected_examples` com pergunta e motivo. Atualizar o README (seção de exemplos). Testes em `tests/test_catalog_context.py` e `tests/test_catalog_api.py`: exemplo com `ano` em `mv_bolsas_metricas` recusado com motivo citando a coluna; exemplos válidos todos presentes.
- [x] 3.3 Mostrar `rejected_examples` na prévia de contexto da demo (`demo/catalog.js`).

## 4. Aviso de resultado vazio e regra no prompt

- [x] 4.1 Em `QueryRunner.query_data`, acrescentar `hint` quando há zero linhas ou uma única linha com todos os valores nulos (D7). Testes em `tests/test_query_execution.py`: soma nula com aviso, zero linhas com aviso, `COUNT = 0` e resultado com dados sem aviso.
- [x] 4.2 Acrescentar a regra "conferir os valores existentes antes de afirmar que não há dados" ao `TOOL_RULES_PROMPT` em `llm/prompts.py`. Testes em `tests/test_agent_chat.py`: prompt com fontes contém a regra; com modelo fake, filtro errado → aviso → `DISTINCT` → consulta corrigida → resposta, dentro do orçamento padrão.

## 5. Seed do fomento

- [x] 5.1 Em `catalog/fomento.yaml`, remover os valores de `bolsas.modalidade` e trocar `ano` por `ano_inicio` no exemplo de totais por ano. Teste em `tests/test_catalog_yaml.py` (ou no teste de seed existente): todos os exemplos do seed do fomento passam na validação contra o catálogo semeado com as colunas visíveis.

## 6. Verificação integrada

- [x] 6.1 Rodar `task test` (lint, testes e cobertura) sem falhas.
- [x] 6.2 Sincronizar a fonte `fomento` contra o banco real e conferir na prévia de contexto: `mv_bolsas_metricas.modalidade` e `bolsas.modalidade` listam os 4 valores com "- Cotas", `Doutorado` aparece como obsoleto na API e nenhum exemplo é recusado.
- [x] 6.3 Perguntar à Maria "Quantas bolsas de doutorado entre 2016 e 2026?" e conferir que a resposta usa `Doutorado - Cotas` e bate com `SELECT SUM(quantidade) ... WHERE modalidade = 'Doutorado - Cotas' AND ano_inicio BETWEEN 2016 AND 2026`.
- [x] 6.4 Verificar a demo no navegador, em desktop e a 375px: valores lidos da origem, pendentes e obsoletos na coluna `modalidade` e exemplos recusados na prévia de contexto. Desfazer qualquer edição de teste no catálogo.

## Workflow follow-up

- Commits no padrão do projeto: `docs(openspec): planeja add-valores-observados-no-catalogo`, depois `feat: ...` com "Implementa openspec/changes/add-valores-observados-no-catalogo." e, no fim, `docs(openspec): arquiva add-valores-observados-no-catalogo` citando `data-catalog`, `data-querying` e `conversation-messaging`.
- Em ambientes cujo `.env` fixa `MARIA_AGENT_MAX_MODEL_CALLS` (o compose de produção, por exemplo), atualizar o valor à mão se o novo padrão for desejado.
